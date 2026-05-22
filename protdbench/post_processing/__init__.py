"""Post-processing analyses that produce ProtDBench paper figures.

Quick start::

    from post_processing import BinderPostProcessing, BenchmarkData

    data = BenchmarkData.from_eval_outputs("./output/binder", model_name="PXDesignDemo")
    bp = BinderPostProcessing(data, output_dir="./figs")

    df, paths = bp.per_sequence_success_rate()
    df, paths = bp.alpha_helix_ratio()
    df, paths = bp.secondary_structure()
    df, paths = bp.cluster_success_rate(
        sample_paths={"PXDesignDemo": "./examples/pxdesign_binders"},
        filter_name="af2_easy",
    )

CLI::

    python -m post_processing.cli success-rate
    python -m post_processing.cli alpha-ratio
    python -m post_processing.cli secondary-structure
    python -m post_processing.cli cluster-success-rate --sample-root ./examples/pxdesign_binders
"""
from .data import BenchmarkData
from .binder import BinderPostProcessing

__all__ = [
    "BenchmarkData",
    "BinderPostProcessing",
]
