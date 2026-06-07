# currency-api
Simple currency exchange API — Tobias income substrate (A20-MVP smoke test)
## Endpoints

- `GET /` — service info + endpoint list
- `GET /health` — liveness check
- `GET /rates?base=USD` — rates against the given base currency

## Status

MVP. Returns placeholder rates today; wire a real FX source before paid traffic.

## Deploy

Auto-deploys to Render on push to `main`.
