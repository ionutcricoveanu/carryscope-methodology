#!/usr/bin/env python3
"""CarryScope: net-of-cost crypto carry, computed from public data.

This is the exact, reproducible method behind the free "is carry worth it right
now?" number at CarryScope. It is deliberately boring and fully open: a number
you can't reproduce isn't worth trusting.

What it computes
----------------
For BTC and ETH it builds a delta-neutral funding-carry book (long spot, short
the perpetual, rehedged each 8h funding settlement) and reports:
  - GROSS funding APY  (the headline number the dashboards show)
  - NET-of-cost APY    (after trading fees + the basis half-spread they omit)
and compares the net to a risk-free reference. When net sits below risk-free,
the carry isn't paying you for the operational risk.

Data
----
Public Binance endpoints (funding rate + mark price + spot klines). No API key.
This is a dated illustration, not a live feed and not financial advice.

Run
---
    python3 carry.py
"""
import json
import urllib.request
from datetime import datetime, timezone

# ---- method constants -------------------------------------------------------
FEE_PER_FILL_PCT = 0.075         # taker fee per fill (≈ 0.30% per open+close, /4 fills)
BASIS_PENALTY_BP_PER_LEG = 2.0   # basis half-spread floor, basis points per leg
BASIS_CLIP_BP = 50.0             # data-hygiene clip on |basis| (kills bad prints)
RISK_FREE_APY = 4.5              # risk-free hurdle, %
DAYS_PER_YEAR = 365.0
N_SETTLES = 90                   # ~30 days at 3 settlements/day
FAPI = "https://fapi.binance.com"
SAPI = "https://api.binance.com"
SYMBOLS = [("BTCUSDT", "BTC"), ("ETHUSDT", "ETH")]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "carryscope-method/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_funding(sym, limit):
    rows = _get(f"{FAPI}/fapi/v1/fundingRate?symbol={sym}&limit={limit}")
    return [(int(r["fundingTime"]), float(r["fundingRate"]), float(r["markPrice"]))
            for r in rows if r.get("markPrice") not in (None, "", "0")]


def fetch_spot_1h(sym, start_ms, end_ms):
    # 1h spot klines; the bar CLOSE sits within ~1h of each settlement (using
    # coarser bars injects price drift into the basis).
    out, cur, end = [], start_ms - 2 * 3600 * 1000, end_ms + 2 * 3600 * 1000
    while cur < end:
        batch = _get(f"{SAPI}/api/v3/klines?symbol={sym}&interval=1h"
                     f"&startTime={cur}&endTime={end}&limit=1000")
        if not batch:
            break
        out.extend((int(k[6]), float(k[4])) for k in batch)  # (closeTime, close)
        cur = int(batch[-1][0]) + 3600 * 1000
        if len(batch) < 1000:
            break
    return out


def _spot_asof(spot, t_ms, tol=90 * 60 * 1000):
    best = None
    for ct, close in spot:
        if ct <= t_ms and (best is None or ct > best[0]):
            best = (ct, close)
    return None if best is None or (t_ms - best[0]) > tol else best[1]


def compute(sym):
    fund = fetch_funding(sym, N_SETTLES)
    spot = fetch_spot_1h(sym, fund[0][0], fund[-1][0])
    clip = BASIS_CLIP_BP / 1e4
    rows = []
    for t_ms, rate, mark in fund:
        s = _spot_asof(spot, t_ms)
        if s is None:
            continue
        basis = (s - mark) / mark
        rows.append({"t": t_ms, "fund": rate,
                     "basis_clipped": max(-clip, min(clip, basis))})

    # basis half-spread per leg = max(floor, measured median |basis|)
    med_bp = sorted(abs(r["basis_clipped"]) * 1e4 for r in rows)[len(rows) // 2]
    basis_bp_per_leg = max(BASIS_PENALTY_BP_PER_LEG, round(med_bp, 2))
    toggle_cost = 2.0 * (FEE_PER_FILL_PCT / 100.0 + basis_bp_per_leg / 1e4)

    # per-8h-settlement P&L: funding + basis drift; one entry cost over the window
    cum, prev_basis = -toggle_cost, None
    for r in rows:
        step = r["fund"]
        if prev_basis is not None:
            step += (r["basis_clipped"] - prev_basis)
        cum += step
        prev_basis = r["basis_clipped"]

    span_days = max((rows[-1]["t"] - rows[0]["t"]) / 86_400_000.0, 1.0)
    gross_apy = sum(r["fund"] for r in rows) / span_days * DAYS_PER_YEAR * 100.0
    net_apy = cum / span_days * DAYS_PER_YEAR * 100.0
    return {
        "gross_funding_apy_pct": round(gross_apy, 2),
        "net_of_cost_apy_pct": round(net_apy, 2),
        "worth_it_vs_risk_free": net_apy >= RISK_FREE_APY,
        "window": (datetime.fromtimestamp(rows[0]["t"] / 1000, tz=timezone.utc).date().isoformat()
                   + " → "
                   + datetime.fromtimestamp(rows[-1]["t"] / 1000, tz=timezone.utc).date().isoformat()),
        "n_settlements": len(rows),
    }


if __name__ == "__main__":
    print(f"CarryScope: net-of-cost carry (risk-free reference {RISK_FREE_APY}%)\n")
    for sym, label in SYMBOLS:
        r = compute(sym)
        verdict = "worth a look" if r["worth_it_vs_risk_free"] else "NOT worth it right now"
        print(f"{label}  ({r['window']}, {r['n_settlements']} settlements)")
        print(f"   gross funding APY : {r['gross_funding_apy_pct']:+.2f}%   (the headline)")
        print(f"   net of costs      : {r['net_of_cost_apy_pct']:+.2f}%   ({verdict})")
        print()
    print("Dated illustration from public data. Not financial advice. https://github.com/ionutcricoveanu/carryscope-methodology")
