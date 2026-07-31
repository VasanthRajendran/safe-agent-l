import pytest

from safeagentl.constraints import (
    Constraint,
    ConstraintEngine,
    EnforcementMode,
    InvalidConstraintError,
)


def test_reject_mode_denies_out_of_bounds_action():
    engine = ConstraintEngine([Constraint(field="price", op="gte", bound=19.99, reason="MAP policy")])
    result = engine.enforce({"price": 9.99})
    assert result.allowed is False
    assert "price" in result.violations[0]


def test_action_within_bounds_passes_unmodified():
    engine = ConstraintEngine([Constraint(field="price", op="gte", bound=19.99)])
    result = engine.enforce({"price": 25.00})
    assert result.allowed is True
    assert result.action == {"price": 25.00}
    assert result.violations == []


def test_clip_mode_coerces_value_into_range():
    engine = ConstraintEngine([Constraint(field="price", op="lte", bound=100.0, mode=EnforcementMode.CLIP)])
    result = engine.enforce({"price": 150.0})
    assert result.allowed is True
    assert result.action["price"] == 100.0
    assert result.violations  # the original value was recorded as a violation


def test_unregistered_fields_pass_through_untouched():
    engine = ConstraintEngine([Constraint(field="price", op="gte", bound=1.0)])
    result = engine.enforce({"quantity": 5})
    assert result.allowed is True
    assert result.action == {"quantity": 5}


def test_required_constraint_rejects_action_missing_the_field():
    engine = ConstraintEngine(
        [
            Constraint(
                field="tool",
                op="in",
                bound={"lookup_customer", "create_ticket"},
                required=True,
            )
        ]
    )
    result = engine.enforce({"customer_id": "CUST-001"})
    assert result.allowed is False
    assert result.action == {"customer_id": "CUST-001"}
    assert "required field 'tool' is missing" in result.violations[0]
    assert "rejected: 'tool' violates" in result.applied_constraints[0]


def test_non_required_constraint_ignores_missing_field():
    engine = ConstraintEngine([Constraint(field="tool", op="in", bound={"lookup_customer", "create_ticket"})])
    result = engine.enforce({"customer_id": "CUST-001"})
    assert result.allowed is True
    assert result.action == {"customer_id": "CUST-001"}
    assert result.violations == []
    assert result.applied_constraints == []


def test_required_field_violation_is_auditable_in_enforcement_history():
    engine = ConstraintEngine([Constraint(field="reason", op="in", bound={"billing", "support"}, required=True)])
    result = engine.enforce({"tool": "create_ticket"})
    assert result.allowed is False
    assert len(result.violations) == 1
    assert len(result.applied_constraints) == 1
    assert "required field 'reason' is missing" in result.violations[0]
    assert "required field 'reason' is missing" in result.applied_constraints[0]


def test_multiple_constraints_on_same_field_all_apply():
    engine = ConstraintEngine(
        [
            Constraint(field="price", op="gte", bound=10.0),
            Constraint(field="price", op="lte", bound=100.0),
        ]
    )
    assert engine.enforce({"price": 5.0}).allowed is False
    assert engine.enforce({"price": 500.0}).allowed is False
    assert engine.enforce({"price": 50.0}).allowed is True


def test_invalid_operator_rejected_at_construction():
    with pytest.raises(InvalidConstraintError):
        Constraint(field="price", op="between", bound=(1, 2))


def test_clip_mode_incompatible_with_non_clippable_operator():
    with pytest.raises(InvalidConstraintError):
        Constraint(field="status", op="in", bound=["ok"], mode=EnforcementMode.CLIP)


def test_verify_configuration_flags_contradictory_bounds():
    engine = ConstraintEngine(
        [
            Constraint(field="price", op="gte", bound=100.0),
            Constraint(field="price", op="lte", bound=10.0),
        ]
    )
    problems = engine.verify_configuration()
    assert len(problems) == 1
    assert "price" in problems[0]


def test_verify_configuration_passes_for_consistent_bounds():
    engine = ConstraintEngine(
        [
            Constraint(field="price", op="gte", bound=10.0),
            Constraint(field="price", op="lte", bound=100.0),
        ]
    )
    assert engine.verify_configuration() == []


def test_history_is_auditable():
    engine = ConstraintEngine([Constraint(field="price", op="gte", bound=10.0)])
    engine.enforce({"price": 5.0})
    engine.enforce({"price": 50.0})
    assert len(engine.history) == 2
    assert engine.history[0].allowed is False
    assert engine.history[1].allowed is True


def test_len_reports_number_of_constrained_fields():
    engine = ConstraintEngine(
        [
            Constraint(field="price", op="gte", bound=10.0),
            Constraint(field="price", op="lte", bound=100.0),
            Constraint(field="quantity", op="gte", bound=0),
        ]
    )
    assert len(engine) == 2
