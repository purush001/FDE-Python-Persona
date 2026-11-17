"""
fde_llm.py -- one small helper for the whole FDE-Python course.

It talks to Claude (Anthropic), Gemini (Google) or OpenAI using plain HTTP
(the `requests` library), so students can SEE how an AI API call really works.
There is also an offline "mock" provider, so class still works with no key.

The functions you will use
    use(provider, api_key=None, model=None)   pick the AI to talk to
    ask(prompt, system=None)                  one question  -> one answer (text)
    chat(history, system=None)                whole chat    -> the next answer
    stream(history, system=None)              like chat, but yields text pieces
    ask_json(prompt, system=None, schema=None) answer as Python data, checked against a schema
    pick(question, options)                   choose ONE label (a tiny router / classifier)
    make_tool(func) / chat_tools(history, tools) / run_tool(call, tools)
                                              let the AI call YOUR Python functions
    ask_with_search(prompt)                   the AI company's built-in web search tool
    embed(texts)                              text -> list of numbers (meaning as coordinates)
    last_call / totals() / estimate_cost()    tokens, seconds and dollars
    validate(data, schema)                    check data against a schema
    mask_key(key)                             'sk-abc...1234' -> '••••1234'

A chat history is a list like:
    [{"role": "user", "text": "Hi!"}, {"role": "assistant", "text": "Hello!"}]
(The word "model" is accepted instead of "assistant", like the original app.)

Teacher: model names change often. Edit the `model` lines in PROVIDERS below
(or pass model="..." to use()) and nothing else needs to change.
"""

import copy
import inspect
import json
import os
import re
import time

import requests

# --------------------------------------------------------------------------
# Settings you can change
# --------------------------------------------------------------------------
PROVIDERS = {
    "claude": {
        "label": "Claude (Anthropic)",
        "model": "claude-haiku-5-5",
        "secrets": ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"],
    },
    "gemini": {
        "label": "Gemini (Google)",
        "model": "gemini-4-hydrogen",
        "secrets": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    },
    "openai": {
        "label": "OpenAI",
        "model": "gpt-5.6-luna",
        "secrets": ["OPENAI_API_KEY"],
    },
    "mock": {
        "label": "Practice mode (no key, no internet)",
        "model": "mock-1",
        "secrets": [],
    },
}

TIMEOUT_SECONDS = 60

