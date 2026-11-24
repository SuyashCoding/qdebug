"""The optional Claude integration, tested against a fake client (no network, no SDK needed)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from helpers import PLANNER, SHOP, make_tree, snap
from qdebug import cli
from qdebug.ai import Agent, AIError, AIUnavailable, Assistant, Claude, ClaudeOracle, HybridOracle
from qdebug.ai.assistant import Triage
from qdebug.ai.oracle import LINE_VERDICTS
from qdebug.ai.prompts import describe_call, parse_sections, test_key, write_project_agent
from qdebug.belief import Belief
from qdebug.oracles import Answer, Oracle, Question, ai_hint
from qdebug.session import answer_error
from qdebug.spectrum import FuncInfo
from qdebug.suites import ensure_variants

# ------------------------------------------------------------------ fakes


def block(kind, text=""):
    return SimpleNamespace(type=kind, text=text, thinking="")


def response(data, stop="end_turn"):
    text = data if isinstance(data, str) else json.dumps(data)
    usage = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=50,
                            cache_creation_input_tokens=0)
    return SimpleNamespace(content=[block("thinking"), block("text", text)], stop_reason=stop, usage=usage)


class FakeMessages:
    def __init__(self, reply):
        self.reply = reply  # function(kwargs) -> response, or an exception to raise
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = self.reply(kwargs)
        if isinstance(result, Exception):
            raise result
        return result


def fake_claude(reply, **kwargs):
    messages = FakeMessages(reply)
    return Claude(client=SimpleNamespace(messages=messages), **kwargs), messages


def schema_of(kwargs):
    return kwargs["output_config"]["format"]["schema"]["properties"]


def verdict(value, confidence=0.9, reason="checked it"):
    return lambda kwargs: response({"verdict": value, "confidence": confidence, "reason": reason})


class FakeSession:
    """Just what the prompts read from a DebugSession."""

    def __init__(self, tree):
        self.tree = tree
        self.test_id = "tests/test_m.py::test_it"
        self.failure_text = "E   assert 3 == 4"
        self.log = []
        self.lines = {"m.py": ["def f(x):", "    return x + 1", "", "def g(x):", "    return f(x)"],
                      "tests/test_m.py": ["def test_it():", "    assert g(2) == 4"]}
        self.functions = {
            "m.py::f": FuncInfo("m.py::f", "m.py", "f", 1, 1, 2, "f(x)", "Add one.", "", False),
            "tests/test_m.py::test_it": FuncInfo("tests/test_m.py::test_it", "tests/test_m.py", "test_it",
                                                 1, 1, 2, "test_it()", "", "", True)}
        self.messages = []

    def file_lines(self, relfile):
        return self.lines.get(relfile, [])

    def out(self, message):
        self.messages.append(message)


def small_session():
    tree = make_tree(("test", [("f", [])]), values={"f": ("2", "3")})
    tree.nodes[0].file = "tests/test_m.py"
    tree.nodes[1].call_line = 2
    return FakeSession(tree)


def call_question(session):
    return Question("call", session.tree.nodes[1], session.functions["m.py::f"], number=1)


# ----------------------------------------------------------------- client

def test_request_uses_structured_output_effort_and_caching():
    claude, messages = fake_claude(lambda kw: response({"ok": True}), model="claude-haiku-5-5", effort="low")
    assert claude.ask(["rules", "context"], "question?", {"type": "object"}) == {"ok": True}
    kwargs = messages.calls[0]
    assert kwargs["model"] == "claude-haiku-5-5"
    assert kwargs["output_config"] == {"effort": "low",
                                       "format": {"type": "json_schema", "schema": {"type": "object"}}}
    assert [b["text"] for b in kwargs["system"]] == ["rules", "context"]
    assert "cache_control" not in kwargs["system"][0]
    assert kwargs["system"][1]["cache_control"] == {"type": "ephemeral"}
    assert kwargs["messages"] == [{"role": "user", "content": "question?"}]
    # Claude Haiku 5.5 rejects sampling parameters and assistant prefill
    assert not {"temperature", "top_p", "top_k"} & set(kwargs)
    assert claude.usage.requests == 1 and claude.usage.cache_read_tokens == 50


def test_default_model_is_haiku(monkeypatch):
    monkeypatch.delenv("QDEBUG_AI_MODEL", raising=False)
    assert Claude(client=object()).model == "claude-haiku-5-5"
    monkeypatch.setenv("QDEBUG_AI_MODEL", "claude-sonnet-5-5")
    assert Claude(client=object()).model == "claude-sonnet-5-5"


@pytest.mark.parametrize("reply", [response({}, stop="refusal"), response({}, stop="max_tokens"),
                                   response("not json"), response("[1, 2]")])
def test_unusable_answers_are_errors_for_one_request(reply):
    claude, _ = fake_claude(lambda kw: reply)
    with pytest.raises(AIError) as caught:
        claude.ask(["s"], "p", {})
    assert not isinstance(caught.value, AIUnavailable)
    assert claude.disabled is None and claude.usage.failures == 1


def test_missing_credentials_switch_claude_off():
    claude, messages = fake_claude(lambda kw: TypeError("Could not resolve authentication method"))
    for _ in range(2):
        with pytest.raises(AIUnavailable):
            claude.ask(["s"], "p", {})
    assert len(messages.calls) == 1  # not retried once it is known to be unavailable


def test_bad_effort_is_rejected():
    with pytest.raises(ValueError):
        Claude(client=object(), effort="turbo")


# ------------------------------------------------------------------ oracle

def test_claude_oracle_maps_verdict_and_confidence():
    session = small_session()
    claude, messages = fake_claude(verdict("no", 0.7, "2 + 1 is 3, but the docstring says add one"))
    answer = ClaudeOracle(claude, Agent.load()).judge(call_question(session), session)
    assert answer.verdict == "no" and answer.confidence == 0.7
    assert "docstring" in answer.note
    assert schema_of(messages.calls[0])["verdict"]["enum"] == ["yes", "no", "inadmissible", "unknown"]


def test_line_questions_cannot_be_inadmissible():
    session = small_session()
    node = session.tree.nodes[1]
    cp = {"kind": "line", "line": 2, "occurrence": 1, "locals": {"x": snap("2")}, "aliases": []}
    claude, messages = fake_claude(verdict("yes"))
    ClaudeOracle(claude, Agent.load()).judge(Question("line", node, checkpoint=cp), session)
    assert schema_of(messages.calls[0])["verdict"]["enum"] == LINE_VERDICTS
    assert "return x + 1" in messages.calls[0]["messages"][0]["content"]  # line questions show code


def test_a_failed_request_is_an_unknown_answer():
    session = small_session()
    claude, _ = fake_claude(lambda kw: response("garbage"))
    answer = ClaudeOracle(claude, Agent.load()).judge(call_question(session), session)
    assert answer.verdict == "unknown" and "claude failed" in answer.note


def test_call_prompt_hides_the_body_unless_asked():
    session = small_session()
    session.functions["m.py::f"].source = "def f(x):\n    return x + 1"
    node = session.tree.nodes[1]
    hidden = describe_call(session, node)
    assert "Add one." in hidden and "return x + 1" not in hidden
    assert "Called by: test" in hidden and "assert g(2) == 4" in hidden  # the caller's line
    assert "return x + 1" in describe_call(session, node, show_source=True)


def test_closure_variables_are_labelled():
    session = small_session()
    node = session.tree.nodes[1]
    node.closure = ["x"]
    assert "(closure: a variable of the enclosing function)" in describe_call(session, node)


def test_test_key():
    assert test_key("tests/t.py::TestX::test_a[1-2]") == "tests/t.py::TestX.test_a"
    assert test_key("t.py::test_b") == "t.py::test_b"


class Scripted(Oracle):
    name = "scripted"

    def __init__(self, reply):
        self.reply = reply
        self.seen = []

    def judge(self, question, ctx=None):
        self.seen.append(question)
        return self.reply


def test_hybrid_uses_claude_when_sure_and_asks_you_otherwise():
    session = small_session()
    human = Scripted(Answer("yes"))
    shown = []
    claude, _ = fake_claude(verdict("no", 0.95))
    hybrid = HybridOracle(ClaudeOracle(claude, Agent.load()), human, threshold=0.8,
                          show=lambda q, c, a: shown.append(a))
    assert hybrid.judge(call_question(session), session).verdict == "no"
    assert human.seen == [] and len(shown) == 1

    claude, _ = fake_claude(verdict("no", 0.6, "looks off"))
    hybrid = HybridOracle(ClaudeOracle(claude, Agent.load()), human, threshold=0.8)
    question = call_question(session)
    reply = hybrid.judge(question, session)
    assert reply.verdict == "yes" and human.seen == [question]
    assert ai_hint(question).startswith("Claude thinks: wrong (60% sure)")
    assert reply.note == "you (Claude said no)"


def test_hybrid_falls_back_to_you_when_claude_is_unavailable():
    session = small_session()
    claude, messages = fake_claude(lambda kw: TypeError("missing api_key"))
    hybrid = HybridOracle(ClaudeOracle(claude, Agent.load()), Scripted(Answer("no")))
    assert hybrid.judge(call_question(session), session).verdict == "no"
    assert hybrid.judge(call_question(session), session).verdict == "no"
    assert hybrid.notice and len(messages.calls) == 1
    assert "unavailable" in session.messages[0]


# ------------------------------------------------------------------ prompt

def test_project_agent_replaces_sections_and_adds_notes(tmp_path):
    (tmp_path / ".qdebug").mkdir()
    (tmp_path / ".qdebug" / "agent.md").write_text(
        "# mine\n\n## call\nJudge money in cents.\n\n## project notes\nAll amounts are integer cents.\n",
        encoding="utf-8")
    agent = Agent.load(project=str(tmp_path))
    assert agent.sections["call"] == "Judge money in cents."
    assert sorted(agent.overridden) == ["call", "project notes"]
    system = agent.system("call")
    assert "Judge money in cents." in system and "All amounts are integer cents." in system
    assert "oracle in an algorithmic debugging session" in system  # built-in section kept


def test_unknown_agent_sections_are_reported(tmp_path):
    path = tmp_path / "agent.md"
    path.write_text("## sistem\ntypo\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sistem"):
        Agent.load(str(path))


def test_init_agent_writes_a_copy_once(tmp_path):
    path = write_project_agent(str(tmp_path))
    with open(path, encoding="utf-8") as fh:
        assert set(parse_sections(fh.read())) >= {"system", "call", "line"}
    with pytest.raises(FileExistsError):
        write_project_agent(str(tmp_path))


# ------------------------------------------------- confidence and triage

def test_an_unsure_answer_moves_the_belief_less():
    tree = make_tree(("test", [("a", []), ("b", [])]))
    belief = Belief(tree, lambda func: 0.5)
    plain = belief.posterior({"test/a#0": "no"})[1]
    tree.hints.answer_error["test/a#0"] = answer_error(0.6, 0.1)
    unsure = belief.posterior({"test/a#0": "no"})[1]
    assert plain > unsure > belief.posterior({})[1]


def test_answer_error_never_trusts_a_confidence_more_than_a_plain_answer():
    assert answer_error(1.0, 0.1) is None
    assert answer_error(0.99, 0.1) == 0.1
    assert answer_error(0.7, 0.1) == pytest.approx(0.3)
    assert answer_error(0.1, 0.1) == 0.45


@pytest.mark.e2e
def test_triage_tunes_the_search_and_boosts_its_suspects():
    from qdebug.evaluate import RunCache
    from qdebug.session import DebugSession, SessionConfig

    ensure_variants(PLANNER)
    session = DebugSession(SessionConfig(project=PLANNER.variant("p31-mutable-default"), policy="tuned"),
                           oracle=None, run=RunCache(), out=lambda *a: None)
    session.prepare()
    assert session.tuning.assertion_weight == 0.05

    def reply(kwargs):
        listed = kwargs["messages"][0]["content"]
        assert "planner/workload.py::owners_of" in listed
        return response({"bug_kind": "state", "reason": "results pile up between calls",
                         "suspects": ["planner/workload.py::owners_of", "made/up.py::nothing"]})

    claude, _ = fake_claude(reply)
    triage = Assistant(claude, Agent.load()).triage(session)
    assert triage == Triage("state", ["planner/workload.py::owners_of"], "results pile up between calls")
    session.apply_triage(triage)
    assert session.tuning.assertion_weight == 1.0
    session.build_tree()
    boosted = [n for n in session.tree.nodes if n.func == "planner/workload.py::owners_of"]
    assert boosted and all(session.tree.hints.prior_scale[n.id] == 2.0 for n in boosted)


# ---------------------------------------------------------------- the CLI

def scripted_claude(kwargs):
    props = schema_of(kwargs)
    if "bug_kind" in props:
        return response({"bug_kind": "wrong-value", "suspects": [], "reason": "a total is off"})
    if "summary" in props:
        return response({"summary": "the discount threshold is off by one",
                         "explanation": "10 units should get the bulk rate.",
                         "fix": "    if quantity >= 10:", "confidence": "high"})
    return response({"verdict": "unknown", "confidence": 0.2, "reason": "cannot tell"})


@pytest.mark.e2e
def test_cli_runs_with_claude_and_reports_it(monkeypatch, tmp_path, capsys):
    ensure_variants(SHOP)
    claude, messages = fake_claude(scripted_claude)
    monkeypatch.setattr(cli, "make_assistant", lambda args: Assistant(claude, Agent.load()))
    code = cli.main(["debug", "--project", SHOP.variant("bug_01"), "--oracle", "claude", "--plain",
                     "--save-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "Claude's first look: a wrong-value bug" in out
    assert "the discount threshold is off by one" in out and "if quantity >= 10:" in out
    report = json.loads(next(tmp_path.glob("session_*.json")).read_text(encoding="utf-8"))
    assert report["oracle"] == "claude"
    assert report["ai"]["usage"]["requests"] == len(messages.calls) >= 3
    assert report["ai"]["triage"]["bug_kind"] == "wrong-value"


def test_cli_explains_how_to_install_the_sdk(monkeypatch, capsys):
    import qdebug.ai
    monkeypatch.setattr(qdebug.ai, "sdk_available", lambda: False)
    code = cli.main(["debug", "--project", SHOP.project, "--oracle", "claude", "--plain"])
    assert code == 2
    assert "pip install 'qdebug[ai]'" in capsys.readouterr().err


# ------------------------------------------- the real SDK, against a stub

class _Stub(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):  # noqa: N802 - http.server API
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Stub.requests.append((self.path, body))
        payload = {"id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
                   "content": [{"type": "thinking", "thinking": "", "signature": "sig"},
                               {"type": "text", "text": json.dumps({"verdict": "yes", "confidence": 0.9,
                                                                    "reason": "ok"})}],
                   "stop_reason": "end_turn", "stop_sequence": None,
                   "usage": {"input_tokens": 10, "output_tokens": 5}}
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def test_the_real_sdk_sends_and_parses_the_request():
    anthropic = pytest.importorskip("anthropic")
    server = HTTPServer(("127.0.0.1", 0), _Stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = anthropic.Anthropic(api_key="test-key", base_url=f"http://127.0.0.1:{server.server_port}",
                                     max_retries=0)
        claude = Claude(client=client, effort="low")
        assert claude.ask(["rules"], "q", {"type": "object"}) == {"verdict": "yes", "confidence": 0.9,
                                                                    "reason": "ok"}
    finally:
        server.shutdown()
    path, body = _Stub.requests[-1]
    assert path == "/v1/messages"
    assert body["model"] == "claude-haiku-5-5"
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}


# --------------------------------------------------------- eval-ai harness

class SimulatedClaude(Oracle):
    """The ground truth, wrong on every third call question, with a confidence to match."""

    name = "claude"

    def __init__(self, truth):
        self.truth = truth
        self.calls = 0

    def judge(self, question, ctx=None):
        answer = self.truth.judge(question, ctx)
        if question.kind == "call":
            self.calls += 1
            if self.calls % 3 == 0 and answer.verdict in ("yes", "no"):
                return Answer("no" if answer.verdict == "yes" else "yes", 0.6, note="claude 60%: a guess")
        return Answer(answer.verdict, 0.95, note="claude 95%: checked")


def harness_reply(kwargs):
    props = schema_of(kwargs)
    if "bug_kind" in props:
        return response({"bug_kind": "state", "suspects": ["planner/workload.py::owners_of"], "reason": "r"})
    return response({"summary": "s", "explanation": "e", "fix": "def owners_of(plan, tag, found=None):",
                     "confidence": "high"})


@pytest.mark.e2e
@pytest.mark.parametrize("mode", ["claude", "hybrid"])
def test_eval_ai_grades_claude_against_the_ground_truth(monkeypatch, tmp_path, mode):
    from qdebug.ai import benchmark

    def oracle(self, kind, human=None, threshold=0.8, show=None):
        truth = human if human is not None else GroundTruthOracleFor.made.current
        sim = SimulatedClaude(truth)
        return HybridOracle(sim, human, threshold) if kind == "hybrid" else sim

    class GroundTruthOracleFor(benchmark.GroundTruthOracle):
        # one per thread: the two bugs run in parallel, and each bug's simulated Claude must judge
        # against its own bug's ground truth (a shared attribute let one bug take the other's)
        made = threading.local()

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            GroundTruthOracleFor.made.current = self

    monkeypatch.setattr(benchmark, "GroundTruthOracle", GroundTruthOracleFor)
    monkeypatch.setattr(Assistant, "oracle", oracle)
    client = SimpleNamespace(messages=FakeMessages(harness_reply))
    rows, questions = benchmark.run_ai_benchmark(
        [PLANNER], mode=mode, out_dir=str(tmp_path), bug_ids={"p31-mutable-default", "p21-truncation"},
        workers=2, client=client, log=lambda *a: None)
    by_bug = {r["bug"]: r for r in rows}
    assert not any(r["error"] for r in rows), rows
    p31 = by_bug["p31-mutable-default"]
    assert p31["triage_kind_correct"] == 1 and p31["triage_suspect_hit"] == 1
    assert p31["fix_correct"] == 1 and by_bug["p21-truncation"]["fix_correct"] == 0
    assert p31["requests"] == 2 and p31["cost_usd"] > 0
    assert {q["outcome"] for q in questions} <= {"correct", "wrong", "abstained", "ungradable"}
    assert sum(r["claude_answers"] for r in rows) == len(questions)
    if mode == "hybrid":
        assert sum(r["human_questions"] for r in rows) > 0
    summary = (tmp_path / "planner" / "ai_summary.md").read_text(encoding="utf-8")
    assert "Claude's answers against the ground truth" in summary and "Calibration" in summary


def test_fix_grading():
    from qdebug.ai.benchmark import fix_restores_original
    bug = {"old": "        for dep in plan.get(name).after:\n            place(dep)",
           "new": "        for dep in plan.get(name).after[:1]:\n            place(dep)"}
    assert fix_restores_original(bug, "for dep in plan.get(name).after:\n    place(dep)")
    assert not fix_restores_original(bug, "for dep in plan.get(name).after[:2]:")
    assert not fix_restores_original(bug, "")


@pytest.mark.e2e
def test_passing_tests_supply_examples_of_a_function():
    from qdebug.evaluate import RunCache
    from qdebug.session import DebugSession, SessionConfig

    ensure_variants(SHOP)
    session = DebugSession(SessionConfig(project=SHOP.variant("bug_04"), policy="tuned"), oracle=None,
                           run=RunCache(), out=lambda *a: None)
    session.prepare()
    examples = session.passing_examples("shop/pricing.py::compute_tax")
    assert examples and all(session.spectrum.tests[test].outcome == "passed" for _, _, test in examples)
    assert all(set(args) == {"amount", "address"} and out.startswith("→") for args, out, _ in examples)
    session.build_tree()
    call = next(n for n in session.tree.nodes if n.func == "shop/pricing.py::compute_tax")
    text = describe_call(session, call)
    assert "tests that PASS" in text and "compute_tax" in session.format_examples(call)


def test_relay_passes_requests_and_answers_through_files(tmp_path):
    from qdebug.ai.relay import RelayClient, next_request

    directory = str(tmp_path / "shop-bug_01")
    relay = RelayClient(directory, timeout=20, poll=0.05)
    claude = Claude(client=relay, effort="low")
    shown = []

    def answer():
        for text in ("```json\n{\"verdict\": \"yes\", \"confidence\": 0.9, \"reason\": \"ok\"}\n```",
                     "{\"verdict\": \"no\", \"confidence\": 0.7, \"reason\": \"off\"}"):
            listing = next_request([directory], wait=10)
            shown.append(listing)
            target = listing.rsplit("WRITE THE JSON TO THIS FILE: ", 1)[1].split(" ---")[0]
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(text)

    thread = threading.Thread(target=answer)
    thread.start()
    first = claude.ask(["rules", "context"], "question one", {"type": "object"})
    second = claude.ask(["rules", "context"], "question two", {"type": "object"})
    thread.join()
    relay.close()
    assert first["verdict"] == "yes" and second["verdict"] == "no"
    assert "rules" in shown[0] and "question one" in shown[0]
    assert "same as the last SYSTEM" in shown[1] and "question two" in shown[1]
    assert next_request([directory], wait=1).startswith("ALL DONE")
