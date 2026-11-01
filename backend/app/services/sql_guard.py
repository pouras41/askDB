import re

import sqlparse

class SqlGuardError(ValueError):
    pass


_FORBIDDEN = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|"
    r"execute|exec|call|attach|detach|pragma|vacuum|reindex|merge|into|"
    r"pg_read_file|pg_read_binary_file|pg_ls_dir|pg_stat_file|"
    r"lo_import|lo_export|dblink|pg_sleep|pg_terminate_backend|pg_cancel_backend"
    r")\b",
    re.IGNORECASE,
)
_COMMENT_ON = re.compile(r"\bcomment\s+on\b", re.IGNORECASE)
_FOR_UPDATE = re.compile(r"\bfor\s+(update|share|no\s+key\s+update|key\s+share)\b", re.IGNORECASE)
_STRING = re.compile(r"('([^']|'')*')|(\"([^\"]|\"\")*\")")
_TRAILING_LIMIT = re.compile(r"\blimit\s+(\d+)(\s+offset\s+\d+)?\s*$", re.IGNORECASE)


def _mask_strings(sql: str) -> str:
    return _STRING.sub("''", sql)


def _statements(sql: str) -> list[str]:
    found = []
    for statement in sqlparse.parse(sql):
        text = str(statement).strip().rstrip(";").strip()
        if text:
            found.append(text)
    return found


def guard_sql(sql: str, max_rows: int = 500) -> str:
    if not sql or not sql.strip():
        raise SqlGuardError("SQL is empty.")
    if "\x00" in sql:
        raise SqlGuardError("SQL contains a null byte.")

    cleaned = sqlparse.format(sql, strip_comments=True).strip()
    statements = _statements(cleaned)
    if len(statements) != 1:
        raise SqlGuardError("Only a single read-only statement is allowed.")

    statement = statements[0].strip().rstrip(";").strip()
    masked = _mask_strings(statement)
    if ";" in masked:
        raise SqlGuardError("Only a single read-only statement is allowed.")

    first = masked.lstrip().split(None, 1)[0].lower() if masked.strip() else ""
    if first not in {"select", "with"}:
        raise SqlGuardError("Only SELECT queries are allowed.")
    if _FORBIDDEN.search(masked) or _COMMENT_ON.search(masked) or _FOR_UPDATE.search(masked):
        raise SqlGuardError("That query uses a statement that is not allowed. AskDB only runs read-only SELECT queries.")

    match = _TRAILING_LIMIT.search(statement)
    if not match:
        return f"{statement} LIMIT {max_rows}"
    if int(match.group(1)) > max_rows:
        return statement[: match.start(1)] + str(max_rows) + statement[match.end(1) :]
    return statement