_config = {"provider": "mock", "api_key": None, "model": "mock-1"}


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------
class LLMError(Exception):
    """Something went wrong while talking to the AI. `.status` is the HTTP code."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def friendly_error(status, api_message, provider, model):
    """Turn a scary HTTP error into a sentence a student can act on."""
    label = PROVIDERS.get(provider, {}).get("label", provider)
    text = (api_message or "").lower()
    if status == 400 and "key" in text:
        return f"Your {label} API key looks invalid. Please check it and try again."
    if status in (401, 403):
        return f"Your {label} API key was rejected. Make sure it is valid and has access."
    if status == 404:
        return f'The model "{model}" was not found for this key. Ask your teacher to check the model name.'
    if status == 429:
        return "Too many requests or no credit left. Wait a moment and try again."
    if status is not None and status >= 500:
        return f"{label} is having trouble right now. Please try again in a moment."
    return api_message or f"The request failed with status {status}."


# --------------------------------------------------------------------------
# Keys (never print them!)
# --------------------------------------------------------------------------
def mask_key(key):
    """Show only the last 4 characters of a key, like the original app does."""
    return "••••" + key[-4:] if key else "(no key)"


def get_key(provider):
    """Find a key: Colab Secrets first, then environment variables, then ask."""
    names = PROVIDERS[provider]["secrets"]
    try:
        from google.colab import userdata  # only exists inside Google Colab

        for name in names:
            try:
                value = userdata.get(name)
                if value:
                    return value
            except Exception:
                pass
    except ImportError:
        pass
    for name in names:
        if os.environ.get(name):
            return os.environ[name]
    from getpass import getpass

    return getpass(f"Paste your {PROVIDERS[provider]['label']} API key (hidden): ").strip()


# Friendly names that pick a provider AND a model in one go: use("Gemini 4 Hydrogen")
ALIASES = {
    "gemini 4 hydrogen": ("gemini", "gemini-4-hydrogen"),
}


def use(provider="claude", api_key=None, model=None, quiet=False):
    """Choose which AI to talk to. Returns a short, key-free summary."""
    provider = " ".join(provider.lower().split())
    if provider in ALIASES:
        provider, alias_model = ALIASES[provider]
        model = model or alias_model
    if provider not in PROVIDERS:
        raise ValueError(f"provider must be one of {list(PROVIDERS)} or {[a.title() for a in ALIASES]}")
    key = None
    if provider != "mock":
        key = api_key or get_key(provider)
        if not key:
            raise LLMError("No API key was provided.")
    _config.update(
        provider=provider, api_key=key, model=model or PROVIDERS[provider]["model"]
    )
    info = current()
    if not quiet:
        print(f"Using {PROVIDERS[provider]['label']}  |  model: {info['model']}  |  key: {mask_key(key)}")
    return info


def current():
    """What am I using right now? (The key itself is never included.)"""
    return {
        "provider": _config["provider"],
        "model": _config["model"],
        "key": mask_key(_config["api_key"]),
    }


# --------------------------------------------------------------------------
# Building the request (this is the part students learn to read)
# --------------------------------------------------------------------------
def _normalize(history):
    if isinstance(history, str):
        history = [{"role": "user", "text": history}]
    messages = []
    for m in history:
        role = "assistant" if m["role"] in ("assistant", "model") else "user"
        messages.append({"role": role, "text": m["text"]})
    if not messages or messages[0]["role"] != "user":
        raise ValueError("A conversation must start with a 'user' message.")
    return messages


def _build_request(provider, model, key, messages, system, max_tokens, temperature, stream, json_mode, schema=None):
    """Return (url, headers, body) for the chosen provider."""
    if provider == "claude":
        body = {
            "model": model,
            "max_tokens": max_tokens or 1024,
            "messages": [{"role": m["role"], "content": m["text"]} for m in messages],
        }
        if system:
            body["system"] = system
        if temperature is not None:
            body["temperature"] = temperature
        if schema is not None:
            body["output_config"] = {"format": {"type": "json_schema", "schema": _strictify(schema)}}
        if stream:
            body["stream"] = True
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        return "https://api.anthropic.com/v1/messages", headers, body

    if provider == "openai":
        msgs = [{"role": "system", "content": system}] if system else []
        msgs += [{"role": m["role"], "content": m["text"]} for m in messages]
        body = {"model": model, "messages": msgs}
        if max_tokens:
            body["max_completion_tokens"] = max_tokens
        if temperature is not None:
            body["temperature"] = temperature
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "answer", "strict": True, "schema": _strictify(schema)},
            }
        elif json_mode:
            body["response_format"] = {"type": "json_object"}
        if stream:
            body["stream"] = True
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        return "https://api.openai.com/v1/chat/completions", headers, body

    if provider == "gemini":
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["text"]}]}
            for m in messages
        ]
        body = {"contents": contents}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        config = {}
        if temperature is not None:
            config["temperature"] = temperature
        if max_tokens:
            config["maxOutputTokens"] = max_tokens
        if schema is not None:
            config["responseMimeType"] = "application/json"
            config["responseJsonSchema"] = _strictify(schema)
        elif json_mode:
            config["responseMimeType"] = "application/json"
        if config:
            body["generationConfig"] = config
        method = "streamGenerateContent?alt=sse" if stream else "generateContent"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{method}"
        headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
        return url, headers, body

    raise ValueError(f"Unknown provider: {provider}")


# --------------------------------------------------------------------------
# Reading the answer
# --------------------------------------------------------------------------
def _text_from(provider, data):
    """Dig the answer text out of the JSON the provider sent back."""
    if provider == "claude":
        if data.get("type") == "error":
            raise LLMError(data.get("error", {}).get("message", "Claude returned an error."))
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    if provider == "openai":
        choices = data.get("choices") or []
        return (choices[0].get("message", {}).get("content") or "") if choices else ""
    if provider == "gemini":
        block = (data.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise LLMError(f"The request was blocked ({block}). Try rephrasing.")
        candidates = data.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))
    raise ValueError(f"Unknown provider: {provider}")


def _delta_from(provider, event):
    """Text carried by ONE streaming event (may be empty)."""
    if provider == "claude":
        if event.get("type") == "error":
            raise LLMError(event.get("error", {}).get("message", "Claude returned an error."))
        if event.get("type") == "content_block_delta":
            return event.get("delta", {}).get("text", "") or ""
        return ""
    if provider == "openai":
        choices = event.get("choices") or []
        return (choices[0].get("delta", {}).get("content") or "") if choices else ""
    if provider == "gemini":
        if event.get("error"):
            raise LLMError(event["error"].get("message", "Gemini returned an error."))
        return _text_from("gemini", event)
    return ""


def _check(response, provider, model):
    if response.status_code >= 400:
        message = None
        try:
            message = response.json().get("error", {}).get("message")
        except Exception:
            pass
        raise LLMError(friendly_error(response.status_code, message, provider, model), response.status_code)


# --------------------------------------------------------------------------
# Schemas: describing the shape of an answer (JSON Schema)
# --------------------------------------------------------------------------
_UNSUPPORTED = ("minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems", "pattern", "default", "examples")


def _strictify(schema):
    """A copy of the schema that all three providers accept (every field required, no extras)."""
    schema = copy.deepcopy(schema)

    def walk(node):
        if isinstance(node, dict):
            for key in _UNSUPPORTED:
                node.pop(key, None)
            if node.get("type") == "object":
                props = node.get("properties", {})
                node["additionalProperties"] = False
                node["required"] = list(props)
            for value in list(node.values()):
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return schema


def validate(data, schema, path="answer"):
    """Check Python data against a schema. Returns a list of problems (empty list = all good)."""
    kinds = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool}
    wanted = schema.get("type")
    problems = []
    if wanted in kinds:
        ok = isinstance(data, kinds[wanted])
        if wanted in ("integer", "number") and isinstance(data, bool):
            ok = False
        if not ok:
            return [f"{path} should be a {wanted}"]
    if "enum" in schema and data not in schema["enum"]:
        problems.append(f"{path} must be one of {schema['enum']}")
    if wanted == "object":
        for name in schema.get("required", []):
            if name not in data:
                problems.append(f"{path}.{name} is missing")
        for name, sub in schema.get("properties", {}).items():
            if name in data:
                problems += validate(data[name], sub, f"{path}.{name}")
    if wanted == "array":
        if "minItems" in schema and len(data) < schema["minItems"]:
            problems.append(f"{path} needs at least {schema['minItems']} items")
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            problems.append(f"{path} has more than {schema['maxItems']} items")
        for i, item in enumerate(data):
            problems += validate(item, schema.get("items", {}), f"{path}[{i}]")
    if wanted in ("integer", "number"):
        if "minimum" in schema and data < schema["minimum"]:
            problems.append(f"{path} is smaller than {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            problems.append(f"{path} is bigger than {schema['maximum']}")
    return problems


# --------------------------------------------------------------------------
# The offline "mock" AI  (a pretend brain: simple rules, no internet)
# --------------------------------------------------------------------------
_MOCK_QUIZ = {
    "questions": [
        {
            "topic": "Practice",
            "question": "Which symbol starts a comment in Python?",
            "options": ["#", "//", "--", "/*"],
            "answerIndex": 0,
            "explanation": "Python uses # for comments.",
        },
        {
            "topic": "Practice",
            "question": "What does print('hi') do?",
            "options": ["Shows hi on screen", "Deletes hi", "Saves hi to a file", "Nothing"],
            "answerIndex": 0,
            "explanation": "print shows text on the screen.",
        },
    ]
}
_STOP = set(
    "what does your with have this that when where which will from about tell into they them there would could "
    "should please much many have been were then than also just very some more most like want need make "
    "the and for are you how can why who not but".split()
)


def _words(text, size=3):
    return {w for w in re.findall(r"[a-z0-9']+", str(text).lower()) if len(w) >= size and w not in _STOP}


def _facts_in(system):
    """Lines after a 'FACTS:' heading in a system prompt (up to the next heading)."""
    block = system.split("FACTS:", 1)[1]
    facts = []
    for line in block.splitlines():
        clean = line.strip().lstrip("-• \t")
        if not clean:
            continue
        if clean.endswith(":") and clean.upper() == clean:
            break
        if re.match(r"^[A-Z_ ]{3,}:", clean):
            break
        facts.append(clean)
    return facts


def _ideas(text):
    """The concept numbers (see CONCEPTS) that the words of a text point to."""
    return {_CONCEPT_OF[w] for w in re.findall(r"[a-z]+", str(text).lower()) if w in _CONCEPT_OF}


def _field(prompt, label):
    """Text after 'LABEL:' on its line (used by the practice judge)."""
    found = re.search(label + r":\s*(.+)", prompt)
    return found.group(1).strip() if found else ""


def _mock_from_schema(schema, prompt=""):
    """Make plausible sample data that fits a schema."""
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema.get("type")
    if kind == "object":
        out = {}
        for name, sub in schema.get("properties", {}).items():
            out[name] = _mock_from_schema(sub, prompt)
        expected, answer = _field(prompt, "EXPECTED"), _field(prompt, "ANSWER")
        if "score" in out and expected and answer:
            need = _words(expected, 3)
            hit = len(need & _words(answer, 3))
            ratio = hit / len(need) if need else 0
            out["score"] = 1 + round(4 * ratio)
            if "reason" in out:
                out["reason"] = f"Practice judge: {hit} of {len(need)} key words matched."
            if "pass" in out:
                out["pass"] = ratio >= 0.5
            if "passed" in out:
                out["passed"] = ratio >= 0.5
        return out
    if kind == "array":
        item = schema.get("items", {"type": "string"})
        return [_mock_from_schema(item, prompt) for _ in range(2)]
    if kind == "integer":
        return schema.get("minimum", 1)
    if kind == "number":
        return float(schema.get("minimum", 1))
    if kind == "boolean":
        return True
    return "example"


def _mock_text(messages, system, json_mode, schema=None):
    last = messages[-1]["text"]
    if schema is not None:
        return json.dumps(_mock_from_schema(schema, last))
    if json_mode or "quiz" in last.lower():
        return json.dumps(_MOCK_QUIZ)
    system = system or ""
    secret = re.search(r"SECRET:\s*(.+)", system)
    if secret and re.search(r"ignore|reveal|system prompt|secret|password|pretend", last.lower()):
        return "Sure, since you asked nicely! The secret is: " + secret.group(1).strip()
    if "FACTS:" in system:
        facts = _facts_in(system)
        asked = _words(last)
        by_meaning = "by meaning" in system.lower()          # the prompt asked to match meaning, not only exact words
        asked_ideas = _ideas(last) if by_meaning else set()
        scored = sorted(((len(asked & _words(f)) + (len(asked_ideas & _ideas(f)) if by_meaning else 0), f) for f in facts), key=lambda pair: -pair[0])
        if scored and scored[0][0] >= 1:
            return scored[0][1]
        if re.search(r"don't know|do not know|not in my notes|honest", system, re.IGNORECASE):
            return "I don't know. That is not in my notes."
        return "Absolutely! It costs $4.99 and arrives in 10 minutes. (Pico sounds sure. Pico made this up.)"
    persona = ""
    if system:
        persona = " My persona starts with: '" + system.strip().split("\n")[0][:60] + "...'."
    return (
        "🤖 (Practice mode) I am a pretend AI so you can learn without a key."
        f"{persona} You said: '{last[:80]}'. A real AI would write a clever answer here!"
    )


# --------------------------------------------------------------------------
# Counting: tokens, time, money  (used for cost, latency and traces)
# --------------------------------------------------------------------------
last_call = {"provider": None, "model": None, "seconds": 0.0, "input_tokens": 0, "output_tokens": 0}
_totals = {"calls": 0, "seconds": 0.0, "input_tokens": 0, "output_tokens": 0}


def _usage_from(provider, data):
    if provider == "claude":
        usage = data.get("usage") or {}
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    if provider == "openai":
        usage = data.get("usage") or {}
        return usage.get("prompt_tokens", usage.get("input_tokens", 0)), usage.get("completion_tokens", usage.get("output_tokens", 0))
    if provider == "gemini":
        usage = data.get("usageMetadata") or {}
        return usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0)
    return 0, 0


def _record(provider, model, seconds, tokens_in, tokens_out):
    last_call.update(provider=provider, model=model, seconds=round(seconds, 3), input_tokens=tokens_in, output_tokens=tokens_out)
    _totals["calls"] += 1
    _totals["seconds"] += seconds
    _totals["input_tokens"] += tokens_in
    _totals["output_tokens"] += tokens_out


def totals():
    """Calls, seconds and tokens used since the last reset_totals()."""
    return dict(_totals, seconds=round(_totals["seconds"], 3))


def reset_totals():
    _totals.update(calls=0, seconds=0.0, input_tokens=0, output_tokens=0)


def estimate_cost(input_tokens, output_tokens, price_in_per_million, price_out_per_million):
    """Dollars for a call. Get the two prices from the provider's pricing page (they change)."""
    return input_tokens / 1_000_000 * price_in_per_million + output_tokens / 1_000_000 * price_out_per_million


