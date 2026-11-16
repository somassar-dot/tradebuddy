---
description: Tradebuddy – Schnell-Check mehrerer Ticker (nur Charttechnik + vorhandene Daten)
argument-hint: TICKER1 TICKER2 ...
---
Für jeden Ticker in "$ARGUMENTS": nur `TIME_SERIES_DAILY` (compact, csv) und, falls älter als
20 h, `TIME_SERIES_WEEKLY` abrufen (Alpha Vantage, nacheinander – Limit 25/Tag beachten),
mit `python3 -m tradebuddy ingest` ablegen und `python3 -m tradebuddy analyze <T> --horizon swing --quiet`
ausführen. Danach eine Tabelle: Ticker | Kurs | Technik-Score | Trend | Fundamental-Score (falls Daten) |
Urteil | Einstiegszone | Stop. Sortiert nach Gesamtscore.
