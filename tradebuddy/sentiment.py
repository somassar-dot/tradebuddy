"""Nachrichten-Sentiment (Alpha Vantage NEWS_SENTIMENT) und Insider-Aktivität."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np


def _f(x, default=math.nan):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def news(news_obj: dict, ticker: str, days: int = 30) -> dict:
    feed = (news_obj or {}).get("feed") or []
    if not feed:
        return {"score": math.nan, "artikel": 0, "top": []}
    now = None
    rows = []
    for a in feed:
        ts = a.get("time_published", "")
        try:
            t = datetime.strptime(ts[:15], "%Y%m%dT%H%M%S")
        except ValueError:
            continue
        now = max(now, t) if now else t
        for ts_ in a.get("ticker_sentiment", []) or []:
            if ts_.get("ticker", "").upper() == ticker.upper():
                rows.append((t, _f(ts_.get("relevance_score"), 0), _f(ts_.get("ticker_sentiment_score"), 0), a))
    rows = [r for r in rows if r[0] >= now - timedelta(days=days)] if now else []
    if not rows:
        return {"score": math.nan, "artikel": 0, "top": []}
    w = np.array([r[1] for r in rows]) + 1e-6
    s = np.array([r[2] for r in rows])
    avg = float((w * s).sum() / w.sum())  # -1 … +1, AV: >0.15 bullisch, <-0.15 bärisch
    top = sorted(rows, key=lambda r: -r[1])[:8]
    return {
        "score": float(np.clip(50 + avg * 160, 0, 100)),
        "roh": avg,
        "label": "bullisch" if avg > 0.15 else ("bärisch" if avg < -0.15 else "neutral"),
        "artikel": len(rows),
        "top": [{"datum": r[0].strftime("%Y-%m-%d"), "titel": r[3].get("title", ""), "quelle": r[3].get("source", ""),
                 "url": r[3].get("url", ""), "sentiment": r[2]} for r in top],
    }


def insider(ins_obj: dict, months: int = 6) -> dict:
    data = (ins_obj or {}).get("data") or []
    if not data:
        return {"score": math.nan, "käufe": 0, "verkäufe": 0}
    dates = [d.get("transaction_date", "") for d in data if d.get("transaction_date")]
    if not dates:
        return {"score": math.nan, "käufe": 0, "verkäufe": 0}
    latest = max(datetime.strptime(x[:10], "%Y-%m-%d") for x in dates)
    cutoff = latest - timedelta(days=30 * months)
    buy_v = sell_v = 0.0
    buys = sells = 0
    for d in data:
        try:
            t = datetime.strptime(d.get("transaction_date", "")[:10], "%Y-%m-%d")
        except ValueError:
            continue
        if t < cutoff:
            continue
        price = _f(d.get("share_price"), 0)
        val = _f(d.get("shares"), 0) * price
        code = (d.get("acquisition_or_disposal") or "").upper()
        # Form-4-Codes: P = Kauf am Markt, S = Verkauf am Markt. A/M/F/G = Zuteilung, Ausübung,
        # Steuereinbehalt, Schenkung → kein Meinungssignal. Älteres Schema: A/D mit Preis.
        if code == "P" or (code == "A" and price > 0 and "Unit" not in d.get("security_type", "")):
            buy_v += val; buys += 1
        elif code in ("S", "D") and price > 0:
            sell_v += val; sells += 1
    # Insider verkaufen routinemäßig – Käufe sind das stärkere Signal
    score = 50.0
    if buys:
        score += min(35, 10 + 5 * buys)
    if sell_v > 0 and buy_v == 0:
        score -= min(8, 2 + sells * 0.3)
    return {"score": float(np.clip(score, 0, 100)), "käufe": buys, "verkäufe": sells,
            "kaufvolumen": buy_v, "verkaufsvolumen": sell_v, "monate": months}