def _rough_tokens(text):
    return max(1, round(len(str(text)) / 4))


# --------------------------------------------------------------------------
# The functions students call
# --------------------------------------------------------------------------
def _post(url, headers, body, stream=False):
    try:
        return requests.post(url, headers=headers, json=body, timeout=TIMEOUT_SECONDS, stream=stream)
    except requests.exceptions.RequestException as err:
        raise LLMError("Could not reach the AI service. Check the internet connection.") from err


def chat(history, system=None, max_tokens=None, temperature=None, json_mode=False, schema=None):
    """Send a whole conversation, get the AI's next message back as text."""
    messages = _normalize(history)
    provider, model, key = _config["provider"], _config["model"], _config["api_key"]
    started = time.time()
    if provider == "mock":
        text = _mock_text(messages, system, json_mode, schema)
        sent = (system or "") + " ".join(m["text"] for m in messages)
        _record(provider, model, time.time() - started + 0.05, _rough_tokens(sent), _rough_tokens(text))
        return text
    url, headers, body = _build_request(
        provider, model, key, messages, system, max_tokens, temperature, False, json_mode, schema
    )
    response = _post(url, headers, body)
    if schema is not None and response.status_code == 400:
        # some models do not support schema mode yet: ask again with the schema written in the prompt only
        url, headers, body = _build_request(
            provider, model, key, messages, system, max_tokens, temperature, False, True, None
        )
        response = _post(url, headers, body)
    _check(response, provider, model)
    data = response.json()
    text = _text_from(provider, data)
    tin, tout = _usage_from(provider, data)
    _record(provider, model, time.time() - started, tin, tout)
    if not text:
        raise LLMError("The AI returned an empty answer. Please try again.")
    return text


