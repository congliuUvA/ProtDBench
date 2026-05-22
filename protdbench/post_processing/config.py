"""Shared constants for the post-processing analyses.

The package is method-agnostic: the model name and target list come from the
score CSVs at runtime (see ``BenchmarkData.from_eval_outputs``). The constants
here are only the things the analyses still need to look up by hand —
column-name aliases, threshold defaults, etc.
"""
from __future__ import annotations

# Map from human filter name → list of candidate success column names.
# Tolerates the historical drift of column naming across eval pipeline versions.
SUCCESS_COL_ALIASES = {
    "af2_easy": [
        "af2_easy_success_ignore_missing",
        "af2_ig_easy_success_ignore_missing",
        "af2_ig_success_ignore_missing",
        "bindcraft_success_ignore_missing",
    ],
    "af2_opt": ["af2_opt_success_ignore_missing"],
    "protenix": ["ptx_success_ignore_missing", "Protenix_success_ignore_missing"],
    "protenix_basic": ["ptx_basic_success_ignore_missing"],
    "protenix_mini": ["ptx_mini_success_ignore_missing", "ptx_mini_success"],
}

# Common column names produced by the eval pipeline.
COL_TARGET = "Target"
COL_MODEL = "Model"
COL_DESIGN = "name"           # backbone identifier (one row per (design, seq_idx))
COL_SEQ_IDX = "seq_idx"
COL_SEQUENCE = "sequence"

# Cluster-SR runs at these three TM-score thresholds by default.
CLUSTER_TM_THRESHOLDS = [0.6, 0.8, 1.0]

# Secondary-structure classification thresholds (used by `secondary_structure`).
BETA_ALL_ALPHA_MAX = 0.01
BETA_MAINLY_BETA_MIN = 0.30

# AF2-IG iPAE / Protenix-Mini iPTM column candidates used by `secondary_structure`.
AF2_IPAE_CANDIDATES = [
    "unscaled_i_pAE", "i_pAE", "i_pae", "unscaled_i_pae",
    "af2_i_pAE", "af2_i_pae", "af2_unscaled_i_pAE", "af2_unscaled_i_pae",
    "initial_guess_i_pAE", "initial_guess_i_pae",
]
PTX_IPTM_CANDIDATES = ["ptx_mini_iptm", "ptx_mini_iptm_binder", "ptx_iptm", "iptm"]
