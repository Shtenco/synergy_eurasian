#!/usr/bin/env python3
"""Run reproducible paired V6.6.3 financing experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from synergy_v66.financing_experiments import (
    compare_all_shock_regimes,
    compare_regional_pool_sensitivities,
    compare_reserve_contribution_schemes,
    compare_regional_loss_waterfalls,
    compare_liquidity_capped_reserve_contributions,
    make_synthetic_heterogeneous_cash_fixture,
    compare_regional_reserve_size_sensitivities,
    compare_liquidity_capped_federation_contributions,
    compare_federation_reserve_allocation_rules,
    analyze_claim_class_relabeling_incentives,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-start", type=int, default=2026)
    parser.add_argument("--seed-count", type=int, default=10)
    parser.add_argument("--days", type=int, default=45)
    parser.add_argument("--output", default="outputs/synergy_v66_financing_experiment.json")
    parser.add_argument("--sensitivity", action="store_true")
    parser.add_argument("--reserve-allocation", action="store_true")
    parser.add_argument("--loss-waterfall", action="store_true")
    parser.add_argument("--liquidity-capped-reserve", action="store_true")
    parser.add_argument("--reserve-sizing", action="store_true")
    parser.add_argument("--federation-liquidity-cap", action="store_true")
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
                "regional_pool_reserve_balance_mean": metrics["regional_pool_reserve_balance"]["mean"],
                "regional_pool_guarantee_paid_mean": metrics["regional_pool_guarantee_paid"]["mean"],
                "trade_bad_debt_mean": metrics["trade_bad_debt"]["mean"],
                "external_supplier_bad_debt_mean": metrics["external_supplier_bad_debt"]["mean"],
                "paired_delta_service_level_vs_reference": deltas.get("service_level", {}).get("mean"),
                "paired_delta_unmet_demand_vs_reference": deltas.get("unmet_demand_units", {}).get("mean"),
                "paired_delta_defaults_vs_reference": deltas.get("defaulted_cells", {}).get("mean"),
                "physical_balance_error_max": metrics["physical_balance_error"]["max"],
                "cash_conservation_error_max": metrics["cash_conservation_error"]["max"],
            }, sort_keys=True))
    print(f"REPORT_WRITTEN: {output}")

    if args.sensitivity:
        sensitivity = compare_regional_pool_sensitivities(
            seeds=range(args.seed_start, args.seed_start + args.seed_count),
            days=args.days,
            shock_regime="severe",
            pool_limits=(5.0, 150.0),
            member_limits=(2.0, 80.0),
        )
        sensitivity_path = output.with_name("synergy_v66_regional_pool_sensitivity.json")
        sensitivity_path.write_text(json.dumps(sensitivity, indent=2, allow_nan=False), encoding="utf-8")
        for case in sensitivity["sensitivity_reports"]:
            print(json.dumps({
                "pool_limit_per_region": case["pool_limit_per_region"],
                "member_limit_per_cell": case["member_debit_and_credit_limit_per_cell"],
                "mutual_credit_pool_rejections_mean": case["summary"]["mutual_credit"]["regional_pool_rejections"]["mean"],
                "hybrid_pool_rejections_mean": case["summary"]["hybrid"]["regional_pool_rejections"]["mean"],
                "mutual_credit_service_level_mean": case["summary"]["mutual_credit"]["service_level"]["mean"],
                "hybrid_service_level_mean": case["summary"]["hybrid"]["service_level"]["mean"],
            }, sort_keys=True))
        print(f"SENSITIVITY_REPORT_WRITTEN: {sensitivity_path}")

    if args.reserve_allocation:
        cash_fixture = make_synthetic_heterogeneous_cash_fixture()
        allocation = compare_reserve_contribution_schemes(
            seeds=range(args.seed_start, args.seed_start + args.seed_count),
            days=args.days,
            shock_regime="severe",
            reserve_per_region=20.0,
            base_config={"initial_cash_by_cell": cash_fixture},
        )
        allocation_path = output.with_name("synergy_v66_reserve_contribution_allocation.json")
        allocation_path.write_text(json.dumps(allocation, indent=2, allow_nan=False), encoding="utf-8")
        for scheme, payload in allocation["reports_by_contribution_scheme"].items():
            comparison = payload["comparison"]
            for mode in ("mutual_credit", "hybrid"):
                metrics = comparison["summary"][mode]
                print(json.dumps({
                    "contribution_scheme": scheme,
                    "mode": mode,
                    "service_level_mean": metrics["service_level"]["mean"],
                    "defaults_mean": metrics["defaulted_cells"]["mean"],
                    "reserve_guarantee_paid_mean": metrics["regional_pool_guarantee_paid"]["mean"],
                    "seller_trade_bad_debt_mean": metrics["trade_bad_debt"]["mean"],
                    "reserve_balance_mean": metrics["regional_pool_reserve_balance"]["mean"],
                    "cash_conservation_error_max": metrics["cash_conservation_error"]["max"],
                }, sort_keys=True))
        print(f"ALLOCATION_REPORT_WRITTEN: {allocation_path}")

    if args.loss_waterfall:
        waterfall = compare_regional_loss_waterfalls(
            seeds=range(args.seed_start, args.seed_start + args.seed_count),
            days=args.days,
            shock_regime="severe",
            reserve_per_region=20.0,
            assessment_rate=0.10,
            assessment_limit_per_cell=2.0,
        )
        waterfall_path = output.with_name("synergy_v66_regional_loss_waterfall.json")
        waterfall_path.write_text(json.dumps(waterfall, indent=2, allow_nan=False), encoding="utf-8")
        for case, report in waterfall["reports_by_waterfall"].items():
            for mode in ("mutual_credit", "hybrid"):
                metrics = report["summary"][mode]
                print(json.dumps({
                    "loss_waterfall": case,
                    "mode": mode,
                    "service_level_mean": metrics["service_level"]["mean"],
                    "defaults_mean": metrics["defaulted_cells"]["mean"],
                    "reserve_paid_mean": metrics["regional_pool_guarantee_paid"]["mean"],
                    "member_assessment_paid_mean": metrics["regional_member_assessment_paid"]["mean"],
                    "member_assessment_requested_mean": metrics["regional_assessment_requested"]["mean"],
                    "member_assessment_eligible_capacity_mean": metrics["regional_assessment_eligible_capacity"]["mean"],
                    "seller_trade_bad_debt_mean": metrics["trade_bad_debt"]["mean"],
                    "cash_conservation_error_max": metrics["cash_conservation_error"]["max"],
                }, sort_keys=True))
        for case_name, case in waterfall["targeted_default_stress"]["cases"].items():
            print(json.dumps({
                "targeted_default_case": case_name,
                "guarantee_paid": case["guarantee_paid"],
                "federation_guarantee_paid": case["federation_guarantee_paid"],
                "member_assessment_paid": case["member_assessment_paid"],
                "written_off": case["written_off"],
                "assessment_attempts": case["regional_assessment_attempt_count"],
                "cash_conservation_error": case["cash_conservation_error"],
            }, sort_keys=True))
        print(f"LOSS_WATERFALL_REPORT_WRITTEN: {waterfall_path}")
        reserve_allocation = compare_federation_reserve_allocation_rules(
            claims=[
                {"invoice_id": "CLAIM-003", "due_day": 0, "eligible_amount": 30.0, "claim_class": "ordinary"},
                {"invoice_id": "CLAIM-001", "due_day": 2, "eligible_amount": 10.0, "claim_class": "essential"},
                {"invoice_id": "CLAIM-002", "due_day": 1, "eligible_amount": 20.0, "claim_class": "essential"},
            ],
            reserve_available=25.0,
            priority_order=["essential", "ordinary"],
        )
        allocation_path = output.with_name("synergy_v66_federation_reserve_allocation_rules.json")
        allocation_path.write_text(json.dumps(reserve_allocation, indent=2, allow_nan=False), encoding="utf-8")
        for rule, allocation in reserve_allocation["reports_by_rule"].items():
            print(json.dumps({
                "federation_reserve_allocation_rule": rule,
                "priority_order": allocation["priority_order"],
                "reserve_available": allocation["reserve_opening"],
                "eligible_claim_total": allocation["eligible_claim_total"],
                "allocated_total": allocation["allocated_total"],
                "reserve_remaining": allocation["reserve_remaining"],
                "uncovered_total": sum(allocation["uncovered_by_invoice"].values()),
            }, sort_keys=True))
        print(f"FEDERATION_RESERVE_ALLOCATION_REPORT_WRITTEN: {allocation_path}")
        relabeling = analyze_claim_class_relabeling_incentives(
            claims=[
                {"invoice_id": "ORDINARY", "due_day": 0, "eligible_amount": 30.0, "claim_class": "ordinary"},
                {"invoice_id": "ESSENTIAL", "due_day": 1, "eligible_amount": 10.0, "claim_class": "essential"},
            ],
            reserve_available=20.0,
            priority_order=["essential", "ordinary"],
            allocation_rule="priority_class_then_batch_pro_rata",
        )
        relabeling_path = output.with_name("synergy_v66_claim_class_relabeling_sensitivity.json")
        relabeling_path.write_text(json.dumps(relabeling, indent=2, allow_nan=False), encoding="utf-8")
        for item in relabeling["relabeling_sensitivity"]:
            print(json.dumps({
                "claim_class_relabeling": item["invoice_id"],
                "original_class": item["original_class"],
                "relabeled_class": item["relabeled_class"],
                "payout_before": item["payout_before"],
                "payout_after": item["payout_after"],
                "claimant_payout_delta": item["claimant_payout_delta"],
                "other_claim_payout_delta_total": item["other_claim_payout_delta_total"],
            }, sort_keys=True))
        print(f"CLAIM_CLASS_RELABELING_REPORT_WRITTEN: {relabeling_path}")

    if args.liquidity_capped_reserve:
        cash_fixture = make_synthetic_heterogeneous_cash_fixture()
        liquidity_report = compare_liquidity_capped_reserve_contributions(
            seeds=range(args.seed_start, args.seed_start + args.seed_count),
            initial_cash_by_cell=cash_fixture,
            days=args.days,
            shock_regime="severe",
            reserve_per_region=10.0,
            max_contribution_fraction=0.10,
            scheme="production_capacity_weighted",
            minimum_post_contribution_cash=75.0,
        )
        liquidity_path = output.with_name("synergy_v66_liquidity_capped_reserve.json")
        liquidity_path.write_text(json.dumps(liquidity_report, indent=2, allow_nan=False), encoding="utf-8")
        comparison = liquidity_report["comparison"]
        for mode in ("mutual_credit", "hybrid"):
            metrics = comparison["summary"][mode]
            print(json.dumps({
                "liquidity_capped_reserve": True,
                "mode": mode,
                "reserve_per_region": liquidity_report["reserve_per_region"],
                "max_contribution_fraction": liquidity_report["max_contribution_fraction"],
                "minimum_post_contribution_cash": liquidity_report["minimum_post_contribution_cash"],
                "service_level_mean": metrics["service_level"]["mean"],
                "defaults_mean": metrics["defaulted_cells"]["mean"],
                "reserve_paid_mean": metrics["regional_pool_guarantee_paid"]["mean"],
                "member_contribution_total": sum(liquidity_report["contributions_by_cell"].values()),
                "cash_conservation_error_max": metrics["cash_conservation_error"]["max"],
            }, sort_keys=True))
        print(f"LIQUIDITY_CAPPED_REPORT_WRITTEN: {liquidity_path}")

    if args.reserve_sizing:
        cash_fixture = make_synthetic_heterogeneous_cash_fixture()
        sizing = compare_regional_reserve_size_sensitivities(
            seeds=range(args.seed_start, args.seed_start + args.seed_count),
            reserve_levels_per_region=(0.0, 5.0, 10.0, 20.0, 40.0),
            days=args.days,
            shock_regime="severe",
            contribution_scheme="equal_all_members",
            max_contribution_fraction=0.10,
            base_config={"initial_cash_by_cell": cash_fixture},
            minimum_post_contribution_cash=75.0,
        )
        sizing_path = output.with_name("synergy_v66_regional_reserve_sizing.json")
        sizing_path.write_text(json.dumps(sizing, indent=2, allow_nan=False), encoding="utf-8")
        for item in sizing["sensitivity_reports"]:
            for mode, metrics in item["diagnostics"].items():
                print(json.dumps({
                    "reserve_per_region": item["reserve_per_region"],
                    "minimum_post_contribution_cash": sizing["minimum_post_contribution_cash"],
                    "mode": mode,
                    "reserve_paid_mean": metrics["reserve_paid_mean"],
                    "reserve_remaining_mean": metrics["reserve_remaining_mean"],
                    "reserve_exhaustion_rate": metrics["reserve_exhaustion_rate"],
                    "reserve_utilization_mean": metrics["reserve_utilization_mean"],
                    "seller_trade_bad_debt_mean": metrics["seller_trade_bad_debt_mean"],
                    "service_level_mean": metrics["service_level_mean"],
                    "defaults_mean": metrics["defaults_mean"],
                    "cash_conservation_error_max": metrics["cash_conservation_error_max"],
                }, sort_keys=True))
        print(f"RESERVE_SIZING_REPORT_WRITTEN: {sizing_path}")

    if args.federation_liquidity_cap:
        cash_fixture = make_synthetic_heterogeneous_cash_fixture()
        federal_report = compare_liquidity_capped_federation_contributions(
            seeds=range(args.seed_start, args.seed_start + args.seed_count),
            initial_cash_by_cell=cash_fixture,
            reserve_total=10.0,
            max_combined_contribution_fraction=0.10,
            scheme="production_capacity_weighted",
            days=args.days,
            shock_regime="severe",
            base_config={
                "regional_pool_reserve_per_region": 5.0,
                "regional_reserve_contributions_by_cell": {
                    cell_id: 0.5 for cell_id in cash_fixture
                },
            },
            minimum_post_contribution_cash=75.0,
        )
        federal_path = output.with_name("synergy_v66_federation_liquidity_cap.json")
        federal_path.write_text(json.dumps(federal_report, indent=2, allow_nan=False), encoding="utf-8")
        comparison = federal_report["comparison"]
        for mode in ("mutual_credit", "hybrid"):
            metrics = comparison["summary"][mode]
            print(json.dumps({
                "federation_liquidity_cap": True,
                "mode": mode,
                "federation_reserve_total": federal_report["reserve_total"],
                "federation_contribution_total": sum(federal_report["federation_contributions_by_cell"].values()),
                "combined_contribution_cap_fraction": federal_report["max_combined_contribution_fraction"],
                "minimum_post_contribution_cash": federal_report["minimum_post_contribution_cash"],
                "service_level_mean": metrics["service_level"]["mean"],
                "federation_guarantee_paid_mean": metrics["federation_pool_guarantee_paid"]["mean"],
                "federation_reserve_remaining_mean": metrics["federation_pool_reserve_balance"]["mean"],
                "cash_conservation_error_max": metrics["cash_conservation_error"]["max"],
            }, sort_keys=True))
        print(f"FEDERATION_LIQUIDITY_CAP_REPORT_WRITTEN: {federal_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
