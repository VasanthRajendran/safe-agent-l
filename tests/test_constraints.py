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
