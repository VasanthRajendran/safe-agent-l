"""LangChain tool-call enforcement through agent middleware.

Install the optional dependency with ``pip install safe-agent-l[langchain]``
and pass :class:`SafeAgentMiddleware` to LangChain's ``create_agent``. Every
tool call is converted to a flat action, governed by :class:`SafeAgent`, and
only then forwarded to the real tool handler.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from threading import Lock
from typing import Any, Dict, Optional, Tuple, cast

try:
    from langchain.agents.middleware import AgentMiddleware
    from langchain.messages import ToolCall, ToolMessage
    from langchain.tools.tool_node import ToolCallRequest
    from langgraph.types import Command
except ModuleNotFoundError as exc:  # pragma: no cover - exercised without the optional extra
    raise ImportError(
        "The LangChain adapter requires the optional dependency. "
        "On Python 3.10 or later, install it with: pip install 'safe-agent-l[langchain]'"
    ) from exc

from ..agent import Decision, SafeAgent

StateMapper = Callable[[ToolCallRequest], Dict[str, Any]]
DenialFormatter = Callable[[Decision], str]


def _default_state_mapper(request: ToolCallRequest) -> Dict[str, Any]:
    """Take a shallow, loggable snapshot of common LangChain state shapes."""
    state = request.state
    if isinstance(state, Mapping):
        return dict(state)
    if isinstance(state, list):
        return {"messages": list(state)}

    model_dump = getattr(state, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dict(dumped)

    return {"state": state}


def _default_denial_formatter(decision: Decision) -> str:
    reason = decision.reason or "policy_denied"
    if decision.trace is None:
        return f"Tool call blocked by Safe Agent policy ({reason})."
    return f"Tool call blocked by Safe Agent policy ({reason}; decision_id={decision.trace.decision_id})."


class SafeAgentMiddleware(AgentMiddleware):
    """Apply a :class:`SafeAgent` gate immediately before LangChain tool execution.

    LangChain tool calls are represented as ``{"tool": name, **arguments}``
    by default. Constraints may reject a call or clip argument values. Rejected
    calls return an error ``ToolMessage`` without invoking the tool handler.

    Args:
        gate: Configured SafeAgent used to govern each tool call.
        state_mapper: Optional function converting a ``ToolCallRequest`` into
            the input-state dictionary recorded in the decision trace.
        denial_formatter: Optional function producing the model-visible text
            for a denied decision.
        tool_name_field: Reserved action field holding the LangChain tool name.
            Tool argument schemas must not use the same field name.
    """

    def __init__(
        self,
        gate: SafeAgent,
        *,
        state_mapper: Optional[StateMapper] = None,
        denial_formatter: Optional[DenialFormatter] = None,
        tool_name_field: str = "tool",
    ) -> None:
        super().__init__()
        if not tool_name_field:
            raise ValueError("tool_name_field must not be empty")
        self.gate = gate
        self.state_mapper = state_mapper or _default_state_mapper
        self.denial_formatter = denial_formatter or _default_denial_formatter
        self.tool_name_field = tool_name_field
        # LangChain may dispatch independent tool calls in parallel. The core
        # gate keeps in-memory histories, so serialize the decision step while
        # still allowing approved tool handlers to run concurrently.
        self._decision_lock = Lock()

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command[Any]],
    ) -> ToolMessage | Command[Any]:
        """Govern a synchronous LangChain tool call before execution."""
        governed_request, denial = self._govern(request)
        if denial is not None:
            return denial
        assert governed_request is not None
        return handler(governed_request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        """Govern an asynchronous LangChain tool call before execution."""
        governed_request, denial = self._govern(request)
        if denial is not None:
            return denial
        assert governed_request is not None
        return await handler(governed_request)

    def _govern(self, request: ToolCallRequest) -> Tuple[Optional[ToolCallRequest], Optional[ToolMessage]]:
        tool_call = request.tool_call
        tool_call_id = str(tool_call.get("id", "unknown"))
        tool_name = tool_call.get("name")
        arguments = tool_call.get("args", {})

        if not isinstance(tool_name, str) or not tool_name:
            return None, self._adapter_denial(request, "tool call has no valid name")
        if not isinstance(arguments, Mapping):
            return None, self._adapter_denial(request, "tool arguments must be a mapping")
        if self.tool_name_field in arguments:
            return None, self._adapter_denial(
                request,
                f"tool argument '{self.tool_name_field}' conflicts with the reserved tool-name field",
            )

        action = dict(arguments)
        action[self.tool_name_field] = tool_name
        with self._decision_lock:
            decision = self.gate.decide(self.state_mapper(request), propose_fn=lambda _: action)
        if not decision.allowed:
            return None, ToolMessage(
                content=self.denial_formatter(decision),
                tool_call_id=tool_call_id,
                name=tool_name,
                status="error",
            )

        governed_action = dict(decision.action)
        governed_tool_name = governed_action.pop(self.tool_name_field, None)
        if governed_tool_name != tool_name:
            return None, self._adapter_denial(request, "policy attempted to change the registered tool name")

        governed_tool_call = dict(tool_call)
        governed_tool_call["args"] = governed_action
        return request.override(tool_call=cast(ToolCall, governed_tool_call)), None

    @staticmethod
    def _adapter_denial(request: ToolCallRequest, reason: str) -> ToolMessage:
        """Fail closed on malformed calls or unsafe adapter transformations."""
        return ToolMessage(
            content=f"Tool call blocked by Safe Agent adapter: {reason}.",
            tool_call_id=str(request.tool_call.get("id", "unknown")),
            name=request.tool_call.get("name"),
            status="error",
        )


__all__ = ["SafeAgentMiddleware"]
