"""Abhängigkeitsfreie SVG-Charts (Kerzen, Linien, Balken) für den HTML-Report."""
from __future__ import annotations

import math
from html import escape

import pandas as pd

W = 920


def _ok(v):
    return v is not None and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))


class Pane:
    def __init__(self, x0, y0, w, h, lo, hi, n):
        self.x0, self.y0, self.w, self.h, self.lo, self.hi, self.n = x0, y0, w, h, lo, hi, n

    def x(self, i):
        return self.x0 + (i + 0.5) * self.w / self.n

    def y(self, v):
        return self.y0 + self.h - (v - self.lo) / (self.hi - self.lo or 1) * self.h


def _poly(p: Pane, s: pd.Series, cls: str, width=1.6, dash=""):
    pts = [f"{p.x(i):.1f},{p.y(v):.1f}" for i, v in enumerate(s.values) if _ok(v)]
    if len(pts) < 2:
        return ""
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<polyline class="{cls}" fill="none" stroke-width="{width}"{d} points="{" ".join(pts)}"/>'


def _grid(p: Pane, ticks=5, fmt="{:.0f}"):
    out = []
    for k in range(ticks + 1):
        v = p.lo + (p.hi - p.lo) * k / ticks
        y = p.y(v)
        out.append(f'<line class="grid" x1="{p.x0}" x2="{p.x0 + p.w}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<text class="ax" x="{p.x0 + p.w + 6}" y="{y + 4:.1f}">{fmt.format(v)}</text>')
    return "".join(out)


def _xlabels(p: Pane, idx, every):
    out = []
    for i, d in enumerate(idx):
        if i % every == 0:
            anchor = "start" if i == 0 else "middle"
            out.append(f'<text class="ax" text-anchor="{anchor}" x="{p.x(i) - (3 if i == 0 else 0):.1f}" y="{p.y0 + p.h + 14:.1f}">{d:%d.%m.%y}</text>')
    return "".join(out)


