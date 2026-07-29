from trippilot.infrastructure.observability import redact_sensitive_values


def test_redacts_secret_bearing_log_fields() -> None:
    event = {
        "event": "request",
        "authorization": "Bearer secret",
        "plan_token": "tp_plan_secret",
        "city": "成都",
    }

    result = redact_sensitive_values(None, "info", event)

    assert result["authorization"] == "[REDACTED]"
    assert result["plan_token"] == "[REDACTED]"
    assert result["city"] == "成都"