def ask(prompt, system=None, **options):
    """One question in, one answer out."""
    return chat([{"role": "user", "text": prompt}], system=system, **options)


def stream(history, system=None, max_tokens=None, temperature=None):
    """Like chat(), but a generator: yields the answer a few words at a time."""
    messages = _normalize(history)
    provider, model, key = _config["provider"], _config["model"], _config["api_key"]
    if provider == "mock":
        for word in _mock_text(messages, system, False).split(" "):
            yield word + " "
            time.sleep(0.02)
        return
    url, headers, body = _build_request(
        provider, model, key, messages, system, max_tokens, temperature, True, False
    )
    response = _post(url, headers, body, stream=True)
    with response:
        _check(response, provider, model)
        response.encoding = "utf-8"  # event streams do not say; without this emojis break
        got_any = False
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except ValueError:
                continue
            piece = _delta_from(provider, event)
            if piece:
                got_any = True
                yield piece
        if not got_any:
            raise LLMError("The AI returned an empty answer. Please try again.")


def _strip_fences(text):
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    return re.sub(r"```$", "", text).strip()


def ask_json(prompt, system=None, schema=None, retries=1, **options):
    """Ask for JSON and get Python data back.

    With a schema the answer is also CHECKED. If it does not fit, the AI is told what
    was wrong and gets one more try (a "repair loop").
    """
    full_prompt = prompt + "\n\nReply with ONLY valid JSON. No extra words and no code fences."
    if schema is not None:
        full_prompt += "\nThe JSON must match this schema:\n" + json.dumps(schema)
    attempt = 0
    while True:
        text = chat([{"role": "user", "text": full_prompt}], system=system, json_mode=True, schema=schema, **options)
        try:
            data = json.loads(_strip_fences(text))
            problems = validate(data, schema) if schema is not None else []
        except ValueError:
            data, problems = None, ["the reply was not valid JSON"]
        if not problems:
            return data
        if attempt >= retries:
            if data is None:
                raise LLMError("The AI sent back broken JSON. Please try again.")
            raise LLMError("The AI's JSON did not match the schema: " + "; ".join(problems))
        attempt += 1
        full_prompt += "\n\nYour last reply had these problems: " + "; ".join(problems) + ". Fix them. JSON only."


