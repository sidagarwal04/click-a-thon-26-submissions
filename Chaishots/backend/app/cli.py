from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from app.services.feature_pipeline import (
    FeaturePipeline,
    get_feature_pipeline_service,
    process_feature_pipeline,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Process an Atlys feature through the shared pipeline."
    )
    parser.add_argument(
        "--feature",
        required=True,
        help="Safe folder name below incoming_features (for example 01_express_checkout).",
    )
    return parser


def _flush_traces_safely(pipeline: FeaturePipeline) -> Exception | None:
    """Flush once without allowing telemetry to replace a pipeline result."""

    try:
        pipeline.flush_traces()
    except Exception as exc:
        return exc
    return None


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    service: FeaturePipeline | None = None,
) -> int:
    args = _parser().parse_args(argv)
    pipeline: FeaturePipeline | None = None
    try:
        pipeline = service or get_feature_pipeline_service()
        result = process_feature_pipeline(args.feature, service=pipeline)
    except Exception as exc:
        if pipeline is not None:
            _flush_traces_safely(pipeline)
        sys.stderr.write(f"Pipeline failed: {exc}\n")
        return 1

    flush_error = _flush_traces_safely(pipeline)
    sys.stdout.write(result.model_dump_json(indent=2) + "\n")
    if flush_error is not None:
        sys.stderr.write(f"Trace flush failed: {flush_error}\n")
    return 0


def main() -> None:
    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
