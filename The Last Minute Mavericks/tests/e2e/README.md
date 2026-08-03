# tests/e2e — blind end-to-end evaluation (QUARANTINED)

`manifest.json` is the **ground truth** for the synthetic `rca_e2e` slice
(built by `scripts/gen_e2e_dataset.py`, ~10M rows, 5 planted incidents).

**Quarantine rule: no engine, agent, or UI code may read `manifest.json`.**
The engine runs blind (`python run_incident.py --db rca_e2e --json <bundle>`);
only `score.py` opens the manifest, *after* the scan, to grade the bundle.
Tuning any threshold against this file invalidates the rehearsal.

Workflow:
```bash
python scripts/gen_e2e_dataset.py                                  # build rca_e2e (server-side, ~1 min)
python run_incident.py --db rca_e2e --json tests/e2e/scan_bundle_e2e.json
python tests/e2e/score.py tests/e2e/scan_bundle_e2e.json           # precision / recall vs manifest
```
