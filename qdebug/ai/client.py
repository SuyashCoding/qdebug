"""A thin wrapper over the Anthropic SDK: one structured-output request at a time.

The SDK is imported lazily, the first time a request is made, so the rest
of qdebug works without it (`pip install qdebug` vs `pip install
'qdebug[ai]'`). Credentials are resolved by the SDK itself:
ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or a profile from `ant auth login`.
"""

import json
import os
from dataclasses import dataclass

DEFAULT_MODEL = "claude-haiku-5-5"
EFFORTS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_EFFORT = "medium"
INSTALL_HINT = "pip install 'qdebug[ai]'"
AUTH_HINT = "set ANTHROPIC_API_KEY, or run `ant auth login`"


class AIError(RuntimeError):
    """One request failed (refusal, bad output, a network or server error). The session can go on."""


class AIUnavailable(AIError):
    """Claude cannot be used at all: no SDK, no credentials, or an unknown model."""


def load_sdk():
    try:
        import anthropic
    except ImportError:
        raise AIUnavailable(f"the Claude features need the Anthropic SDK: {INSTALL_HINT}") from None
    return anthropic


def sdk_available():
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass
class Usage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    failures: int = 0

    def add(self, usage):
        self.requests += 1
        if usage is None:
            return
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0
        self.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0

    def as_dict(self):
        return dict(vars(self))


class Claude:
    """Sends prompts to one model and returns the parsed JSON of its answer.

    client: an object with the SDK's messages.create signature; by default an
    anthropic.Anthropic() created on first use (tests pass a fake).
    """

    def __init__(self, model=None, effort=None, client=None, max_tokens=8000, timeout=180.0,
                 max_retries=3):
        self.model = model or os.environ.get("QDEBUG_AI_MODEL") or DEFAULT_MODEL
        self.effort = effort or os.environ.get("QDEBUG_AI_EFFORT") or DEFAULT_EFFORT
        if self.effort not in EFFORTS:
            raise ValueError(f"unknown effort {self.effort!r}; choose from {', '.join(EFFORTS)}")
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = client
        self._sdk = None
        self.usage = Usage()
        self.disabled = None  # the AIUnavailable that switched Claude off, if any

    @property
    def client(self):
        if self._client is None:
            self._sdk = load_sdk()
            self._client = self._sdk.Anthropic(timeout=self.timeout, max_retries=self.max_retries)
        return self._client

    def ask(self, system, prompt, schema, effort=None, max_tokens=None):
        """Send one request and return the JSON object Claude answered with.

        system: list of text blocks; the last one is marked for prompt
        caching, so keep them identical across a session's requests.
        schema: a JSON schema (structured outputs) the answer must follow.
        Raises AIUnavailable (stop using Claude) or AIError (this request only).
        """
        if self.disabled is not None:
            raise self.disabled
        blocks = [{"type": "text", "text": text} for text in system if text]
        if blocks:
            blocks[-1]["cache_control"] = {"type": "ephemeral"}
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                system=blocks,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": effort or self.effort,
                               "format": {"type": "json_schema", "schema": schema}},
            )
        except AIError:
            raise
        except Exception as exc:  # noqa: BLE001 - translated below
            error = self._translate(exc)
            if isinstance(error, AIUnavailable):
                self.disabled = error
            else:
                self.usage.failures += 1
            raise error from exc
        self.usage.add(getattr(response, "usage", None))
        stop = getattr(response, "stop_reason", None)
        if stop == "refusal":
            self.usage.failures += 1
            raise AIError("Claude declined to answer this question")
        if stop == "max_tokens":
            self.usage.failures += 1
            raise AIError("Claude's answer was cut off (max_tokens); try a lower --ai-effort")
        text = "".join(getattr(block, "text", "") for block in getattr(response, "content", [])
                       if getattr(block, "type", None) == "text")
        try:
            data = json.loads(text)
        except ValueError:
            self.usage.failures += 1
            raise AIError(f"Claude's answer was not valid JSON: {text[:200]!r}") from None
        if not isinstance(data, dict):
            self.usage.failures += 1
            raise AIError("Claude's answer was not a JSON object")
        return data

    def _translate(self, exc):
        """An SDK exception as AIUnavailable (fatal) or AIError (this request only)."""
        sdk = self._sdk
        message = str(exc)
        if sdk is not None:
            if isinstance(exc, (sdk.AuthenticationError, sdk.PermissionDeniedError)):
                return AIUnavailable(f"Claude rejected the credentials ({message}); {AUTH_HINT}")
            if isinstance(exc, sdk.NotFoundError):
                return AIUnavailable(f"model {self.model!r} was not found; pick another with --ai-model")
            if isinstance(exc, sdk.BadRequestError):
                return AIError(f"Claude rejected the request: {message}")
            if isinstance(exc, sdk.RateLimitError):
                return AIError("rate limited by the Claude API (after retries)")
            if isinstance(exc, sdk.APIConnectionError):
                return AIError(f"could not reach the Claude API: {message}")
            if isinstance(exc, sdk.APIStatusError):
                return AIError(f"the Claude API returned an error ({exc.status_code}): {message}")
        if "authentication" in message.lower() or "api_key" in message.lower():
            return AIUnavailable(f"no Claude credentials found; {AUTH_HINT}")
        return AIError(f"{type(exc).__name__}: {message}")
