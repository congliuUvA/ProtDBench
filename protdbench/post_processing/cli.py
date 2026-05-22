"""CLI dispatcher.

Each subcommand calls one method of ``BinderPostProcessing``. By default,
commands read direct eval outputs from ``--eval-dir ./output/binder`` where
each target has ``sample_level_output.csv``.

::

    python -m post_processing.cli success-rate --eval-dir ./output/binder --output ./figs
    python -m post_processing.cli alpha-ratio
    python -m post_processing.cli secondary-structure
    python -m post_processing.cli cluster-success-rate \\
        --eval-dir ./output/binder --sample-root ./examples/pxdesign_binders --filter af2_easy

Use ``-h`` on any subcommand for its options.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .binder import BinderPostProcessing
from .data import BenchmarkData


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="post_processing")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common_eval_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--eval-dir", type=Path, default=Path("./output/binder"),
                        help="binder eval output dir containing <Target>/sample_level_output.csv")
        sp.add_argument("--model-name", default=None,
                        help="label to attach to the Model column "
                             "(default: --eval-dir's directory name)")
        sp.add_argument("--output", type=Path, default=Path("./figs"))
        sp.add_argument("--models", nargs="+", default=None,
                        help="override model order/filter")
        sp.add_argument("--targets", nargs="+", default=None,
                        help="override target list/filter")

    # --- per-design analyses ---
    for name in ("success-rate", "alpha-ratio", "secondary-structure"):
        sp = sub.add_parser(name)
        add_common_eval_args(sp)

    # alpha-ratio extras
    ar = next(a for a in sub.choices.values() if a.prog.endswith("alpha-ratio"))
    ar.add_argument("--aggregation", choices=["median", "mean", "max", "min"], default="median")

    # --- cluster-level analysis (needs raw PDBs + postprocess_binder.py) ---
    cs = sub.add_parser("cluster-success-rate")
    add_common_eval_args(cs)
    cs.add_argument("--sample-root", type=Path, default=Path("./examples/pxdesign_binders"),
                    help="raw sample root with <Target>/converted_pdbs for direct eval outputs")
    cs.add_argument("--filter", default="af2_easy",
                    help="filter name: af2_easy / af2_opt / protenix / protenix_basic / protenix_mini")
    cs.add_argument("--binder-chain", default="B",
                    help="which PDB chain is the binder (default: B)")
    cs.add_argument("--cluster-script", default=None,
                    help="path to protdbench/scripts/postprocess_binder.py")
    cs.add_argument("--workers", type=int, default=None)
    cs.add_argument("--force-rerun", action="store_true")

    args = parser.parse_args(argv)
    return _dispatch(args)


def _dispatch(args: argparse.Namespace) -> int:
    if args.cmd == "success-rate":
        bp = _make_bp(args)
        df, paths = bp.per_sequence_success_rate()
    elif args.cmd == "alpha-ratio":
        bp = _make_bp(args)
        df, paths = bp.alpha_helix_ratio(aggregation=args.aggregation)
    elif args.cmd == "secondary-structure":
        bp = _make_bp(args)
        df, paths = bp.secondary_structure()
    elif args.cmd == "cluster-success-rate":
        bp = _make_bp(args)
        sample_paths = {bp.models[0]: args.sample_root}
        kw: dict = {}
        if args.cluster_script:
            kw["cluster_script"] = args.cluster_script
        df, paths = bp.cluster_success_rate(
            sample_paths=sample_paths,
            binder_chain=args.binder_chain,
            filter_name=args.filter,
            num_workers=args.workers,
            force_rerun=args.force_rerun,
            **kw,
        )
    else:
        print(f"unknown command: {args.cmd}", file=sys.stderr)
        return 2

    print(f"✅ {args.cmd}: {len(df)} summary rows, {len(paths)} files written")
    for p in paths:
        print(f"   - {p}")
    return 0


def _make_bp(args: argparse.Namespace) -> BinderPostProcessing:
    data = BenchmarkData.from_eval_outputs(
        args.eval_dir,
        model_name=args.model_name,
        targets=args.targets,
    )
    return BinderPostProcessing(
        data=data,
        models=args.models,
        targets=args.targets,
        output_dir=args.output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
