
from safeagentl.safety import AnomalyDetector, CircuitBreaker, CircuitState, SafetyStack


def test_circuit_breaker_opens_after_threshold_failures():
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout=100)
    assert breaker.allow() is True
    breaker.record_failure()
    assert breaker.allow() is True
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    assert breaker.allow() is False


def test_circuit_breaker_half_opens_after_reset_timeout():
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=0.05)
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN
    import time

    time.sleep(0.1)
    assert breaker.state == CircuitState.HALF_OPEN
    assert breaker.allow() is True


def test_circuit_breaker_success_resets_failure_count():
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout=100)
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED


def test_anomaly_detector_needs_baseline_before_flagging():
    detector = AnomalyDetector(min_samples=5, z_threshold=3.0)
    for value in [10, 10, 10, 10]:
        assert detector.is_anomalous(value) is False  # still building baseline


def test_anomaly_detector_flags_outlier_after_baseline():
    detector = AnomalyDetector(min_samples=5, z_threshold=2.0)
    for value in [10, 10, 10, 10, 10]:
        detector.is_anomalous(value)
    assert detector.is_anomalous(1000) is True


def test_safety_stack_passes_when_all_layers_pass():
    stack = SafetyStack(layers=[lambda action: True, lambda action: True])
    result = stack.check({"price": 10})
    assert result.safe is True
    assert result.failed_layers == []


def test_safety_stack_denies_when_any_layer_fails():
    stack = SafetyStack(layers=[lambda action: True, lambda action: False])
    result = stack.check({"price": 10})
    assert result.safe is False
    assert len(result.failed_layers) == 1


def test_safety_stack_layer_exception_counts_as_failure_not_pass():
    def broken_layer(action):
        raise RuntimeError("boom")

    stack = SafetyStack(layers=[broken_layer])
    result = stack.check({"price": 10})
    assert result.safe is False
    assert "error=boom" in result.failed_layers[0]


def test_safety_stack_trips_breaker_after_repeated_failures():
    stack = SafetyStack(layers=[lambda action: False], breaker=CircuitBreaker(failure_threshold=2, reset_timeout=100))
    stack.check({})
    result = stack.check({})
    assert result.breaker_state == CircuitState.OPEN

    result_after_open = stack.check({})
    assert result_after_open.safe is False
    assert result_after_open.failed_layers == ["circuit_breaker_open"]


def test_anomaly_detector_as_layer_ignores_missing_field():
    detector = AnomalyDetector(min_samples=2)
    layer = detector.as_layer("price")
    assert layer({"quantity": 5}) is True
