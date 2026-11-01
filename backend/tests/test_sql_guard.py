import pytest

from app.services.sql_guard import SqlGuardError, guard_sql


def test_select_gets_a_limit():
    assert guard_sql("SELECT * FROM products", max_rows=500) == "SELECT * FROM products LIMIT 500"


def test_existing_limit_is_kept():
    assert guard_sql("SELECT id FROM products LIMIT 10") == "SELECT id FROM products LIMIT 10"


def test_large_limit_is_capped():
    assert guard_sql("SELECT id FROM products LIMIT 9000 OFFSET 2", max_rows=500) == (
        "SELECT id FROM products LIMIT 500 OFFSET 2"
    )


def test_with_query_is_allowed():
    sql = "WITH recent AS (SELECT id FROM orders) SELECT id FROM recent"
    assert guard_sql(sql, max_rows=100).endswith("LIMIT 100")


def test_string_can_mention_a_blocked_word():
    sql = "SELECT name FROM products WHERE name = 'drop table'"
    assert "LIMIT 500" in guard_sql(sql)


def test_comments_cannot_hide_a_second_statement():
    with pytest.raises(SqlGuardError):
        guard_sql("SELECT 1; /* hide */ DROP TABLE products")


def test_comment_only_select_is_allowed():
    assert guard_sql("SELECT 1 /* comment */", max_rows=20).upper().startswith("SELECT 1")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM products",
        "UPDATE products SET stock = 0",
        "DROP TABLE products",
        "INSERT INTO products (name) VALUES ('x')",
        "SELECT * FROM products; SELECT * FROM orders",
        "WITH doomed AS (DELETE FROM products RETURNING *) SELECT * FROM doomed",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT 1 FOR UPDATE",
        "",
    ],
)
def test_blocked_sql(sql):
    with pytest.raises(SqlGuardError):
        guard_sql(sql)
