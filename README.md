# 📈 Tradebuddy

**Dein Einzelaktien-Analyst in Claude Code** – kombiniert **Fundamentalanalyse** (Was kaufe ich?)
mit **Charttechnik** (Wann kaufe ich?) und liefert ein klares Urteil, einen Trade-Plan mit
Einstieg/Stop/Zielen/Positionsgröße und einen interaktiven HTML-Report.

```
/analyse AAPL              # Anleger-Sicht (60 % Fundamental / 30 % Technik / 10 % Sentiment)
/analyse NVDA swing        # Swing-Trader (25 / 65 / 10)
/watchlist MSFT AMZN META  # Schnell-Check mehrerer Werte
```

## Was steckt drin?

| Baustein | Inhalt |
|---|---|
| **Charttechnik** | Wochenchart (SMA10w/40w ≈ 200-Tage-Linie, Golden/Death Cross), Tageschart (SMA20/50, EMA21, RSI, MACD, Bollinger, ATR, ADX, Stochastik, OBV), RSI-Divergenzen, Ausbrüche, Squeeze, Unterstützungen/Widerstände per Pivot-Clustering, relative Stärke vs. S&P 500, automatische Split-Bereinigung |
| **Fundamental** | TTM-Kennzahlen aus Quartalsberichten: KGV, KUV, KBV, EV/EBITDA, FCF-Rendite, PEG, Margen, ROE/ROIC, Cash Conversion, SBC, Wachstum (TTM & 3J-CAGR), Verschuldung, Zinsdeckung, **Piotroski F-Score**, **Altman Z-Score**, Earnings-Beat-Quote |
| **Bewertung** | 10-Jahres-DCF in 3 Szenarien (Bär/Basis/Bulle), **Reverse-DCF** (eingepreistes Wachstum), wachstumsadjustiertes KGV, Analysten-Konsens → gewichteter Fair Value |
| **Sentiment** | Insider-Transaktionen (Form-4-Codes korrekt interpretiert), News-Sentiment (falls verfügbar) |
| **Urteil** | Gewichteter Gesamtscore + Vetos (Altman-Gefahrenzone, Bewertung, Abwärtstrend) + Konfidenz |
| **Trade-Plan** | Einstiegszone je Trendphase, Stop unter Unterstützung (1–3 ATR), Ziele ab CRV ≥ 1, Positionsgröße nach festem Risiko (Standard 1 %, max. 25 % Depotanteil) |
| **Report** | HTML (Kerzenchart mit Stop/Ziel-Linien, RSI, MACD, Wochenchart, Fundamentalbalken, Hell/Dunkel), Markdown, JSON |

## Datenquellen (alles kostenlos)

| Connector | Wofür |
|---|---|
| **Alpha Vantage** (MCP) | Kurse (Tag/Woche), GuV, Bilanz, Cashflow, Earnings, Insider, S&P-Benchmark |
| **Websuche** | Aktuelle News, Guidance, Analysten-Kursziele, Burggraben, Risiken |
| **Perplexity** | Fertigen Report als Dashboard importieren und dort weiter recherchieren |
| **Google Drive / Calendar / Gmail** | Report ablegen, Earnings-Termin eintragen, Zusammenfassung als Entwurf |
| **GitHub** | Versionierte Historie aller Analysen (`reports/`, `data/`) |

> Alpha Vantage Free: **25 Abrufe/Tag, 1 pro Sekunde** → eine Vollanalyse braucht ~8 Abrufe
> (≈ 3 Analysen/Tag). Daten werden 20 h gecacht. Premium-only und daher nicht genutzt:
> `COMPANY_OVERVIEW`, `NEWS_SENTIMENT`, Tagesdaten > 100 Tage – Tradebuddy berechnet
> Marktkapitalisierung & Kennzahlen selbst und nutzt Wochendaten für den Langfristtrend.

## Nutzung ohne Claude (lokal)

```bash
pip install -r requirements.txt
export ALPHAVANTAGE_API_KEY=dein_kostenloser_key   # alphavantage.co/support/#api-key
python3 -m tradebuddy fetch AAPL                   # lädt alle Daten nach data/AAPL
python3 -m tradebuddy analyze AAPL --horizon invest --account 25000 --risk 1 \
  --extra '{"name":"Apple Inc.","analyst_target":336}'
open reports/AAPL_*.html
```

Weitere Optionen: `--wacc 0.10`, `--notes kommentar.md`, `--extra '{"growth_override": 8}'`.

## Projektstruktur

```
tradebuddy/        Engine (loader, technicals, fundamentals, sentiment, analysis, charts, report, cli)
.claude/skills/    Skill "tradebuddy" – der komplette Analysten-Workflow für Claude
.claude/commands/  /analyse, /watchlist
app/              Tradebuddy-App: Eingabefeld für jeden Ticker, läuft als claude.ai-Artifact über den Alpha-Vantage-Connector
data/<TICKER>/     Rohdaten (daily.csv, weekly.csv, income.json, …)
reports/           Erzeugte Reports (.html/.md/.json) + Analystenkommentare
tests/             python3 tests/test_engine.py
```

## Scoring-Logik

**Technik:** Langfristtrend 30 % · Mittelfristtrend 20 % · Momentum 20 % · Struktur 12 % · Volumen 10 % · Rel. Stärke 8 %
**Fundamental:** Bewertung 27 % · Qualität 25 % · Wachstum 23 % · Bilanz 15 % · Gewinndynamik 10 %
**Urteil:** ≥75 Starker Kauf · ≥62 Kaufen · ≥48 Halten · ≥35 Reduzieren · darunter Verkaufen/Meiden

---
⚠️ **Keine Anlageberatung.** Tradebuddy ist ein Analysewerkzeug. Daten können verzögert oder
fehlerhaft sein; Modelle vereinfachen. Entscheidungen triffst du selbst und auf eigenes Risiko.
