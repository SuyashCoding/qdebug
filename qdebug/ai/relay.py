"""Answer Claude's requests through files, so that an agent can stand in for the API.

`qdebug eval-ai --relay DIR` gives every benchmark session a RelayClient instead
of the Anthropic SDK: each request (system text, prompt, JSON schema) is
written to DIR/<suite>-<bug>/req_<n>.json, and the session waits for
resp_<n>.json. An agent such as Claude Code answers them with

    python -m qdebug.ai.relay next DIR/<suite>-<bug> [more dirs...]

which waits for the next pending request, prints it, and says where to write
the answer. When a session ends, DONE is written to its directory.

This exists to measure the prompts with a model where no API key is
available. It is slower than the API, has no token counts, and the agent
runs with its own system prompt as well.
"""

import glob
import hashlib
import json
import os
import sys
import time
from types import SimpleNamespace

from qdebug.ai.client import AIError

WAIT_SLICE = 90  # seconds `next` waits before asking to be run again (stays under tool timeouts)


def _write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


class _Messages:
    def __init__(self, relay):
        self.relay = relay

    def create(self, **kwargs):
        return self.relay.request(kwargs)


class RelayClient:
    """Implements the SDK's messages.create by writing requests and reading answers from files."""

    def __init__(self, directory, timeout=1800.0, poll=0.5):
        self.directory = directory
        self.timeout = timeout
        self.poll = poll
        self.count = 0
        self.messages = _Messages(self)
        os.makedirs(directory, exist_ok=True)
        for stale in glob.glob(os.path.join(directory, "*.json")) + [os.path.join(directory, "DONE")]:
            if os.path.exists(stale):
                os.remove(stale)

    def request(self, kwargs):
        self.count += 1
        number = self.count
        request = {
            "id": number,
            "model": kwargs.get("model"),
            "effort": kwargs.get("output_config", {}).get("effort"),
            "system": [block["text"] for block in kwargs.get("system", [])],
            "prompt": kwargs["messages"][-1]["content"],
            "schema": kwargs.get("output_config", {}).get("format", {}).get("schema"),
        }
        _write_atomic(os.path.join(self.directory, f"req_{number}.json"), json.dumps(request))
        path = os.path.join(self.directory, f"resp_{number}.json")
        deadline = time.monotonic() + self.timeout
        bad_reads = 0
        while time.monotonic() < deadline:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as fh:
                    text = fh.read().strip()
                try:
                    json.loads(text)
                except ValueError:
                    bad_reads += 1
                    if bad_reads < 4:  # may still be being written
                        time.sleep(1.0)
                        continue
                text = _strip_fences(text)
                return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                                       stop_reason="end_turn", usage=None)
            time.sleep(self.poll)
        raise AIError(f"no answer to request {number} in {self.directory} within {self.timeout:.0f}s")

    def close(self):
        _write_atomic(os.path.join(self.directory, "DONE"), "done")


def _strip_fences(text):
    """Accept an answer wrapped in a markdown code fence."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def _pending(directory):
    def number(path):
        return int(os.path.basename(path)[4:-5])

    requests = sorted(glob.glob(os.path.join(directory, "req_*.json")), key=number)
    return [p for p in requests if not os.path.exists(os.path.join(directory, f"resp_{number(p)}.json"))]


def show(directory, path):
    with open(path, encoding="utf-8") as fh:
        request = json.load(fh)
    system = "\n\n".join(request["system"])
    digest = hashlib.sha1(system.encode()).hexdigest()
    seen_path = os.path.join(directory, ".shown_system")
    seen = ""
    if os.path.exists(seen_path):
        with open(seen_path, encoding="utf-8") as fh:
            seen = fh.read()
    name = os.path.basename(directory)
    answer_path = os.path.abspath(os.path.join(directory, f"resp_{request['id']}.json"))
    out = [f"=== REQUEST {request['id']} of session {name} ==="]
    if digest != seen:
        out += ["--- SYSTEM (instructions and context; new for this request) ---", system]
        with open(seen_path, "w", encoding="utf-8") as fh:
            fh.write(digest)
    else:
        out.append("--- SYSTEM: the same as the last SYSTEM shown for this session ---")
    out += ["--- USER ---", request["prompt"],
            "--- ANSWER: exactly one JSON object matching this schema, nothing else ---",
            json.dumps(request["schema"]),
            f"--- WRITE THE JSON TO THIS FILE: {answer_path} ---"]
    return "\n".join(out)


def next_request(directories, wait=WAIT_SLICE):
    """The text of the next request to answer, in session order, or a status line."""
    deadline = time.monotonic() + wait
    while True:
        active = [d for d in directories if not os.path.exists(os.path.join(d, "DONE"))]
        if not active:
            return "ALL DONE: every session has finished. Stop."
        current = active[0]  # one session at a time: finish it before the next
        pending = _pending(current)
        if pending:
            return show(current, pending[0])
        if time.monotonic() > deadline:
            return "NOTHING YET: qdebug is still working. Run the same command again."
        time.sleep(0.5)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2 or argv[0] != "next":
        print("usage: python -m qdebug.ai.relay next DIR [DIR...]", file=sys.stderr)
        return 2
    for stream in (sys.stdout,):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    print(next_request(argv[1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
