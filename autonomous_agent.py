"""Fully autonomous AIProve agent — no human in the loop.

Reads https://aiprove.fun/skill.md, signs in with its own keypair, then
works through every open bounty on its own:

- Forecast (Brier, yes/no): trend-following call from live CoinGecko
  24h change, hedged confidence 0.55-0.65 (a confident wrong Brier call
  costs more than a hedged one).
- Forecast (absolute error, $): last regular-market close from Yahoo
  Finance as the prediction (best naive forecast: tomorrow's close is
  closest to today's close).
- Trading signal (long/short ETH 24h): direction from live ETH 24h change.
- Code / design / content / marketing bounties: entered (free) and logged
  as NOT submittable autonomously — they need a human-owned repo, artwork,
  video, or social account. The agent never fakes a repoUrl.
- `top5-pons-24h`: entered only; no reliable live source for fresh pons
  launches exists in this sandbox, so no guess is submitted.

The submission payload shape follows skill.md:
    {"prediction": {"answer": ..., "confidence": ...}, "handle": ...}
If the server rejects that shape, one fallback shape is tried
({"prediction": <answer>}) and the outcome is logged.

The private key is NEVER hard-coded: AGENT_PRIVATE_KEY env, or the file
named by AGENT_KEY_FILE (default ~/.pg/agent.key). Tokens are never printed.

Usage:
    pip install eth-account
    export AGENT_PRIVATE_KEY=0x...
    python3 autonomous_agent.py [--dry-run] [--only btc-tomorrow,spy-close-1dollar]
"""

import json
import os
import sys

import aiprove_client as api
import prices

HANDLE = os.environ.get("AGENT_HANDLE", "nuraliana-ana")

# slug -> (kind, symbol) for bounties this agent can actually predict.
FORECAST_YESNO = {  # Brier-scored direction calls
    "btc-tomorrow": "bitcoin",
    "forecast-btc-7d": "bitcoin",
    "forecast-eth-24h": "ethereum",
}
FORECAST_NUMBER = {  # absolute-error numeric closes
    "spy-close-1dollar": "SPY",
    "forecast-nvda-3d": "NVDA",
    "forecast-gold-tomorrow": "GLD",
}
SIGNAL_ETH = "signal-eth-pnl-24h"


def submit_prediction(token, slug, answer, confidence=None, dry_run=False):
    payload = {"prediction": {"answer": answer}, "handle": HANDLE}
    if confidence is not None:
        payload["prediction"]["confidence"] = confidence
    if dry_run:
        api.log(f"[dry-run] would submit {slug}: {json.dumps(payload)}")
        return 0, {"dry_run": True}
    code, resp = api.submit(token, slug, payload)
    api.log(f"submit {slug}: HTTP {code} {str(resp)[:300]}")
    if code not in (200, 201):
        # Fallback shape: bare prediction value.
        alt = {"prediction": answer, "handle": HANDLE}
        code2, resp2 = api.submit(token, slug, alt)
        api.log(f"submit {slug} (fallback shape): HTTP {code2} {str(resp2)[:300]}")
        return code2, resp2
    return code, resp


def main():
    dry_run = "--dry-run" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))

    # 1. Read skill.md live.
    code, skill = api.curl_json("GET", "/skill.md", raw=True)
    if code != 200 or "Authenticate" not in skill:
        raise SystemExit(f"skill.md fetch failed: HTTP {code}")
    api.log(f"skill.md read OK ({len(skill)} chars)")

    # 2. Authenticate with own keypair.
    address, acct = api.load_keypair()
    api.log(f"agent address: {address}")
    token = api.authenticate(address, acct)

    # 3. List open bounties.
    bounties = api.list_open_bounties()
    api.log(f"open bounties: {len(bounties)}")
    if only:
        bounties = [b for b in bounties if b.get("slug") in only]

    crypto = prices.crypto_prices()
    if crypto:
        api.log(f"live crypto: BTC ${crypto['bitcoin']['usd']:,.2f} "
                f"({crypto['bitcoin']['usd_24h_change']:+.2f}% 24h), "
                f"ETH ${crypto['ethereum']['usd']:,.2f} "
                f"({crypto['ethereum']['usd_24h_change']:+.2f}% 24h)")
    else:
        api.log("WARNING: CoinGecko unreachable; direction calls fall back to neutral")

    entered, submitted, skipped = [], [], []
    for b in bounties:
        slug = b.get("slug")
        cat, lane = b.get("cat"), b.get("lane")
        api.log(f"--- {slug} [{cat}/{lane}] {b.get('title', '')[:60]}")

        # Enter everything (free); submitting auto-enters too.
        if not dry_run:
            code, resp = api.enter(token, slug, HANDLE)
            api.log(f"enter {slug}: HTTP {code} {str(resp)[:200]}")
            if code in (200, 201):
                entered.append(slug)

        if slug in FORECAST_YESNO:
            coin = FORECAST_YESNO[slug]
            chg = crypto.get(coin, {}).get("usd_24h_change") if crypto else None
            answer, conf = prices.direction_call(chg)
            api.log(f"forecast {slug}: 24h change {chg}; call={answer} conf={conf}")
            code, _ = submit_prediction(token, slug, answer, conf, dry_run)
            if code in (200, 201):
                submitted.append(slug)
        elif slug in FORECAST_NUMBER:
            last = prices.stock_last_close(FORECAST_NUMBER[slug])
            if last is None:
                api.log(f"SKIP submit {slug}: no live price source")
                skipped.append(slug)
                continue
            api.log(f"forecast {slug}: last close ${last:,.2f}; predicting same")
            code, _ = submit_prediction(token, slug, last, None, dry_run)
            if code in (200, 201):
                submitted.append(slug)
        elif slug == SIGNAL_ETH:
            chg = crypto.get("ethereum", {}).get("usd_24h_change") if crypto else None
            side = "long" if (chg or 0) >= 0 else "short"
            api.log(f"signal {slug}: ETH 24h {chg}; call={side}")
            code, _ = submit_prediction(token, slug, side, None, dry_run)
            if code in (200, 201):
                submitted.append(slug)
        else:
            reason = {
                "development": "needs a real repo built by the agent",
                "design": "needs artwork produced by the agent",
                "content": "needs an article/video produced by the agent",
                "marketing": "needs a social post / referrals",
                "forecast": "no reliable live data source in sandbox",
                "trading": "needs a backtested strategy repo",
            }.get(cat, "not submittable autonomously")
            api.log(f"SKIP submit {slug}: {reason} (entered only)")
            skipped.append(slug)

    # 4. Verify via /api/me.
    code, me = api.me(token)
    api.log(f"/api/me: HTTP {code} {json.dumps(me)[:800]}")

    api.log(f"SUMMARY entered={len(entered)} {entered}")
    api.log(f"SUMMARY submitted={len(submitted)} {submitted}")
    api.log(f"SUMMARY skipped-submit={len(skipped)} {skipped}")
    api.log("AUTONOMOUS RUN COMPLETE")


if __name__ == "__main__":
    main()
