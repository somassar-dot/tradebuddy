"""Gesamturteil: kombiniert Fundamental-, Technik- und Sentiment-Score und erstellt einen Trade-Plan."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from . import fundamentals, sentiment, technicals
from .fundamentals import ok

HORIZONS = {
    # Anleger: Fundamentaldaten dominieren, Charttechnik fürs Timing
    "invest": {"Fundamental": 0.60, "Technik": 0.30, "Sentiment": 0.10},
    # Swing-Trader: Charttechnik dominiert, Fundamentaldaten als Qualitätsfilter
    "swing": {"Fundamental": 0.25, "Technik": 0.65, "Sentiment": 0.10},
    "balanced": {"Fundamental": 0.45, "Technik": 0.45, "Sentiment": 0.10},
}

VERDICTS = [(75, "STARKER KAUF"), (62, "KAUFEN"), (48, "HALTEN / BEOBACHTEN"), (35, "REDUZIEREN"), (0, "VERKAUFEN / MEIDEN")]


@dataclass
class Report:
    ticker: str
    horizon: str
    price: float
    date: str
    currency: str
    scores: dict = field(default_factory=dict)
    overall: float = math.nan
    verdict: str = ""
    confidence: str = ""
    plan: dict = field(default_factory=dict)
    tech: object = None
    fund: object = None
    news: dict = field(default_factory=dict)
    insider: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    name: str = ""

    def summary(self) -> dict:
        t, f = self.tech, self.fund
        return {
            "ticker": self.ticker, "name": self.name, "datum": self.date, "kurs": self.price, "währung": self.currency,
            "horizont": self.horizon, "gesamt": self.overall, "urteil": self.verdict, "konfidenz": self.confidence,
            "scores": self.scores,
            "technik": {"score": t.score, "trend": t.trend, "teilscores": t.subscores, "indikatoren": t.indicators,
                        "performance": t.performance, "unterstützungen": t.supports, "widerstände": t.resistances,
                        "signale": [(s.area, s.text, s.weight) for s in t.signals]},
            "fundamental": {"score": f.score, "teilscores": f.subscores, "kennzahlen": f.metrics,
                            "piotroski": f.piotroski.get("score"), "altman": f.altman, "dcf": f.dcf,
                            "fair_value": f.fair_value, "signale": f.signals},
            "news": self.news, "insider": self.insider, "plan": self.plan, "warnungen": self.warnings,
        }


def trade_plan(tech, fair_value: float, account: float, risk_pct: float) -> dict:
    p = tech.price
    a = tech.indicators.get("atr14") or p * 0.025
    sup = [l for l, _ in tech.supports]
    res = [l for l, _ in tech.resistances]
    ema21 = tech.indicators.get("ema21", math.nan)
    # Einstieg: im Aufwärtstrend Rücksetzer an EMA21/nächste Unterstützung, sonst erst nach Bestätigung
    if tech.trend == "Aufwärtstrend":
        zone_lo = max([s for s in sup if s > p - 2 * a] or [p - a])
        zone_hi = p if tech.indicators.get("ext_ema21_atr", 0) <= 1.5 else max(zone_lo, ema21 if ok(ema21) else p)
        typ = "Pullback-Kauf im Aufwärtstrend"
    elif tech.trend == "Abwärtstrend":
        trig = res[0] if res else p + a
        zone_lo, zone_hi = trig, trig + 0.3 * a
        typ = "Nur bei Trendwende: Kauf erst über Widerstand"
    else:
        zone_lo = sup[0] if sup else p - a
        zone_hi = p
        typ = "Range: Kauf nahe Unterstützung"
    entry = (zone_lo + zone_hi) / 2
    # Stop: unter nächster relevanter Unterstützung unterhalb der Einstiegszone, mind. 1 ATR, max. 3 ATR
    below = [s for s in sup if s < zone_lo - 0.2 * a]
    stop = (below[0] - 0.5 * a) if below else entry - 2 * a
    stop = min(stop, entry - 1.0 * a)
    stop = max(stop, entry - 3.0 * a)
    risk = entry - stop
    hurdles = [r for r in res if entry < r <= entry + risk]  # Widerstände vor CRV 1 = Hürden, keine Ziele
    targets = [r for r in res if r > entry + risk][:2]
    if len(targets) < 2:
        targets.append(entry + 3 * risk if not targets else max(targets[-1] + 2 * a, entry + 3 * risk))
    if len(targets) < 2:
        targets.append(entry + 4 * risk)
    if ok(fair_value) and fair_value > targets[-1]:
        targets.append(fair_value)
    crv = [(t - entry) / risk for t in targets] if risk > 0 else []
    shares = int((account * risk_pct / 100) / risk) if risk > 0 else 0
    shares = min(shares, int(account * 0.25 / entry)) if entry > 0 else 0  # max. 25% Depotanteil
    return {
        "setup": typ, "einstieg_zone": [round(zone_lo, 2), round(zone_hi, 2)], "einstieg": round(entry, 2),
        "stop": round(stop, 2), "stop_abstand_%": round(risk / entry * 100, 2), "ziele": [round(t, 2) for t in targets],
        "crv": [round(c, 2) for c in crv], "stück": shares, "positionswert": round(shares * entry, 2),
        "risiko_eur": round(shares * risk, 2), "hürden": [round(h, 2) for h in hurdles], "konto": account, "risiko_%": risk_pct, "atr": round(a, 2),
    }


def run(bundle, horizon: str = "invest", account: float = 10000, risk_pct: float = 1.0,
        wacc: float = 0.09) -> Report:
    tech = technicals.analyze(bundle.daily, bundle.weekly, bundle.benchmark)
    fund = fundamentals.analyze(bundle, tech.price, wacc=wacc)
    nws = sentiment.news(bundle.news, bundle.ticker)
    ins = sentiment.insider(bundle.insider)
    sent = [x for x in (nws.get("score"), ins.get("score")) if ok(x)]
    sent_score = sum(sent) / len(sent) if sent else math.nan
    rep = Report(bundle.ticker, horizon, tech.price, tech.date, fund.currency, tech=tech, fund=fund, news=nws, insider=ins)
    rep.name = (bundle.overview or {}).get("Name") or (bundle.extra or {}).get("name", "")
    rep.scores = {"Fundamental": fund.score, "Technik": tech.score, "Sentiment": sent_score}
    w = HORIZONS.get(horizon, HORIZONS["invest"])
    have = {k: v for k, v in rep.scores.items() if ok(v)}
    rep.overall = round(sum(have[k] * w[k] for k in have) / sum(w[k] for k in have), 1)

    # Veto-Regeln eines vorsichtigen Analysten
    verdict = next(v for th, v in VERDICTS if rep.overall >= th)
    if fund.altman.get("zone") == "Gefahrenzone" and verdict in ("STARKER KAUF", "KAUFEN"):
        verdict = "HALTEN / BEOBACHTEN"; rep.warnings.append("Veto: Altman-Z in Gefahrenzone – kein Kaufurteil trotz guter Scores.")
    if tech.trend == "Abwärtstrend" and verdict == "STARKER KAUF":
        verdict = "KAUFEN"; rep.warnings.append("Herabgestuft: langfristiger Abwärtstrend – Timing abwarten.")
    if ok(fund.fair_value.get("upside_%")) and fund.fair_value["upside_%"] < -30 and verdict == "STARKER KAUF":
        verdict = "KAUFEN"; rep.warnings.append("Herabgestuft: Kurs deutlich über modellbasiertem fairen Wert.")
    up = fund.fair_value.get("upside_%")
    if ok(up) and up < -25:
        if horizon == "invest" and verdict in ("STARKER KAUF", "KAUFEN"):
            verdict = "HALTEN / BEOBACHTEN"
            rep.warnings.append(f"Bewertungs-Veto: modellbasierter Fair Value liegt {abs(up):.0f}% unter dem Kurs – für Anleger erst nach Rücksetzer interessant.")
        else:
            rep.warnings.append(f"Fair Value liegt {abs(up):.0f}% unter dem Kurs – Trade rein technisch begründet, enger Stop.")
    rep.verdict = verdict

    # Konfidenz: Datenabdeckung und Einigkeit Fundamental vs. Technik
    agree = abs((fund.score if ok(fund.score) else 50) - tech.score)
    cov = fund.coverage
    rep.confidence = "hoch" if agree < 15 and cov > 0.8 else ("mittel" if agree < 30 else "niedrig")
    if agree >= 30:
        rep.warnings.append(f"Fundamental ({fund.score:.0f}) und Technik ({tech.score:.0f}) widersprechen sich deutlich.")
    for m in bundle.missing:
        if m in ("daily", "weekly", "income", "balance", "cashflow"):
            rep.warnings.append(f"Datenlücke: '{m}' fehlt – Ergebnis eingeschränkt.")
    rep.plan = trade_plan(tech, fund.fair_value.get("fair_value", math.nan), account, risk_pct)
    return rep