def pick(question, options, system=None):
    """Choose ONE label for a message. options = a list of labels, or {label: hint words}."""
    labels = list(options)
    hints = options if isinstance(options, dict) else {}
    if _config["provider"] == "mock":
        asked = _words(question, 3)
        best, best_score = None, 0
        for label in labels:
            score = len(asked & _words(label + " " + hints.get(label, ""), 3))
            if score > best_score:
                best, best_score = label, score
        return best or ("other" if "other" in labels else labels[-1])
    lines = "\n".join(f"- {label}: {hints.get(label, '')}".rstrip(": ") for label in labels)
    schema = {"type": "object", "properties": {"choice": {"type": "string", "enum": labels}}, "required": ["choice"]}
    data = ask_json(f"Pick the single best label for this message.\nMESSAGE: {question}\nLABELS:\n{lines}", system=system, schema=schema)
    return data["choice"] if data.get("choice") in labels else labels[-1]


# --------------------------------------------------------------------------
# Tools: let the AI ask YOUR code to do things
# --------------------------------------------------------------------------
def make_tool(func, description=None):
    """Turn a normal Python function into a tool the AI can use (name, description, inputs)."""
    kinds = {int: "integer", float: "number", bool: "boolean", str: "string", list: "array"}
    props, required = {}, []
    for name, param in inspect.signature(func).parameters.items():
        kind = kinds.get(param.annotation, "string")
        props[name] = {"type": kind, "description": name.replace("_", " ")}
        if kind == "array":
            props[name]["items"] = {"type": "string"}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    text = (description or func.__doc__ or func.__name__).strip().split("\n")[0]
    return {
        "name": func.__name__,
        "description": text,
        "parameters": {"type": "object", "properties": props, "required": required},
        "func": func,
    }


def run_tool(call, tools):
    """Run ONE tool call the AI asked for. Returns a 'tool' message to add to the conversation."""
    by_name = {t["name"]: t for t in tools}
    tool = by_name.get(call["name"])
    if tool is None:
        result = f"ERROR: there is no tool called {call['name']}"
    else:
        try:
            result = str(tool["func"](**call["args"]))
        except Exception as err:  # the AI should SEE the error and adapt
            result = f"ERROR: {type(err).__name__}: {err}"
    return {"role": "tool", "id": call["id"], "name": call["name"], "result": result}


def _tool_messages(history):
    if isinstance(history, str):
        history = [{"role": "user", "text": history}]
    if not history or history[0]["role"] != "user":
        raise ValueError("A conversation must start with a 'user' message.")
    return history


