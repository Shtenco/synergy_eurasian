#!/usr/bin/env python3
"""Run the continuous 100-cycle V6.6.4-Q3 production-default experiment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_v66.continuous_default_experiments import (
    Q3_RECOVERY_RULES,
    run_continuous_production_default_experiment,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=[11])
    parser.add_argument("--recovery-rules", nargs="+", choices=Q3_RECOVERY_RULES,
                        default=list(Q3_RECOVERY_RULES))
    parser.add_argument("--output", default="outputs/synergy_v664q3_continuous_defaults.json")
    args = parser.parse_args()

    report = run_continuous_production_default_experiment(
        seeds=tuple(args.seeds),
        recovery_rules=tuple(args.recovery_rules),
    )
    failed = [
        {"seed": row["seed"], "recovery_rule": row["recovery_rule"],
         "invariants": [key for key, value in row["invariants"].items() if not value]}
        for row in report["results"]
        if not all(row["invariants"].values())
    ]
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({
        "model_id": report["model_id"],
        "seeds": report["seeds"],
        "cycles_per_path": report["cycles_per_path"],
        "paths": len(report["results"]),
        "failed_invariants": failed,
        "summary": [
            {key: value for key, value in row.items() if key != "cycle_rows" and key != "invariants"}
            for row in report["results"]
        ],
        "output": str(output.relative_to(ROOT)),
    }, indent=2, allow_nan=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
