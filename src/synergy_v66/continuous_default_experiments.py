"""Continuous multi-cycle production-default experiments for V6.6.4-Q3.

Each path uses one parameterized CreditLedger for all cycles. Every cycle
introduces a previously unused borrower, issues one actual payable invoice,
processes its due date, resolves any default through the production waterfall,
and optionally replenishes reserves. All parameters are synthetic.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .credit import CreditLedger, EPS
from .network_topology import CellSpec
from .reserve_recovery import execute_reserve_recovery, plan_reserve_recovery

Q3_CYCLES = 100
Q3_CLAIM_AMOUNT = 100.0
Q3_BUYER_CASH = 10.0
Q3_SELLER_CASH = 20.0
Q3_RESERVE_MEMBER_CASH = 1000.0
Q3_LOCAL_RESERVE_TARGET = 45.0
Q3_FEDERATION_RESERVE_TARGET = 500.0
Q3_CASH_FLOOR = 500.0
Q3_PERIOD_CAP_FRACTION = 0.10
Q3_RECOVERY_RULES = (
    "no_replenishment",
    "equal",
    "production_capacity",
    "opening_cash",
    "adaptive_liquidity",
)


def _gini(values: list[float]) -> float:
    ordered = sorted(max(0.0, float(value)) for value in values)
    total = sum(ordered)
    if not ordered or total <= EPS:
        return 0.0
    n = len(ordered)
    weighted = sum((i + 1) * value for i, value in enumerate(ordered))
    return max(0.0, min(1.0, 2.0 * weighted / (n * total) - (n + 1) / n))


def _build_scenario(seed: int) -> dict[str, Any]:
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    cells: list[CellSpec] = []
    opening_cash: dict[str, float] = {}
    buyers_by_region: dict[str, list[str]] = {"WEST": [], "EAST": []}
    sellers_by_region: dict[str, list[str]] = {"WEST": [], "EAST": []}
    regional_members: dict[str, tuple[str, ...]] = {}
    federation_members: list[str] = []

    # Distinct borrower/seller pairs ensure 100 independent borrower identities.
    for region, prefix in (("WEST", "W"), ("EAST", "E")):
        for i in range(50):
            buyer = f"{prefix}-B{i:03d}"
            seller = f"{prefix}-S{i:03d}"
            buyers_by_region[region].append(buyer)
            sellers_by_region[region].append(seller)
            cells.append(CellSpec(buyer, region, "trade", "borrower", 1.0))
            cells.append(CellSpec(seller, region, "trade", "seller", 1.0))
            opening_cash[buyer] = Q3_BUYER_CASH
            opening_cash[seller] = Q3_SELLER_CASH

        reserve_ids = []
        for i in range(5):
            member = f"{prefix}-R{i:02d}"
            reserve_ids.append(member)
            federation_members.append(member)
            cells.append(CellSpec(member, region, "services", "reserve_member", float(i + 1)))
            opening_cash[member] = Q3_RESERVE_MEMBER_CASH
        regional_members[region] = tuple(reserve_ids)

    invoices = []
    for cycle in range(Q3_CYCLES):
        region = "WEST" if cycle % 2 == 0 else "EAST"
        index = cycle // 2
        buyer = buyers_by_region[region][index]
        seller = sellers_by_region[region][index]
        invoices.append({
            "invoice_id": f"Q3-{seed}-{cycle + 1:03d}",
            "buyer": buyer,
            "seller": seller,
            "region": region,
            "amount": Q3_CLAIM_AMOUNT,
            "issue_day": cycle,
            "due_day": cycle + 1,
        })

    scenario = {
        "seed": seed,
        "cells": tuple(cells),
        "opening_cash": opening_cash,
        "buyers_by_region": buyers_by_region,
        "sellers_by_region": sellers_by_region,
        "regional_members": regional_members,
        "federation_members": tuple(federation_members),
        "invoices": invoices,
    }
    fingerprint_payload = {
        "seed": seed,
        "opening_cash": opening_cash,
        "invoices": invoices,
        "regional_members": {k: list(v) for k, v in regional_members.items()},
        "federation_members": federation_members,
        "reserve_targets": {
            "regional": Q3_LOCAL_RESERVE_TARGET,
            "federation": Q3_FEDERATION_RESERVE_TARGET,
        },
    }
    scenario["path_fingerprint"] = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"),
                   allow_nan=False).encode("utf-8")
    ).hexdigest()
    return scenario


def _new_ledger(scenario: dict[str, Any]) -> CreditLedger:
    cells = scenario["cells"]
    regional_initial = {cell.cell_id: 0.0 for cell in cells}
    federation_initial = {cell.cell_id: 0.0 for cell in cells}
    for region, members in scenario["regional_members"].items():
        for member in members:
            regional_initial[member] = Q3_LOCAL_RESERVE_TARGET / len(members)
    for member in scenario["federation_members"]:
        federation_initial[member] = (
            Q3_FEDERATION_RESERVE_TARGET / len(scenario["federation_members"])
        )

    return CreditLedger(
        cells=cells,
        regions=("WEST", "EAST"),
        initial_cash_by_cell=dict(scenario["opening_cash"]),
        bank_limit_per_cell=0.0,
        trade_credit_limit_per_cell=1000.0,
        trade_receivable_limit_per_cell=1000.0,
        regional_pool_reserve_per_region=Q3_LOCAL_RESERVE_TARGET,
        regional_reserve_contributions_by_cell=regional_initial,
        federation_pool_reserve_total=Q3_FEDERATION_RESERVE_TARGET,
        federation_reserve_contributions_by_cell=federation_initial,
        federation_reserve_allocation_rule="first_come_first_served",
        grace_days=0,
        minimum_post_contribution_cash=Q3_CASH_FLOOR,
        reserve_recovery_contribution_fraction=Q3_PERIOD_CAP_FRACTION,
        regional_reserve_members_by_region=scenario["regional_members"],
        federation_reserve_members=scenario["federation_members"],
    )


def _run_one(scenario: dict[str, Any], recovery_rule: str) -> dict[str, Any]:
    if recovery_rule not in Q3_RECOVERY_RULES:
        raise ValueError(f"recovery_rule must be one of {Q3_RECOVERY_RULES}")
    ledger = _new_ledger(scenario)
    ledger.process_day(0)
    cycle_rows: list[dict[str, Any]] = []
    path_invoice_fingerprints = []
    total_recovery_requested = 0.0
    total_recovery_funded = 0.0
    total_recovered = 0.0
    max_cash_error = 0.0
    max_claim_reconciliation_error = 0.0
    max_seller_bad_debt_error = 0.0

    for cycle, invoice in enumerate(scenario["invoices"], start=1):
        issue = ledger.authorize_purchase(
            buyer=invoice["buyer"],
            seller=invoice["seller"],
            amount=invoice["amount"],
            due_day=invoice["due_day"],
            day=invoice["issue_day"],
            invoice_id=invoice["invoice_id"],
        )
        if not issue["authorized"]:
            raise RuntimeError(f"invoice rejected at cycle {cycle}: {issue['reason']}")
        path_invoice_fingerprints.append(invoice["invoice_id"])

        before_due = ledger.snapshot()
        ledger.process_day(invoice["due_day"])
        after_default = ledger.snapshot()
        default_events = [
            event for event in ledger.events
            if event.get("type") == "default_resolution"
            and event.get("invoice_id") == invoice["invoice_id"]
        ]
        if len(default_events) != 1:
            raise AssertionError(
                f"cycle {cycle}: expected exactly one production default resolution, got {len(default_events)}"
            )
        event = default_events[0]
        claim_requested = float(event["remaining_before_resolution"])
        local_paid = float(event["guarantee_paid"])
        federation_paid = float(event["federation_guarantee_paid"])
        member_assessment = float(event["member_assessment_paid"])
        written_off = float(event["written_off"])
        claim_paid = local_paid + federation_paid + member_assessment
        claim_error = abs(claim_requested - claim_paid - written_off)
        seller_bad_debt = float(after_default["trade_bad_debt_by_cell"][invoice["seller"]])
        seller_error = abs(seller_bad_debt - written_off)
        max_claim_reconciliation_error = max(max_claim_reconciliation_error, claim_error)
        max_seller_bad_debt_error = max(max_seller_bad_debt_error, seller_error)

        recovery_requested = recovery_funded = recovered = 0.0
        recovery_unfunded = 0.0
        if recovery_rule != "no_replenishment":
            plan = plan_reserve_recovery(
                ledger,
                target_regional_by_region={
                    "WEST": Q3_LOCAL_RESERVE_TARGET,
                    "EAST": Q3_LOCAL_RESERVE_TARGET,
                },
                target_federation=Q3_FEDERATION_RESERVE_TARGET,
                allocation_rule=recovery_rule,
            )
            recovery_requested = float(plan["requested_total"])
            recovery_funded = float(plan["funded_total"])
            recovery_unfunded = float(plan["unfunded_total"])
            total_recovery_requested += recovery_requested
            total_recovery_funded += recovery_funded
            if recovery_funded > EPS:
                result = execute_reserve_recovery(
                    ledger,
                    plan,
                    replenishment_id=f"Q3-{scenario['seed']}-{recovery_rule}-{cycle:03d}",
                    day=ledger.current_day,
                )
                recovered = float(result["total_amount"])
                total_recovered += recovered

        final_cycle = ledger.snapshot()
        cash_error = abs(float(final_cycle["cash_conservation_error"]))
        max_cash_error = max(max_cash_error, cash_error)
        defaulted_cells = set(final_cycle["defaulted_cells"])
        if invoice["buyer"] not in defaulted_cells:
            raise AssertionError(f"cycle {cycle}: buyer was not permanently defaulted")
        if ledger.accounts[invoice["buyer"]].defaulted is not True:
            raise AssertionError(f"cycle {cycle}: buyer default flag was lost")
        if ledger.accounts[invoice["buyer"]].cash > EPS:
            raise AssertionError(f"cycle {cycle}: defaulted buyer retained spendable cash")
        if final_cycle["bank_draws"] > EPS:
            raise AssertionError("closed-system Q3 fixture unexpectedly drew a bank line")

        cycle_rows.append({
            "cycle": cycle,
            "day": ledger.current_day,
            "invoice_id": invoice["invoice_id"],
            "region": invoice["region"],
            "buyer": invoice["buyer"],
            "seller": invoice["seller"],
            "buyer_defaulted": True,
            "claim_requested": claim_requested,
            "local_guarantee_paid": local_paid,
            "federation_guarantee_paid": federation_paid,
            "member_assessment_paid": member_assessment,
            "claim_paid": claim_paid,
            "claim_uncovered": written_off,
            "claim_reconciliation_error": claim_error,
            "seller_bad_debt_reconciliation_error": seller_error,
            "regional_west_balance": final_cycle["regional_pool_reserve_by_region"]["WEST"],
            "regional_east_balance": final_cycle["regional_pool_reserve_by_region"]["EAST"],
            "federation_balance": final_cycle["federation_pool_reserve_balance"],
            "recovery_requested": recovery_requested,
            "recovery_funded": recovery_funded,
            "recovery_unfunded": recovery_unfunded,
            "recovered": recovered,
            "member_cash_total": sum(final_cycle["cash_by_cell"].values()),
            "system_cash_total": (
                sum(final_cycle["cash_by_cell"].values())
                + sum(final_cycle["regional_pool_reserve_by_region"].values())
                + float(final_cycle["federation_pool_reserve_balance"])
            ),
            "cash_conservation_error": cash_error,
            "bank_draws": float(final_cycle["bank_draws"]),
            "external_inflows": float(final_cycle["customer_collections"]),
            "external_outflows": float(final_cycle["external_supplier_payments"]),
            "defaulted_borrowers": sum(
                cell_id.startswith(("W-B", "E-B")) for cell_id in defaulted_cells
            ),
        })

    final = ledger.snapshot()
    contribution_by_cell = {cell_id: 0.0 for cell_id in ledger.cell_by_id}
    period_contribution_by_cell: dict[str, dict[str, float]] = {}
    for event in ledger.events:
        if event.get("type") in {
            "regional_reserve_replenishment_contribution",
            "federation_reserve_replenishment_contribution",
        }:
            cell_id = event["cell_id"]
            amount = float(event["amount"])
            contribution_by_cell[cell_id] += amount
            period = str(event["recovery_period_id"])
            period_contribution_by_cell.setdefault(period, {}).setdefault(cell_id, 0.0)
            period_contribution_by_cell[period][cell_id] += amount

    cap_excess = max(
        (
            amount - ledger.initial_cash_by_cell[cell_id] * Q3_PERIOD_CAP_FRACTION
            for period_values in period_contribution_by_cell.values()
            for cell_id, amount in period_values.items()
        ),
        default=0.0,
    )
    member_ids = set(scenario["federation_members"])
    member_contributions = [contribution_by_cell[cell_id] for cell_id in sorted(member_ids)]
    reserve_members_floor_breaches = sum(
        final["cash_by_cell"][cell_id] < Q3_CASH_FLOOR - EPS for cell_id in member_ids
    )
    total_claims = sum(row["claim_requested"] for row in cycle_rows)
    total_paid = sum(row["claim_paid"] for row in cycle_rows)
    total_written_off = sum(row["claim_uncovered"] for row in cycle_rows)
    system_cash = (
        sum(final["cash_by_cell"].values())
        + sum(final["regional_pool_reserve_by_region"].values())
        + float(final["federation_pool_reserve_balance"])
    )
    opening_system_cash = sum(scenario["opening_cash"].values())
    return {
        "seed": scenario["seed"],
        "recovery_rule": recovery_rule,
        "path_fingerprint": scenario["path_fingerprint"],
        "cycle_count": len(cycle_rows),
        "invoice_count": len(ledger.payables),
        "defaulted_borrower_count": sum(
            account.defaulted for cell_id, account in ledger.accounts.items()
            if cell_id.startswith(("W-B", "E-B"))
        ),
        "total_claim_requested": total_claims,
        "local_guarantee_paid": sum(row["local_guarantee_paid"] for row in cycle_rows),
        "federation_guarantee_paid": sum(row["federation_guarantee_paid"] for row in cycle_rows),
        "member_assessment_paid": sum(row["member_assessment_paid"] for row in cycle_rows),
        "total_claim_paid": total_paid,
        "total_claim_uncovered": total_written_off,
        "claim_coverage_ratio": total_paid / total_claims if total_claims > EPS else 1.0,
        "claim_reconciliation_error": abs(total_claims - total_paid - total_written_off),
        "seller_bad_debt_reconciliation_error": max_seller_bad_debt_error,
        "recovery_requested": total_recovery_requested,
        "recovery_funded": total_recovery_funded,
        "recovery_unfunded": max(0.0, total_recovery_requested - total_recovery_funded),
        "total_member_contributions": sum(contribution_by_cell.values()),
        "contributor_gini": _gini(member_contributions),
        "top_20_percent_contribution_share": (
            sum(sorted(member_contributions, reverse=True)[:2]) / sum(member_contributions)
            if sum(member_contributions) > EPS else 0.0
        ),
        "max_30_day_cap_excess": max(0.0, cap_excess),
        "reserve_member_cash_floor_breaches": reserve_members_floor_breaches,
        "minimum_reserve_member_cash": min(final["cash_by_cell"][cell_id] for cell_id in member_ids),
        "final_regional_reserve_by_region": dict(final["regional_pool_reserve_by_region"]),
        "final_federation_reserve": float(final["federation_pool_reserve_balance"]),
        "initial_system_cash": opening_system_cash,
        "final_system_cash": system_cash,
        "system_cash_conservation_error": abs(system_cash - opening_system_cash),
        "max_ledger_cash_conservation_error": max_cash_error,
        "bank_draws": float(final["bank_draws"]),
        "external_inflows": float(final["customer_collections"]),
        "external_outflows": float(final["external_supplier_payments"]),
        "cycle_rows": cycle_rows,
        "invariants": {
            "100_distinct_production_defaults": len(cycle_rows) == Q3_CYCLES and len({
                row["buyer"] for row in cycle_rows
            }) == Q3_CYCLES,
            "all_claims_reconciled": abs(total_claims - total_paid - total_written_off) <= 1e-7,
            "seller_bad_debt_reconciled": max_seller_bad_debt_error <= 1e-7,
            "cash_conserved_each_cycle": max_cash_error <= 1e-7,
            "system_cash_conserved": abs(system_cash - opening_system_cash) <= 1e-7,
            "no_bank_draws": float(final["bank_draws"]) <= EPS,
            "no_external_cash_flows": (
                float(final["customer_collections"]) <= EPS
                and float(final["external_supplier_payments"]) <= EPS
            ),
            "no_defaulted_borrower_contributes": all(
                contribution_by_cell[cell_id] <= EPS
                for cell_id in ledger.accounts
                if cell_id.startswith(("W-B", "E-B"))
            ),
            "30_day_cap_respected": cap_excess <= 1e-7,
            "reserve_member_cash_floor_respected": reserve_members_floor_breaches == 0,
            "no_negative_reserves": (
                min(final["regional_pool_reserve_by_region"].values()) >= -EPS
                and float(final["federation_pool_reserve_balance"]) >= -EPS
            ),
            "all_cycle_claims_positive": all(row["claim_requested"] > EPS for row in cycle_rows),
        },
    }


def run_continuous_production_default_experiment(
    seeds: tuple[int, ...] = (11,),
    recovery_rules: tuple[str, ...] = Q3_RECOVERY_RULES,
) -> dict[str, Any]:
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be non-empty and unique")
    if any(not isinstance(seed, int) or isinstance(seed, bool) for seed in seeds):
        raise ValueError("seeds must be integers")
    if not recovery_rules or len(set(recovery_rules)) != len(recovery_rules):
        raise ValueError("recovery_rules must be non-empty and unique")
    if any(rule not in Q3_RECOVERY_RULES for rule in recovery_rules):
        raise ValueError(f"recovery_rules must be selected from {Q3_RECOVERY_RULES}")

    scenarios = [_build_scenario(seed) for seed in seeds]
    observations = []
    for scenario in scenarios:
        for rule in recovery_rules:
            observations.append(_run_one(scenario, rule))
    fingerprints_by_seed: dict[int, set[str]] = {}
    for row in observations:
        fingerprints_by_seed.setdefault(row["seed"], set()).add(row["path_fingerprint"])
    if any(len(values) != 1 for values in fingerprints_by_seed.values()):
        raise AssertionError("paired policies do not share identical invoice paths")

    return {
        "model_id": "SYNERGY_V6.6.4Q3_CONTINUOUS_PRODUCTION_DEFAULTS",
        "classification": (
            "synthetic research experiment using actual CreditLedger payable invoices "
            "and production default waterfall; not empirically calibrated"
        ),
        "cycles_per_path": Q3_CYCLES,
        "seeds": list(seeds),
        "recovery_rules": list(recovery_rules),
        "scenario_parameters": {
            "borrowers": 100,
            "sellers": 100,
            "reserve_members": 10,
            "opening_cash_borrower": Q3_BUYER_CASH,
            "opening_cash_seller": Q3_SELLER_CASH,
            "opening_cash_reserve_member": Q3_RESERVE_MEMBER_CASH,
            "invoice_amount": Q3_CLAIM_AMOUNT,
            "local_reserve_initial_and_target_per_region": Q3_LOCAL_RESERVE_TARGET,
            "federation_reserve_initial_and_target": Q3_FEDERATION_RESERVE_TARGET,
            "minimum_reserve_member_cash": Q3_CASH_FLOOR,
            "member_contribution_cap_per_30d": Q3_PERIOD_CAP_FRACTION,
            "cycle_spacing_days": 1,
            "default_schedule": "one fresh borrower defaults per day; WEST/EAST alternate",
            "local_fund_members": "five dedicated reserve members per region",
            "federation_fund_members": "all ten dedicated reserve members",
            "bank_lines": 0,
            "customer_invoices_or_external_inflows": 0,
        },
        "paired_path_fingerprints": {
            str(scenario["seed"]): scenario["path_fingerprint"] for scenario in scenarios
        },
        "results": observations,
    }