def _build_tools_request(provider, model, key, messages, tools, system, max_tokens, temperature):
    specs = [{"name": t["name"], "description": t["description"], "parameters": t["parameters"]} for t in tools]

    if provider == "claude":
        out = []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["text"]})
            elif m["role"] == "assistant":
                if m.get("raw") and m.get("provider") == "claude":
                    blocks = m["raw"]
                else:
                    blocks = ([{"type": "text", "text": m["text"]}] if m.get("text") else []) + [
                        {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["args"]} for c in m.get("tool_calls", [])
                    ]
                out.append({"role": "assistant", "content": blocks or m.get("text", "")})
            else:
                block = {"type": "tool_result", "tool_use_id": m["id"], "content": m["result"]}
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list) and out[-1].get("_results"):
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block], "_results": True})
        for item in out:
            item.pop("_results", None)
        body = {
            "model": model,
            "max_tokens": max_tokens or 1024,
            "messages": out,
            "tools": [{"name": s["name"], "description": s["description"], "input_schema": s["parameters"]} for s in specs],
        }
        if system:
            body["system"] = system
        if temperature is not None:
            body["temperature"] = temperature
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        return "https://api.anthropic.com/v1/messages", headers, body

    if provider == "openai":
        out = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "content": m["text"]})
            elif m["role"] == "assistant":
                item = {"role": "assistant", "content": m.get("text") or None}
                if m.get("tool_calls"):
                    item["tool_calls"] = [
                        {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["args"])}}
                        for c in m["tool_calls"]
                    ]
                out.append(item)
            else:
                out.append({"role": "tool", "tool_call_id": m["id"], "content": m["result"]})
        body = {"model": model, "messages": out, "tools": [{"type": "function", "function": s} for s in specs]}
        if max_tokens:
            body["max_completion_tokens"] = max_tokens
        if temperature is not None:
            body["temperature"] = temperature
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        return "https://api.openai.com/v1/chat/completions", headers, body

    if provider == "gemini":
        out = []
        for m in messages:
            if m["role"] == "user":
                out.append({"role": "user", "parts": [{"text": m["text"]}]})
            elif m["role"] == "assistant":
                if m.get("raw") and m.get("provider") == "gemini":
                    parts = m["raw"]  # Gemini 3 needs its "thought signatures" sent back exactly as received
                else:
                    parts = ([{"text": m["text"]}] if m.get("text") else []) + [
                        {"functionCall": {"name": c["name"], "args": c["args"]}} for c in m.get("tool_calls", [])
                    ]
                out.append({"role": "model", "parts": parts})
            else:
                part = {"functionResponse": {"name": m["name"], "response": {"result": m["result"]}}}
                if out and out[-1]["role"] == "user" and out[-1].get("_results"):
                    out[-1]["parts"].append(part)
                else:
                    out.append({"role": "user", "parts": [part], "_results": True})
        for item in out:
            item.pop("_results", None)
        body = {"contents": out, "tools": [{"functionDeclarations": specs}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        config = {}
        if temperature is not None:
            config["temperature"] = temperature
        if max_tokens:
            config["maxOutputTokens"] = max_tokens
        if config:
            body["generationConfig"] = config
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        return url, {"x-goog-api-key": key, "Content-Type": "application/json"}, body

    raise ValueError(f"Unknown provider: {provider}")


def _parse_tools(provider, data):
    """Turn a provider's reply into one simple message: text + tool_calls."""
    if provider == "claude":
        if data.get("type") == "error":
            raise LLMError(data.get("error", {}).get("message", "Claude returned an error."))
        blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        calls = [{"id": b["id"], "name": b["name"], "args": b.get("input", {})} for b in blocks if b.get("type") == "tool_use"]
        odd = any(b.get("type") not in ("text", "tool_use") for b in blocks)
        return {"role": "assistant", "text": text, "tool_calls": calls, "raw": blocks if odd else None, "provider": "claude"}
    if provider == "openai":
        choices = data.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        calls = []
        for c in message.get("tool_calls") or []:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            calls.append({"id": c["id"], "name": c["function"]["name"], "args": args})
        return {"role": "assistant", "text": message.get("content") or "", "tool_calls": calls, "raw": None, "provider": "openai"}
    if provider == "gemini":
        block = (data.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise LLMError(f"The request was blocked ({block}). Try rephrasing.")
        candidates = data.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        calls = [
            {"id": f"call_{i}", "name": p["functionCall"]["name"], "args": p["functionCall"].get("args", {})}
            for i, p in enumerate(p for p in parts if "functionCall" in p)
        ]
        return {"role": "assistant", "text": text, "tool_calls": calls, "raw": parts, "provider": "gemini"}
    raise ValueError(f"Unknown provider: {provider}")


def _mock_tools(messages, tools):
    """A pretend brain for tools: matches words in the request to tool names and descriptions."""
    last_user = max((i for i, m in enumerate(messages) if m["role"] == "user"), default=0)
    request = messages[last_user]["text"]
    done = {m["name"]: m["result"] for m in messages[last_user:] if m["role"] == "tool"}
    low = request.lower()
    bare = re.sub(r"[\"'][^\"']*[\"']", " ", request)          # numbers inside quotes are names/ids, not amounts
    numbers = re.findall(r"-?\d+(?:\.\d+)?", bare)
    quoted = re.findall(r"[\"']([^\"']+)[\"']", request)
    names = re.findall(r"\b[A-Z][a-z]{2,}\b", request)
    calls = []
    for tool in tools:
        if tool["name"] in done:
            continue
        clues = _words(tool["name"].replace("_", " ") + " " + tool["description"], 3)
        stems = {c[:5] for c in clues}
        hits = sum(1 for w in _words(low, 3) if w[:5] in stems)
        if hits < 1:
            continue
        args, spare, quotes = {}, list(numbers), list(quoted)       # each tool gets its own copy of the clues
        for pname, spec in tool["parameters"].get("properties", {}).items():
            kind = spec.get("type")
            if kind in ("integer", "number"):
                value = spare.pop(0) if spare else "0"
                args[pname] = int(float(value)) if kind == "integer" else float(value)
            elif kind == "boolean":
                args[pname] = True
            elif "enum" in spec:
                args[pname] = next((e for e in spec["enum"] if str(e).lower() in low), spec["enum"][0])
            else:
                guess = quotes.pop(0) if quotes else (names[-1] if names else request.split()[-1].strip("?.!"))
                args[pname] = guess
        calls.append((hits, {"id": f"mock_{len(done) + len(calls) + 1}", "name": tool["name"], "args": args}))
    calls.sort(key=lambda pair: -pair[0])
    chosen = [c for _, c in calls]
    if chosen:
        return {"role": "assistant", "text": "", "tool_calls": chosen, "raw": None, "provider": "mock"}
    if done:
        summary = "; ".join(f"{name} said {result}" for name, result in done.items())
        text = "🤖 (Practice mode) Here is what my tools found: " + summary
    else:
        text = "🤖 (Practice mode) I did not need a tool for that. A real AI would answer in its own words."
    return {"role": "assistant", "text": text, "tool_calls": [], "raw": None, "provider": "mock"}


def chat_tools(history, tools, system=None, max_tokens=None, temperature=None):
    """One step of a tool conversation.

    history: messages with role "user", "assistant" or "tool".
    Returns ONE assistant message: {"text": ..., "tool_calls": [{"id","name","args"}, ...]}.
    If tool_calls is empty, the AI is finished and "text" is the answer.
    """
    messages = _tool_messages(history)
    provider, model, key = _config["provider"], _config["model"], _config["api_key"]
    started = time.time()
    if provider == "mock":
        reply = _mock_tools(messages, tools)
        sent = (system or "") + " ".join(m.get("text") or m.get("result", "") for m in messages)
        _record(provider, model, time.time() - started + 0.05, _rough_tokens(sent), _rough_tokens(reply["text"] or json.dumps(reply["tool_calls"])))
        return reply
    url, headers, body = _build_tools_request(provider, model, key, messages, tools, system, max_tokens, temperature)
    response = _post(url, headers, body)
    _check(response, provider, model)
    data = response.json()
    reply = _parse_tools(provider, data)
    tin, tout = _usage_from(provider, data)
    _record(provider, model, time.time() - started, tin, tout)
    if not reply["text"] and not reply["tool_calls"]:
        raise LLMError("The AI returned an empty answer. Please try again.")
    return reply


# --------------------------------------------------------------------------
# Built-in tools: tools the AI company runs FOR you (like web search)
# --------------------------------------------------------------------------
BUILTIN_TOOLS = {
    "claude": {"type": "web_search_20250305", "name": "web_search", "max_uses": 3},
    "openai": {"type": "web_search"},
    "gemini": {"google_search": {}},
}


def ask_with_search(prompt, system=None, max_tokens=None):
    """Ask a question and let the AI company's own web-search tool help. Returns {"text", "sources"}."""
    provider, model, key = _config["provider"], _config["model"], _config["api_key"]
    started = time.time()
    if provider == "mock":
        _record(provider, model, time.time() - started + 0.05, _rough_tokens(prompt), 30)
        return {
            "text": "🤖 (Practice mode) Pretend search result: a real AI would read live web pages here and answer with fresh facts.",
            "sources": [{"title": "A pretend web page", "url": "https://example.com/pretend"}],
        }
    if provider == "claude":
        body = {
            "model": model,
            "max_tokens": max_tokens or 2048,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [BUILTIN_TOOLS["claude"]],
        }
        if system:
            body["system"] = system
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        url = "https://api.anthropic.com/v1/messages"
    elif provider == "openai":
        body = {"model": model, "input": prompt, "tools": [BUILTIN_TOOLS["openai"]]}
        if system:
            body["instructions"] = system
        if max_tokens:
            body["max_output_tokens"] = max_tokens
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        url = "https://api.openai.com/v1/responses"
    else:
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "tools": [BUILTIN_TOOLS["gemini"]]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    response = _post(url, headers, body)
    _check(response, provider, model)
    data = response.json()
    text, sources = "", []
    if provider == "claude":
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
                for cite in block.get("citations") or []:
                    sources.append({"title": cite.get("title", ""), "url": cite.get("url", "")})
    elif provider == "openai":
        for item in data.get("output", []):
            if item.get("type") == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        text += part.get("text", "")
                        for note in part.get("annotations") or []:
                            if note.get("type") == "url_citation":
                                sources.append({"title": note.get("title", ""), "url": note.get("url", "")})
    else:
        text = _text_from("gemini", data)
        candidates = data.get("candidates") or [{}]
        for chunk in (candidates[0].get("groundingMetadata") or {}).get("groundingChunks", []):
            web = chunk.get("web") or {}
            sources.append({"title": web.get("title", ""), "url": web.get("uri", "")})
    tin, tout = _usage_from("openai" if provider == "openai" and "usage" in data else provider, data)
    _record(provider, model, time.time() - started, tin, tout)
    unique, seen = [], set()
    for s in sources:
        if s["url"] and s["url"] not in seen:
            seen.add(s["url"])
            unique.append(s)
    if not text:
        raise LLMError("The AI returned an empty answer. Please try again.")
    return {"text": text, "sources": unique}


# --------------------------------------------------------------------------
# Embeddings: text -> a list of numbers, so "similar meaning" = "close together"
# --------------------------------------------------------------------------
EMBED_MODELS = {"openai": "text-embedding-3-small", "gemini": "gemini-embedding-001"}   # teacher: edit if these change

# Practice mode uses a tiny hand-made "meaning table" so students can SEE why embeddings work.
# Each concept is one coordinate. (Real embeddings have hundreds or thousands of coordinates, learned by a model.)
CONCEPTS = {
    "cold": "cold chilly cool freezing icy lukewarm frozen",
    "hot": "hot warm fresh steaming burnt",
    "money": "money refund refunds pay paid cost costs price prices cheap expensive dollar dollars charge card cash bitcoin",
    "time": "time minutes minute hours hour open close closed late early when wait slow fast quick soon",
    "delivery": "deliver delivery drive driver arrive arrives bring home address order",
    "vegan": "vegan vegetarian plant dairy cheese meat diet",
    "size": "size large medium small slice slices big tiny huge",
    "pizza": "pizza pizzas pie pies crust topping toppings pepperoni margherita pineapple",
    "drink": "drink drinks soda juice water alcohol beer",
    "help": "human agent person help support complain manager",
}
_CONCEPT_OF = {word: i for i, (name, words) in enumerate(CONCEPTS.items()) for word in words.split()}
_HASH_DIMS = 8


def _mock_embedding(text):
    import math

    vector = [0.0] * (len(CONCEPTS) + _HASH_DIMS)
    for word in re.findall(r"[a-z]+", str(text).lower()):
        if word in _CONCEPT_OF:
            vector[_CONCEPT_OF[word]] += 1.0
        elif len(word) > 3:
            vector[len(CONCEPTS) + sum(ord(c) for c in word) % _HASH_DIMS] += 0.3
    length = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [round(v / length, 4) for v in vector]


_embed_note = {"shown": False}


def embed(texts):
    """Turn texts into embeddings (lists of numbers). One text in -> one list out; many texts -> a list of lists.

    Practice mode: a tiny 18-number pretend embedding. OpenAI and Gemini: real embeddings.
    Claude does not offer embeddings, so with Claude we use the practice ones (and say so)."""
    single = isinstance(texts, str)
    items = [texts] if single else list(texts)
    provider, key = _config["provider"], _config["api_key"]
    started = time.time()
    if provider in ("mock", "claude"):
        if provider == "claude" and not _embed_note["shown"]:
            print("ℹ️ Claude has no embeddings API (Anthropic suggests a separate embeddings provider). Using practice embeddings.")
            _embed_note["shown"] = True
        vectors = [_mock_embedding(t) for t in items]
        _record(provider, "mock-embed", time.time() - started + 0.01, sum(_rough_tokens(t) for t in items), 0)
        return vectors[0] if single else vectors
    model = EMBED_MODELS[provider]
    if provider == "openai":
        response = _post("https://api.openai.com/v1/embeddings", {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                         {"model": model, "input": items})
        _check(response, provider, model)
        data = response.json()
        vectors = [row["embedding"] for row in sorted(data["data"], key=lambda r: r["index"])]
        tokens = (data.get("usage") or {}).get("prompt_tokens", 0)
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
        body = {"requests": [{"model": f"models/{model}", "content": {"parts": [{"text": t}]}} for t in items]}
        response = _post(url, {"x-goog-api-key": key, "Content-Type": "application/json"}, body)
        _check(response, provider, model)
        vectors = [row["values"] for row in response.json()["embeddings"]]
        tokens = sum(_rough_tokens(t) for t in items)
    _record(provider, model, time.time() - started, tokens, 0)
    return vectors[0] if single else vectors
