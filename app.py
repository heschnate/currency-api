"""currency-api — simple currency exchange rate Flask service.

Live FX via the Frankfurter API (free, no key, ECB rates) — switched
from exchangerate.host on 2026-06-08 after that service started requiring
an access_key. Frankfurter exposes ~30 currencies sourced from the
European Central Bank, refreshed once per business day.

Cache: 60s in-process dict, keyed by base currency. Rates only refresh
once a day at the source, so 60s is more than enough granularity for
free-tier traffic and keeps us well under any reasonable rate limit.
"""
import logging
import os
import time

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
log = logging.getLogger(__name__)

# Simple in-memory cache: {base_currency: {"rates": {...}, "timestamp": float}}
RATE_CACHE: dict[str, dict] = {}
CACHE_TTL_SECONDS = 60

# Frankfurter API — free, no auth required, ECB-sourced rates.
# Endpoint format: https://api.frankfurter.dev/v1/latest?base=USD
FX_API_URL = "https://api.frankfurter.dev/v1/latest"
FX_API_TIMEOUT_SECONDS = 5


@app.get("/")
def root():
    return jsonify(
        service="currency-api",
        endpoints=["/health", "/rates?base=USD"],
        source="frankfurter.dev (ECB)",
    )


@app.get("/health")
def health():
    return jsonify(ok=True, service="currency-api")


def get_live_rates(base_currency: str):
    """Fetch live FX rates from Frankfurter, with 60s in-memory cache.

    Returns the rates dict on success ({EUR: 0.92, GBP: 0.78, ...}) or
    None on any failure (network, non-200, missing rates field).
    """
    now = time.time()
    cached = RATE_CACHE.get(base_currency)
    if cached and (now - cached["timestamp"]) < CACHE_TTL_SECONDS:
        return cached["rates"]

    try:
        resp = requests.get(
            FX_API_URL,
            params={"base": base_currency},
            timeout=FX_API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        log.warning("FX fetch failed for %s: %s", base_currency, e)
        return None
    except ValueError as e:  # json decode error
        log.warning("FX response not JSON for %s: %s", base_currency, e)
        return None

    rates = data.get("rates")
    if not rates:
        log.warning("FX response missing 'rates' for %s: %r", base_currency, data)
        return None

    RATE_CACHE[base_currency] = {"rates": rates, "timestamp": now}
    return rates


@app.get("/rates")
def rates():
    base = request.args.get("base", "USD").upper()
    live = get_live_rates(base)
    if live is None:
        return jsonify(
            error=f"Could not retrieve rates for base: {base}",
            source="frankfurter.dev",
        ), 502
    # Drop the base currency from the response if present (it'd always be 1.0)
    rebased = {k: round(v, 4) for k, v in live.items() if k != base}
    return jsonify(base=base, rates=rebased, source="frankfurter.dev")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
