"""currency-api — simple currency exchange rate Flask service.

A20-MVP smoke test (2026-06-07). Public repo so Render free tier can
fetch it. Replace placeholder rates with a real FX source before paid
traffic (exchangerate.host / openexchangerates.org).
"""
import os

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.get("/")
def root():
    return jsonify(
        service="currency-api",
        endpoints=["/health", "/rates?base=USD"],
    )


@app.get("/health")
def health():
    return jsonify(ok=True, service="currency-api")


@app.get("/rates")
def rates():
    base = request.args.get("base", "USD").upper()
    placeholder = {
        "USD": 1.0, "EUR": 0.92, "GBP": 0.78, "JPY": 156.0,
        "CAD": 1.36, "AUD": 1.51, "CHF": 0.88, "CNY": 7.25,
    }
    if base not in placeholder:
        return jsonify(error=f"unsupported base: {base}"), 400
    factor = placeholder[base]
    rebased = {k: round(v / factor, 4) for k, v in placeholder.items() if k != base}
    return jsonify(base=base, rates=rebased, source="placeholder-MVP")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
