from app.services.gemini import (
    condense_rows,
    build_summary_prompt,
    normalize_summary,
    parse_summary_json,
)


def test_condense_rows_small():
    rows = [{"id": i} for i in range(5)]
    condensed = condense_rows(rows, max_rows=20)
    assert len(condensed) == 5
    assert condensed == rows


def test_condense_rows_large():
    rows = [{"id": i} for i in range(50)]
    condensed = condense_rows(rows, max_rows=20)
    assert len(condensed) == 20
    # First 10
    assert [r["id"] for r in condensed[:10]] == list(range(10))
    # Last 10
    assert [r["id"] for r in condensed[10:]] == list(range(40, 50))


def test_normalize_summary_defaults():
    empty_data = {}
    normalized = normalize_summary(empty_data)
    assert "headline" in normalized
    assert isinstance(normalized["key_findings"], list)
    assert len(normalized["key_findings"]) >= 1
    assert isinstance(normalized["anomalies"], list)
    assert isinstance(normalized["follow_up_questions"], list)


def test_normalize_summary_populates_values():
    data = {
        "headline": "Top revenue came from Espresso machines.",
        "key_findings": ["Point 1", "Point 2"],
        "anomalies": ["None detected"],
        "follow_up_questions": ["What about last quarter?"],
    }
    normalized = normalize_summary(data)
    assert normalized["headline"] == "Top revenue came from Espresso machines."
    assert normalized["key_findings"] == ["Point 1", "Point 2"]
    assert normalized["anomalies"] == ["None detected"]
    assert normalized["follow_up_questions"] == ["What about last quarter?"]


def test_parse_summary_json_fenced():
    raw = """```json
    {
      "headline": "Austin is the fastest growing market.",
      "key_findings": ["Austin generated $12,000", "Second is Portland with $8,000"],
      "anomalies": [],
      "follow_up_questions": ["Show monthly growth rate for Austin"]
    }
    ```"""
    parsed = parse_summary_json(raw)
    assert parsed["headline"] == "Austin is the fastest growing market."
    assert len(parsed["key_findings"]) == 2
    assert parsed["follow_up_questions"] == ["Show monthly growth rate for Austin"]


def test_build_summary_prompt():
    prompt = build_summary_prompt(
        question="Show total revenue by store",
        sql="SELECT store, sum(revenue) FROM orders GROUP BY store",
        columns=["store", "revenue"],
        sample_rows=[{"store": "Austin", "revenue": 1000}],
        stats=[{"column": "revenue", "kind": "number", "count": 1}],
        total_row_count=1,
    )
    assert "Show total revenue by store" in prompt
    assert "SELECT store" in prompt
    assert "Austin" in prompt