def price_chart(df: pd.DataFrame, supports, resistances, plan: dict | None = None) -> str:
    df = df.tail(100)
    n = len(df)
    lo = min(df["low"].min(), df["bb_lower"].min(skipna=True) if df["bb_lower"].notna().any() else df["low"].min())
    hi = max(df["high"].max(), df["bb_upper"].max(skipna=True) if df["bb_upper"].notna().any() else df["high"].max())
    if plan:
        lo = min(lo, plan["stop"])
    pad = (hi - lo) * 0.06
    lo, hi = lo - pad, hi + pad
    H = 560
    pp = Pane(10, 10, W - 80, 300, lo, hi, n)
    vp = Pane(10, 318, W - 80, 50, 0, df["volume"].max() * 1.05, n)
    rp = Pane(10, 392, W - 80, 70, 0, 100, n)
    mp = Pane(10, 478, W - 80, 62, 0, 1, n)
    mlo = min(df[["macd", "macd_signal", "macd_hist"]].min(skipna=True).min(), 0)
    mhi = max(df[["macd", "macd_signal", "macd_hist"]].max(skipna=True).max(), 0)
    mp.lo, mp.hi = mlo * 1.1 - 1e-9, mhi * 1.1 + 1e-9
    s = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Tageschart mit Indikatoren">']
    s.append(_grid(pp, 6, "{:.0f}" if hi > 50 else "{:.2f}"))
    # Bollinger-Fläche
    up = [(pp.x(i), pp.y(v)) for i, v in enumerate(df["bb_upper"].values) if _ok(v)]
    dn = [(pp.x(i), pp.y(v)) for i, v in enumerate(df["bb_lower"].values) if _ok(v)]
    if up and dn:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in up + dn[::-1])
        s.append(f'<polygon class="bb" points="{pts}"/>')
    # Unterstützungen / Widerstände
    for lvl, t in supports[:3]:
        if lo < lvl < hi:
            s.append(f'<line class="sup" x1="{pp.x0}" x2="{pp.x0 + pp.w}" y1="{pp.y(lvl):.1f}" y2="{pp.y(lvl):.1f}"/>'
                     f'<text class="lbl sup-t" x="{pp.x0 + 4}" y="{pp.y(lvl) - 3:.1f}">S {lvl:.2f} ({t}×)</text>')
    for lvl, t in resistances[:3]:
        if lo < lvl < hi:
            s.append(f'<line class="res" x1="{pp.x0}" x2="{pp.x0 + pp.w}" y1="{pp.y(lvl):.1f}" y2="{pp.y(lvl):.1f}"/>'
                     f'<text class="lbl res-t" x="{pp.x0 + 4}" y="{pp.y(lvl) - 3:.1f}">R {lvl:.2f} ({t}×)</text>')
    # Kerzen
    cw = max(1.5, pp.w / n * 0.62)
    for i, (_, r) in enumerate(df.iterrows()):
        cls = "up" if r["close"] >= r["open"] else "dn"
        x = pp.x(i)
        y1, y2 = pp.y(max(r["open"], r["close"])), pp.y(min(r["open"], r["close"]))
        s.append(f'<line class="wick {cls}" x1="{x:.1f}" x2="{x:.1f}" y1="{pp.y(r["high"]):.1f}" y2="{pp.y(r["low"]):.1f}"/>'
                 f'<rect class="{cls}" x="{x - cw / 2:.1f}" y="{y1:.1f}" width="{cw:.1f}" height="{max(y2 - y1, 0.8):.1f}"/>')
        vh = vp.h * r["volume"] / (vp.hi or 1)
        s.append(f'<rect class="vol {cls}" x="{x - cw / 2:.1f}" y="{vp.y0 + vp.h - vh:.1f}" width="{cw:.1f}" height="{vh:.1f}"/>')
    s.append(_poly(pp, df["sma20"], "l-sma20"))
    s.append(_poly(pp, df["sma50"], "l-sma50"))
    # Trade-Plan (Linien über die letzten Kerzen, Beschriftung kollisionsfrei rechts)
    if plan:
        x_end = pp.x0 + pp.w
        x_st = pp.x(n - 12)
        marks = [("stop", "stop", "Stop", plan["stop"]), ("entry", "entry", "Einstieg", plan["einstieg"])]
        marks += [("tgt", "tgt", f"Ziel {k + 1}", t_) for k, t_ in enumerate(plan["ziele"][:2]) if lo < t_ < hi]
        ys = []
        for _, cls, lab, v in marks:
            y = pp.y(v)
            s.append(f'<line class="{cls}" x1="{x_st:.1f}" x2="{x_end}" y1="{y:.1f}" y2="{y:.1f}"/>')
            ys.append([y - 3, cls, f"{lab} {v:.2f}"])
        ys.sort()
        for k in range(1, len(ys)):
            if ys[k][0] - ys[k - 1][0] < 13:
                ys[k][0] = ys[k - 1][0] + 13
        for y, cls, txt in ys:
            s.append(f'<text class="lbl halo {cls}-t" text-anchor="end" x="{x_st - 4:.1f}" y="{y + 4:.1f}">{txt}</text>')
    # RSI
    s.append(f'<text class="pt" x="{rp.x0}" y="{rp.y0 - 4}">RSI 14</text>')
    for v in (30, 50, 70):
        s.append(f'<line class="grid{" mid" if v == 50 else ""}" x1="{rp.x0}" x2="{rp.x0 + rp.w}" y1="{rp.y(v):.1f}" y2="{rp.y(v):.1f}"/>'
                 f'<text class="ax" x="{rp.x0 + rp.w + 6}" y="{rp.y(v) + 4:.1f}">{v}</text>')
    s.append(_poly(rp, df["rsi"], "l-rsi"))
    # MACD
    s.append(f'<text class="pt" x="{mp.x0}" y="{mp.y0 - 4}">MACD (12/26/9)</text>')
    z = mp.y(0)
    s.append(f'<line class="grid mid" x1="{mp.x0}" x2="{mp.x0 + mp.w}" y1="{z:.1f}" y2="{z:.1f}"/>')
    for i, v in enumerate(df["macd_hist"].values):
        if _ok(v):
            y = mp.y(v)
            s.append(f'<rect class="{"up" if v >= 0 else "dn"} hist" x="{mp.x(i) - cw / 2:.1f}" y="{min(y, z):.1f}" width="{cw:.1f}" height="{abs(z - y):.1f}"/>')
    s.append(_poly(mp, df["macd"], "l-macd", 1.3))
    s.append(_poly(mp, df["macd_signal"], "l-sig", 1.3))
    s.append(_xlabels(mp, df.index, max(1, n // 8)))
    s.append("</svg>")
    return "".join(s)


def weekly_chart(df: pd.DataFrame) -> str:
    n = len(df)
    lo, hi = df.min(skipna=True).min(), df.max(skipna=True).max()
    pad = (hi - lo) * 0.06
    p = Pane(10, 10, W - 80, 220, lo - pad, hi + pad, n)
    s = [f'<svg viewBox="0 0 {W} 260" class="chart" role="img" aria-label="Wochenchart mit gleitenden Durchschnitten">',
         _grid(p, 5, "{:.0f}" if hi > 50 else "{:.2f}")]
    pts = [f"{p.x(i):.1f},{p.y(v):.1f}" for i, v in enumerate(df["close"].values)]
    area = f"{p.x(0):.1f},{p.y0 + p.h} " + " ".join(pts) + f" {p.x(n - 1):.1f},{p.y0 + p.h}"
    s.append(f'<polygon class="area" points="{area}"/>')
    s.append(_poly(p, df["close"], "l-close", 1.8))
    s.append(_poly(p, df["sma10w"], "l-sma20", 1.4))
    s.append(_poly(p, df["sma40w"], "l-sma50", 1.6))
    s.append(_xlabels(p, df.index, max(1, n // 7)))
    s.append("</svg>")
    return "".join(s)


def bars(rows: list[dict], keys: list[tuple[str, str]], unit="Mrd.") -> str:
    rows = [r for r in rows if any(_ok(r.get(k)) for k, _ in keys)]
    if not rows:
        return ""
    vals = [r[k] for r in rows for k, _ in keys if _ok(r.get(k))]
    lo, hi = min(0, min(vals)), max(vals) * 1.12
    H = 230
    p = Pane(10, 10, W - 80, 180, lo, hi, len(rows))
    s = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="Umsatz, Gewinn und Free Cashflow je Geschäftsjahr">', _grid(p, 4)]
    gw = p.w / len(rows) * 0.7
    bw = gw / len(keys)
    for i, r in enumerate(rows):
        for j, (k, cls) in enumerate(keys):
            v = r.get(k)
            if not _ok(v):
                continue
            x = p.x(i) - gw / 2 + j * bw
            y, z = p.y(v), p.y(0)
            s.append(f'<rect class="{cls}" rx="2" x="{x + 1:.1f}" y="{min(y, z):.1f}" width="{bw - 2:.1f}" height="{abs(z - y):.1f}">'
                     f'<title>{escape(r["jahr"])} {k}: {v:.1f} {unit}</title></rect>')
        s.append(f'<text class="ax" text-anchor="middle" x="{p.x(i):.1f}" y="{p.y0 + p.h + 16}">{escape(r["jahr"])}</text>')
    s.append("</svg>")
    return "".join(s)
