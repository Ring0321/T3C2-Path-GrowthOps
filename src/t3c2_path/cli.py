"""Command-line entry points for deterministic synthetic demonstrations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from t3c2_path.application import GrowthOpsOrchestrator
from t3c2_path.audit import AppendOnlyAuditStore
from t3c2_path.demo import demo_request


RESEARCH_BOUNDARY = "synthetic_only_not_real_world_evidence"


def render_demo() -> dict[str, Any]:
    package = GrowthOpsOrchestrator(AppendOnlyAuditStore()).evaluate(demo_request())
    result = package.model_dump(mode="json")
    result["research_boundary"] = RESEARCH_BOUNDARY
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="t3c2-path",
        description="T3-C2 Path GrowthOps synthetic research CLI",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    demo = subcommands.add_parser("demo", help="run the fixed synthetic end-to-end case")
    demo.add_argument("--output", type=Path, help="optional UTF-8 JSON output path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "demo":
        return 2
    rendered = json.dumps(render_demo(), ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is None:
        print(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


__all__ = ["RESEARCH_BOUNDARY", "main", "render_demo"]
