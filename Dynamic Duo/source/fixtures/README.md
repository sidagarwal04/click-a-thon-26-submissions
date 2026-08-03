# Fixture artifacts

`edge_manifest.json` is the oracle and IS committed — it records the seed, the resolved
targets and the expected verdict per scenario.

The `.parquet` slices are gitignored (85MB/10MB). They are pure functions of the
generator plus the seed in the manifest, so regenerate rather than copy them around:

```bash
python3 tools/gen_edge_cases.py --out-dir fixtures --seed $(python3 -c "import json;print(json.load(open('fixtures/edge_manifest.json'))['seed'])")
```

See [../EDGE_CASES.md](../EDGE_CASES.md) for the catalogue and the full run recipe.
