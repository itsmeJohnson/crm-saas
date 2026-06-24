import pytest
from app.services.import_.csv_parser import parse_csv

def test_parse_csv_success():
    csv_bytes = b"first_name,last_name,email,title\nAlice,Smith,alice@test.com,VP Sales\nBob,Jones,bob@test.com,Dev"
    headers, rows = parse_csv(csv_bytes)
    assert headers == ["first_name", "last_name", "email", "title"]
    assert len(rows) == 2
    assert rows[0]["first_name"] == "Alice"
    assert rows[1]["email"] == "bob@test.com"

def test_parse_csv_semicolon_delimiter():
    csv_bytes = b"first_name;last_name;email;title\nAlice;Smith;alice@test.com;VP Sales"
    headers, rows = parse_csv(csv_bytes)
    assert headers == ["first_name", "last_name", "email", "title"]
    assert len(rows) == 1
    assert rows[0]["first_name"] == "Alice"

def test_parse_csv_exceeds_row_limit():
    headers = "first_name,last_name,email,title\n"
    data = "Alice,Smith,alice@test.com,VP Sales\n" * 1001
    content = (headers + data).encode("utf-8")
    
    with pytest.raises(ValueError) as exc:
        parse_csv(content)
    assert "maximum 1000 allowed" in str(exc.value)

def test_parse_csv_exceeds_size_limit():
    content = b"a" * (5 * 1024 * 1024 + 1)
    
    with pytest.raises(ValueError) as exc:
        parse_csv(content)
    assert "exceeds 5MB limit" in str(exc.value)

def test_parse_csv_missing_headers():
    with pytest.raises(ValueError) as exc:
        parse_csv(b"\n\n\n")
    assert "missing header row" in str(exc.value)
