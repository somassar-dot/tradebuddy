"""Kommandozeile: python -m tradebuddy <befehl> ..."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import analysis, report
from .loader import ingest, load_bundle

AV_FUNCS = {  # Dateiname -> (function, extra params) – nur kostenlose Endpunkte
    "daily": ("TIME_SERIES_DAILY", {"outputsize": "compact", "datatype": "csv"}),
    "weekly": ("TIME_SERIES_WEEKLY", {"datatype": "csv"}),
    "income": ("INCOME_STATEMENT", {}),
    "balance": ("BALANCE_SHEET", {}),
    "cashflow": ("CASH_FLOW", {}),
    "earnings": ("EARNINGS", {}),
    "news": ("NEWS_SENTIMENT", {"limit": "50"}),
    "insider": ("INSIDER_TRANSACTIONS", {}),
}


def cmd_fetch(a):
    """Direktabruf über die Alpha-Vantage-REST-API (für lokale Nutzung mit eigenem Free-Key)."""
    key = a.apikey or os.environ.get("ALPHAVANTAGE_API_KEY")
    if not key:
        sys.exit("Kein API-Key: --apikey oder ALPHAVANTAGE_API_KEY setzen (kostenlos: alphavantage.co/support/#api-key)")
    out = Path(a.data) / a.ticker.upper()
    out.mkdir(parents=True, exist_ok=True)
    jobs = dict(AV_FUNCS)
    if a.benchmark:
        jobs["benchmark"] = ("TIME_SERIES_WEEKLY", {"datatype": "csv", "_symbol": a.benchmark})
    for name, (fn, extra) in jobs.items():
        if not a.force and any((out / f"{name}.{e}").exists() and time.time() - (out / f"{name}.{e}").stat().st_mtime < 20 * 3600
                               for e in ("csv", "json")):
            print(f"  {name}: Cache (<20h) – übersprungen"); continue
        params = {"function": fn, "apikey": key}
        sym = extra.get("_symbol", a.ticker)
        params["tickers" if fn == "NEWS_SENTIMENT" else "symbol"] = sym
        params.update({k: v for k, v in extra.items() if not k.startswith("_")})
        url = "https://www.alphavantage.co/query?" + urllib.parse.urlencode(params)
        raw = urllib.request.urlopen(url, timeout=60).read().decode()
        tmp = out / f".{name}.raw"
        tmp.write_text(raw)
        try:
            p = ingest(tmp, out / name)
            print(f"  {name}: {p.name}")
        except ValueError as e:
            print(f"  {name}: FEHLER {e}")
        tmp.unlink(missing_ok=True)
        time.sleep(1.2)  # Free-Tier: max. 1 Request/Sekunde, 25/Tag


def cmd_ingest(a):
    p = ingest(a.src, Path(a.data) / a.ticker.upper() / a.kind)
    print(p)


def cmd_analyze(a):
    data_dir = Path(a.data) / a.ticker.upper() if not Path(a.ticker).is_dir() else Path(a.ticker)
    b = load_bundle(data_dir, a.ticker if not Path(a.ticker).is_dir() else None)
    if a.extra:
        b.extra.update(json.loads(a.extra))
    rep = analysis.run(b, a.horizon, a.account, a.risk, a.wacc)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{rep.ticker}_{rep.date}"
    notes = Path(a.notes).read_text(encoding="utf-8") if a.notes else ""
    (out / f"{stem}.html").write_text(report.html(rep, notes), encoding="utf-8")
    (out / f"{stem}.md").write_text(report.markdown(rep), encoding="utf-8")
    (out / f"{stem}.json").write_text(report.to_json(rep), encoding="utf-8")
    print(report.markdown(rep) if not a.quiet else "")
    print(f"\nReports: {out / stem}.html | .md | .json")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tradebuddy", description="Tradebuddy – Einzelaktien-Analyst")
    ap.add_argument("--data", default="data", help="Datenverzeichnis (Standard: data)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="Daten direkt per Alpha-Vantage-API laden")
    f.add_argument("ticker"); f.add_argument("--apikey"); f.add_argument("--benchmark", default="SPY")
    f.add_argument("--force", action="store_true")
    i = sub.add_parser("ingest", help="MCP-/API-Ausgabedatei normalisiert ablegen")
    i.add_argument("ticker"); i.add_argument("kind", choices=list(AV_FUNCS) + ["benchmark", "overview", "estimates", "extra"])
    i.add_argument("src")
    z = sub.add_parser("analyze", help="Analyse + Report erzeugen")
    z.add_argument("ticker", help="Ticker (Daten unter data/<TICKER>) oder Pfad zum Datenordner")
    z.add_argument("--horizon", choices=list(analysis.HORIZONS), default="invest")
    z.add_argument("--account", type=float, default=10000, help="Depotgröße für Positionsgröße")
    z.add_argument("--risk", type=float, default=1.0, help="Risiko je Trade in %% des Depots")
    z.add_argument("--wacc", type=float, default=0.09)
    z.add_argument("--notes", help="Markdown-Datei mit Analystenkommentar (wird in den Report eingebettet)")
    z.add_argument("--extra", help='JSON, z. B. \'{"analyst_target": 300, "name": "Apple Inc."}\'')
    z.add_argument("--out", default="reports"); z.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    {"fetch": cmd_fetch, "ingest": cmd_ingest, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
