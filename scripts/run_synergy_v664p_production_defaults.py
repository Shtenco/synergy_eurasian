#!/usr/bin/env python3
"""Run paired SYNERGY production payable-default batch experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_v66.default_batch_experiments import (
    CLEARING_RULES,
    RECOVERY_RULES,
    run_paired_production_default_batch_experiment,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-start", type=int, default=11)
    parser.add_argument("--seed-count", type=int, default=10)
    parser.add_argument("--output", default="outputs/synergy_v664p_production_default_batch.json")
    parser.add_argument("--clearing-rules", nargs="+", choices=CLEARING_RULES, default=list(CLEARING_RULES))
    parser.add_argument("--recovery-rules", nargs="+", choices=RECOVERY_RULES, default=list(RECOVERY_RULES))
    args = parser.parse_args()
    if args.seed_count < 1:
        parser.error("--seed-count must be >= 1")

    report = run_paired_production_default_batch_experiment(
        seeds=range(args.seed_start, args.seed_start + args.seed_count),
        clearing_rules=args.clearing_rules,
        recovery_rules=args.recovery_rules,
    )
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({
        "model_id": report["model_id"],
        "seeds": report["seeds"],
        "clearing_rules": report["clearing_rules"],
        "recovery_rules": report["recovery_rules"],
        "invariants": report["invariants"],
        "summary": report["summary"],
        "output": str(output.relative_to(ROOT)),
    }, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
