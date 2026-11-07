#!/usr/bin/env python3
"""Run reproducible paired V6.6.3 financing experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_v66.financing_experiments import compare_all_shock_regimes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-start", type=int, default=2026)
    parser.add_argument("--seed-count", type=int, default=10)
    parser.add_argument("--days", type=int, default=45)
    parser.add_argument("--output", default="outputs/synergy_v66_financing_experiment.json")
    args = parser.parse_args()
    if args.seed_count < 1 or args.days < 1:
        parser.error("--seed-count and --days must be >= 1")

    report = compare_all_shock_regimes(
        seeds=range(args.seed_start, args.seed_start + args.seed_count),
        days=args.days,
    )
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")

    for regime, comparison in report["reports_by_regime"].items():
        print(f"SHOCK REGIME: {regime}")
        for mode, metrics in comparison["summary"].items():
            deltas = comparison["paired_delta_summary_vs_unconstrained_reference"].get(mode, {})
            print(json.dumps({
                "mode": mode,
                "service_level_mean": metrics["service_level"]["mean"],
                "finished_output_mean": metrics["finished_output"]["mean"],
                "unmet_demand_mean": metrics["unmet_demand_units"]["mean"],
                "defaulted_cells_mean": metrics["defaulted_cells"]["mean"],
                "bank_debt_mean": metrics["bank_debt"]["mean"],
                "customer_bad_debt_mean": metrics["customer_bad_debt"]["mean"],
                "regional_pool_outstanding_mean": metrics["regional_pool_outstanding"]["mean"],
                "regional_pool_rejections_mean": metrics["regional_pool_rejections"]["mean"],
                "paired_delta_service_level_vs_reference": deltas.get("service_level", {}).get("mean"),
                "paired_delta_unmet_demand_vs_reference": deltas.get("unmet_demand_units", {}).get("mean"),
                "paired_delta_defaults_vs_reference": deltas.get("defaulted_cells", {}).get("mean"),
                "physical_balance_error_max": metrics["physical_balance_error"]["max"],
                "cash_conservation_error_max": metrics["cash_conservation_error"]["max"],
            }, sort_keys=True))
    print(f"REPORT_WRITTEN: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
