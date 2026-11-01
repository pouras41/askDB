import math
from decimal import Decimal
from statistics import mean


def _is_number(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float, Decimal)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return False
        return True
    return False


def _as_float(value: object) -> float:
    return float(value)  # type: ignore[arg-type]


def summarize(columns: list[str], rows: list[dict]) -> list[dict]:
    stats = []
    for column in columns:
        values = [row.get(column) for row in rows]
        present = [value for value in values if value is not None]
        nulls = len(values) - len(present)
        numeric = present and all(_is_number(value) for value in present)
        if numeric:
            numbers = [_as_float(value) for value in present]
            stats.append(
                {
                    "column": column,
                    "kind": "number",
                    "count": len(present),
                    "nulls": nulls,
                    "distinct": len({round(number, 6) for number in numbers}),
                    "min": _trim(min(numbers)),
                    "max": _trim(max(numbers)),
                    "mean": round(mean(numbers), 4) if numbers else None,
                    "top": None,
                }
            )
            continue
        counts: dict[str, int] = {}
        for value in present:
            label = str(value)
            counts[label] = counts.get(label, 0) + 1
        top = max(counts, key=counts.get) if counts else None
        stats.append(
            {
                "column": column,
                "kind": "text",
                "count": len(present),
                "nulls": nulls,
                "distinct": len(counts),
                "min": None,
                "max": None,
                "mean": None,
                "top": top,
            }
        )
    return stats


def _trim(number: float) -> str:
    if float(number).is_integer():
        return str(int(number))
    return f"{number:.4f}".rstrip("0").rstrip(".")
