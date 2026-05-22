# Post-processing analyses

Computes the per-method analyses behind the ProtDBench paper figures from the
`sample_level_output.csv` files that [`protdbench/run.py`](../run.py) writes
per target. **Output is CSV + a terminal table — no plots.** Wrap the
returned `DataFrame` in your own plotting code if you want figures.

```
protdbench/post_processing/
├── config.py            constants: column aliases, thresholds
├── data.py              BenchmarkData — loads direct eval outputs
├── binder.py            BinderPostProcessing — all binder analyses on one class
├── cli.py               argparse dispatcher
└── README.md
```

## Inputs

The recommended input is the direct output of `binder_eval_demo.sh` /
`protdbench.run`. This is the eval root (`EVAL_DIR`):

```text
EVAL_DIR/
├── BHRF1/sample_level_output.csv
├── IL7RA/sample_level_output.csv
└── ...
```

For `cluster_success_rate`, also provide the raw sample root (`SAMPLE_ROOT`)
with target dirs that match `EVAL_DIR`:

```text
SAMPLE_ROOT/
├── BHRF1/converted_pdbs/*.{pdb,cif}
├── IL7RA/converted_pdbs/*.{pdb,cif}
└── ...
```

The other three analyses run from the score CSVs alone.

```
EVAL_DIR/<Target>/sample_level_output.csv  ──►  per_sequence_success_rate
                                                alpha_helix_ratio
                                                secondary_structure
                                          ──►  cluster_success_rate
                                                (+ SAMPLE_ROOT/<Target>/converted_pdbs)
```

On load, `BenchmarkData` prints what it picked up:

```text
[BenchmarkData] loaded 2 eval output CSV(s) from output/binder:
  - output/binder/BHRF1/sample_level_output.csv → model='binder', target='BHRF1'
  - output/binder/IL7RA/sample_level_output.csv → model='binder', target='IL7RA'
```

If both `EVAL_DIR/sample_level_output.csv` and
`EVAL_DIR/<Target>/sample_level_output.csv` exist, the per-target layout wins.

## Outputs

Each analysis writes one CSV into `--output` and prints a summary table to the
terminal. Filenames:

| Analysis | CSV | Rows |
|---|---|---|
| `success-rate` | `per_sequence_success_rate.csv` | one per (Model, Target) |
| `alpha-ratio` | `alpha_helix_ratio_<aggregation>.csv` | one per (Model, Target), aggregated over backbones |
| `secondary-structure` | `secondary_structure.csv` | one per (Model, Target, SS_Category, MetricFamily) |
| `cluster-success-rate` | `cluster_success_rate_<filter>.csv` | one per (Model, Target, TM_threshold) |

Sample terminal output for `success-rate`:

```text
=== per_sequence_success_rate (% passing) ===
 Model Target  AF2_Easy_SR  PTX_Mini_SR  PTX_Consistency_SR
binder  BHRF1        60.00        30.00               75.00
binder  IL7RA        45.00         5.00               35.00
```

## CLI

All analyses accept `--eval-dir ./output/binder --output ./figs`. Targets are
inferred from the subdirectories under `--eval-dir`. The `Model` column in
the output CSVs defaults to `--eval-dir`'s directory name; pass
`--model-name` to override. Use `--models` / `--targets` to filter.

```bash
# per-design SR (3 metrics: AF2-IG-Easy / Protenix-mini / Protenix consistency)
python -m protdbench.post_processing.cli success-rate --eval-dir ./output/binder

# α-helix ratio (per-backbone median-of-N sequences)
python -m protdbench.post_processing.cli alpha-ratio --eval-dir ./output/binder
python -m protdbench.post_processing.cli alpha-ratio --aggregation max --eval-dir ./output/binder

# secondary-structure-stratified iPAE / iPTM summary
python -m protdbench.post_processing.cli secondary-structure --eval-dir ./output/binder
```

For a small end-to-end demo:

```bash
bash binder_eval_demo.sh
bash post_processing_demo.sh
```

Override paths via environment variables:

```bash
EVAL_DIR=./output/binder \
SAMPLE_ROOT=./examples/pxdesign_binders \
OUTPUT_DIR=./output/post_processing_demo \
bash post_processing_demo.sh
```

## Cluster-level SR (needs the raw PDBs too)

```bash
python -m protdbench.post_processing.cli cluster-success-rate \
  --eval-dir ./output/binder \
  --sample-root ./examples/pxdesign_binders \
  --filter af2_easy \
  --binder-chain B \
  --workers 4 \
  --output ./figs
```

Filters: `af2_easy`, `af2_opt`, `protenix`, `protenix_basic`, `protenix_mini`.

`--binder-chain` tells the clustering script which PDB chain is the designed
binder (default `B`). Internally calls
[`protdbench/scripts/postprocess_binder.py`](../scripts/postprocess_binder.py)
once per (model × target × TM-threshold) via the bundled
[`protdbench/metrics/TMalign`](../metrics/TMalign) binary. Override the script
path with `--cluster-script`.

---

## Python API

The CLI is a thin wrapper around `BinderPostProcessing`:

```python
from protdbench.post_processing import BinderPostProcessing, BenchmarkData

# model_name defaults to the eval-output directory name. Pass it explicitly
# if you want a custom label in the Model column.
data = BenchmarkData.from_eval_outputs("./output/binder")
print(data.models)  # → ['binder']  (= the eval-dir name)

bp = BinderPostProcessing(data, output_dir="./figs")

df, paths = bp.per_sequence_success_rate()
df, paths = bp.alpha_helix_ratio(aggregation="median")
df, paths = bp.secondary_structure()
df, paths = bp.cluster_success_rate(
    sample_paths={data.models[0]: "./examples/pxdesign_binders"},
    filter_name="af2_easy",
)
```

Each method returns `(summary_df, [csv_path])`. The summary df is the
authoritative result — feed it into your own plotting / table-formatting code
as needed.
