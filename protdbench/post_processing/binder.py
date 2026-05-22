"""All binder post-processing analyses, expressed as methods of one class.

::

    from post_processing import BinderPostProcessing, BenchmarkData

    data = BenchmarkData.from_eval_outputs("./output/binder", model_name="PXDesignDemo")
    bp = BinderPostProcessing(data, output_dir="./figs")

    df, paths = bp.per_sequence_success_rate()
    df, paths = bp.alpha_helix_ratio(aggregation="median")
    df, paths = bp.secondary_structure()
    df, paths = bp.cluster_success_rate(
        sample_paths={"PXDesignDemo": "./examples/pxdesign_binders"},
        filter_name="af2_easy",
    )

The first three methods only need the score CSVs (``BenchmarkData``).
``cluster_success_rate`` additionally needs the raw design PDBs on disk so it
can shell out to ``protdbench/scripts/postprocess_binder.py`` for TMalign
clustering.

Each method writes a small summary CSV and prints a terminal table — no
plots. Wrap the returned dataframe in your own plotting code if you want
figures.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Iterable, Literal

import numpy as np
import pandas as pd

from .config import (
    AF2_IPAE_CANDIDATES,
    BETA_ALL_ALPHA_MAX,
    BETA_MAINLY_BETA_MIN,
    CLUSTER_TM_THRESHOLDS,
    COL_MODEL,
    COL_TARGET,
    PTX_IPTM_CANDIDATES,
)
from .data import BenchmarkData, find_success_column, parse_bracketed_float


# Default location of the per-design clustering helper, relative to the repo
# root (= the directory you run the CLI from). Override per call.
DEFAULT_CLUSTER_SCRIPT = "protdbench/scripts/postprocess_binder.py"


class BinderPostProcessing:
    """All binder post-processing analyses on a unified score table.

    Wraps a ``BenchmarkData`` and exposes one method per paper analysis.
    Each method filters the score table to ``self.models × self.targets``,
    computes a summary DataFrame, writes one CSV into ``self.output_dir``,
    prints a short table to the terminal, and returns ``(df, [csv_path])``.

    No plotting — bring your own.
    """

    def __init__(
        self,
        data: BenchmarkData,
        *,
        models: Iterable[str] | None = None,
        targets: Iterable[str] | None = None,
        output_dir: str | Path = "./figs",
    ):
        self.data = data
        # Default to whatever's actually in the score table — no canonical
        # roster, since the package is method-agnostic.
        self.models = list(models) if models else list(data.models)
        self.targets = list(targets) if targets else list(data.targets)
        self.output_dir = Path(output_dir)

    # ------------------------------------------------------------------
    # 1. Per-sequence success rate (paper Figure 4-5)
    # ------------------------------------------------------------------

    def per_sequence_success_rate(
        self,
        *,
        rmsd_threshold: float = 2.5,
        rmsd_col: str = "ptx_mini_pred_design_rmsd",
    ) -> tuple[pd.DataFrame, list[Path]]:
        """SR by (Target, Model) under three filters: AF2-IG-Easy, Protenix-mini,
        Protenix structural-consistency (RMSD < ``rmsd_threshold``).

        Writes ``per_sequence_success_rate.csv``.
        """
        df_in = self.data.filter(models=self.models, targets=self.targets).df

        rows: list[dict] = []
        for (model, target), grp in df_in.groupby([COL_MODEL, COL_TARGET], sort=False):
            af2_col = find_success_column(grp, "af2_easy")
            if af2_col is None:
                continue
            row: dict = {"Model": model, "Target": target,
                         "AF2_Easy_SR": grp[af2_col].mean() * 100}

            ptx_col = find_success_column(grp, "protenix_mini")
            row["PTX_Mini_SR"] = grp[ptx_col].mean() * 100 if ptx_col else np.nan

            row["PTX_Consistency_SR"] = np.nan
            for c in (rmsd_col, "ptx_pred_design_rmsd"):
                if c in grp.columns:
                    rmsd = parse_bracketed_float(grp[c])
                    row["PTX_Consistency_SR"] = (rmsd < rmsd_threshold).mean() * 100
                    break
            rows.append(row)

        summary = pd.DataFrame(rows)
        if summary.empty:
            print("⚠️  per_sequence_success_rate: no data after filtering.")
            return summary, []

        csv_path = self._write_csv(summary, "per_sequence_success_rate.csv")
        self._print_summary(
            "per_sequence_success_rate (% passing)",
            summary,
            value_cols=["AF2_Easy_SR", "PTX_Mini_SR", "PTX_Consistency_SR"],
        )
        return summary, [csv_path]

    # ------------------------------------------------------------------
    # 2. Alpha-helix ratio per backbone
    # ------------------------------------------------------------------

    def alpha_helix_ratio(
        self,
        *,
        aggregation: Literal["median", "mean", "max", "min"] = "median",
    ) -> tuple[pd.DataFrame, list[Path]]:
        """Per-backbone α-helix ratio aggregated across the 8 ProteinMPNN sequences,
        then summarized per (Target, Model).

        Writes ``alpha_helix_ratio.csv`` with one row per (Target, Model).
        """
        df = self.data.filter(models=self.models, targets=self.targets).df
        if "alpha" not in df.columns or "name" not in df.columns:
            print("⚠️  alpha_helix_ratio: missing 'alpha' or 'name'; skipping.")
            return pd.DataFrame(), []

        df = df.copy()
        df["alpha"] = parse_bracketed_float(df["alpha"])
        df = df[(df["alpha"] >= 0.0) & (df["alpha"] <= 1.0)]

        per_backbone = (
            df.groupby([COL_TARGET, COL_MODEL, "name"], as_index=False)["alpha"]
              .agg(aggregation)
        )
        if per_backbone.empty:
            print("⚠️  alpha_helix_ratio: no rows after filtering.")
            return per_backbone, []

        summary = (
            per_backbone.groupby([COL_TARGET, COL_MODEL])["alpha"]
            .agg(n="count", mean="mean", median="median", std="std", q25=lambda s: s.quantile(0.25), q75=lambda s: s.quantile(0.75))
            .reset_index()
        )
        summary["aggregation"] = aggregation

        csv_path = self._write_csv(summary, f"alpha_helix_ratio_{aggregation}.csv")
        self._print_summary(
            f"alpha_helix_ratio (per-backbone {aggregation}-of-N, summarized over backbones)",
            summary,
            value_cols=["n", "mean", "median", "q25", "q75"],
        )
        return summary, [csv_path]

    # ------------------------------------------------------------------
    # 3. Secondary-structure conditional analysis
    # ------------------------------------------------------------------

    def secondary_structure(self) -> tuple[pd.DataFrame, list[Path]]:
        """Stratify designs by SS class (all-alpha vs mainly-beta) and summarize
        AF2 unscaled-iPAE / Protenix-mini iPTM distributions per (Target, Model).

        Writes ``secondary_structure.csv`` with one row per
        (Target, Model, SS_Category, MetricFamily).
        """
        df = self.data.filter(models=self.models, targets=self.targets).df
        if "beta" not in df.columns:
            print("⚠️  secondary_structure: no 'beta' column.")
            return pd.DataFrame(), []

        df = df.copy()
        df["beta_num"] = parse_bracketed_float(df["beta"])
        df["SS_Category"] = np.where(
            df["beta_num"] < BETA_ALL_ALPHA_MAX, "all-alpha",
            np.where(df["beta_num"] > BETA_MAINLY_BETA_MIN, "mainly-beta", "other"),
        )
        df = df[df["SS_Category"].isin(["all-alpha", "mainly-beta"])]

        af2_col = _first_present(df, AF2_IPAE_CANDIDATES)
        ptx_col = _first_present(df, PTX_IPTM_CANDIDATES)

        rows: list[pd.DataFrame] = []
        for fam_name, col in (("AF2_unscaled_iPAE", af2_col), ("PTX_Mini_iPTM", ptx_col)):
            if col is None:
                continue
            df[col] = parse_bracketed_float(df[col])
            sub = df[[COL_TARGET, COL_MODEL, "SS_Category", col]].rename(columns={col: "Value"})
            sub["MetricFamily"] = fam_name
            rows.append(sub)
        if not rows:
            print("⚠️  secondary_structure: no AF2/Protenix metric columns.")
            return pd.DataFrame(), []
        long_df = pd.concat(rows, ignore_index=True).dropna(subset=["Value"])

        summary = (
            long_df.groupby([COL_TARGET, COL_MODEL, "SS_Category", "MetricFamily"])["Value"]
            .agg(n="count", mean="mean", median="median", std="std", q25=lambda s: s.quantile(0.25), q75=lambda s: s.quantile(0.75))
            .reset_index()
        )

        csv_path = self._write_csv(summary, "secondary_structure.csv")
        self._print_summary(
            "secondary_structure (per (Target, Model, SS_Category, MetricFamily))",
            summary,
            value_cols=["n", "median", "q25", "q75"],
        )
        return summary, [csv_path]

    # ------------------------------------------------------------------
    # 4. Cluster-level success rate (needs raw PDBs)
    # ------------------------------------------------------------------

    def cluster_success_rate(
        self,
        *,
        sample_paths: dict[str, str | Path],
        binder_chain: str | dict[str, str] = "B",
        filter_name: str = "af2_easy",
        tm_thresholds: list[float] | None = None,
        cluster_script: str = DEFAULT_CLUSTER_SCRIPT,
        cluster_dirname: str = "cluster_results_passedonly",
        force_rerun: bool = False,
        num_workers: int | None = None,
    ) -> tuple[pd.DataFrame, list[Path]]:
        """Cluster-level SR at the configured TM-score thresholds.

        For each (Model, Target):

            1. Pull passed design names + total count from the score table.
            2. Symlink the passed PDBs into ``_passedonly_<filter>_pdbs/``.
            3. Run TMalign clustering at each TM threshold via ``cluster_script``.
            4. Count cluster centers; pass-rate = centers / total backbones.

        Writes ``cluster_success_rate_<filter>.csv``.
        """
        if not sample_paths:
            raise ValueError("cluster_success_rate needs sample_paths (raw PDB dump per method)")
        tm_thresholds = list(tm_thresholds) if tm_thresholds else list(CLUSTER_TM_THRESHOLDS)

        df = self.data.filter(models=self.models, targets=self.targets).df
        success_col = find_success_column(df, filter_name)
        if success_col is None:
            raise ValueError(f"no success column for filter={filter_name!r} in score table")
        if "name" not in df.columns:
            raise ValueError("score table missing 'name' column")
        if df.empty:
            raise ValueError(
                "no rows after filtering score table; check --models/--targets "
                f"(available targets: {sorted(self.data.df[COL_TARGET].dropna().unique().tolist())})"
            )

        missing_roots: list[str] = []
        missing_target_dirs: list[str] = []
        roots_to_models: dict[Path, list[str]] = {}
        pairs = df[[COL_MODEL, COL_TARGET]].drop_duplicates()
        for model in self.models:
            model_targets = pairs.loc[pairs[COL_MODEL] == model, COL_TARGET].tolist()
            if not model_targets:
                continue
            sample_root = sample_paths.get(model)
            if not sample_root:
                missing_roots.append(f"{model}: no sample_paths entry")
                continue
            sample_root = Path(sample_root)
            if not sample_root.exists():
                missing_roots.append(f"{model}: {sample_root}")
                continue
            roots_to_models.setdefault(sample_root.resolve(), []).append(model)
            for target in model_targets:
                if _resolve_converted_dir(sample_root, target) is None:
                    missing_target_dirs.append(
                        f"{model}/{target}: expected {sample_root / target / 'converted_pdbs'}"
                    )
        shared_roots = {
            root: models for root, models in roots_to_models.items() if len(models) > 1
        }
        if missing_roots or missing_target_dirs or shared_roots:
            msg = ["cluster_success_rate sample path validation failed."]
            if missing_roots:
                msg.append("Missing sample roots:\n  - " + "\n  - ".join(missing_roots))
            if missing_target_dirs:
                msg.append("Missing target converted_pdbs directories:\n  - " + "\n  - ".join(missing_target_dirs))
            if shared_roots:
                msg.append(
                    "Shared sample roots are not allowed:\n  - "
                    + "\n  - ".join(
                        f"{root}: {', '.join(models)}"
                        for root, models in sorted(shared_roots.items())
                    )
                )
            if missing_roots or missing_target_dirs:
                raise FileNotFoundError("\n".join(msg))
            raise ValueError("\n".join(msg))

        # Pre-extract passed names + totals per (Model, Target). Workers receive
        # plain Python objects only, no pandas state — keeps pickling cheap.
        tasks: list[tuple] = []
        for model in self.models:
            sample_root = sample_paths.get(model)
            if not sample_root or not Path(sample_root).exists():
                continue
            sample_root = str(sample_root)
            chain = (
                binder_chain.get(model, "B")
                if isinstance(binder_chain, dict)
                else binder_chain
            )
            for target in self.targets:
                sub = df[(df[COL_MODEL] == model) & (df[COL_TARGET] == target)]
                if sub.empty:
                    continue
                passed = set(sub.loc[sub[success_col] == 1, "name"].astype(str))
                total = int(sub["name"].astype(str).nunique())
                tasks.append((model, target, sample_root, passed, total, chain))

        if not tasks:
            print("⚠️  cluster_success_rate: no (Model, Target) pairs match the score table.")
            return pd.DataFrame(), []

        n_workers = num_workers or max(1, min(cpu_count() // 2, 8))
        print(f"[cluster-SR] filter={filter_name} workers={n_workers} tasks={len(tasks)}")

        worker = _ClusterSRWorker(
            filter_name=filter_name,
            cluster_script=cluster_script,
            cluster_dirname=cluster_dirname,
            tm_thresholds=tm_thresholds,
            force_rerun=force_rerun,
        )
        rows: list[dict] = []
        with Pool(processes=n_workers, maxtasksperchild=1) as pool:
            for out_rows in pool.imap_unordered(worker, tasks, chunksize=1):
                rows.extend(out_rows)

        summary = pd.DataFrame(rows)
        if summary.empty:
            return summary, []

        csv_path = self._write_csv(summary, f"cluster_success_rate_{filter_name}.csv")
        self._print_summary(
            f"cluster_success_rate (filter={filter_name})",
            summary,
            value_cols=["TMthr", "UniquePassedClusters", "TotalBackbones", "ClusterPassRatePct"],
        )
        return summary, [csv_path]

    # ------------------------------------------------------------------
    # I/O helpers
    # ------------------------------------------------------------------

    def _write_csv(self, df: pd.DataFrame, name: str) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / name
        df.to_csv(path, index=False)
        print(f"💾 wrote {path} ({len(df)} rows)")
        return path

    @staticmethod
    def _print_summary(title: str, df: pd.DataFrame, value_cols: list[str]) -> None:
        present = [c for c in value_cols if c in df.columns]
        id_cols = [c for c in (COL_MODEL, COL_TARGET, "SS_Category", "MetricFamily")
                   if c in df.columns]
        cols = id_cols + present
        if not cols:
            return
        print(f"\n=== {title} ===")
        # Pandas display: full table, no truncation, fixed float fmt.
        with pd.option_context(
            "display.max_rows", None,
            "display.max_columns", None,
            "display.width", 200,
            "display.float_format", "{:8.2f}".format,
        ):
            print(df[cols].to_string(index=False))
        print()


# ============================================================================
# Module-level helpers (used by the class methods and the worker)
# ============================================================================

def _first_present(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _resolve_converted_dir(sample_root: Path, target: str) -> Path | None:
    primary = sample_root / target / "converted_pdbs"
    if primary.is_dir():
        return primary
    alt = primary / "postprocess"
    return alt if alt.is_dir() else None


def _list_structures(directory: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not directory.is_dir():
        return out
    for f in directory.iterdir():
        if f.suffix in {".pdb", ".cif"}:
            out[f.stem] = f
    return out


def _safe_path_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _sync_passed_structures(
    link_dir: Path,
    names: Iterable[str],
    file_map: dict[str, Path],
) -> tuple[int, str]:
    """Mirror the current passed structure set into ``link_dir``.

    ``cluster_success_rate`` reuses TMalign outputs when possible, so this
    directory must exactly match the current CSV filter result. Stale PDB/CIF
    files from previous runs would otherwise inflate cluster counts.
    """
    link_dir.mkdir(parents=True, exist_ok=True)
    desired: dict[str, Path] = {}
    for name in names:
        src = file_map.get(name)
        if src is not None:
            desired[src.name] = src.resolve()

    for old in link_dir.iterdir():
        if old.suffix in {".pdb", ".cif"} and old.name not in desired and not old.is_dir():
            old.unlink()

    n = 0
    manifest_rows: list[str] = []
    for filename, src in sorted(desired.items()):
        # Use the absolute path as the symlink target. Relative symlinks resolve
        # relative to the symlink's *directory*, not CWD, which silently breaks
        # when ``sample_root`` is itself a relative path.
        dst = link_dir / filename
        if dst.is_symlink() or dst.exists():
            if not dst.is_symlink() or dst.resolve() != src:
                if dst.is_dir():
                    continue
                dst.unlink()
            else:
                n += 1
                manifest_rows.append(_manifest_row(filename, src))
                continue
        try:
            dst.symlink_to(src)
        except (FileExistsError, OSError):
            try:
                shutil.copy2(src, dst)
            except Exception:
                continue
        n += 1
        manifest_rows.append(_manifest_row(filename, src))
    return n, _manifest_hash(manifest_rows)


def _manifest_row(filename: str, src: Path) -> str:
    try:
        stat = src.stat()
        return f"{filename}\t{src}\t{stat.st_size}\t{stat.st_mtime_ns}"
    except OSError:
        return f"{filename}\t{src}"


def _manifest_hash(rows: list[str]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _parse_cluster_centers(clusters_txt: Path) -> list[str]:
    if not clusters_txt.exists():
        return []
    out: list[str] = []
    with clusters_txt.open() as f:
        for line in f:
            if "(center)" not in line:
                continue
            m = re.search(r"([\w.\-]+\.(?:pdb|cif))", line)
            if m:
                out.append(m.group(1))
    return out


class _ClusterSRWorker:
    """Picklable callable for ``cluster_success_rate``'s multiprocessing pool.

    The worker only does filesystem + subprocess work — no pandas — so it
    pickles fast and parallelizes well across (Model, Target) tasks.
    """

    def __init__(
        self,
        *,
        filter_name: str,
        cluster_script: str,
        cluster_dirname: str,
        tm_thresholds: list[float],
        force_rerun: bool,
    ):
        self.filter_name = filter_name
        self.cluster_script = cluster_script
        self.cluster_dirname = cluster_dirname
        self.tm_thresholds = tm_thresholds
        self.force_rerun = force_rerun

    def __call__(self, args: tuple[str, str, str, set[str], int, str]) -> list[dict]:
        model, target, sample_root, passed, total_backbones, binder_chain = args
        converted = _resolve_converted_dir(Path(sample_root), target)
        if converted is None:
            return []

        safe_model = _safe_path_part(model)
        link_dir = converted / f"_passedonly_{safe_model}_{self.filter_name}_pdbs"
        n_linked, manifest_hash = _sync_passed_structures(
            link_dir, passed, _list_structures(converted)
        )

        rows: list[dict] = []
        for th in self.tm_thresholds:
            centers = 0
            if n_linked > 0:
                out_dir = converted / self.cluster_dirname / f"{safe_model}_{self.filter_name}_th{th}"
                try:
                    self._cluster(link_dir, binder_chain, th, out_dir, manifest_hash)
                    centers = len(_parse_cluster_centers(out_dir / "clusters.txt"))
                except subprocess.CalledProcessError as e:
                    err = (e.stderr or b"").decode(errors="replace") if isinstance(e.stderr, (bytes, bytearray)) else (e.stderr or "")
                    print(f"[cluster-SR][{model}/{target}/tm{th}] cluster_script failed "
                          f"(exit {e.returncode}); stderr tail:\n{err[-500:]}")
                    centers = 0
            rate = 100.0 * centers / max(1, total_backbones)
            rows.append({
                "Filter": self.filter_name,
                "Model": model,
                "Target": target,
                "TMthr": th,
                "UniquePassedClusters": centers,
                "TotalBackbones": total_backbones,
                "ClusterPassRatePct": rate,
                "Group": f"{model}_tm{th}",
            })
        return rows

    def _cluster(
        self,
        input_dir: Path,
        binder_chain: str,
        th: float,
        out_dir: Path,
        manifest_hash: str,
    ) -> None:
        clusters = out_dir / "clusters.txt"
        manifest = out_dir / "passed_manifest.sha256"
        if (
            not self.force_rerun
            and clusters.exists()
            and manifest.exists()
            and manifest.read_text().strip() == manifest_hash
        ):
            return
        out_dir.mkdir(parents=True, exist_ok=True)
        # ``postprocess_binder.py`` does ``from protdbench.globals import …``.
        # That import works out of the box if the user ran ``pip install -e .``
        # (i.e. ``install.sh``), but we belt-and-brace by also injecting the
        # repo root onto PYTHONPATH so dev environments without a pip install
        # still work. ``<repo>/protdbench/scripts/postprocess_binder.py`` →
        # repo root = parents[2].
        script = Path(self.cluster_script).resolve()
        repo_root = script.parents[2] if len(script.parents) >= 3 else script.parent
        env = {**os.environ}
        env["PYTHONPATH"] = (
            f"{repo_root}{os.pathsep}{env['PYTHONPATH']}"
            if env.get("PYTHONPATH") else str(repo_root)
        )
        subprocess.run(
            ["python3", str(script),
             "--input_dir", str(input_dir),
             "--binder_chain", binder_chain,
             "--threshold", str(th),
             "--output_dir", str(out_dir)],
            env=env,
            capture_output=True,
            check=True,
        )
        manifest.write_text(manifest_hash + "\n")
