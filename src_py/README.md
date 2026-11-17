# src_py: the lab code, one runnable file per lab

These are the labs from the **RAG-MCP-Agentic** course (Pico, the AI Interview Coach) that are built
from new code instead of from a file of the original app. Each lab has **one standalone Python file**
with the same lesson code as the lab's Colab notebook and slide deck, in the same order.

Every file runs **offline**: it uses the built-in pretend AI (`mock`), so it needs no key and no internet.

## Run a lab

```bash
pip install requests
python 23_watch_everything.py
```

To use a real model instead of the pretend one:

```bash
PICO_PROVIDER=gemini GEMINI_API_KEY=your-key python 23_watch_everything.py     # or claude / openai
```

Check that every lab still runs (each one in its own temporary folder, so nothing is left behind):

```bash
python run_all.py          # all 29 labs
python run_all.py 23 41    # only some classes
```

## What is in each file

- A header with the class name, the opening mystery, the Python skills and the FDE ideas for that lab.
- The lesson code, split into the same parts as the notebook, with its comments.
- For some labs, an optional **Going further** part showing the real-world tool behind the toy version.

What is **not** here, on purpose: the quiz, the bug hunt, the fill-the-blank deep dive (those are
for students to do in the notebook) and the optional real-model bonus cells of classes 29-44.

`fde_llm.py` is the one helper every lab imports (Claude, Gemini, OpenAI and the pretend AI). It is the
same file as in the course folder.

## The labs

| Class | File | Lab | World |
|---|---|---|---|
| 7 | [`07_tool_calling.py`](07_tool_calling.py) | Tool Calling | World 2 · Tools & Knowledge 🔌 |
| 8 | [`08_plug_it_in.py`](08_plug_it_in.py) | Plug It In | World 2 · Tools & Knowledge 🔌 |
| 9 | [`09_mcp_in_the_real_world.py`](09_mcp_in_the_real_world.py) | MCP in the Real World | World 2 · Tools & Knowledge 🔌 |
| 11 | [`11_vector_pico.py`](11_vector_pico.py) | Vector Pico | World 3 · Memory & Workflows 🧠 |
| 16 | [`16_the_react_agent.py`](16_the_react_agent.py) | The ReAct Agent | World 4 · Agents & Evaluation 🤖 |
| 18 | [`18_human_in_the_loop.py`](18_human_in_the_loop.py) | Human in the Loop | World 4 · Agents & Evaluation 🤖 |
| 19 | [`19_the_test_set.py`](19_the_test_set.py) | The Test Set | World 4 · Agents & Evaluation 🤖 |
| 20 | [`20_the_judge.py`](20_the_judge.py) | The Judge | World 4 · Agents & Evaluation 🤖 |
| 21 | [`21_the_guards.py`](21_the_guards.py) | The Guards | World 5 · Production & Launch 🚀 |
| 23 | [`23_watch_everything.py`](23_watch_everything.py) | Watch Everything | World 5 · Production & Launch 🚀 |
| 26 | [`26_pico_s_playbook.py`](26_pico_s_playbook.py) | Pico's Playbook | World 6 · Pro Skills 🎓 (bonus) |
| 27 | [`27_the_blueprint.py`](27_the_blueprint.py) | The Blueprint | World 6 · Pro Skills 🎓 (bonus) |
| 28 | [`28_from_idea_to_launch.py`](28_from_idea_to_launch.py) | From Idea to Launch | World 6 · Pro Skills 🎓 (bonus) |
| 29 | [`29_cut_it_right.py`](29_cut_it_right.py) | Cut It Right | World 7 · RAG Pro 📖 (advanced) |
| 30 | [`30_two_searches_are_better_than_one.py`](30_two_searches_are_better_than_one.py) | Two Searches Are Better Than One | World 7 · RAG Pro 📖 (advanced) |
| 31 | [`31_rerank_rewrite_cite.py`](31_rerank_rewrite_cite.py) | Rerank, Rewrite, Cite | World 7 · RAG Pro 📖 (advanced) |
| 32 | [`32_judge_the_retriever.py`](32_judge_the_retriever.py) | Judge the Retriever | World 7 · RAG Pro 📖 (advanced) |
| 33 | [`33_the_planner.py`](33_the_planner.py) | The Planner | World 8 · Agentic Pro 🧭 (advanced) |
| 34 | [`34_save_your_place.py`](34_save_your_place.py) | Save Your Place | World 8 · Agentic Pro 🧭 (advanced) |
| 35 | [`35_guardrails.py`](35_guardrails.py) | Guardrails | World 8 · Agentic Pro 🧭 (advanced) |
| 36 | [`36_judge_the_agent.py`](36_judge_the_agent.py) | Judge the Agent | World 8 · Agentic Pro 🧭 (advanced) |
| 37 | [`37_what_is_mcp_really.py`](37_what_is_mcp_really.py) | What Is MCP, Really | World 9 · Many MCPs 🔌 (advanced) |
| 38 | [`38_many_servers_one_client.py`](38_many_servers_one_client.py) | Many Servers, One Client | World 9 · Many MCPs 🔌 (advanced) |
| 39 | [`39_trust_no_tool_much.py`](39_trust_no_tool_much.py) | Trust No Tool (Much) | World 9 · Many MCPs 🔌 (advanced) |
| 40 | [`40_when_a_server_fails.py`](40_when_a_server_fails.py) | When a Server Fails | World 9 · Many MCPs 🔌 (advanced) |
| 41 | [`41_the_message_board.py`](41_the_message_board.py) | The Message Board | World 10 · The Agent Board 💬 (advanced) |
| 42 | [`42_agents_talk_to_each_other.py`](42_agents_talk_to_each_other.py) | Agents Talk to Each Other | World 10 · The Agent Board 💬 (advanced) |
| 43 | [`43_who_said_that.py`](43_who_said_that.py) | Who Said That | World 10 · The Agent Board 💬 (advanced) |
| 44 | [`44_the_finale_a_day_at_pico_s.py`](44_the_finale_a_day_at_pico_s.py) | The Finale: A Day at Pico's | World 10 · The Agent Board 💬 (advanced) |

Each notebook and each slide deck links to its file here (the "Real code on GitHub" chip on the
"Today's goals" slide, and a pointer cell right after the notebook title).
