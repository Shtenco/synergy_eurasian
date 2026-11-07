"""Paired production-default batch experiments for SYNERGY V6.6.4-P.

Unlike the exogenous reserve stress harness, this module creates real payable
invoices and resolves them through CreditLedger.process_day and the production
default waterfall. The 100-invoice cohort is one correlated due-day batch,
not 100 sequential independent borrower defaults.
"""
from __future__ import annotations

import hashlib
import json
import random
from statistics import mean, median
from typing import Any, Iterable

from .credit import CreditLedger, EPS
from .network_topology import CELLS, REGIONS
from .reserve_recovery import execute_reserve_recovery, plan_reserve_recovery

CLEARING_RULES = ("first_come_first_served", "batch_pro_rata")
RECOVERY_RULES = (
    "no_replenishment",
    "equal",
    "production_capacity",
    "opening_cash",
    "adaptive_liquidity",
)
REGIONAL_TARGET = 20.0
FEDERATION_TARGET = 40.0
MINIMUM_CASH_FLOOR = 20.0
PERIOD_CONTRIBUTION_FRACTION = 0.10
BUYER_CASH = 20.0
SELLER_CASH = 100.0
INVOICE_COUNT_PER_BUYER = 10


def _gini(values: list[float]) -> float:
    ordered = sorted(max(0.0, float(value)) for value in values)
    total = sum(ordered)
    if not ordered or total <= EPS:
        return 0.0
    n = len(ordered)
    weighted = sum((index + 1) * value for index, value in enumerate(ordered))
    return max(0.0, min(1.0, (2.0 * weighted) / (n * total) - (n + 1) / n))


