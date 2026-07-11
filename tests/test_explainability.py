import json
import time

import pytest

from safeagentl.explainability import DecisionLogger, DecisionTrace, TraceIncompleteError


def make_trace(**overrides):
    defaults = dict(
        agent_id="pricing-agent-1",
        input_state={"sku": "ABC123"},
        applied_constraints=["price >= 19.99"],
        output={"price": 24.99},
        reasoning=["applied MAP floor"],
    )
    defaults.update(overrides)
    return DecisionTrace(**defaults)


def test_complete_trace_has_score_one():
    trace = make_trace()
    assert trace.completeness_score() == 1.0


def test_logger_accepts_complete_trace_and_reconstructs_it():
    logger = DecisionLogger()
    trace = logger.log(make_trace())
    reconstructed = logger.reconstruct(trace.decision_id)
    assert reconstructed is trace
    assert reconstructed.output == {"price": 24.99}


def test_logger_rejects_incomplete_trace_by_default():
    logger = DecisionLogger()
    incomplete = DecisionTrace(agent_id="", input_state={}, applied_constraints=[], output={})
    with pytest.raises(TraceIncompleteError):
        logger.log(incomplete)


def test_reconstruct_unknown_id_raises_key_error():
    logger = DecisionLogger()
    with pytest.raises(KeyError):
        logger.reconstruct("does-not-exist")


def test_retention_evicts_old_traces():
    logger = DecisionLogger(retention_seconds=0.05)
    trace = logger.log(make_trace())
    assert len(logger) == 1
    time.sleep(0.1)
    logger.log(make_trace())  # triggers eviction sweep
    assert trace.decision_id not in {t.decision_id for t in logger.all_traces()}


def test_sink_path_writes_append_only_jsonl(tmp_path):
    sink = tmp_path / "audit.jsonl"
    logger = DecisionLogger(sink_path=sink)
    logger.log(make_trace())
    logger.log(make_trace())
    lines = sink.read_text().strip().splitlines()
    assert len(lines) == 2
    record = json.loads(lines[0])
    assert record["agent_id"] == "pricing-agent-1"


def test_min_completeness_can_be_relaxed():
    logger = DecisionLogger(min_completeness=0.5)
    partial = DecisionTrace(agent_id="a", input_state={}, applied_constraints=[], output={"x": 1})
    logger.log(partial)  # does not raise
    assert len(logger) == 1
