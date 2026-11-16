"""Fundamentalanalyse: Kennzahlen, Qualitäts-Scores, DCF und Fundamental-Score."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

nan = math.nan


def ok(x) -> bool:
    return x is not None and isinstance(x, (int, float)) and not math.isnan(x) and not math.isinf(x)


def g(rep: dict | None, *keys) -> float:
    """Erstes verfügbares Feld."""
    if not rep:
        return nan
    for k in keys:
        v = rep.get(k)
        if ok(v):
            return float(v)
    return nan


def div(a, b):
    return a / b if ok(a) and ok(b) and b != 0 else nan


def ttm(quarters: list[dict], *keys, n=4, offset=0) -> float:
    qs = quarters[offset:offset + n]
    if len(qs) < n:
        return nan
    vals = [g(q, *keys) for q in qs]
    return float(sum(vals)) if all(ok(v) for v in vals) else nan


def cagr(new, old, years):
    if not (ok(new) and ok(old)) or old <= 0 or new <= 0 or years <= 0:
        return nan
    return ((new / old) ** (1 / years) - 1) * 100


def scale(x, bad, good):
    """Lineare Abbildung auf 0..100 (good kann < bad sein)."""
    if not ok(x):
        return nan
    t = (x - bad) / (good - bad)
    return float(np.clip(t, 0, 1) * 100)


def avg(vals):
    v = [x for x in vals if ok(x)]
    return float(np.mean(v)) if v else nan


@dataclass
class FundResult:
    metrics: dict = field(default_factory=dict)
    subscores: dict = field(default_factory=dict)
    score: float = nan
    piotroski: dict = field(default_factory=dict)
    altman: dict = field(default_factory=dict)
    dcf: dict = field(default_factory=dict)
    fair_value: dict = field(default_factory=dict)
    signals: list = field(default_factory=list)
    history: dict = field(default_factory=dict)
    currency: str = "USD"
    coverage: float = 0.0


def debt_of(b):
    d = g(b, "shortLongTermDebtTotal")
    if ok(d):
        return d
    parts = [g(b, "shortTermDebt", "currentDebt", "currentLongTermDebt"), g(b, "longTermDebt", "longTermDebtNoncurrent")]
    parts = [p for p in parts if ok(p)]
    return float(sum(parts)) if parts else 0.0


def cash_of(b):
    c = g(b, "cashAndShortTermInvestments", "cashAndCashEquivalentsAtCarryingValue")
    st = g(b, "shortTermInvestments")
    if ok(c) and ok(st) and abs(c - g(b, "cashAndCashEquivalentsAtCarryingValue")) < 1:
        c += st  # AV meldet teils nur Cash in cashAndShortTermInvestments
    return c if ok(c) else 0.0


def piotroski(inc, bal, cf) -> dict:
    """Piotroski F-Score (0-9) auf Jahresbasis (t vs. t-1)."""
    if len(inc) < 2 or len(bal) < 3 or len(cf) < 1:
        return {"score": nan, "details": {}}
    i0, i1 = inc[0], inc[1]
    b0, b1, b2 = bal[0], bal[1], bal[2]
    c0 = cf[0]
    ta0, ta1, ta2 = g(b0, "totalAssets"), g(b1, "totalAssets"), g(b2, "totalAssets")
    roa0 = div(g(i0, "netIncome"), (ta0 + ta1) / 2)
    roa1 = div(g(i1, "netIncome"), (ta1 + ta2) / 2)
    cfo = g(c0, "operatingCashflow")
    lev0 = div(g(b0, "longTermDebt", "longTermDebtNoncurrent"), ta0)
    lev1 = div(g(b1, "longTermDebt", "longTermDebtNoncurrent"), ta1)
    cr0 = div(g(b0, "totalCurrentAssets"), g(b0, "totalCurrentLiabilities"))
    cr1 = div(g(b1, "totalCurrentAssets"), g(b1, "totalCurrentLiabilities"))
    sh0, sh1 = g(b0, "commonStockSharesOutstanding"), g(b1, "commonStockSharesOutstanding")
    gm0 = div(g(i0, "grossProfit"), g(i0, "totalRevenue"))
    gm1 = div(g(i1, "grossProfit"), g(i1, "totalRevenue"))
    at0 = div(g(i0, "totalRevenue"), ta1)
    at1 = div(g(i1, "totalRevenue"), ta2)
    tests = {
        "ROA positiv": ok(roa0) and roa0 > 0,
        "Operativer Cashflow positiv": ok(cfo) and cfo > 0,
        "ROA steigend": ok(roa0) and ok(roa1) and roa0 > roa1,
        "Cashflow > Gewinn (Qualität)": ok(cfo) and ok(g(i0, "netIncome")) and cfo > g(i0, "netIncome"),
        "Verschuldung gesunken": (ok(lev0) and ok(lev1) and lev0 <= lev1) or (not ok(lev0) and not ok(lev1)),
        "Liquidität verbessert": ok(cr0) and ok(cr1) and cr0 > cr1,
        "Keine Verwässerung": ok(sh0) and ok(sh1) and sh0 <= sh1 * 1.005,
        "Bruttomarge gestiegen": ok(gm0) and ok(gm1) and gm0 > gm1,
        "Kapitalumschlag gestiegen": ok(at0) and ok(at1) and at0 > at1,
    }
    return {"score": int(sum(tests.values())), "details": tests}


def altman_z(inc_ttm: dict, bal: dict, mcap: float) -> dict:
    ta = g(bal, "totalAssets")
    tl = g(bal, "totalLiabilities")
    wc = g(bal, "totalCurrentAssets") - g(bal, "totalCurrentLiabilities")
    re_ = g(bal, "retainedEarnings")
    ebit = inc_ttm.get("ebit", nan)
    sales = inc_ttm.get("revenue", nan)
    if not all(ok(x) for x in (ta, tl, wc, ebit, sales, mcap)) or ta == 0:
        return {"z": nan, "zone": "n/a"}
    re_ = re_ if ok(re_) else 0.0
    z = 1.2 * wc / ta + 1.4 * re_ / ta + 3.3 * ebit / ta + 0.6 * mcap / max(tl, 1) + 1.0 * sales / ta
    zone = "sicher" if z > 2.99 else ("Grauzone" if z > 1.81 else "Gefahrenzone")
    return {"z": round(z, 2), "zone": zone}


def dcf(fcf: float, shares: float, net_debt: float, growth: float, wacc: float = 0.09,
        terminal: float = 0.025, years: int = 10) -> float:
    """Zweistufiges DCF: Wachstum `growth` linear abnehmend auf `terminal` über `years` Jahre."""
    if not (ok(fcf) and ok(shares)) or fcf <= 0 or shares <= 0 or wacc <= terminal:
        return nan
    pv, cash = 0.0, fcf
    for y in range(1, years + 1):
        gr = growth - (growth - terminal) * (y - 1) / (years - 1)
        cash *= 1 + gr
        pv += cash / (1 + wacc) ** y
    tv = cash * (1 + terminal) / (wacc - terminal)
    pv += tv / (1 + wacc) ** years
    return (pv - net_debt) / shares


def reverse_dcf(price, fcf, shares, net_debt, wacc=0.09, terminal=0.025):
    """Welches Anfangswachstum preist der Markt ein?"""
    if not (ok(price) and ok(fcf)) or fcf <= 0:
        return nan
    lo, hi = -0.2, 0.6
    for _ in range(60):
        mid = (lo + hi) / 2
        v = dcf(fcf, shares, net_debt, mid, wacc, terminal)
        if not ok(v):
            return nan
        lo, hi = (mid, hi) if v < price else (lo, mid)
    return mid * 100


def analyze(bundle, price: float, wacc: float = 0.09, terminal: float = 0.025) -> FundResult:
    r = FundResult()
    inc_q, inc_a = bundle.income["quarterly"], bundle.income["annual"]
    bal_q, bal_a = bundle.balance["quarterly"], bundle.balance["annual"]
    cf_q, cf_a = bundle.cashflow["quarterly"], bundle.cashflow["annual"]
    ov = bundle.overview or {}
    ex = bundle.extra or {}
    m = r.metrics
    if not (inc_q or inc_a):
        r.signals.append(("Daten", "Keine Finanzberichte vorhanden – Fundamental-Score nicht berechenbar", 0))
        return r
    r.currency = (inc_q or inc_a)[0].get("reportedCurrency", "USD")
    b0 = bal_q[0] if bal_q else (bal_a[0] if bal_a else {})

    # ---------------------------------------------------- TTM-Werte
    use_q = len(inc_q) >= 4 and len(cf_q) >= 4
    def T(src_q, src_a, *keys, offset=0):
        v = ttm(src_q, *keys, offset=offset) if use_q else nan
        if not ok(v) and len(src_a) > offset // 4:
            v = g(src_a[offset // 4], *keys)
        return v
    rev = T(inc_q, inc_a, "totalRevenue")
    rev_prev = T(inc_q, inc_a, "totalRevenue", offset=4)
    gp = T(inc_q, inc_a, "grossProfit")
    op = T(inc_q, inc_a, "operatingIncome")
    ni = T(inc_q, inc_a, "netIncome")
    ni_prev = T(inc_q, inc_a, "netIncome", offset=4)
    ebit = T(inc_q, inc_a, "ebit", "operatingIncome")
    ebitda = T(inc_q, inc_a, "ebitda")
    if not ok(ebitda):
        ebitda = ebit + T(inc_q, inc_a, "depreciationAndAmortization") if ok(ebit) else nan
    int_exp = T(inc_q, inc_a, "interestExpense")
    tax = T(inc_q, inc_a, "incomeTaxExpense")
    pretax = T(inc_q, inc_a, "incomeBeforeTax")
    ocf = T(cf_q, cf_a, "operatingCashflow")
    capex = T(cf_q, cf_a, "capitalExpenditures")
    sbc = T(cf_q, cf_a, "stockBasedCompensation")
    divs = T(cf_q, cf_a, "dividendPayout", "dividendPayoutCommonStock")
    buyb = T(cf_q, cf_a, "paymentsForRepurchaseOfCommonStock", "paymentsForRepurchaseOfEquity")
    if not ok(buyb):  # AV meldet Rückkäufe teils als negatives "proceedsFromRepurchaseOfEquity"
        pr = T(cf_q, cf_a, "proceedsFromRepurchaseOfEquity")
        buyb = abs(pr) if ok(pr) and pr < 0 else nan
    fcf = ocf - abs(capex) if ok(ocf) and ok(capex) else ocf
    fcf_prev = nan
    if use_q and len(cf_q) >= 8:
        fcf_prev = ttm(cf_q, "operatingCashflow", offset=4) - abs(ttm(cf_q, "capitalExpenditures", offset=4) or 0)

    shares = g(b0, "commonStockSharesOutstanding")
    if not ok(shares):
        shares = g(ov, "SharesOutstanding")
    mcap = price * shares if ok(shares) else g(ov, "MarketCapitalization")
    debt, cash = debt_of(b0), cash_of(b0)
    lt_inv = g(b0, "longTermInvestments")
    net_debt = debt - cash
    ev = mcap + net_debt if ok(mcap) else nan
    equity = g(b0, "totalShareholderEquity")
    eq_prev = g(bal_q[4], "totalShareholderEquity") if len(bal_q) > 4 else g(bal_a[1], "totalShareholderEquity") if len(bal_a) > 1 else equity
    ta = g(b0, "totalAssets")
    eps_ttm = div(ni, shares)
    tax_rate = float(np.clip(div(tax, pretax), 0, 0.35)) if ok(div(tax, pretax)) else 0.21
    invested = debt + (equity if ok(equity) else 0) - cash
    m.update({
        "Kurs": price, "Aktien (Mio.)": shares / 1e6 if ok(shares) else nan,
        "Marktkapitalisierung (Mrd.)": mcap / 1e9 if ok(mcap) else nan,
        "Enterprise Value (Mrd.)": ev / 1e9 if ok(ev) else nan,
        "Nettoverschuldung (Mrd.)": net_debt / 1e9,
        "Umsatz TTM (Mrd.)": rev / 1e9 if ok(rev) else nan,
        "Nettogewinn TTM (Mrd.)": ni / 1e9 if ok(ni) else nan,
        "Free Cashflow TTM (Mrd.)": fcf / 1e9 if ok(fcf) else nan,
        "EPS TTM": eps_ttm,
        # Bewertung
        "KGV (P/E)": div(mcap, ni) if ok(ni) and ni > 0 else nan,
        "KUV (P/S)": div(mcap, rev),
        "KBV (P/B)": div(mcap, equity) if ok(equity) and equity > 0 else nan,
        "EV/EBITDA": div(ev, ebitda) if ok(ebitda) and ebitda > 0 else nan,
        "EV/Umsatz": div(ev, rev),
        "FCF-Rendite %": div(fcf, mcap) * 100,
        "Dividendenrendite %": div(abs(divs), mcap) * 100 if ok(divs) else 0.0,
        "Aktionärsrendite % (Div.+Rückkauf)": div(abs(divs if ok(divs) else 0) + abs(buyb if ok(buyb) else 0), mcap) * 100,
        # Profitabilität
        "Bruttomarge %": div(gp, rev) * 100,
        "Operative Marge %": div(op, rev) * 100,
        "Nettomarge %": div(ni, rev) * 100,
        "FCF-Marge %": div(fcf, rev) * 100,
        "ROE %": div(ni, (equity + eq_prev) / 2) * 100 if ok(equity) and equity > 0 else nan,
        "ROA %": div(ni, ta) * 100,
        "ROIC %": div(ebit * (1 - tax_rate), invested) * 100 if invested > 0 else nan,
        "Cash Conversion (OCF/NI)": div(ocf, ni) if ok(ni) and ni > 0 else nan,
        "SBC/Umsatz %": div(sbc, rev) * 100,
        # Wachstum
        "Umsatzwachstum TTM %": (div(rev, rev_prev) - 1) * 100,
        "Gewinnwachstum TTM %": (div(ni, ni_prev) - 1) * 100 if ok(ni_prev) and ni_prev > 0 else nan,
        "FCF-Wachstum TTM %": (div(fcf, fcf_prev) - 1) * 100 if ok(fcf_prev) and fcf_prev > 0 else nan,
        # Bilanz
        "Nettoverschuldung/EBITDA": div(net_debt, ebitda) if ok(ebitda) and ebitda > 0 else nan,
        "Verschuldungsgrad (D/E)": div(debt, equity) if ok(equity) and equity > 0 else nan,
        "Current Ratio": div(g(b0, "totalCurrentAssets"), g(b0, "totalCurrentLiabilities")),
        "Zinsdeckung (EBIT/Zins)": div(ebit, int_exp) if ok(int_exp) and int_exp > 0 else (99.0 if ok(ebit) and ebit > 0 else nan),
    })
    if ok(lt_inv) and lt_inv > 0:
        m["Langfr. Finanzanlagen (Mrd.)"] = lt_inv / 1e9

    # Mehrjahres-Wachstum
    if len(inc_a) >= 4:
        m["Umsatz-CAGR 3J %"] = cagr(g(inc_a[0], "totalRevenue"), g(inc_a[3], "totalRevenue"), 3)
    ae = (bundle.earnings or {}).get("annualEarnings") or []
    if len(ae) >= 4:
        m["EPS-CAGR 3J %"] = cagr(float(ae[0]["reportedEPS"]), float(ae[3]["reportedEPS"]), 3)
    elif len(inc_a) >= 4:
        m["EPS-CAGR 3J %"] = cagr(g(inc_a[0], "netIncome"), g(inc_a[3], "netIncome"), 3)
    if len(inc_q) >= 5:
        m["Umsatz letztes Quartal YoY %"] = (div(g(inc_q[0], "totalRevenue"), g(inc_q[4], "totalRevenue")) - 1) * 100
    eg = m.get("EPS-CAGR 3J %", nan)
    m["PEG"] = div(m["KGV (P/E)"], eg) if ok(eg) and eg > 0 else nan

    # Margentrend (operative Marge, letzte 4 Jahre)
    om = [div(g(a, "operatingIncome"), g(a, "totalRevenue")) * 100 for a in inc_a[:4]]
    if len([x for x in om if ok(x)]) >= 3:
        m["Op.-Margen-Trend 3J (PP)"] = om[0] - om[min(3, len(om) - 1)]

    # Earnings-Surprises
    qe = (bundle.earnings or {}).get("quarterlyEarnings") or []
    surprises = []
    for q in qe[:8]:
        try:
            surprises.append(float(q.get("surprisePercentage")))
        except (TypeError, ValueError):
            pass
    if surprises:
        m["Beat-Quote 8Q %"] = 100 * sum(s > 0 for s in surprises) / len(surprises)
        m["Ø Überraschung 8Q %"] = float(np.mean(surprises))
    if qe:
        r.history["next_after"] = qe[0].get("reportedDate")

    # Historie für Charts (Jahreswerte)
    r.history["annual"] = [
        {"jahr": a.get("fiscalDateEnding", "")[:4], "umsatz": g(a, "totalRevenue") / 1e9,
         "gewinn": g(a, "netIncome") / 1e9,
         "fcf": (g(c, "operatingCashflow") - abs(g(c, "capitalExpenditures"))) / 1e9 if c else nan}
        for a, c in zip(inc_a[:6], (cf_a + [None] * 6)[:6])][::-1]

    # ---------------------------------------------------- Scores
    r.piotroski = piotroski(inc_a, bal_a, cf_a)
    r.altman = altman_z({"ebit": ebit, "revenue": rev}, b0, mcap)

    # DCF-Szenarien
    base_g = avg([m.get("Umsatz-CAGR 3J %"), m.get("EPS-CAGR 3J %"), m.get("Umsatzwachstum TTM %")])
    base_g = float(np.clip((base_g if ok(base_g) else 5) / 100, -0.02, 0.20))
    if ok(ex.get("growth_override")):
        base_g = ex["growth_override"] / 100
    wacc = ex.get("wacc", wacc)
    fcf_norm = fcf - (sbc if ok(sbc) and ex.get("sbc_as_cost", True) else 0) if ok(fcf) else nan
    scen = {"Bär": (max(base_g - 0.05, -0.03), wacc + 0.01), "Basis": (base_g, wacc), "Bulle": (base_g + 0.04, wacc - 0.005)}
    r.dcf = {"fcf_basis_mrd": fcf_norm / 1e9 if ok(fcf_norm) else nan, "wacc": wacc, "terminal": terminal,
             "sbc_abgezogen": bool(ok(sbc) and ex.get("sbc_as_cost", True)), "szenarien": {}}
    for k, (gr, w) in scen.items():
        r.dcf["szenarien"][k] = {"wachstum_%": gr * 100, "wacc_%": w * 100,
                                 "wert_je_aktie": dcf(fcf_norm, shares, net_debt, gr, w, terminal)}
    r.dcf["impliziertes_wachstum_%"] = reverse_dcf(price, fcf_norm, shares, net_debt, wacc, terminal)

    # Multiplikator-Fair-Value (wachstumsadjustiertes KGV, Graham-ähnlich)
    fair_pe = float(np.clip(8.5 + 1.5 * (eg if ok(eg) else base_g * 100), 8, 35))
    pe_value = eps_ttm * fair_pe if ok(eps_ttm) and eps_ttm > 0 else nan
    analyst = ex.get("analyst_target")
    vals = {"DCF (Basis)": r.dcf["szenarien"]["Basis"]["wert_je_aktie"], "Faires KGV": pe_value}
    if ok(analyst):
        vals["Analysten-Kursziel"] = float(analyst)
    weights = {"DCF (Basis)": 0.5, "Faires KGV": 0.3, "Analysten-Kursziel": 0.2}
    num = sum(v * weights[k] for k, v in vals.items() if ok(v))
    den = sum(weights[k] for k, v in vals.items() if ok(v))
    fv = num / den if den else nan
    r.fair_value = {"komponenten": vals, "faires_kgv": fair_pe, "fair_value": fv,
                    "upside_%": (fv / price - 1) * 100 if ok(fv) else nan}

    # Teilscores
    val = avg([scale(m["KGV (P/E)"], 45, 10), scale(m["EV/EBITDA"], 30, 7), scale(m["FCF-Rendite %"], 0, 8),
               scale(m["PEG"], 3.5, 0.8), scale(r.fair_value["upside_%"], -40, 40)])
    qual = avg([scale(m["ROIC %"], 3, 25), scale(m["Operative Marge %"], 0, 30), scale(m["Bruttomarge %"], 15, 65),
                scale(m["Cash Conversion (OCF/NI)"], 0.5, 1.2), scale(m["SBC/Umsatz %"], 10, 1),
                r.piotroski["score"] / 9 * 100 if ok(r.piotroski.get("score")) else nan])
    grow = avg([scale(m["Umsatzwachstum TTM %"], -5, 20), scale(m.get("Umsatz-CAGR 3J %"), -3, 18),
                scale(m.get("EPS-CAGR 3J %"), -5, 25), scale(m["Gewinnwachstum TTM %"], -10, 30),
                scale(m.get("Op.-Margen-Trend 3J (PP)"), -5, 5)])
    health = avg([scale(m["Nettoverschuldung/EBITDA"], 4, 0), scale(m["Current Ratio"], 0.6, 2.0),
                  scale(m["Zinsdeckung (EBIT/Zins)"], 2, 15),
                  {"sicher": 100, "Grauzone": 50, "Gefahrenzone": 10}.get(r.altman["zone"], nan)])
    momo = avg([scale(m.get("Beat-Quote 8Q %"), 40, 100), scale(m.get("Ø Überraschung 8Q %"), -5, 8)])
    r.subscores = {"Bewertung": val, "Qualität": qual, "Wachstum": grow, "Bilanz": health, "Gewinndynamik": momo}
    wts = {"Bewertung": 0.27, "Qualität": 0.25, "Wachstum": 0.23, "Bilanz": 0.15, "Gewinndynamik": 0.10}
    have = {k: v for k, v in r.subscores.items() if ok(v)}
    r.score = round(sum(have[k] * wts[k] for k in have) / sum(wts[k] for k in have), 1) if have else nan
    r.coverage = sum(ok(v) for v in m.values()) / max(len(m), 1)

    # ---------------------------------------------------- Signale (Text)
    S = r.signals
    pe = m["KGV (P/E)"]
    if ok(r.fair_value["upside_%"]):
        u = r.fair_value["upside_%"]
        S.append(("Bewertung", f"Fairer Wert ≈ {fv:.2f} {r.currency} → {u:+.0f}% Potenzial", 1.5 if u > 15 else (-1.5 if u < -15 else 0)))
    if ok(r.dcf["impliziertes_wachstum_%"]):
        S.append(("Bewertung", f"Kurs impliziert ~{r.dcf['impliziertes_wachstum_%']:.1f}% FCF-Wachstum p.a. (Reverse-DCF)", 0))
    if ok(m["ROIC %"]):
        if m["ROIC %"] > 20: S.append(("Qualität", f"Exzellente Kapitalrendite: ROIC {m['ROIC %']:.0f}%", 1.5))
        elif m["ROIC %"] < 6: S.append(("Qualität", f"Schwache Kapitalrendite: ROIC {m['ROIC %']:.1f}%", -1))
    if ok(r.piotroski.get("score")):
        p = r.piotroski["score"]
        S.append(("Qualität", f"Piotroski F-Score {p}/9", 1 if p >= 7 else (-1 if p <= 3 else 0)))
    if r.altman["zone"] == "Gefahrenzone":
        S.append(("Bilanz", f"Altman-Z {r.altman['z']} – erhöhtes Insolvenzrisiko-Profil", -2))
    if ok(m["Nettoverschuldung/EBITDA"]) and m["Nettoverschuldung/EBITDA"] > 3:
        S.append(("Bilanz", f"Hohe Verschuldung: Net Debt/EBITDA {m['Nettoverschuldung/EBITDA']:.1f}×", -1))
    elif ok(m["Nettoverschuldung/EBITDA"]) and m["Nettoverschuldung/EBITDA"] < 0:
        S.append(("Bilanz", "Netto-Cash-Position", 1))
    if ok(m["Umsatzwachstum TTM %"]):
        gr = m["Umsatzwachstum TTM %"]
        S.append(("Wachstum", f"Umsatzwachstum TTM {gr:+.1f}%", 1 if gr > 10 else (-1 if gr < 0 else 0)))
    if ok(m.get("Beat-Quote 8Q %")):
        S.append(("Gewinndynamik", f"Erwartungen in {m['Beat-Quote 8Q %']:.0f}% der letzten 8 Quartale übertroffen", 1 if m['Beat-Quote 8Q %'] >= 75 else 0))
    if ok(pe) and pe > 40:
        S.append(("Bewertung", f"Ambitioniertes KGV von {pe:.0f}", -1))
    if ok(m["SBC/Umsatz %"]) and m["SBC/Umsatz %"] > 8:
        S.append(("Qualität", f"Hohe aktienbasierte Vergütung ({m['SBC/Umsatz %']:.0f}% vom Umsatz) verwässert", -1))
    return r
