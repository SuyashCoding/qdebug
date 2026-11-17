"""Claude as the oracle: fully automatic, or as a first opinion that a person confirms."""

from qdebug.ai.client import AIError, AIUnavailable
from qdebug.ai.prompts import describe_call, describe_checkpoint, earlier_answers, test_context
from qdebug.oracles import Answer, Oracle

CALL_VERDICTS = ["yes", "no", "inadmissible", "unknown"]
LINE_VERDICTS = ["yes", "no", "unknown"]


def verdict_schema(verdicts):
    return {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": verdicts},
            "confidence": {"type": "number", "description": "probability that the verdict is right, 0 to 1"},
            "reason": {"type": "string"},
        },
        "required": ["verdict", "confidence", "reason"],
        "additionalProperties": False,
    }


def _confidence(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    if number > 1.0:  # "85" meaning 85%
        number /= 100.0
    return min(0.99, max(0.0, number))  # below 1.0: marks the answer as having a confidence


class ClaudeOracle(Oracle):
    """Asks Claude every question.

    For call questions Claude sees the function's signature, docstring and
    caller, the concrete inputs and outputs, the failing test and the earlier
    answers, but not the function's body (unless show_source): a model shown
    the buggy implementation tends to explain the buggy behaviour as
    intended. Line questions need the body, so it is shown there.

    Claude's stated confidence becomes the answer's own error rate in the
    belief model (session.answer_error). A failed request is answered
    "unknown", which carries no evidence; AIUnavailable stops the session.
    """

    name = "claude"

    def __init__(self, claude, agent, show_source=False):
        self.claude = claude
        self.agent = agent
        self.show_source = show_source
        self._context = None
        self.last_error = None

    def _system(self, ctx, task):
        if self._context is None:
            self._context = test_context(ctx)
        return [self.agent.system(task), self._context]

    def prompt(self, question, ctx):
        if question.kind == "call":
            body = describe_call(ctx, question.node, self.show_source)
            history = earlier_answers(ctx)
            ask = "Is this call's output correct for these inputs?"
        else:
            body = describe_checkpoint(ctx, question)
            history = ""
            ask = "Is every variable correct at this point?"
        return "\n\n".join(part for part in (body, history, ask) if part)

    def judge(self, question, ctx=None):
        if ctx is None:
            raise ValueError("ClaudeOracle needs the session as ctx")
        task = "call" if question.kind == "call" else "line"
        verdicts = CALL_VERDICTS if task == "call" else LINE_VERDICTS
        try:
            data = self.claude.ask(self._system(ctx, task), self.prompt(question, ctx),
                                   verdict_schema(verdicts))
        except AIUnavailable:
            raise
        except AIError as exc:
            self.last_error = str(exc)
            return Answer("unknown", note=f"claude failed: {exc}")
        verdict = data.get("verdict")
        if verdict not in verdicts:
            return Answer("unknown", note=f"claude gave no usable verdict ({verdict!r})")
        confidence = _confidence(data.get("confidence"))
        reason = str(data.get("reason", "")).strip()
        return Answer(verdict, confidence=confidence, note=f"claude {confidence:.0%}: {reason}")


class HybridOracle(Oracle):
    """Claude answers when it is sure; otherwise the person decides, with Claude's view shown.

    threshold: Claude's answer is taken as is when its confidence is at
    least this and its verdict is not "unknown". Below it, the question goes
    to the person (human: a HumanOracle or FriendlyOracle), with Claude's
    verdict and reason in question.meta["ai"] so it can be shown as a hint.
    If Claude becomes unavailable mid-session, every question goes to the
    person.
    """

    name = "hybrid"

    def __init__(self, ai, human, threshold=0.8, show=None):
        self.ai = ai
        self.human = human
        self.threshold = threshold
        self.show = show          # show(question, ctx, answer): narrates an answer Claude gave
        self.ai_answers = 0
        self.human_answers = 0
        self.notice = None        # why Claude stopped being asked, if it did

    def judge(self, question, ctx=None):
        answer = None
        if self.notice is None:
            try:
                answer = self.ai.judge(question, ctx)
            except AIUnavailable as exc:
                self.notice = str(exc)
                if ctx is not None:
                    ctx.out(f"Claude is unavailable, so you answer from here on ({exc})")
        if (answer is not None and answer.verdict not in (None, "unknown")
                and answer.confidence >= self.threshold):
            self.ai_answers += 1
            if self.show is not None:
                self.show(question, ctx, answer)
            return answer
        if answer is not None:
            question.meta["ai"] = answer
        self.human_answers += 1
        reply = self.human.judge(question, ctx)
        if answer is not None and reply.verdict is not None and not reply.note:
            reply.note = f"you (Claude said {answer.verdict})"
        return reply
