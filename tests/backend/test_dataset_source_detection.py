import pytest
from services.dataset_service import _detect_source


def test_detect_http_csv():
    st, fmt, src = _detect_source("https://example.com/data.csv")
    assert st == "http"
    assert fmt == "csv"
    assert src == "https://example.com/data.csv"


def test_detect_http_parquet():
    st, fmt, src = _detect_source("http://data.org/file.parquet")
    assert st == "http"
    assert fmt == "parquet"


def test_detect_file_json():
    st, fmt, src = _detect_source("file:///home/user/data.json")
    assert st == "file"
    assert fmt == "json"
    assert src == "/home/user/data.json"


def test_detect_file_jsonl():
    st, fmt, src = _detect_source("file:///home/user/data.jsonl")
    assert st == "file"
    assert fmt == "json"


def test_detect_huggingface():
    st, fmt, src = _detect_source("stanfordnlp/imdb")
    assert st == "huggingface"
    assert fmt is None
    assert src == "stanfordnlp/imdb"


def test_detect_huggingface_plain():
    st, fmt, src = _detect_source("imdb")
    assert st == "huggingface"
    assert fmt is None


def test_detect_unsupported_format():
    with pytest.raises(ValueError, match="Unsupported format"):
        _detect_source("https://example.com/data.xlsx")


def test_detect_url_with_query_params():
    st, fmt, src = _detect_source("https://example.com/data.csv?download=1")
    assert st == "http"
    assert fmt == "csv"