def _scenario(seed: int) -> tuple[dict[str, float], list[dict[str, Any]], list[str], list[str], str]:
    by_region = {
        region: sorted(cell.cell_id for cell in CELLS if cell.region == region)
        for region in REGIONS
    }
    if any(len(members) < 2 for members in by_region.values()):
        raise ValueError("each region needs at least two cells for the buyer/seller fixture")
    buyers = [cell_id for region in REGIONS for cell_id in by_region[region][: len(by_region[region]) // 2]]
    sellers = [cell_id for region in REGIONS for cell_id in by_region[region][len(by_region[region]) // 2 :]]
    if len(buyers) != len(sellers) or not buyers or not sellers:
        raise ValueError("the paired fixture requires equal non-empty buyer and seller groups")

    opening_cash = {
        cell.cell_id: (BUYER_CASH if cell.cell_id in buyers else SELLER_CASH)
        for cell in CELLS
    }
    rng = random.Random(seed)
    invoices: list[dict[str, Any]] = []
    for buyer_index, buyer in enumerate(buyers):
        rotation = buyer_index % len(sellers)
        seller_order = sellers[rotation:] + sellers[:rotation]
        for seller in seller_order:
            invoices.append({
                "invoice_id": f"SEED-{seed}-{buyer}-{seller}",
                "buyer": buyer,
                "seller": seller,
                "amount": round(rng.uniform(10.0, 15.0), 8),
                "issued_day": 0,
                "due_day": 1,
            })

    payload = {
        "opening_cash": opening_cash,
        "buyers": buyers,
        "sellers": sellers,
        "invoices": invoices,
        "regional_target": REGIONAL_TARGET,
        "federation_target": FEDERATION_TARGET,
        "cash_floor": MINIMUM_CASH_FLOOR,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return opening_cash, invoices, buyers, sellers, fingerprint


def _new_ledger(
    opening_cash: dict[str, float],
    sellers: list[str],
    clearing_rule: str,
) -> CreditLedger:
    regional_contributions = {cell.cell_id: 0.0 for cell in CELLS}
    federation_contributions = {cell.cell_id: 0.0 for cell in CELLS}
    sellers_by_region = {
        region: [cell_id for cell_id in sellers if next(c for c in CELLS if c.cell_id == cell_id).region == region]
        for region in REGIONS
    }
    for region, members in sellers_by_region.items():
        if not members:
            raise ValueError(f"no reserve-funding sellers in region {region}")
        per_member = REGIONAL_TARGET / len(members)
        for cell_id in members:
            regional_contributions[cell_id] = per_member
    federation_per_member = FEDERATION_TARGET / len(sellers)
    for cell_id in sellers:
        federation_contributions[cell_id] = federation_per_member

    return CreditLedger(
        initial_cash_by_cell=opening_cash,
        bank_limit_per_cell=0.0,
        trade_credit_limit_per_cell=1000.0,
        trade_receivable_limit_per_cell=1000.0,
        regional_pool_reserve_per_region=REGIONAL_TARGET,
        regional_reserve_contributions_by_cell=regional_contributions,
        federation_pool_reserve_total=FEDERATION_TARGET,
        federation_reserve_contributions_by_cell=federation_contributions,
        federation_reserve_allocation_rule=clearing_rule,
        grace_days=0,
        minimum_post_contribution_cash=MINIMUM_CASH_FLOOR,
        reserve_recovery_contribution_fraction=PERIOD_CONTRIBUTION_FRACTION,
    )


def _run_one(
    seed: int,
    clearing_rule: str,
    recovery_rule: str,
    opening_cash: dict[str, float],
    invoices: list[dict[str, Any]],
    buyers: list[str],
    sellers: list[str],
    path_fingerprint: str,
) -> dict[str, Any]:
    ledger = _new_ledger(opening_cash, sellers, clearing_rule)
    ledger.process_day(0)
    for invoice in invoices:
        result = ledger.authorize_purchase(
            buyer=invoice["buyer"],
            seller=invoice["seller"],
            amount=invoice["amount"],
            due_day=invoice["due_day"],
            day=invoice["issued_day"],
            invoice_id=invoice["invoice_id"],
        )
        if not result["authorized"]:
            raise RuntimeError(
                f"paired default fixture invoice was rejected: {invoice['invoice_id']} ({result['reason']})"
            )

    pre_default = ledger.snapshot()
    ledger.process_day(1)
    post_default = ledger.snapshot()
    default_events = [event for event in ledger.events if event.get("type") == "default_resolution"]
    claim_requested = sum(float(event["remaining_before_resolution"]) for event in default_events)
    local_paid = sum(float(event["guarantee_paid"]) for event in default_events)
    federation_paid = sum(float(event["federation_guarantee_paid"]) for event in default_events)
    assessment_paid = sum(float(event["member_assessment_paid"]) for event in default_events)
    written_off = sum(float(event["written_off"]) for event in default_events)
    claim_paid = local_paid + federation_paid + assessment_paid
    claim_reconciliation_error = abs(claim_requested - claim_paid - written_off)

    defaulted_cells = set(post_default["defaulted_cells"])
    defaulted_buyers = len(defaulted_cells.intersection(buyers))
    defaulted_sellers = len(defaulted_cells.intersection(sellers))
    seller_payouts = {cell_id: 0.0 for cell_id in sellers}
    for event in ledger.events:
        if event.get("type") in {"regional_pool_guarantee_paid", "federation_pool_guarantee_paid"}:
            seller_payouts[event["seller"]] += float(event["amount"])

    recovery_requested = 0.0
    recovery_unfunded = 0.0
    recovered = 0.0
    if recovery_rule != "no_replenishment":
        plan = plan_reserve_recovery(
            ledger,
            target_regional_by_region={region: REGIONAL_TARGET for region in REGIONS},
            target_federation=FEDERATION_TARGET,
            allocation_rule=recovery_rule,
        )
        recovery_requested = float(plan["requested_total"])
        recovery_unfunded = float(plan["unfunded_total"])
        if float(plan["funded_total"]) > EPS:
            settlement = execute_reserve_recovery(
                ledger,
                plan,
                replenishment_id=f"PROD-DEFAULT-RECOVERY-{seed}-{clearing_rule}-{recovery_rule}",
                day=ledger.current_day,
            )
            recovered = float(settlement["total_amount"])

    final = ledger.snapshot()
    contributions = {cell.cell_id: 0.0 for cell in CELLS}
    for event in ledger.events:
        if event.get("type") in {
            "regional_reserve_replenishment_contribution",
            "federation_reserve_replenishment_contribution",
        }:
            contributions[event["cell_id"]] += float(event["amount"])
    contributors = [cell_id for cell_id, amount in contributions.items() if amount > EPS]
    contribution_values = list(contributions.values())
    total_contributions = sum(contribution_values)
    top_count = max(1, math.ceil(0.20 * len(contribution_values)))
    top_share = (
        sum(sorted(contribution_values, reverse=True)[:top_count]) / total_contributions
        if total_contributions > EPS else 0.0
    )
    cap_excess = max(
        (
            contributions[cell_id] - opening_cash[cell_id] * PERIOD_CONTRIBUTION_FRACTION
            for cell_id in opening_cash
        ),
        default=0.0,
    )
    contributor_floor_breaches = sum(
        final["cash_by_cell"][cell_id] < MINIMUM_CASH_FLOOR - EPS
        for cell_id in contributors
    )
    minimum_contributor_cash = (
        min(final["cash_by_cell"][cell_id] for cell_id in contributors)
        if contributors else None
    )
    initial_system_cash = sum(opening_cash.values())
    final_system_cash = (
        sum(final["cash_by_cell"].values())
        + sum(final["regional_pool_reserve_by_region"].values())
        + float(final["federation_pool_reserve_balance"])
    )
    max_cash_error = max(
        abs(float(pre_default["cash_conservation_error"])),
        abs(float(post_default["cash_conservation_error"])),
        abs(float(final["cash_conservation_error"])),
    )
    requested_total = claim_requested
    coverage_ratio = claim_paid / requested_total if requested_total > EPS else 1.0

    return {
        "seed": seed,
        "clearing_rule": clearing_rule,
        "recovery_rule": recovery_rule,
        "paired_path_fingerprint": path_fingerprint,
        "invoice_count": len(invoices),
        "borrower_count": len(buyers),
        "seller_count": len(sellers),
        "default_resolution_invoice_count": len(default_events),
        "defaulted_buyer_count": defaulted_buyers,
        "defaulted_seller_count": defaulted_sellers,
        "cash_settled_before_default": sum(
            float(event["amount"]) for event in ledger.events
            if event.get("type") == "purchase_cash_settled"
        ),
        "total_claim_requested": requested_total,
        "local_guarantee_paid": local_paid,
        "federation_guarantee_paid": federation_paid,
        "member_assessment_paid": assessment_paid,
        "total_claim_paid": claim_paid,
        "total_claim_uncovered": written_off,
        "claim_coverage_ratio": coverage_ratio,
        "claim_reconciliation_error": claim_reconciliation_error,
        "seller_guarantee_payout_gini": _gini(list(seller_payouts.values())),
        "seller_guarantee_payout_by_cell": seller_payouts,
        "recovery_requested": recovery_requested,
        "recovery_unfunded": recovery_unfunded,
        "recovered": recovered,
        "recovery_funding_ratio": (
            (recovery_requested - recovery_unfunded) / recovery_requested
            if recovery_requested > EPS else 1.0
        ),
        "total_member_contributions": total_contributions,
        "member_contributions_by_cell": contributions,
        "contribution_gini": _gini(contribution_values),
        "top_20_percent_contribution_share": top_share,
        "max_contribution_opening_cash_ratio": max(
            (contributions[cell_id] / opening_cash[cell_id] for cell_id in opening_cash),
            default=0.0,
        ),
        "contributor_cash_floor_breach_count": contributor_floor_breaches,
        "minimum_contributor_cash": minimum_contributor_cash,
        "max_period_cap_excess": max(0.0, cap_excess),
        "final_regional_reserve_total": sum(final["regional_pool_reserve_by_region"].values()),
        "final_federation_reserve": float(final["federation_pool_reserve_balance"]),
        "max_cash_conservation_error": max_cash_error,
        "initial_system_cash": initial_system_cash,
        "final_system_cash": final_system_cash,
        "system_cash_change": final_system_cash - initial_system_cash,
        "bank_draws": float(final["bank_draws"]),
        "external_inflows": float(final["customer_collections"]),
        "external_outflows": float(final["external_supplier_payments"]),
        "customer_bad_debt": float(final["customer_bad_debt"]),
        "defaulted_cells": sorted(defaulted_cells),
        "interpretation_guard": (
            "Actual synthetic payable invoices resolved through CreditLedger.process_day and the "
            "production default waterfall. This is one correlated 100-invoice cohort with a single "
            "due-day default batch, not 100 sequential independent borrower defaults. All values "
            "and reserve assumptions are synthetic, not empirical EAEU estimates."
        ),
    }


def run_paired_production_default_batch_experiment(
    seeds: Iterable[int] = (11, 23, 37),
    clearing_rules: Iterable[str] = CLEARING_RULES,
    recovery_rules: Iterable[str] = RECOVERY_RULES,
) -> dict[str, Any]:
    """Compare real invoice-default clearing and recovery on paired 100-invoice cohorts."""
    seed_list = list(seeds)
    clear_list = list(clearing_rules)
    recovery_list = list(recovery_rules)
    if not seed_list or len(set(seed_list)) != len(seed_list):
        raise ValueError("seeds must be non-empty and unique")
    if any(not isinstance(seed, int) or isinstance(seed, bool) for seed in seed_list):
        raise ValueError("seeds must be integers")
    if not clear_list or len(set(clear_list)) != len(clear_list) or any(rule not in CLEARING_RULES for rule in clear_list):
        raise ValueError(f"clearing_rules must be a non-empty unique subset of {CLEARING_RULES}")
    if not recovery_list or len(set(recovery_list)) != len(recovery_list) or any(rule not in RECOVERY_RULES for rule in recovery_list):
        raise ValueError(f"recovery_rules must be a non-empty unique subset of {RECOVERY_RULES}")

    observations: dict[str, list[dict[str, Any]]] = {
        f"{clearing}|{recovery}": []
        for clearing in clear_list
        for recovery in recovery_list
    }
    paired_paths = []
    for seed in seed_list:
        opening_cash, invoices, buyers, sellers, fingerprint = _scenario(seed)
        paired_paths.append({"seed": seed, "path_fingerprint": fingerprint})
        for clearing in clear_list:
            for recovery in recovery_list:
                key = f"{clearing}|{recovery}"
                observations[key].append(
                    _run_one(
                        seed, clearing, recovery, opening_cash, invoices,
                        buyers, sellers, fingerprint,
                    )
                )

    scalar_metrics = (
        "invoice_count",
        "borrower_count",
        "seller_count",
        "default_resolution_invoice_count",
        "defaulted_buyer_count",
        "defaulted_seller_count",
        "total_claim_requested",
        "local_guarantee_paid",
        "federation_guarantee_paid",
        "total_claim_paid",
        "total_claim_uncovered",
        "claim_coverage_ratio",
        "claim_reconciliation_error",
        "seller_guarantee_payout_gini",
        "recovery_requested",
        "recovery_unfunded",
        "recovered",
        "recovery_funding_ratio",
        "total_member_contributions",
        "contribution_gini",
        "top_20_percent_contribution_share",
        "max_contribution_opening_cash_ratio",
        "contributor_cash_floor_breach_count",
        "max_period_cap_excess",
        "final_regional_reserve_total",
        "final_federation_reserve",
        "max_cash_conservation_error",
        "system_cash_change",
        "bank_draws",
        "external_inflows",
        "external_outflows",
    )
    summary = {
        key: {
            metric: {
                "mean": mean(float(row[metric]) for row in rows),
                "median": median(float(row[metric]) for row in rows),
                "min": min(float(row[metric]) for row in rows),
                "max": max(float(row[metric]) for row in rows),
            }
            for metric in scalar_metrics
        }
        for key, rows in observations.items()
    }
    all_rows = [row for rows in observations.values() for row in rows]
    invariants = {
        "all_borrower_cohorts_defaulted": all(row["defaulted_buyer_count"] == row["borrower_count"] for row in all_rows),
        "no_seller_defaults": all(row["defaulted_seller_count"] == 0 for row in all_rows),
        "defaulted_members_do_not_replenish": all(
            all(row["member_contributions_by_cell"][cell_id] <= EPS for cell_id in row["defaulted_cells"])
            for row in all_rows
        ),
        "reserve_payout_does_not_exceed_claims": all(
            row["total_claim_paid"] <= row["total_claim_requested"] + 1e-8 for row in all_rows
        ),
        "all_claims_reconciled": all(row["claim_reconciliation_error"] <= 1e-8 for row in all_rows),
        "cash_conserved": all(row["max_cash_conservation_error"] <= 1e-8 for row in all_rows),
        "zero_bank_draws": all(row["bank_draws"] <= EPS for row in all_rows),
        "zero_external_inflows": all(row["external_inflows"] <= EPS for row in all_rows),
        "zero_external_outflows": all(row["external_outflows"] <= EPS for row in all_rows),
        "contributor_cash_floor_enforced": all(row["contributor_cash_floor_breach_count"] == 0 for row in all_rows),
        "period_contribution_cap_enforced": all(row["max_period_cap_excess"] <= 1e-8 for row in all_rows),
    }
    return {
        "model_id": "SYNERGY_V6.6.4P_PRODUCTION_DEFAULT_BATCH",
        "invoice_cohort_size": INVOICE_COUNT_PER_BUYER * sum(
            sum(cell.region == region for cell in CELLS) // 2 for region in REGIONS
        ),
        "seeds": seed_list,
        "clearing_rules": clear_list,
        "recovery_rules": recovery_list,
        "paired_paths": paired_paths,
        "observations": observations,
        "summary": summary,
        "invariants": invariants,
        "interpretation_guard": (
            "This experiment uses actual payable invoice issuance, cash-first settlement, buyer "
            "cross-default and local-first/federation-second guarantee resolution. Each seed is one "
            "correlated due-day batch of 100 invoices, not a 100-day sequence of independent defaults. "
            "It is synthetic and is not an empirical EAEU solvency estimate."
        ),
    }
