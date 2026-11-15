#!/usr/bin/env python3
"""Run paired 100-cycle SYNERGY reserve survival experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_v66.reserve_cycle_experiments import (
    ALLOCATION_RULES,
    run_paired_reserve_recovery_experiment,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-start", type=int, default=11)
    parser.add_argument("--seed-count", type=int, default=10)
    parser.add_argument("--cycles", type=int, default=100)
    parser.add_argument("--shock-regime", choices=("moderate", "severe", "systemic"), default="severe")
    parser.add_argument("--output", default="outputs/synergy_v664o_100_cycle_reserve_survival.json")
    parser.add_argument("--rules", nargs="+", choices=ALLOCATION_RULES, default=list(ALLOCATION_RULES))
    args = parser.parse_args()
    if args.seed_count < 1 or args.cycles < 1:
        parser.error("--seed-count and --cycles must be >= 1")

    report = run_paired_reserve_recovery_experiment(
        seeds=range(args.seed_start, args.seed_start + args.seed_count),
        cycles=args.cycles,
        shock_regime=args.shock_regime,
        allocation_rules=args.rules,
    )
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")

    print(json.dumps({
        "model_id": report["model_id"],
        "cycles": report["cycles"],
        "shock_regime": report["shock_regime"],
        "seeds": report["seeds"],
        "allocation_rules": report["allocation_rules"],
        "summary": report["summary"],
        "output": str(output.relative_to(ROOT)),
    }, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
