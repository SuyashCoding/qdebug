"""Optional Claude integration: an automatic or hybrid oracle, triage and explanations.

Nothing here is needed to use qdebug by hand. The Anthropic SDK is only
imported when a request is made (install it with `pip install 'qdebug[ai]'`).
The prompt lives in agent.md; projects can override it with
.qdebug/agent.md (`qdebug init-agent`).
"""

from qdebug.ai.assistant import Assistant, Explanation, Triage
from qdebug.ai.client import DEFAULT_MODEL, EFFORTS, AIError, AIUnavailable, Claude, sdk_available
from qdebug.ai.oracle import ClaudeOracle, HybridOracle
from qdebug.ai.prompts import Agent, write_project_agent

__all__ = ["DEFAULT_MODEL", "EFFORTS", "AIError", "AIUnavailable", "Agent", "Assistant", "Claude",
           "ClaudeOracle", "Explanation", "HybridOracle", "Triage", "sdk_available",
           "write_project_agent"]
