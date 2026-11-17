"""Run every lab script offline (pretend AI, no keys, no internet) and report pass / fail.

    python run_all.py            # all labs
    python run_all.py 23 41      # only these classes

Each lab runs in its own temporary folder, so the helper servers and small databases some labs
write never end up in the repo. A lab passes when it exits cleanly and prints something.
"""
import glob
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KEYS = ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "CLAUDE_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY")


def run_lab(path, timeout=120):
    env = {k: v for k, v in os.environ.items() if k not in KEYS}
    env["PICO_PROVIDER"] = "mock"
    with tempfile.TemporaryDirectory() as tmp:
        try:
            done = subprocess.run([sys.executable, path], cwd=tmp, env=env, capture_output=True,
                                  text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return False, "timed out"
    if done.returncode != 0:
        return False, (done.stderr.strip().splitlines() or ["failed"])[-1]
    if not done.stdout.strip():
        return False, "printed nothing"
    return True, f"{len(done.stdout.splitlines())} lines of output"


def main(wanted):
    labs = sorted(glob.glob(os.path.join(HERE, "[0-9][0-9]_*.py")))
    if wanted:
        labs = [p for p in labs if int(os.path.basename(p)[:2]) in wanted]
    failed = 0
    for path in labs:
        ok, note = run_lab(path)
        failed += not ok
        print(("PASS " if ok else "FAIL ") + os.path.basename(path) + "  " + note)
    print(f"\n{len(labs) - failed} of {len(labs)} labs passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main({int(a) for a in sys.argv[1:]}))
