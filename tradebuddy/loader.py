"""Robustes Einlesen von Alpha-Vantage-Daten.

Akzeptiert alles, was der Alpha-Vantage-MCP-Connector oder die REST-API liefert:
- rohes CSV (timestamp,open,high,low,close,volume)
- rohes JSON ({"Time Series (Daily)": ...}, {"annualReports": ...}, {"feed": ...})
- MCP-Hülle {"result": "<csv oder json als string>"}
- MCP-Vorschau {"preview": true, "sample_data": "..."}
"""
from __future__ import annotations

import io
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

PRICE_FILES = {
    "daily": ["daily.csv", "daily.json", "daily.txt"],
    "weekly": ["weekly.csv", "weekly.json", "weekly.txt"],
    "benchmark": ["benchmark.csv", "benchmark.json", "benchmark.txt"],
}
JSON_FILES = ["income", "balance", "cashflow", "earnings", "news", "insider",
              "overview", "estimates", "extra"]


def unwrap(raw: str) -> Any:
    """Entfernt MCP-Hüllen und gibt dict/list oder CSV-Text zurück."""
    raw = raw.strip()
    if not raw:
        return None
    if raw[0] in "{[":
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(obj, dict):
            if "error" in obj and len(obj) <= 2:
                raise ValueError(f"Alpha-Vantage-Fehler in Datei: {obj['error']}")
            if set(obj) == {"result"} or ("result" in obj and isinstance(obj["result"], str) and len(obj) <= 3):
                return unwrap(obj["result"])
            if obj.get("preview") and "sample_data" in obj:
                return unwrap(obj["sample_data"])
            for key in ("Information", "Note", "Error Message"):
                if key in obj and len(obj) == 1:
                    raise ValueError(f"Alpha-Vantage-Meldung: {obj[key]}")
        return obj
    return raw


def read_any(path: str | Path) -> Any:
    return unwrap(Path(path).read_text(encoding="utf-8"))


def _num(v: Any) -> float:
    if v is None:
        return math.nan
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "None", "null", "-", "NaN", "nan"):
        return math.nan
    try:
        return float(s)
    except ValueError:
        return math.nan


def prices_from(obj: Any) -> pd.DataFrame:
    """OHLCV-DataFrame, aufsteigend nach Datum sortiert."""
    if isinstance(obj, str):
        df = pd.read_csv(io.StringIO(obj))
        df.columns = [c.strip().lower() for c in df.columns]
        datecol = "timestamp" if "timestamp" in df.columns else df.columns[0]
        df[datecol] = pd.to_datetime(df[datecol])
        df = df.set_index(datecol)
        if "adjusted_close" in df.columns:
            factor = df["adjusted_close"] / df["close"]
            for c in ("open", "high", "low"):
                df[c] = df[c] * factor
            df["close"] = df["adjusted_close"]
    elif isinstance(obj, dict):
        key = next((k for k in obj if "Time Series" in k or "Weekly" in k or "Monthly" in k), None)
        if key is None:
            raise ValueError("Keine Zeitreihe im JSON gefunden")
        rows = {}
        for d, vals in obj[key].items():
            clean = {k.split(". ", 1)[-1].replace(" ", "_"): _num(v) for k, v in vals.items()}
            rows[pd.Timestamp(d)] = clean
        df = pd.DataFrame.from_dict(rows, orient="index")
        if "adjusted_close" in df.columns:
            factor = df["adjusted_close"] / df["close"]
            for c in ("open", "high", "low"):
                df[c] = df[c] * factor
            df["close"] = df["adjusted_close"]
    else:
        raise ValueError("Unbekanntes Preisformat")
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df.index.name = "date"
    return df.sort_index()


def statements_from(obj: Any) -> dict[str, list[dict[str, float]]]:
    """annual/quarterly Reports als Listen (neueste zuerst) mit float-Werten."""
    out: dict[str, list[dict[str, Any]]] = {"annual": [], "quarterly": []}
    if not isinstance(obj, dict):
        return out
    for src, dst in (("annualReports", "annual"), ("quarterlyReports", "quarterly")):
        for rep in obj.get(src, []) or []:
            row = {k: (v if k in ("fiscalDateEnding", "reportedCurrency") else _num(v)) for k, v in rep.items()}
            out[dst].append(row)
        out[dst].sort(key=lambda r: r.get("fiscalDateEnding", ""), reverse=True)
    return out


class Bundle:
    """Alle Rohdaten zu einem Ticker."""

    def __init__(self, ticker: str):
        self.ticker = ticker.upper()
        self.daily: pd.DataFrame | None = None
        self.weekly: pd.DataFrame | None = None
        self.benchmark: pd.DataFrame | None = None
        self.income = {"annual": [], "quarterly": []}
        self.balance = {"annual": [], "quarterly": []}
        self.cashflow = {"annual": [], "quarterly": []}
        self.earnings: dict = {}
        self.news: dict = {}
        self.insider: dict = {}
        self.overview: dict = {}
        self.estimates: dict = {}
        self.extra: dict = {}
        self.missing: list[str] = []


def load_bundle(data_dir: str | Path, ticker: str | None = None) -> Bundle:
    d = Path(data_dir)
    b = Bundle(ticker or d.name)
    for attr, names in PRICE_FILES.items():
        for n in names:
            p = d / n
            if p.exists():
                setattr(b, attr, prices_from(read_any(p)))
                break
        else:
            b.missing.append(attr)
    for name in JSON_FILES:
        p = d / f"{name}.json"
        if not p.exists():
            b.missing.append(name)
            continue
        obj = read_any(p)
        if name in ("income", "balance", "cashflow"):
            setattr(b, name, statements_from(obj))
        else:
            setattr(b, name, obj if isinstance(obj, dict) else {})
    if b.daily is None and b.weekly is None:
        raise FileNotFoundError(f"Keine Kursdaten in {d} (daily.csv oder weekly.json benötigt)")
    return b


def ingest(src: str | Path, dst: str | Path) -> Path:
    """Normalisiert eine MCP-/API-Ausgabe und speichert sie sauber ab."""
    obj = read_any(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, str):
        dst = dst.with_suffix(".csv")
        dst.write_text(obj.replace("\r\n", "\n"), encoding="utf-8")
    else:
        dst = dst.with_suffix(".json")
        dst.write_text(json.dumps(obj), encoding="utf-8")
    return dst
