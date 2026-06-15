# CarryScope: how we compute carry (the honest number)

This is the exact, reproducible method behind the free **"is crypto carry worth it right now?"** number at
CarryScope. It's deliberately boring and fully open, because a number you can't reproduce isn't worth
trusting.

> **TL;DR:** crypto dashboards show **gross** funding APY. This script subtracts the costs they leave out
> and tells you the **net** number. Right now, on BTC/ETH, that number sits *below the risk-free rate*.

## The problem with the headline funding rate

"Carry" = long spot, short the perpetual, collect the funding. Delta-neutral, so price direction barely
matters. Dashboards quote the **gross funding APY** as if it were clean yield. It isn't: it's before the
trading fees and the basis spread you actually pay to run the position. So the headline always flatters.

## The method

A delta-neutral book (long 1 unit spot, short 1 unit perp), rehedged each 8-hour funding settlement. Price
cancels, so the only things that move P&L are the **funding you receive** and the drift in the **basis**
`(spot − perp) / perp`. Per settlement, while the position is on:

```
step P&L  =  funding_rate  +  (basis_now − basis_last)
cost/leg  =  taker fee (0.075%)  +  basis half-spread (at least 2 bp)
```

From the per-settlement P&L we annualize the **net APY** and compare it to a **4.5% risk-free** reference.
When net is below risk-free, the carry isn't paying you for the liquidation/operational risk.

## Run it

No API key, no dependencies beyond the Python standard library. Uses public Binance endpoints.

```bash
python3 carry.py
```

Example output (a dated snapshot; yours will differ):

```
BTC  (2026-05-16 → 2026-06-15, 90 settlements)
   gross funding APY : +3.98%   (the headline)
   net of costs      : +0.93%   (NOT worth it right now)

ETH  (2026-05-16 → 2026-06-15, 90 settlements)
   gross funding APY : +2.80%   (the headline)
   net of costs      : -0.11%   (NOT worth it right now)
```

## What this is honest about

- It shows the metric is **real and computable**, *not* that carry is a good strategy in general. Whether
  delta-neutral carry has a durable, risk-adjusted edge across years (and through a bear market) is a
  separate, longer question, and a 30-day snapshot doesn't answer it.
- The numbers are a **dated illustration** from public data, not a live feed.
- CarryScope is **analytics only**: no execution, no custody, no advice. The decision is yours.
- The product adds, for subscribers, the things a one-off snapshot can't give you: real-time + more
  symbols, risk-adjusted columns (Sharpe, drawdown, a bear-market drawdown), a regime signal, and alerts.

## Not financial advice

Crypto carry involves real risk including liquidation and loss. Figures may be delayed or wrong; verify
before trading.

## License

MIT, see [LICENSE](LICENSE). Use it, check it, improve it.
