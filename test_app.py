"""Tests for currency-api. Run: pytest test_app.py -v

Mocks the Frankfurter HTTP call so tests don't depend on the live API.
"""
from unittest.mock import MagicMock, patch

import pytest

from app import RATE_CACHE, app, get_live_rates


@pytest.fixture(autouse=True)
def _clear_cache():
    """Each test starts with an empty rate cache."""
    RATE_CACHE.clear()
    yield
    RATE_CACHE.clear()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Static endpoints ────────────────────────────────────────────────


def test_root_endpoint_lists_endpoints(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_json()
    assert body["service"] == "currency-api"
    assert "/health" in body["endpoints"]
    assert any("/rates" in e for e in body["endpoints"])


def test_health_endpoint_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "service": "currency-api"}


# ── /rates endpoint with mocked Frankfurter ─────────────────────────


def _frankfurter_response(base: str, rates: dict) -> MagicMock:
    """Build a mock requests.Response shaped like a real Frankfurter reply."""
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {
        "amount": 1.0,
        "base": base,
        "date": "2026-06-08",
        "rates": rates,
    }
    return mock


@patch("app.requests.get")
def test_rates_usd_returns_expected_currencies(mock_get, client):
    mock_get.return_value = _frankfurter_response(
        "USD", {"EUR": 0.92, "GBP": 0.78, "JPY": 155.0}
    )
    response = client.get("/rates?base=USD")
    assert response.status_code == 200
    body = response.get_json()
    assert body["base"] == "USD"
    assert body["source"] == "frankfurter.dev"
    assert body["rates"]["EUR"] == 0.92
    assert body["rates"]["GBP"] == 0.78
    assert body["rates"]["JPY"] == 155.0


@patch("app.requests.get")
def test_rates_base_currency_filtered_from_response(mock_get, client):
    """If Frankfurter ever returns the base in the rates dict, filter it
    out so /rates?base=USD doesn't include USD: 1.0 in the response."""
    mock_get.return_value = _frankfurter_response(
        "USD", {"EUR": 0.92, "USD": 1.0, "GBP": 0.78}
    )
    response = client.get("/rates?base=USD")
    body = response.get_json()
    assert "USD" not in body["rates"]
    assert "EUR" in body["rates"]


@patch("app.requests.get")
def test_rates_case_insensitive_base(mock_get, client):
    mock_get.return_value = _frankfurter_response("EUR", {"USD": 1.08})
    response = client.get("/rates?base=eur")
    assert response.status_code == 200
    assert response.get_json()["base"] == "EUR"


@patch("app.requests.get")
def test_rates_defaults_to_usd_when_base_omitted(mock_get, client):
    mock_get.return_value = _frankfurter_response("USD", {"EUR": 0.92})
    response = client.get("/rates")
    body = response.get_json()
    assert body["base"] == "USD"


@patch("app.requests.get")
def test_rates_502_when_fx_provider_errors(mock_get, client):
    import requests as req_lib
    mock_get.side_effect = req_lib.exceptions.ConnectionError("boom")
    response = client.get("/rates?base=USD")
    assert response.status_code == 502
    body = response.get_json()
    assert "Could not retrieve" in body["error"]


@patch("app.requests.get")
def test_rates_502_when_fx_response_missing_rates(mock_get, client):
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"amount": 1.0, "base": "USD", "date": "..."}
    mock_get.return_value = mock
    response = client.get("/rates?base=USD")
    assert response.status_code == 502


# ── Cache behavior ──────────────────────────────────────────────────


@patch("app.requests.get")
def test_rates_cache_avoids_second_external_call(mock_get, client):
    mock_get.return_value = _frankfurter_response("USD", {"EUR": 0.92})
    client.get("/rates?base=USD")
    client.get("/rates?base=USD")
    assert mock_get.call_count == 1


@patch("app.requests.get")
def test_rates_different_bases_cached_separately(mock_get, client):
    mock_get.side_effect = [
        _frankfurter_response("USD", {"EUR": 0.92}),
        _frankfurter_response("EUR", {"USD": 1.08}),
    ]
    client.get("/rates?base=USD")
    client.get("/rates?base=EUR")
    assert mock_get.call_count == 2


# ── get_live_rates as a unit ────────────────────────────────────────


@patch("app.requests.get")
def test_get_live_rates_returns_none_on_http_error(mock_get):
    import requests as req_lib
    mock = MagicMock()
    mock.raise_for_status.side_effect = req_lib.exceptions.HTTPError("500")
    mock_get.return_value = mock
    assert get_live_rates("USD") is None


@patch("app.requests.get")
def test_get_live_rates_returns_none_on_invalid_json(mock_get):
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.side_effect = ValueError("not json")
    mock_get.return_value = mock
    assert get_live_rates("USD") is None
