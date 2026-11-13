"""Live-price helpers for the autonomous agent.

Sources (all free, no API key):
- Crypto (BTC/ETH): CoinGecko simple price + 24h change.
- Stocks/ETF (SPY, NVDA, GLD): Yahoo Finance chart API, last regular close.

Every function returns None on failure instead of raising, so one dead
price source never kills the whole autonomous run.
"""

import json
import subprocess

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def _curl_json(url):
    out = subprocess.run(["curl", "-s", "-m", "20", "-A", UA, url],
                         capture_output=True, text=True, timeout=30)
    try:
        return json.loads(out.stdout)
    except Exception:
        return None


def crypto_prices():
    """-> {'bitcoin': {'usd': float, 'usd_24h_change': float}, 'ethereum': {...}}"""
    d = _curl_json("https://api.coingecko.com/api/v3/simple/price"
                   "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true")
    return d if isinstance(d, dict) and "bitcoin" in d else None


def stock_last_close(symbol):
    """Last regular-market close for a Yahoo symbol (SPY, NVDA, GLD)."""
    d = _curl_json(f"https://query1.finance.yahoo.com/v8/finance/chart/"
                   f"{symbol}?range=5d&interval=1d")
    try:
        meta = d["chart"]["result"][0]["meta"]
        return float(meta["regularMarketPrice"])
    except Exception:
        return None


def direction_call(change_24h_pct):
    """Trend-following directional call, hedged confidence.

    Positive 24h drift -> 'yes' (higher), negative -> 'no'. Confidence is
    deliberately modest (0.55-0.65): a confident wrong Brier call costs
    more than a hedged one, per the bounty briefs.
    """
    if change_24h_pct is None:
        return "yes", 0.55
    up = change_24h_pct >= 0
    conf = min(0.65, 0.55 + min(abs(change_24h_pct), 10.0) * 0.01)
    return ("yes" if up else "no"), round(conf, 2)
