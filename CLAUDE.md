# Tradebuddy

Einzelaktien-Analyst: Fundamentalanalyse + Charttechnik → Urteil, Trade-Plan, HTML-Report.

- Hauptworkflow: Skill `.claude/skills/tradebuddy/SKILL.md`, Slash-Befehle `/analyse TICKER`, `/watchlist T1 T2`.
- Datenquelle: Alpha-Vantage-Connector (Free: 25 Abrufe/Tag, 1/s, **nacheinander** aufrufen,
  `return_full_data=true`). Qualitatives: WebSearch; Weiterrecherche: Perplexity-Connector.
- Engine: `python3 -m tradebuddy {fetch|ingest|analyze}` – nur pandas + numpy.
- Tests: `python3 -m pytest -q` (oder `python3 tests/test_engine.py`).
- Sprache der Reports: Deutsch. Zahlenformat deutsch. Immer Disclaimer „Keine Anlageberatung“.
- Nie Zahlen erfinden; Datenlücken offen benennen.
