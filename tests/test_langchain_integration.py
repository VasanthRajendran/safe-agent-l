import asyncio
from typing import Any, Sequence

import pytest

pytest.importorskip("langchain")

from langchain.agents import create_agent
from langchain.messages import AIMessage, ToolCall, ToolMessage
from langchain.tools import tool
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

from safeagentl import Constraint, ConstraintEngine, EnforcementMode, SafeAgent
from safeagentl.integrations.langchain import SafeAgentMiddleware


def build_gate(*, mode: EnforcementMode = EnforcementMode.REJECT) -> SafeAgent:
    return SafeAgent(
        agent_id="langchain-refund-agent",
        constraint_engine=ConstraintEngine(
            [
                Constraint(field="tool", op="eq", bound="issue_refund", required=True),
                Constraint(field="amount", op="lte", bound=100.0, mode=mode, required=True),
            ]
        ),
    )


def make_request(amount: float, *, state=None) -> ToolCallRequest:
    return ToolCallRequest(
        tool_call=ToolCall(name="issue_refund", args={"amount": amount}, id="call-1", type="tool_call"),
        tool=None,
        state=state if state is not None else {"messages": [], "customer_id": "customer-1"},
        runtime=None,  # type: ignore[arg-type]
    )


def test_allowed_call_reaches_handler_and_is_logged():
    gate = build_gate()
    middleware = SafeAgentMiddleware(gate)
    observed = []

    def handler(request):
        observed.append(request.tool_call)
        return ToolMessage(content="refunded", tool_call_id=request.tool_call["id"])

    result = middleware.wrap_tool_call(make_request(50.0), handler)

    assert result.content == "refunded"
    assert observed[0]["args"] == {"amount": 50.0}
    assert gate.logger.all_traces()[0].input_state["customer_id"] == "customer-1"
    assert gate.logger.all_traces()[0].output == {"amount": 50.0, "tool": "issue_refund"}


def test_denied_call_never_reaches_handler():
    gate = build_gate()
    middleware = SafeAgentMiddleware(gate)
    called = False

    def handler(request):
        nonlocal called
        called = True
        return ToolMessage(content="refunded", tool_call_id=request.tool_call["id"])

    result = middleware.wrap_tool_call(make_request(500.0), handler)

    assert called is False
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "constraint_violation" in str(result.content)
    assert "decision_id=" in str(result.content)
    assert gate.logger.all_traces()[0].reasoning[-1] == "allowed=False"


def test_clipped_arguments_are_the_only_values_sent_to_handler():
    middleware = SafeAgentMiddleware(build_gate(mode=EnforcementMode.CLIP))
    observed = []

    def handler(request):
        observed.append(request.tool_call["args"])
        return ToolMessage(content="refunded", tool_call_id=request.tool_call["id"])

    middleware.wrap_tool_call(make_request(500.0), handler)

    assert observed == [{"amount": 100.0}]


def test_async_denial_does_not_await_handler():
    middleware = SafeAgentMiddleware(build_gate())
    called = False

    async def handler(request):
        nonlocal called
        called = True
        return ToolMessage(content="refunded", tool_call_id=request.tool_call["id"])

    result = asyncio.run(middleware.awrap_tool_call(make_request(500.0), handler))

    assert called is False
    assert result.status == "error"


def test_async_allowed_call_reaches_handler():
    middleware = SafeAgentMiddleware(build_gate())
    observed = []

    async def handler(request):
        observed.append(request.tool_call["args"])
        return ToolMessage(content="refunded", tool_call_id=request.tool_call["id"])

    result = asyncio.run(middleware.awrap_tool_call(make_request(50.0), handler))

    assert result.content == "refunded"
    assert observed == [{"amount": 50.0}]


def test_list_state_and_custom_denial_text_are_supported():
    gate = build_gate()
    middleware = SafeAgentMiddleware(gate, denial_formatter=lambda decision: f"blocked:{decision.reason}")

    result = middleware.wrap_tool_call(
        make_request(500.0, state=["message-1"]),
        lambda request: ToolMessage(content="unexpected", tool_call_id=request.tool_call["id"]),
    )

    assert result.content == "blocked:constraint_violation"
    assert gate.logger.all_traces()[0].input_state == {"messages": ["message-1"]}


def test_reserved_tool_field_collision_fails_closed():
    middleware = SafeAgentMiddleware(build_gate())
    request = make_request(50.0)
    request = request.override(
        tool_call=ToolCall(
            name="issue_refund",
            args={"amount": 50.0, "tool": "untrusted-value"},
            id="call-1",
            type="tool_call",
        )
    )
    called = False

    def handler(request):
        nonlocal called
        called = True
        return ToolMessage(content="unexpected", tool_call_id=request.tool_call["id"])

    result = middleware.wrap_tool_call(request, handler)

    assert called is False
    assert result.status == "error"
    assert "reserved tool-name field" in str(result.content)


def test_empty_tool_name_field_is_rejected():
    with pytest.raises(ValueError, match="must not be empty"):
        SafeAgentMiddleware(build_gate(), tool_name_field="")


class ToolCallingFakeModel(FakeMessagesListChatModel):
    def bind_tools(self, tools: Sequence[Any], **kwargs: Any):
        return self


def test_middleware_blocks_tool_in_a_real_langchain_agent_loop():
    executed = []

    @tool
    def issue_refund(amount: float) -> str:
        """Issue a customer refund."""
        executed.append(amount)
        return "refunded"

    model = ToolCallingFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "issue_refund", "args": {"amount": 500.0}, "id": "call-1"}],
            ),
            AIMessage(content="The refund was blocked by policy."),
        ]
    )
    agent = create_agent(model, tools=[issue_refund], middleware=[SafeAgentMiddleware(build_gate())])

    result = agent.invoke({"messages": [{"role": "user", "content": "Refund $500"}]})

    assert executed == []
    tool_messages = [message for message in result["messages"] if isinstance(message, ToolMessage)]
    assert len(tool_messages) == 1
    assert tool_messages[0].status == "error"
