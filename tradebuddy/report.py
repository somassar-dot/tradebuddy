"""HTML-, Markdown- und JSON-Report."""
from __future__ import annotations

import json
import math
import re
from html import escape

from . import charts
from .fundamentals import ok

DISCLAIMER = ("Keine Anlageberatung. Tradebuddy erstellt eine automatisierte, modellbasierte Analyse aus öffentlich "
              "verfügbaren Daten (Alpha Vantage u. a.). Daten können verzögert, unvollständig oder fehlerhaft sein. "
              "Jede Anlageentscheidung triffst du selbst und auf eigenes Risiko.")


def f(v, d=2, suf=""):
    if isinstance(v, (int, float)) and ok(float(v)):
        return f"{v:,.{d}f}{suf}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "–"


def tone(score):
    if not ok(score):
        return "neutral"
    return "pos" if score >= 62 else ("neg" if score < 40 else "neutral")


def md_to_html(md: str) -> str:
    out, in_list = [], False
    for line in md.splitlines():
        t = line.rstrip()
        h = re.match(r"^(#{1,4})\s+(.*)", t)
        li = re.match(r"^\s*[-*]\s+(.*)", t)
        def inline(x):
            x = escape(x)
            x = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", x)
            x = re.sub(r"\[(.+?)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', x)
            return x
        if li:
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline(li.group(1))}</li>")
            continue
        if in_list:
            out.append("</ul>"); in_list = False
        if h:
            lvl = min(len(h.group(1)) + 2, 5)
            out.append(f"<h{lvl}>{inline(h.group(2))}</h{lvl}>")
        elif t:
            out.append(f"<p>{inline(t)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#14171c;--mute:#5d6673;--line:#e3e6eb;--up:#138a4f;--dn:#d1343a;--acc:#2f5bea;
--c1:#e08a00;--c2:#7a4fd6;--bb:rgba(47,91,234,.07);--area:rgba(47,91,234,.08);--neutral:#8a6d00}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1216;--card:#171b21;--ink:#e8ebef;--mute:#98a2b0;
--line:#2a3039;--up:#2fbf71;--dn:#ff5c61;--acc:#6f8fff;--c1:#ffb23e;--c2:#b18cff;--bb:rgba(111,143,255,.10);--area:rgba(111,143,255,.12);--neutral:#e0c050}}
:root[data-theme="dark"]{--bg:#0f1216;--card:#171b21;--ink:#e8ebef;--mute:#98a2b0;--line:#2a3039;--up:#2fbf71;--dn:#ff5c61;
--acc:#6f8fff;--c1:#ffb23e;--c2:#b18cff;--bb:rgba(111,143,255,.10);--area:rgba(111,143,255,.12);--neutral:#e0c050}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Inter,system-ui,-apple-system,Segoe UI,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:24px 16px 60px}
header{display:flex;flex-wrap:wrap;justify-content:space-between;gap:16px;align-items:flex-end;margin-bottom:18px}
h1{margin:0;font-size:28px;letter-spacing:-.02em}h1 small{font-size:15px;color:var(--mute);font-weight:500;margin-left:8px}
h2{font-size:18px;margin:0 0 12px}h3,h4,h5{margin:16px 0 6px}
.brand{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--acc);font-weight:700}
.price{font-size:26px;font-weight:700;font-variant-numeric:tabular-nums}.mute{color:var(--mute)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin:14px 0;overflow:hidden}
.grid{display:grid;gap:14px}.g3{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}.g2{grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}
.verdict{display:flex;flex-wrap:wrap;align-items:center;gap:18px}
.badge{font-weight:800;font-size:20px;padding:10px 16px;border-radius:12px;color:#fff}
.badge.pos{background:var(--up)}.badge.neg{background:var(--dn)}.badge.neutral{background:var(--neutral)}
.score{font-size:34px;font-weight:800;font-variant-numeric:tabular-nums}
.bar{height:8px;background:var(--line);border-radius:6px;overflow:hidden;margin-top:6px}.bar i{display:block;height:100%;border-radius:6px}
.bar i.pos{background:var(--up)}.bar i.neg{background:var(--dn)}.bar i.neutral{background:var(--neutral)}
.kv{display:flex;justify-content:space-between;border-bottom:1px dashed var(--line);padding:5px 0;gap:10px}.kv span:last-child{font-variant-numeric:tabular-nums;font-weight:600}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}td,th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right}td:first-child,th:first-child{text-align:left}
th{color:var(--mute);font-weight:600;font-size:13px}
ul.sig{list-style:none;padding:0;margin:0}ul.sig li{padding:6px 0 6px 26px;position:relative;border-bottom:1px solid var(--line)}
ul.sig li:before{position:absolute;left:4px;top:6px;font-weight:800}
ul.sig li.p:before{content:"▲";color:var(--up)}ul.sig li.n:before{content:"▼";color:var(--dn)}ul.sig li.o:before{content:"●";color:var(--mute)}
.tag{display:inline-block;font-size:11px;color:var(--mute);border:1px solid var(--line);border-radius:6px;padding:0 6px;margin-right:6px}
.warn{border-left:4px solid var(--dn)}
svg.chart{width:100%;height:auto;display:block}
.chart .grid{stroke:var(--line);stroke-width:1}.chart .grid.mid{stroke-dasharray:3 3}
.chart .ax,.chart .pt{fill:var(--mute);font-size:11px}.chart .lbl{font-size:11px;font-weight:600}.chart .halo,.chart .lbl{paint-order:stroke;stroke:var(--card);stroke-width:3px;stroke-linejoin:round}
.chart rect.up,.chart .wick.up{fill:var(--up);stroke:var(--up)}.chart rect.dn,.chart .wick.dn{fill:var(--dn);stroke:var(--dn)}
.chart .vol{opacity:.35}.chart .hist{opacity:.55}.chart .bb{fill:var(--bb)}.chart .area{fill:var(--area)}
.chart .l-sma20{stroke:var(--c1)}.chart .l-sma50{stroke:var(--c2)}.chart .l-close{stroke:var(--acc)}.chart .l-rsi{stroke:var(--acc)}
.chart .l-macd{stroke:var(--acc)}.chart .l-sig{stroke:var(--c1)}
.chart .sup{stroke:var(--up);stroke-dasharray:6 4;opacity:.8}.chart .res{stroke:var(--dn);stroke-dasharray:6 4;opacity:.8}
.chart .sup-t{fill:var(--up)}.chart .res-t{fill:var(--dn)}
.chart .entry{stroke:var(--acc);stroke-width:2}.chart .entry-t{fill:var(--acc)}.chart .stop{stroke:var(--dn);stroke-width:2}.chart .stop-t{fill:var(--dn)}
.chart .tgt{stroke:var(--up);stroke-width:2}.chart .tgt-t{fill:var(--up)}
.chart .b1{fill:var(--acc)}.chart .b2{fill:var(--c1)}.chart .b3{fill:var(--c2)}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--mute);margin-top:6px}.legend i{display:inline-block;width:12px;height:3px;margin-right:5px;vertical-align:middle}
.notes p{margin:6px 0}.foot{font-size:12px;color:var(--mute);margin-top:30px}
a{color:var(--acc)}
"""


def _scorebox(name, v):
    t = tone(v)
    return (f'<div><div class="kv" style="border:0"><span>{escape(name)}</span><span>{f(v, 0)}</span></div>'
            f'<div class="bar"><i class="{t}" style="width:{(v if ok(v) else 0):.0f}%"></i></div></div>')


def _signals(items):
    out = []
    for area, text, w in items:
        c = "p" if w > 0 else ("n" if w < 0 else "o")
        out.append(f'<li class="{c}"><span class="tag">{escape(area)}</span>{escape(text)}</li>')
    return '<ul class="sig">' + "".join(out) + "</ul>"


def html(rep, notes_md: str = "") -> str:
    t, fu = rep.tech, rep.fund
    cur = rep.currency
    title = f"{rep.ticker}" + (f" – {rep.name}" if rep.name else "")
    vt = "pos" if "KAUF" in rep.verdict else ("neg" if rep.verdict.startswith(("VERK", "RED")) else "neutral")
    perf = " · ".join(f"{k} {f(v, 1, '%')}" for k, v in t.performance.items())
    p = rep.plan
    H = [f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tradebuddy {escape(rep.ticker)}</title><style>{CSS}</style></head><body><div class="wrap">
<header><div><div class="brand">Tradebuddy · Einzelaktien-Analyse</div><h1>{escape(title)}<small>Stand {rep.date}</small></h1>
<div class="mute">{escape(perf)}</div></div><div class="price">{f(rep.price)} {cur}</div></header>
<section class="card verdict"><span class="badge {vt}">{escape(rep.verdict)}</span>
<div><div class="mute">Gesamtscore ({escape(rep.horizon)})</div><div class="score">{f(rep.overall, 0)}<span class="mute" style="font-size:16px">/100</span></div></div>
<div style="flex:1;min-width:220px" class="grid">{''.join(_scorebox(k, v) for k, v in rep.scores.items())}</div>
<div class="mute">Konfidenz: <strong>{escape(rep.confidence)}</strong></div></section>"""]
    if rep.warnings:
        H.append('<section class="card warn"><h2>Hinweise</h2><ul>' + "".join(f"<li>{escape(w)}</li>" for w in rep.warnings) + "</ul></section>")
    if notes_md.strip():
        H.append(f'<section class="card notes"><h2>Analystenkommentar</h2>{md_to_html(notes_md)}</section>')
    # Trade-Plan
    crv = ", ".join(f"{f(c, 1)}" for c in p["crv"])
    H.append(f"""<section class="card"><h2>Trade-Plan · {escape(p['setup'])}</h2><div class="grid g3">
<div class="kv"><span>Einstiegszone</span><span>{f(p['einstieg_zone'][0])} – {f(p['einstieg_zone'][1])}</span></div>
<div class="kv"><span>Stop-Loss</span><span>{f(p['stop'])} ({f(p['stop_abstand_%'], 1, '%')})</span></div>
<div class="kv"><span>Kursziele</span><span>{' / '.join(f(x) for x in p['ziele'])}</span></div>
<div class="kv"><span>Chance/Risiko</span><span>{crv}</span></div>
{f'<div class="kv"><span>Hürden (Widerstand vor CRV 1)</span><span>{" / ".join(f(x) for x in p["hürden"])}</span></div>' if p.get("hürden") else ""}
<div class="kv"><span>Positionsgröße</span><span>{p['stück']} Stk. ≈ {f(p['positionswert'], 0)} {cur}</span></div>
<div class="kv"><span>Max. Verlust</span><span>{f(p['risiko_eur'], 0)} {cur} ({f(p['risiko_%'], 1, '%')} v. {f(p['konto'], 0)})</span></div>
</div><p class="mute" style="font-size:13px">Stop basiert auf Unterstützung bzw. ATR ({f(p['atr'])}). Positionsgröße: festes Risiko je Trade, max. 25 % Depotanteil.</p></section>""")
    # Charts
    if "daily" in t.series:
        H.append(f"""<section class="card"><h2>Tageschart (100 Tage)</h2>{charts.price_chart(t.series['daily'], t.supports, t.resistances, p)}
<div class="legend"><span><i style="background:var(--c1)"></i>SMA 20</span><span><i style="background:var(--c2)"></i>SMA 50</span>
<span><i style="background:var(--bb);height:10px"></i>Bollinger 20/2</span><span><i style="background:var(--up)"></i>Unterstützung / Ziel</span>
<span><i style="background:var(--dn)"></i>Widerstand / Stop</span><span><i style="background:var(--acc)"></i>Einstieg</span></div></section>""")
    if "weekly" in t.series:
        H.append(f"""<section class="card"><h2>Wochenchart (3 Jahre)</h2>{charts.weekly_chart(t.series['weekly'])}
<div class="legend"><span><i style="background:var(--acc)"></i>Schlusskurs</span><span><i style="background:var(--c1)"></i>SMA 10 Wochen</span>
<span><i style="background:var(--c2)"></i>SMA 40 Wochen (≈200 Tage)</span></div></section>""")
    # Signale
    H.append(f"""<section class="grid g2"><div class="card"><h2>Charttechnik · {f(t.score, 0)}/100 · {escape(t.trend)}</h2>
{''.join(_scorebox(k, v) for k, v in t.subscores.items())}<h3>Signale</h3>{_signals([(s.area, s.text, s.weight) for s in t.signals])}</div>
<div class="card"><h2>Fundamental · {f(fu.score, 0)}/100</h2>{''.join(_scorebox(k, v) for k, v in fu.subscores.items())}
<h3>Signale</h3>{_signals(fu.signals)}</div></section>""")
    # Kennzahlen
    ind = t.indicators
    tech_rows = [("RSI 14 (Tag / Woche)", f"{f(ind.get('rsi14'), 0)} / {f(ind.get('rsi14w'), 0)}"),
                 ("SMA 20 / 50", f"{f(ind.get('sma20'))} / {f(ind.get('sma50'))}"),
                 ("SMA 40 Wochen (≈200T)", f(ind.get("sma40w"))), ("MACD-Histogramm", f(ind.get("macd_hist"))),
                 ("ADX 14", f(ind.get("adx14"), 0)), ("ATR 14", f"{f(ind.get('atr14'))} ({f(ind.get('atr_pct'), 1, '%')})"),
                 ("Stochastik %K/%D", f"{f(ind.get('stoch_k'), 0)} / {f(ind.get('stoch_d'), 0)}"),
                 ("52W Hoch / Tief", f"{f(ind.get('high_52w'))} / {f(ind.get('low_52w'))}"),
                 ("Abstand 52W-Hoch", f(ind.get("dist_52w_high_pct"), 1, "%")),
                 ("Unterstützungen", ", ".join(f(l) for l, _ in t.supports[:3]) or "–"),
                 ("Widerstände", ", ".join(f(l) for l, _ in t.resistances[:3]) or "–")]
    if ok(ind.get("rel_strength_3m_pp", math.nan)):
        tech_rows.append(("Rel. Stärke 3M / 6M (PP)", f"{f(ind['rel_strength_3m_pp'], 1)} / {f(ind['rel_strength_6m_pp'], 1)}"))
    fm = fu.metrics
    H.append('<section class="grid g2"><div class="card"><h2>Technische Kennzahlen</h2>' +
             "".join(f'<div class="kv"><span>{escape(a)}</span><span>{b}</span></div>' for a, b in tech_rows) +
             '</div><div class="card"><h2>Fundamentale Kennzahlen</h2>' +
             "".join(f'<div class="kv"><span>{escape(k)}</span><span>{f(v, 2)}</span></div>' for k, v in fm.items() if k != "Kurs") +
             f'<div class="kv"><span>Piotroski F-Score</span><span>{fu.piotroski.get("score", "–")}/9</span></div>'
             f'<div class="kv"><span>Altman Z-Score</span><span>{f(fu.altman.get("z"))} ({escape(fu.altman.get("zone", ""))})</span></div></div></section>')
    # Bewertung
    if fu.dcf.get("szenarien"):
        rows = "".join(f"<tr><td>{k}</td><td>{f(v['wachstum_%'], 1, '%')}</td><td>{f(v['wacc_%'], 1, '%')}</td><td>{f(v['wert_je_aktie'])}</td>"
                       f"<td>{f((v['wert_je_aktie'] / rep.price - 1) * 100 if ok(v['wert_je_aktie']) else math.nan, 0, '%')}</td></tr>"
                       for k, v in fu.dcf["szenarien"].items())
        comp = "".join(f'<div class="kv"><span>{escape(k)}</span><span>{f(v)}</span></div>' for k, v in fu.fair_value["komponenten"].items())
        H.append(f"""<section class="card"><h2>Bewertung</h2><div class="grid g2"><div>
<table><tr><th>DCF-Szenario</th><th>Wachstum</th><th>WACC</th><th>Wert/Aktie</th><th>vs. Kurs</th></tr>{rows}</table>
<p class="mute" style="font-size:13px">FCF-Basis {f(fu.dcf['fcf_basis_mrd'])} Mrd. {cur}{' (nach Abzug aktienbasierter Vergütung)' if fu.dcf.get('sbc_abgezogen') else ''},
10 Jahre fallendes Wachstum, ewiges Wachstum {f(fu.dcf['terminal'] * 100, 1, '%')}. Reverse-DCF: Markt preist {f(fu.dcf.get('impliziertes_wachstum_%'), 1, '%')} Anfangswachstum ein.</p></div>
<div>{comp}<div class="kv"><span>Faires KGV (wachstumsadj.)</span><span>{f(fu.fair_value['faires_kgv'], 1)}</span></div>
<div class="kv"><span><strong>Fair Value (gewichtet)</strong></span><span>{f(fu.fair_value['fair_value'])} {cur}</span></div>
<div class="kv"><span>Potenzial</span><span>{f(fu.fair_value['upside_%'], 0, '%')}</span></div></div></div></section>""")
    if fu.history.get("annual"):
        H.append(f"""<section class="card"><h2>Umsatz, Gewinn & Free Cashflow (Mrd. {cur})</h2>
{charts.bars(fu.history['annual'], [('umsatz', 'b1'), ('gewinn', 'b2'), ('fcf', 'b3')])}
<div class="legend"><span><i style="background:var(--acc)"></i>Umsatz</span><span><i style="background:var(--c1)"></i>Nettogewinn</span><span><i style="background:var(--c2)"></i>Free Cashflow</span></div></section>""")
    # News / Insider
    nw, ins = rep.news, rep.insider
    if nw.get("artikel") or ins.get("käufe") or ins.get("verkäufe"):
        items = "".join(f'<li class="{"p" if a["sentiment"] > 0.15 else ("n" if a["sentiment"] < -0.15 else "o")}"><span class="tag">{a["datum"]}</span>'
                        f'<a href="{escape(a["url"])}" target="_blank" rel="noopener">{escape(a["titel"])}</a> <span class="mute">– {escape(a["quelle"])}</span></li>'
                        for a in nw.get("top", []))
        H.append(f"""<section class="card"><h2>Nachrichten & Insider</h2>
<div class="kv"><span>News-Sentiment (30 Tage, {nw.get('artikel', 0)} Artikel)</span><span>{escape(nw.get('label', '–'))} ({f(nw.get('score'), 0)}/100)</span></div>
<div class="kv"><span>Insider (letzte {ins.get('monate', 6)} Monate)</span><span>{ins.get('käufe', 0)} Käufe / {ins.get('verkäufe', 0)} Verkäufe</span></div>
<ul class="sig">{items}</ul></section>""")
    H.append(f'<p class="foot">{escape(DISCLAIMER)}<br>Erstellt mit Tradebuddy. Datenquelle: Alpha Vantage (Kurse, Finanzberichte, News, Insider).</p></div></body></html>')
    return "\n".join(H)


