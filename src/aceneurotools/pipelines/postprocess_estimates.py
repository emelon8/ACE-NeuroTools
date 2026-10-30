"""Recompute component events from a completed cluster extraction bundle."""

from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path

from aceneurotools.gui.cluster_results import file_sha256, read_bundle


def postprocess_bundle(bundle, output, *, derivative="first", event_height=5, loader=None):
    """Write a new, traceable event result without rereading the source movie."""
    if derivative not in {"zeroth", "first", "second"}:
        raise ValueError("Derivative must be zeroth, first, or second.")
    if isinstance(event_height, bool) or not math.isfinite(float(event_height)):
        raise ValueError("Event height must be finite.")
    manifest, estimates_path = read_bundle(bundle, loader=loader)
    if loader is None:
        from aceneurotools.gui.neurons import load_estimates

        loader = load_estimates
    from aceneurotools.calcium_imaging.calcium_imaging_postprocessor import CalciumImagingPostprocessor

    estimates = loader(estimates_path).estimates
    events = CalciumImagingPostprocessor.find_calcium_events_with_derivatives(
        estimates, derivative, float(event_height)
    )
    if file_sha256(estimates_path) != manifest["sha256"]:
        raise ValueError("Estimates changed during postprocessing.")
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Output folder already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".ace-postprocess-", dir=output.parent) as temporary:
        stage = Path(temporary)
        payload = {
            "format": "ace-component-events-v1",
            "experiment": manifest["experiment"],
            "source_sha256": manifest["sha256"],
            "component_ids": manifest["component_ids"],
            "frame_rate": manifest["frame_rate"],
            "derivative": derivative,
            "event_height": float(event_height),
            "index_convention": "Zero-based indices in C or its first/second difference; no frame offset added.",
            "events_by_component_id": {
                str(original): events[local].tolist()
                for local, original in enumerate(manifest["component_ids"])
            },
        }
        (stage / "calcium-events.json").write_text(json.dumps(payload, indent=2, allow_nan=False))
        (stage / "source.json").write_text(
            json.dumps(
                {
                    "bundle": str(Path(bundle).expanduser().resolve()),
                    "estimates": manifest["estimates"],
                    "sha256": manifest["sha256"],
                    "parameters": manifest["parameters"],
                    "software": manifest["software"],
                },
                indent=2,
                allow_nan=False,
            )
        )
        stage.rename(output)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="Detect calcium events from an ACE cluster result bundle.")
    parser.add_argument("--bundle", required=True, help="Folder with manifest.json and CaImAn estimates")
    parser.add_argument("--output", required=True, help="New output folder for derived events")
    parser.add_argument("--derivative", choices=["zeroth", "first", "second"], default="first")
    parser.add_argument("--event-height", type=float, default=5)
    args = parser.parse_args(argv)
    print(postprocess_bundle(args.bundle, args.output, derivative=args.derivative, event_height=args.event_height))


if __name__ == "__main__":
    main()
