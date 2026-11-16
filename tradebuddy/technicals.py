"""Charttechnik: Indikatoren, Unterstützungen/Widerstände, Muster und Technik-Score."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


# ---------------------------------------------------------------- Indikatoren
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / down.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.where(down != 0, 100.0)


def macd(close: pd.Series, fast=12, slow=26, signal=9):
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return line, sig, line - sig


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].shift()
    return pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n=14) -> pd.Series:
    return true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def adx(df: pd.DataFrame, n=14):
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr = true_range(df).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    pdi = 100 * plus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    mdi = 100 * minus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean(), pdi, mdi


def bollinger(close: pd.Series, n=20, k=2.0):
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    return mid + k * sd, mid, mid - k * sd


def stochastic(df: pd.DataFrame, n=14, d=3):
    ll = df["low"].rolling(n, min_periods=n).min()
    hh = df["high"].rolling(n, min_periods=n).max()
    k = 100 * (df["close"] - ll) / (hh - ll).replace(0, np.nan)
    return k, k.rolling(d).mean()


def obv(df: pd.DataFrame) -> pd.Series:
    return (np.sign(df["close"].diff()).fillna(0) * df["volume"]).cumsum()


def adjust_splits(df: pd.DataFrame) -> pd.DataFrame:
    """Erkennt Aktiensplits in unbereinigten Reihen (Gap ≈ ganzzahliges Verhältnis) und bereinigt rückwirkend."""
    df = df.copy()
    prev_close = df["close"].shift()
    ratio = prev_close / df["open"]
    for idx in df.index[ratio.fillna(1) > 1.8]:
        r = ratio.loc[idx]
        for cand in (2, 3, 4, 5, 7, 8, 10, 15, 20, 1.5):
            if abs(r / cand - 1) < 0.06:
                mask = df.index < idx
                df.loc[mask, ["open", "high", "low", "close"]] /= cand
                df.loc[mask, "volume"] *= cand
                break
    for idx in df.index[ratio.fillna(1) < 0.55]:  # Reverse-Split
        r = 1 / ratio.loc[idx]
        for cand in (2, 3, 4, 5, 8, 10, 20):
            if abs(r / cand - 1) < 0.06:
                mask = df.index < idx
                df.loc[mask, ["open", "high", "low", "close"]] *= cand
                df.loc[mask, "volume"] /= cand
                break
    return df


# ---------------------------------------------------------------- Strukturen
def pivots(df: pd.DataFrame, w: int = 5):
    hi, lo = df["high"], df["low"]
    ph = hi[(hi == hi.rolling(2 * w + 1, center=True).max())]
    pl = lo[(lo == lo.rolling(2 * w + 1, center=True).min())]
    return ph.dropna(), pl.dropna()


def levels(df: pd.DataFrame, price: float, tol: float, w: int = 5, extra: list[float] | None = None):
    """Clustert Pivot-Hochs/Tiefs zu Preiszonen. Liefert Liste (level, touches)."""
    ph, pl = pivots(df, w)
    pts = sorted(list(ph.values) + list(pl.values) + (extra or []))
    clusters: list[list[float]] = []
    for p in pts:
        if clusters and abs(p - np.mean(clusters[-1])) <= tol:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    lv = [(float(np.mean(c)), len(c)) for c in clusters]
    supports = sorted([x for x in lv if x[0] < price], key=lambda x: -x[0])
    resist = sorted([x for x in lv if x[0] > price], key=lambda x: x[0])
    return supports, resist


def bullish_divergence(close: pd.Series, osc: pd.Series, lookback=40) -> bool:
    c, o = close.tail(lookback), osc.tail(lookback)
    if len(c) < lookback or o.isna().all():
        return False
    half = lookback // 2
    a, b = c.iloc[:half], c.iloc[half:]
    return bool(b.min() < a.min() and o.loc[b.idxmin()] > o.loc[a.idxmin()])


def bearish_divergence(close: pd.Series, osc: pd.Series, lookback=40) -> bool:
    c, o = close.tail(lookback), osc.tail(lookback)
    if len(c) < lookback or o.isna().all():
        return False
    half = lookback // 2
    a, b = c.iloc[:half], c.iloc[half:]
    return bool(b.max() > a.max() and o.loc[b.idxmax()] < o.loc[a.idxmax()])


def _last(s: pd.Series):
    s = s.dropna()
    return float(s.iloc[-1]) if len(s) else math.nan


def _pct(a, b):
    return (a / b - 1) * 100 if b and not math.isnan(b) and not math.isnan(a) else math.nan


@dataclass
class Signal:
    area: str
    text: str
    weight: float  # +bullisch / -bärisch


@dataclass
class TechResult:
    price: float
    date: str
    indicators: dict = field(default_factory=dict)
    performance: dict = field(default_factory=dict)
    supports: list = field(default_factory=list)
    resistances: list = field(default_factory=list)
    signals: list = field(default_factory=list)
    subscores: dict = field(default_factory=dict)
    score: float = 50.0
    trend: str = "seitwärts"
    series: dict = field(default_factory=dict)


def analyze(daily: pd.DataFrame | None, weekly: pd.DataFrame | None,
            benchmark: pd.DataFrame | None = None) -> TechResult:
    if weekly is not None:
        weekly = adjust_splits(weekly)
    if daily is not None:
        daily = adjust_splits(daily)
    base = daily if daily is not None else weekly
    price = float(base["close"].iloc[-1])
    res = TechResult(price=price, date=str(base.index[-1].date()))
    sig: list[Signal] = []
    ind = res.indicators

    # --------------------------------------------------------- Wochenchart (Langfrist)
    lt_score = 50.0
    if weekly is not None and len(weekly) >= 45:
        w = weekly
        wc = w["close"]
        sma10w, sma40w = sma(wc, 10), sma(wc, 40)
        ind["sma10w"], ind["sma40w"] = _last(sma10w), _last(sma40w)
        slope40 = _pct(_last(sma40w), float(sma40w.dropna().iloc[-5])) if sma40w.notna().sum() > 5 else math.nan
        ind["sma40w_slope_4w_pct"] = slope40
        ind["rsi14w"] = _last(rsi(wc))
        ml, ms, mh = macd(wc)
        ind["macd_w_hist"] = _last(mh)
        last52 = w.tail(52)
        ind["high_52w"], ind["low_52w"] = float(last52["high"].max()), float(last52["low"].min())
        ind["dist_52w_high_pct"] = _pct(price, ind["high_52w"])
        ind["pos_in_52w_range_pct"] = 100 * (price - ind["low_52w"]) / max(ind["high_52w"] - ind["low_52w"], 1e-9)
        for lbl, n in (("1M", 4), ("3M", 13), ("6M", 26), ("1J", 52), ("3J", 156)):
            if len(wc) > n:
                res.performance[lbl] = _pct(price, float(wc.iloc[-n - 1]))
        ytd = wc[wc.index.year < base.index[-1].year]
        if len(ytd):
            res.performance["YTD"] = _pct(price, float(ytd.iloc[-1]))

        if price > ind["sma40w"] and ind["sma10w"] > ind["sma40w"] and slope40 > 0:
            lt_score = 85; res.trend = "Aufwärtstrend"
            sig.append(Signal("Trend", "Langfristiger Aufwärtstrend: Kurs > SMA10w > SMA40w (≈200-Tage-Linie), SMA40w steigt", +2))
        elif price < ind["sma40w"] and ind["sma10w"] < ind["sma40w"] and slope40 < 0:
            lt_score = 15; res.trend = "Abwärtstrend"
            sig.append(Signal("Trend", "Langfristiger Abwärtstrend: Kurs < SMA10w < SMA40w, SMA40w fällt", -2))
        elif price > ind["sma40w"]:
            lt_score = 62
            sig.append(Signal("Trend", "Kurs über der 40-Wochen-Linie (≈200-Tage-Linie)", +1))
        else:
            lt_score = 38
            sig.append(Signal("Trend", "Kurs unter der 40-Wochen-Linie (≈200-Tage-Linie)", -1))
        cross = (sma10w > sma40w).astype(int).diff().tail(8)
        if (cross > 0).any():
            sig.append(Signal("Trend", "Golden Cross (SMA10w über SMA40w) in den letzten 8 Wochen", +1.5))
        if (cross < 0).any():
            sig.append(Signal("Trend", "Death Cross (SMA10w unter SMA40w) in den letzten 8 Wochen", -1.5))
        if ind["dist_52w_high_pct"] > -3:
            sig.append(Signal("Struktur", "Notiert nahe 52-Wochen-Hoch – relative Stärke", +1))
        elif ind["dist_52w_high_pct"] < -35:
            sig.append(Signal("Struktur", f"{ind['dist_52w_high_pct']:.0f}% unter 52-Wochen-Hoch – angeschlagener Chart", -1))
        res.series["weekly"] = pd.DataFrame({"close": wc, "sma10w": sma10w, "sma40w": sma40w}).tail(156)

    # --------------------------------------------------------- Tageschart (Timing)
    mom_score, vol_score, struct_score, mt_score = 50.0, 50.0, 50.0, 50.0
    if daily is not None and len(daily) >= 35:
        d = daily
        c = d["close"]
        s20, s50, e21 = sma(c, 20), sma(c, 50), ema(c, 21)
        r = rsi(c)
        ml, ms, mh = macd(c)
        bu, bm, bl = bollinger(c)
        a = atr(d)
        ax, pdi, mdi = adx(d)
        k, dd = stochastic(d)
        o = obv(d)
        ind.update({
            "sma20": _last(s20), "sma50": _last(s50), "ema21": _last(e21), "rsi14": _last(r),
            "macd": _last(ml), "macd_signal": _last(ms), "macd_hist": _last(mh),
            "bb_upper": _last(bu), "bb_lower": _last(bl), "atr14": _last(a),
            "atr_pct": _last(a) / price * 100, "adx14": _last(ax), "plus_di": _last(pdi), "minus_di": _last(mdi),
            "stoch_k": _last(k), "stoch_d": _last(dd),
        })
        if len(c) > 5:
            res.performance.setdefault("1W", _pct(price, float(c.iloc[-6])))
        # Mittelfristiger Trend
        pts = 0
        pts += 1 if price > ind["sma20"] else -1
        if not math.isnan(ind["sma50"]):
            pts += 1 if price > ind["sma50"] else -1
            pts += 1 if ind["sma20"] > ind["sma50"] else -1
        mt_score = 50 + pts * 16
        if not math.isnan(ind["sma50"]):
            if price > ind["sma20"] > ind["sma50"]:
                sig.append(Signal("Trend", "Kurzfristig intakt: Kurs > SMA20 > SMA50", +1))
            elif price < ind["sma20"] < ind["sma50"]:
                sig.append(Signal("Trend", "Kurzfristig schwach: Kurs < SMA20 < SMA50", -1))
        if ind["adx14"] > 25:
            direction = "aufwärts" if ind["plus_di"] > ind["minus_di"] else "abwärts"
            sig.append(Signal("Trend", f"ADX {ind['adx14']:.0f}: ausgeprägter Trend {direction}", +1 if direction == "aufwärts" else -1))
        elif ind["adx14"] < 18:
            sig.append(Signal("Trend", f"ADX {ind['adx14']:.0f}: kein klarer Trend (Range-Markt)", 0))

        # Momentum
        rv = ind["rsi14"]
        mom = 50.0
        if rv > 70:
            sig.append(Signal("Momentum", f"RSI {rv:.0f} – überkauft, Rücksetzergefahr", -1)); mom = 45
        elif rv < 30:
            sig.append(Signal("Momentum", f"RSI {rv:.0f} – überverkauft, Rebound-Chance", +1)); mom = 55
        elif 50 <= rv <= 70:
            sig.append(Signal("Momentum", f"RSI {rv:.0f} – bullische Zone", +0.5)); mom = 68
        else:
            sig.append(Signal("Momentum", f"RSI {rv:.0f} – bärische Zone", -0.5)); mom = 35
        mcross = (ml > ms).astype(int).diff().tail(5)
        if (mcross > 0).any():
            sig.append(Signal("Momentum", "MACD-Kaufsignal (Kreuzung über Signallinie) in den letzten 5 Tagen", +1)); mom += 10
        elif (mcross < 0).any():
            sig.append(Signal("Momentum", "MACD-Verkaufssignal in den letzten 5 Tagen", -1)); mom -= 10
        elif ind["macd_hist"] > 0:
            mom += 5
        else:
            mom -= 5
        if bullish_divergence(c, r):
            sig.append(Signal("Momentum", "Bullische RSI-Divergenz (tieferes Tief im Kurs, höheres Tief im RSI)", +1.5)); mom += 10
        if bearish_divergence(c, r):
            sig.append(Signal("Momentum", "Bärische RSI-Divergenz (höheres Hoch im Kurs, tieferes Hoch im RSI)", -1.5)); mom -= 10
        mom_score = float(np.clip(mom, 0, 100))

        # Volumen
        v20 = d["volume"].rolling(20).mean()
        ind["vol_ratio"] = float(d["volume"].iloc[-1] / v20.iloc[-1]) if v20.notna().any() else math.nan
        up_vol = d["volume"][c.diff() > 0].tail(20).sum()
        dn_vol = d["volume"][c.diff() < 0].tail(20).sum()
        ind["up_down_volume"] = float(up_vol / dn_vol) if dn_vol else math.nan
        obv_slope = _pct(float(o.iloc[-1]) + 1e12, float(o.iloc[-21]) + 1e12) if len(o) > 21 else 0
        vol = 50 + np.clip((ind["up_down_volume"] - 1) * 40, -30, 30) if not math.isnan(ind["up_down_volume"]) else 50
        if ind["up_down_volume"] > 1.3:
            sig.append(Signal("Volumen", f"Akkumulation: Volumen an Up-Tagen {ind['up_down_volume']:.1f}× Down-Tage (20T)", +1))
        elif ind["up_down_volume"] < 0.75:
            sig.append(Signal("Volumen", f"Distribution: Volumen an Down-Tagen überwiegt ({ind['up_down_volume']:.1f}×)", -1))
        if ind["vol_ratio"] > 1.8:
            dirn = c.iloc[-1] > c.iloc[-2]
            sig.append(Signal("Volumen", f"Volumenspike {ind['vol_ratio']:.1f}× Ø20 an einem {'Plus' if dirn else 'Minus'}tag", +1 if dirn else -1))
        vol_score = float(np.clip(vol + (5 if obv_slope > 0 else -5), 0, 100))

        # Struktur / Ausbrüche / Volatilität
        st = 50.0
        prior_high = float(d["high"].iloc[-21:-1].max())
        prior_low = float(d["low"].iloc[-21:-1].min())
        if price > prior_high:
            sig.append(Signal("Struktur", "Ausbruch über das 20-Tage-Hoch", +1.5)); st += 20
        elif price < prior_low:
            sig.append(Signal("Struktur", "Bruch unter das 20-Tage-Tief", -1.5)); st -= 20
        bw = (bu - bl) / bm
        if bw.notna().sum() > 60 and _last(bw) <= bw.dropna().tail(100).quantile(0.15):
            sig.append(Signal("Volatilität", "Bollinger-Squeeze: Volatilität sehr niedrig – größere Bewegung wahrscheinlich", 0))
        if price > ind["bb_upper"]:
            sig.append(Signal("Volatilität", "Schlusskurs über oberem Bollinger-Band (stark, aber gedehnt)", 0))
        elif price < ind["bb_lower"]:
            sig.append(Signal("Volatilität", "Schlusskurs unter unterem Bollinger-Band (schwach, aber gedehnt)", 0))
        ext = (price / ind["ema21"] - 1) / (ind["atr_pct"] / 100) if ind["atr_pct"] else 0
        ind["ext_ema21_atr"] = ext
        if ext > 3:
            sig.append(Signal("Struktur", f"Kurs {ext:.1f} ATR über EMA21 – überdehnt, kein guter Einstieg", -1)); st -= 10
        elif -1 <= ext <= 1 and res.trend == "Aufwärtstrend":
            sig.append(Signal("Struktur", "Kurs nahe EMA21 im Aufwärtstrend – klassische Einstiegszone", +1)); st += 10
        struct_score = float(np.clip(st, 0, 100))

        res.series["daily"] = pd.DataFrame({
            "open": d["open"], "high": d["high"], "low": d["low"], "close": c, "volume": d["volume"],
            "sma20": s20, "sma50": s50, "bb_upper": bu, "bb_lower": bl, "rsi": r,
            "macd": ml, "macd_signal": ms, "macd_hist": mh})

    # --------------------------------------------------------- Unterstützung / Widerstand
    atr_v = ind.get("atr14") or (float(atr(weekly).iloc[-1]) / 2.2 if weekly is not None else price * 0.02)
    tol = max(atr_v * 0.6, price * 0.006)
    frames = []
    if daily is not None:
        frames.append(daily)
    if weekly is not None:
        frames.append(weekly.tail(104))
    extra = [v for k, v in ind.items() if k in ("sma40w", "sma50") and v and not math.isnan(v)]
    allp = pd.concat(frames).sort_index() if frames else base
    sup, resi = [], []
    for f, w in ((daily, 5), (weekly.tail(104) if weekly is not None else None, 3)):
        if f is not None:
            s_, r_ = levels(f, price, tol, w)
            sup += s_; resi += r_
    def merge(lst, rev):
        lst = sorted(lst, key=lambda x: x[0], reverse=rev)
        out = []
        for lv, t in lst:
            if out and abs(lv - out[-1][0]) <= tol:
                pl, pt = out[-1]
                out[-1] = ((pl * pt + lv * t) / (pt + t), pt + t)
            else:
                out.append((lv, t))
        return out
    res.supports = [(round(l, 2), t) for l, t in merge(sup, True)][:5]
    res.resistances = [(round(l, 2), t) for l, t in merge(resi, False)][:5]
    if not res.resistances and ind.get("high_52w"):
        res.resistances = [(round(ind["high_52w"], 2), 1)]
    if res.supports:
        dist = (price - res.supports[0][0]) / atr_v
        ind["dist_support_atr"] = dist
        if dist < 1:
            sig.append(Signal("Struktur", f"Kurs direkt an Unterstützung {res.supports[0][0]:.2f} (enges Stop-Risiko)", +0.5)); struct_score = min(100, struct_score + 5)

    # --------------------------------------------------------- Relative Stärke
    rs_score = 50.0
    if benchmark is not None and weekly is not None and len(benchmark) > 30:
        bmk = adjust_splits(benchmark)["close"]
        stock = weekly["close"]
        j = pd.concat([stock, bmk], axis=1, keys=["s", "b"]).dropna()
        if len(j) > 27:
            rs13 = _pct(j["s"].iloc[-1], j["s"].iloc[-14]) - _pct(j["b"].iloc[-1], j["b"].iloc[-14])
            rs26 = _pct(j["s"].iloc[-1], j["s"].iloc[-27]) - _pct(j["b"].iloc[-1], j["b"].iloc[-27])
            ind["rel_strength_3m_pp"], ind["rel_strength_6m_pp"] = rs13, rs26
            rs_score = float(np.clip(50 + rs13 * 1.5 + rs26 * 0.75, 0, 100))
            if rs13 > 0 and rs26 > 0:
                sig.append(Signal("Rel. Stärke", f"Outperformance vs. Benchmark: {rs13:+.1f} PP (3M), {rs26:+.1f} PP (6M)", +1))
            elif rs13 < 0 and rs26 < 0:
                sig.append(Signal("Rel. Stärke", f"Underperformance vs. Benchmark: {rs13:+.1f} PP (3M), {rs26:+.1f} PP (6M)", -1))

    res.subscores = {"Langfristtrend": lt_score, "Mittelfristtrend": mt_score, "Momentum": mom_score,
                     "Volumen": vol_score, "Struktur": struct_score, "Relative Stärke": rs_score}
    weights = {"Langfristtrend": 0.30, "Mittelfristtrend": 0.20, "Momentum": 0.20,
               "Volumen": 0.10, "Struktur": 0.12, "Relative Stärke": 0.08}
    res.score = round(sum(res.subscores[k] * w for k, w in weights.items()), 1)
    res.signals = sig
    return res