def markdown(rep) -> str:
    t, fu, p = rep.tech, rep.fund, rep.plan
    L = [f"# Tradebuddy: {rep.ticker}{' – ' + rep.name if rep.name else ''} ({rep.date})", "",
         f"**Urteil: {rep.verdict}** · Gesamtscore {f(rep.overall, 0)}/100 ({rep.horizon}) · Konfidenz {rep.confidence}",
         f"Kurs {f(rep.price)} {rep.currency} · " + " · ".join(f"{k} {f(v, 0)}" for k, v in rep.scores.items()), ""]
    for w in rep.warnings:
        L.append(f"> ⚠️ {w}")
    L += ["", "## Trade-Plan", f"- Setup: {p['setup']}",
          f"- Einstieg: {f(p['einstieg_zone'][0])} – {f(p['einstieg_zone'][1])}",
          f"- Stop: {f(p['stop'])} ({f(p['stop_abstand_%'], 1, '%')})",
          f"- Ziele: {' / '.join(f(x) for x in p['ziele'])} (CRV {', '.join(f(c, 1) for c in p['crv'])})",
          f"- Position: {p['stück']} Stk., Risiko {f(p['risiko_eur'], 0)} {rep.currency}", "",
          f"## Charttechnik ({f(t.score, 0)}/100, {t.trend})"]
    L += [f"- {'▲' if s.weight > 0 else '▼' if s.weight < 0 else '•'} [{s.area}] {s.text}" for s in t.signals]
    L += ["", f"## Fundamental ({f(fu.score, 0)}/100)"]
    L += [f"- {'▲' if w > 0 else '▼' if w < 0 else '•'} [{a}] {x}" for a, x, w in fu.signals]
    L += ["", "| Kennzahl | Wert |", "|---|---|"] + [f"| {k} | {f(v)} |" for k, v in fu.metrics.items()]
    L += ["", f"_{DISCLAIMER}_"]
    return "\n".join(L)


def to_json(rep) -> str:
    def clean(o):
        if isinstance(o, float):
            return None if math.isnan(o) or math.isinf(o) else round(o, 4)
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if hasattr(o, "item"):
            return clean(o.item())
        return o
    return json.dumps(clean(rep.summary()), ensure_ascii=False, indent=2)
