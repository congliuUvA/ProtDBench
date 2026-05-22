"""Load per-design score tables for post-processing.

The preferred input is the direct output of ``binder_eval_demo.sh`` or
``protdbench.run``::

    output/binder/
      <Target>/sample_level_output.csv
      ...

Post-processing starts from the eval outputs produced by the benchmark.
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .config import COL_MODEL, COL_TARGET, SUCCESS_COL_ALIASES

warnings.filterwarnings("ignore")

_NUMERIC_PAT = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def parse_bracketed_float(series: pd.Series) -> pd.Series:
    """Coerce values like ``'[0.87]'``, ``'(0.87)'``, ``'0.87'`` or NaN to float.

    The eval pipeline writes some scalar metrics as 1-element lists.
    """
    def _parse(val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip().strip("[]()")
        try:
            return float(s)
        except ValueError:
            m = _NUMERIC_PAT.search(s)
            return float(m.group()) if m else np.nan
    return series.apply(_parse)


def find_success_column(df: pd.DataFrame, filter_name: str) -> str | None:
    """Return the first matching success column for ``filter_name`` or ``None``."""
    candidates = [f"{filter_name}_success_ignore_missing", *SUCCESS_COL_ALIASES.get(filter_name, [])]
    for c in candidates:
        if c in df.columns:
            return c
    return None


def passed_design_names(df: pd.DataFrame, filter_name: str) -> set[str]:
    """Return the set of ``name`` values that have ``<filter>_success`` == 1."""
    col = find_success_column(df, filter_name)
    if col is None or "name" not in df.columns:
        return set()
    return set(df.loc[df[col] == 1, "name"].astype(str))


class BenchmarkData:
    """A normalized table of (Model, Target, design, metrics).

    Always has at least ``Model`` and ``Target`` columns. Other columns are
    whatever the eval pipeline produced.
    """

    def __init__(self, df: pd.DataFrame):
        for c in (COL_MODEL, COL_TARGET):
            if c not in df.columns:
                raise ValueError(f"BenchmarkData requires column {c!r}")
        self.df = df.reset_index(drop=True)

    def __len__(self) -> int:
        return len(self.df)

    @classmethod
    def from_eval_outputs(
        cls,
        root: str | Path,
        *,
        model_name: str | None = None,
        targets: Iterable[str] | None = None,
        sample_filename: str = "sample_level_output.csv",
    ) -> "BenchmarkData":
        """Load ``sample_level_output.csv`` files directly from eval outputs.

        Supports both multi-target and single-target layouts:

        ``<root>/<Target>/sample_level_output.csv``
            Target comes from the parent directory name.

        ``<root>/sample_level_output.csv``
            Target must be provided via ``targets`` with exactly one value, or
            falls back to the root directory name.

        If both layouts exist, the multi-target layout wins. This avoids a
        stale single-target demo CSV at ``<root>/sample_level_output.csv`` from
        being silently mixed into a newer ``<root>/<Target>/`` run.

        ``model_name`` defaults to the resolved root directory name — pass an
        explicit value if you want a different label in the output ``Model``
        column.
        """
        root = Path(root)
        if not root.is_dir():
            raise FileNotFoundError(root)
        if model_name is None:
            model_name = root.resolve().name or "design"

        target_filter = set(targets) if targets is not None else None
        candidates: list[tuple[Path, str]] = []
        for path in sorted(root.glob(f"*/{sample_filename}")):
            target = path.parent.name
            if target_filter is not None and target not in target_filter:
                continue
            candidates.append((path, target))

        direct = root / sample_filename
        if not candidates and direct.is_file():
            if target_filter and len(target_filter) == 1:
                target = next(iter(target_filter))
            else:
                target = root.name
            candidates.append((direct, target))

        if not candidates:
            where = f"{root}/*/{sample_filename} or {root / sample_filename}"
            raise FileNotFoundError(f"no eval output CSV found at {where}")

        frames = []
        loaded: list[str] = []
        for path, target in candidates:
            df = pd.read_csv(path)
            df[COL_MODEL] = model_name
            df[COL_TARGET] = target
            frames.append(df)
            loaded.append(f"{path} → model={model_name!r}, target={target!r}")

        print(f"[BenchmarkData] loaded {len(frames)} eval output CSV(s) from {root}:")
        for line in loaded:
            print(f"  - {line}")

        return cls(pd.concat(frames, ignore_index=True))

    def filter(
        self,
        models: Iterable[str] | None = None,
        targets: Iterable[str] | None = None,
    ) -> "BenchmarkData":
        df = self.df
        if models is not None:
            df = df[df[COL_MODEL].isin(list(models))]
        if targets is not None:
            df = df[df[COL_TARGET].isin(list(targets))]
        return BenchmarkData(df)

    @property
    def models(self) -> list[str]:
        return sorted(self.df[COL_MODEL].unique().tolist())

    @property
    def targets(self) -> list[str]:
        return sorted(self.df[COL_TARGET].unique().tolist())
