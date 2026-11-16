"""Tests für Tradebuddy (laufen mit pytest oder direkt: python3 tests/test_engine.py)."""
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tradebuddy import analysis, fundamentals, report, technicals  # noqa: E402
from tradebuddy.loader import ingest, load_bundle, prices_from, unwrap  # noqa: E402

FIX = Path(__file__).resolve().parents[1] / "data" / "AAPL"


def synth(n=300, drift=0.001, seed=1, freq="B"):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(drift + 0.012 * rng.standard_normal(n)))
    idx = pd.date_range("2024-01-01", periods=n, freq=freq)
    o = c * (1 + 0.003 * rng.standard_normal(n))
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.006, "low": np.minimum(o, c) * 0.994,
                         "close": c, "volume": rng.integers(1e6, 3e6, n).astype(float)}, index=idx)


def test_rsi_bounds_and_extremes():
    up = pd.Series(np.linspace(1, 100, 60))
    assert technicals.rsi(up).iloc[-1] > 95
    down = pd.Series(np.linspace(100, 1, 60))
    assert technicals.rsi(down).iloc[-1] < 5
    r = technicals.rsi(synth()["close"]).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_split_adjustment():
    df = synth(120, 0, freq="W-FRI")
    df.iloc[:60, :4] *= 4  # künstlicher 4:1-Split
    adj = technicals.adjust_splits(df)
    assert abs(adj["close"].iloc[59] / adj["close"].iloc[60] - 1) < 0.1


def test_uptrend_scores_higher_than_downtrend():
    def pair(dd, wd):
        w = synth(200, wd, freq="W-FRI")
        d = synth(120, dd)
        d.index = pd.bdate_range(end=w.index[-1], periods=120)
        d[["open", "high", "low", "close"]] *= w["close"].iloc[-1] / d["close"].iloc[-1]
        return d, w
    up = technicals.analyze(*pair(0.003, 0.006))
    dn = technicals.analyze(*pair(-0.003, -0.006))
    assert up.trend == "Aufwärtstrend" and dn.trend == "Abwärtstrend"
    assert up.score > dn.score + 20


def test_dcf_monotonic():
    a = fundamentals.dcf(100, 10, 0, 0.05)
    b = fundamentals.dcf(100, 10, 0, 0.10)
    assert b > a > 0
    implied = fundamentals.reverse_dcf(a, 100, 10, 0)
    assert abs(implied - 5) < 0.1


def test_unwrap_variants():
    csv = "timestamp,open,high,low,close,volume\n2026-01-02,1,2,0.5,1.5,100\n2026-01-01,1,2,0.5,1.2,100\n"
    assert isinstance(unwrap(json.dumps({"result": csv})), str)
    df = prices_from(unwrap(json.dumps({"result": csv})))
    assert df.index.is_monotonic_increasing and df["close"].iloc[-1] == 1.5
    av = {"Weekly Time Series": {"2026-01-02": {"1. open": "1", "2. high": "2", "3. low": "0.5", "4. close": "1.5", "5. volume": "9"}}}
    assert prices_from(unwrap(json.dumps(av)))["close"].iloc[0] == 1.5
    try:
        unwrap(json.dumps({"error": {"type": "rate_limit"}}))
        raise AssertionError("Fehler erwartet")
    except ValueError:
        pass


def test_ingest_roundtrip():
    with tempfile.TemporaryDirectory() as t:
        src = Path(t) / "x.txt"
        src.write_text(json.dumps({"result": "timestamp,open,high,low,close,volume\r\n2026-01-01,1,1,1,1,1\r\n"}))
        p = ingest(src, Path(t) / "AAA" / "daily")
        assert p.suffix == ".csv" and "\r" not in p.read_text()


def test_full_pipeline_on_fixture():
    if not FIX.exists():
        return
    b = load_bundle(FIX)
    rep = analysis.run(b, "invest", 10000, 1.0)
    assert 0 <= rep.overall <= 100
    assert rep.verdict
    p = rep.plan
    assert p["stop"] < p["einstieg"] < p["ziele"][0]
    assert p["risiko_eur"] <= 10000 * 0.01 + 1
    m = rep.fund.metrics
    assert 20 < m["Bruttomarge %"] < 70 and m["KGV (P/E)"] > 0
    assert 0 <= rep.fund.piotroski["score"] <= 9
    html = report.html(rep, "## Test\n- **fett** [Link](https://example.com)")
    assert "<svg" in html and "Keine Anlageberatung" in html and "<strong>fett</strong>" in html
    js = json.loads(report.to_json(rep))
    assert js["ticker"] == "AAPL"


def test_missing_fundamentals_graceful():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "ZZZ"
        d.mkdir()
        df = synth(150)
        df.index.name = "timestamp"
        df.to_csv(d / "daily.csv")
        rep = analysis.run(load_bundle(d))
        assert math.isnan(rep.scores["Fundamental"]) and 0 <= rep.overall <= 100
        assert any("income" in w for w in rep.warnings)


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print("OK  ", name)
            except Exception as e:  # noqa: BLE001
                fails += 1; print("FAIL", name, repr(e))
    sys.exit(1 if fails else 0)
