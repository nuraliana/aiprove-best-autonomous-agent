# Best Fully-Autonomous AIProve Agent

A fully autonomous agent — no human in the loop. It reads `skill.md`, signs
in with its own keypair, and enters and completes as many open bounties as
it can on its own. ([AIProve bounty: `best-autonomous-agent`](https://aiprove.fun),
closes 15 Nov 2026 20:49 WIB.)

## What it does

1. Fetches `GET /skill.md` live.
2. Authenticates: challenge → EIP-191 `personal_sign` → Bearer token.
3. Lists all open bounties.
4. For every bounty it **enters** (free), then decides autonomously:
   - **Forecast, yes/no** (`btc-tomorrow`, `forecast-btc-7d`,
     `forecast-eth-24h`): trend-following call from live CoinGecko 24h
     change, hedged confidence 0.55–0.65.
   - **Forecast, numeric close** (`spy-close-1dollar`, `forecast-nvda-3d`,
     `forecast-gold-tomorrow`): last regular-market close from Yahoo
     Finance as the prediction.
   - **Trading signal** (`signal-eth-pnl-24h`): long/short from live ETH
     24h change.
   - **Code / design / content / marketing / backtest bounties**: entered
     only, logged as not submittable autonomously — they need a real repo,
     artwork, video, or social account. The agent never fakes a `repoUrl`.
   - **`top5-pons-24h`**: entered only; no reliable live source for fresh
     pons launches exists here, so no guess is submitted.
5. Verifies everything via `GET /api/me` and prints a summary.

## Run

```bash
pip install eth-account          # python3, curl also required
export AGENT_PRIVATE_KEY=0x...   # your agent keypair — never commit this
# ...or: export AGENT_KEY_FILE=~/.pg/agent.key
python3 autonomous_agent.py
python3 autonomous_agent.py --dry-run                    # no writes
python3 autonomous_agent.py --only btc-tomorrow,spy-close-1dollar
```

Environment variables: `AGENT_PRIVATE_KEY`, `AGENT_KEY_FILE`
(default `~/.pg/agent.key`), `API_BASE_URL` (default `https://aiprove.fun`),
`AGENT_HANDLE` (default `nuraliana-ana`).

## Files

| file | role |
|---|---|
| `autonomous_agent.py` | the autonomous loop (entry point) |
| `aiprove_client.py` | curl HTTP + EIP-191 auth + API calls |
| `prices.py` | live prices: CoinGecko (crypto), Yahoo Finance (stocks) |

## Relation to `sample-agent-skillmd`

This agent reuses the same client/auth pattern as the sample agent
(`sample-agent-skillmd` repo: fetch skill.md → challenge → sign → verify →
list → enter → verify via `/api/me`), extended from "enter one bounty" to
"enter everything, submit every forecast/signal it can reason about, and
honestly skip what it cannot do without a human".

## Notes

- HTTP goes through `curl` with a browser User-Agent (plain Python `urllib`
  against `aiprove.fun` gets 403/timeouts).
- Private key from env/file at runtime only — never hard-coded, never
  logged, never written to this repo. Session tokens are never printed.
- Identity: handle `nuraliana-ana`, GitHub `nuraliana`,
  agent address `0xC8Cdc58D9E02Da269Db5842CA3D25f85b8D4cC37`.

## Test evidence

See `RUN_LOG.md` — a real end-to-end run with a throwaway test keypair
(the production keypair was never used for testing).
