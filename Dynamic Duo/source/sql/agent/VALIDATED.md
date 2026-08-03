# Validation record — sql/agent/*.sql

All queries executed against the local load (9M events via `./load.sh`, dataset `main`,
all 99_validation checks passing). Placeholders substituted with literals exactly as the
runner would. Date: 2026-08-01.

| query | case | result | matches known answer |
|---|---|---|---|
| q1 | Jun 23–25, excl Jun 21 | fill −3.455 pp MOVED; req +4.36; render −0.004; eCPM +0.0008; shares NULL (rev −0.2%, guard); min_clean_days 3 | ✅ |
| q2a (enriched) | fill × os_version | Android 15: delta −0.3517, contribution −3.368 pp; next −0.035 | ✅ |
| q2a (rollup) | fill × os_version | identical to enriched, 6 ms vs 18 ms | ✅ |
| q2b | requests × region, Jun 21 | all regions −43.1…−44.2 % → uniform → GLOBAL path | ✅ |
| q3 | region excl Android 15 | max residual −0.0012 → all RULED OUT | ✅ |
| q4 | os_version, Jun 23–26 | Android 15 vs_peer −0.3511 ANOMALOUS_LOW; rest NORMAL | ✅ |
| q5 | os_version | within −3.422 / mix 0.000 / interaction −0.002 / total −3.424; identity holds | ✅ |
| q0 (since deleted — boundaries are detection's concern) | fill, scan Jun 22–27 | flagged span exactly Jun 23 00:00 → Jun 25 23:00 | ✅ |
| q6 | empty incidents | `[]`, no error | ✅ |
| q1 scoped | `__SCOPE_FILTER__ = country='ID'`, Jun 23–25 | fill −6.594 pp (vs −3.455 global — ID skews Android); unscoped rerun unchanged | ✅ |

Runner notes:
- Host `clickhouse` binary is 22.13 (2022): `clickhouse local` there does NOT support
  `--param_*`. The runner must target the container/Cloud server (25.x+) where bound
  params work; literal substitution is only for offline validation.
- Q0 boundary on Jun 23–25: hourly fill dev ≈ −4…−5.5 % (the −3.4 pp drop ÷ 0.785 base),
  so the ≥2-consecutive-hours rule at the 2 pp fill threshold (≈−2.5 %) flags it cleanly.

## 2026-08-02 — q6 revision (confirmed-cause filter)

q6 now excludes only confirmed-cause verdicts (join to `diagnoses.verdict_code`);
hedged PEER_OUTLIER dates stay in baselines. Validated on the edge fixture (seed
20260802): scorecard 4/11/5 → 6/9/5 with zero peer-path verdicts remaining, and on a
fresh main-only run: Jun 23–25 → CAUSE_CONFIRMED Android 15 (fill −3.417 pp under
chronological hygiene; −3.455 clean-slate). Empty-incidents case unchanged (`[]`).
