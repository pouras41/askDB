from app.crypto import decrypt_secret, encrypt_secret
from app.limiter import enforce_rate_limit, reset_rate_limits
from app.security import hash_password, validate_password, verify_password
from app.services.gemini import normalize_plan, parse_model_json
from app.services.stats import summarize
from fastapi import HTTPException


def test_password_roundtrip():
    hashed = hash_password("harbor123")
    assert verify_password("harbor123", hashed)
    assert not verify_password("harbor124", hashed)


def test_password_rules():
    assert validate_password("short1") == "Password must be at least 8 characters."
    assert validate_password("longenough") == "Password must include a letter and a number."
    assert validate_password("harbor123") is None


def test_secret_roundtrip():
    token = encrypt_secret("demo-password")
    assert token != "demo-password"
    assert decrypt_secret(token) == "demo-password"


def test_rate_limit_trips():
    reset_rate_limits()
    enforce_rate_limit("test-key", 2, 60)
    enforce_rate_limit("test-key", 2, 60)
    try:
        enforce_rate_limit("test-key", 2, 60)
        raised = False
    except HTTPException as exc:
        raised = exc.status_code == 429
    assert raised
    reset_rate_limits()


def test_parse_fenced_json():
    plan = parse_model_json(
        """```json
        {"sql": "SELECT 1", "reasoning": "simple", "confidence": 8, "tables_used": ["orders"], "chart": "bar", "x_column": "name", "y_column": "revenue", "error": ""}
        ```"""
    )
    assert plan["sql"] == "SELECT 1"
    assert plan["confidence"] == 0.8
    assert plan["chart"] == "bar"


def test_unknown_chart_becomes_table():
    plan = normalize_plan({"sql": "SELECT 1", "chart": "sankey", "confidence": 2})
    assert plan["chart"] == "table"
    assert plan["confidence"] == 0.2


def test_summary_splits_numbers_and_text():
    stats = summarize(
        ["city", "total"],
        [{"city": "Austin", "total": 10}, {"city": "Austin", "total": 30}, {"city": None, "total": None}],
    )
    by_name = {item["column"]: item for item in stats}
    assert by_name["city"]["kind"] == "text"
    assert by_name["city"]["distinct"] == 1
    assert by_name["city"]["top"] == "Austin"
    assert by_name["city"]["nulls"] == 1
    assert by_name["total"]["kind"] == "number"
    assert by_name["total"]["mean"] == 20
    assert by_name["total"]["min"] == "10"
    assert by_name["total"]["max"] == "30"
