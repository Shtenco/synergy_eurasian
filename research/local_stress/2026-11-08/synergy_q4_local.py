"""SYNERGY EURASIAN — Q4 local correlated-default and reserve-recovery stress harness.

Independent research model. It is NOT the production CreditLedger implementation.
All balances, claims, cash burns and membership rules are explicit synthetic assumptions.
Run: python /mnt/data/synergy_q4_local.py
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Tuple
import json
import math

EPS = 1e-9
REGIONS = ("WEST", "EAST")
CELLS = tuple([f"W{i}" for i in range(10)] + [f"E{i}" for i in range(10)])
CELL_REGION = {c: ("WEST" if c.startswith("W") else "EAST") for c in CELLS}
INITIAL_MEMBER_CASH = {c: 1_000.0 for c in CELLS}
INITIAL_REGIONAL_RESERVES = {"WEST": 45.0, "EAST": 45.0}
INITIAL_FEDERATION_RESERVE = 500.0
REGIONAL_TARGETS = dict(INITIAL_REGIONAL_RESERVES)
FEDERATION_TARGET = INITIAL_FEDERATION_RESERVE
REGIONAL_MEMBERS = {
    "WEST": frozenset({"W0", "W1", "W2"}),
    "EAST": frozenset({"E0", "E1", "E2"}),
}
FEDERATION_MEMBERS = frozenset({"W2", "W3", "W4", "W5", "E2", "E3", "E4", "E5"})
CASH_FLOOR = 900.0
PERIOD_CONTRIBUTION_CAP_FRACTION = 0.10

# Three correlated due-date waves. Borrowers are deliberately concentrated among
# reserve members, so default exclusion progressively shrinks the recovery base.
DEFAULT_WAVES = (
    ("W0", "W1", "E0", "E1"),
    ("W2", "W3", "E2", "E3"),
    ("W4", "E4"),
)
EXTERNAL_OPERATING_CASH_BURN_PER_DEFAULT = 800.0


@dataclass(frozen=True)
class Claim:
    claim_id: str
    buyer: str
    seller: str
    buyer_region: str
    amount: float


def make_wave_claims(wave_index: int, borrowers: Iterable[str], claim_multiplier: float = 1.0) -> List[Claim]:
    """Two invoices per defaulting borrower: one cross-region and one local."""
    if claim_multiplier <= 0:
        raise ValueError("claim_multiplier must be positive")
    claims: List[Claim] = []
    for buyer_index, buyer in enumerate(borrowers):
        region = CELL_REGION[buyer]
        opposite = "EAST" if region == "WEST" else "WEST"
        local_sellers = [f"{region[0]}{n}" for n in range(5, 10)]
        cross_sellers = [f"{'E' if opposite == 'EAST' else 'W'}{n}" for n in range(5, 10)]
        # Deterministic rotation prevents one seller from absorbing every payout.
        seller_cross = cross_sellers[(wave_index + buyer_index) % len(cross_sellers)]
        seller_local = local_sellers[(2 * wave_index + buyer_index) % len(local_sellers)]
        base = 115.0 + 25.0 * wave_index + 9.0 * buyer_index
        claims.append(Claim(f"Q4-{wave_index+1}-{buyer}-X", buyer, seller_cross, region, (base + 17.0) * claim_multiplier))
        claims.append(Claim(f"Q4-{wave_index+1}-{buyer}-L", buyer, seller_local, region, base * claim_multiplier))
    return claims


def _allocate(amount: float, members: Iterable[str], capacity: Dict[str, float], rule: str):
    eligible = sorted(c for c in members if capacity.get(c, 0.0) > EPS)
    total = sum(capacity[c] for c in eligible)
    paid = min(amount, total)
    out = {c: 0.0 for c in eligible}
    if rule == "pro_rata":
        if total > EPS:
            for c in eligible:
                out[c] = paid * capacity[c] / total
    elif rule == "fcfs":
        left = paid
        for c in eligible:
            take = min(left, capacity[c])
            out[c] = take
            left -= take
    else:
        raise ValueError("recovery_rule must be 'pro_rata' or 'fcfs'")
    return out, amount - paid


def _payout_claims(claims: List[Claim], regional_reserves: Dict[str, float],
                   federation_reserve: float, federation_clearing: str):
    """Local reserve first; federation second. Batch pro-rata applies only to federation."""
    residual: Dict[str, float] = {}
    payouts: Dict[str, float] = {c.claim_id: 0.0 for c in claims}
    local_paid = {r: 0.0 for r in REGIONS}
    # Local first-loss reserve: deterministic claim order within each debtor region.
    for region in REGIONS:
        left = regional_reserves[region]
        for claim in sorted((x for x in claims if x.buyer_region == region), key=lambda x: x.claim_id):
            paid = min(left, claim.amount)
            payouts[claim.claim_id] += paid
            local_paid[region] += paid
            left -= paid
            residual[claim.claim_id] = claim.amount - paid
        regional_reserves[region] = left

    fed_due = {c.claim_id: residual.get(c.claim_id, c.amount) for c in claims}
    total_due = sum(fed_due.values())
    fed_paid_by_claim = {c.claim_id: 0.0 for c in claims}
    fed_paid = min(federation_reserve, total_due)
    if federation_clearing == "fcfs":
        left = fed_paid
        for claim in sorted(claims, key=lambda x: x.claim_id):
            take = min(left, fed_due[claim.claim_id])
            fed_paid_by_claim[claim.claim_id] = take
            left -= take
    elif federation_clearing == "batch_pro_rata":
        if total_due > EPS:
            for claim in claims:
                fed_paid_by_claim[claim.claim_id] = fed_paid * fed_due[claim.claim_id] / total_due
    else:
        raise ValueError("federation_clearing must be 'fcfs' or 'batch_pro_rata'")
    for claim in claims:
        payouts[claim.claim_id] += fed_paid_by_claim[claim.claim_id]
    federation_reserve -= fed_paid
    uncovered = {c.claim_id: max(0.0, c.amount - payouts[c.claim_id]) for c in claims}
    return {
        "payouts": payouts,
        "local_paid": local_paid,
        "federation_paid": fed_paid,
        "uncovered": uncovered,
        "regional_reserves_after": regional_reserves,
        "federation_reserve_after": federation_reserve,
    }


def run_experiment(recovery_rule="pro_rata", federation_clearing="batch_pro_rata",
                   claim_multiplier=1.0, cash_burn_per_default=EXTERNAL_OPERATING_CASH_BURN_PER_DEFAULT):
    if recovery_rule not in ("pro_rata", "fcfs"):
        raise ValueError("invalid recovery_rule")
    if claim_multiplier <= 0 or cash_burn_per_default < 0:
        raise ValueError("invalid stress parameter")
    cash = dict(INITIAL_MEMBER_CASH)
    regional_reserves = dict(INITIAL_REGIONAL_RESERVES)
    federation_reserve = INITIAL_FEDERATION_RESERVE
    defaulted = set()
    cumulative_external_burn = 0.0
    cumulative_claims = 0.0
    cumulative_buyer_cash_paid = 0.0
    cumulative_local_paid = {r: 0.0 for r in REGIONS}
    cumulative_fed_paid = 0.0
    cumulative_uncovered = 0.0
    cumulative_contributions = 0.0
    cumulative_seller_receipts = {c: 0.0 for c in CELLS}
    cumulative_seller_bad_debt = {c: 0.0 for c in CELLS}
    cumulative_member_contributions = {c: 0.0 for c in CELLS}
    max_abs_conservation_residual = 0.0
    rows = []
    initial_system_cash = sum(cash.values()) + sum(regional_reserves.values()) + federation_reserve

    for wave_no, borrowers in enumerate(DEFAULT_WAVES, start=1):
        wave_index = wave_no - 1
        # Exogenous operating burn is a real external cash outflow, recorded separately.
        burn = 0.0
        for buyer in borrowers:
            amount = min(cash_burn_per_default, cash[buyer])
            cash[buyer] -= amount
            burn += amount
            defaulted.add(buyer)
        cumulative_external_burn += burn
        after_burn_total = sum(cash.values()) + sum(regional_reserves.values()) + federation_reserve
        burn_residual = after_burn_total - (initial_system_cash - cumulative_external_burn)
        max_abs_conservation_residual = max(max_abs_conservation_residual, abs(burn_residual))
        assert abs(burn_residual) < 1e-7

        claims = make_wave_claims(wave_index, borrowers, claim_multiplier)
        claims_total = sum(c.amount for c in claims)
        cumulative_claims += claims_total

        # Production-style cash-first settlement: each defaulting buyer uses all
        # remaining cash against its due invoices before guarantee reserves are called.
        # Any residual is the actual default claim presented to the waterfall.
        buyer_cash_paid_by_claim = {c.claim_id: 0.0 for c in claims}
        residual_claims = []
        for claim in sorted(claims, key=lambda x: (x.buyer, x.claim_id)):
            paid_by_buyer = min(cash[claim.buyer], claim.amount)
            cash[claim.buyer] -= paid_by_buyer
            cash[claim.seller] += paid_by_buyer
            buyer_cash_paid_by_claim[claim.claim_id] = paid_by_buyer
            residual = claim.amount - paid_by_buyer
            residual_claims.append(Claim(claim.claim_id, claim.buyer, claim.seller,
                                         claim.buyer_region, residual))
            cumulative_buyer_cash_paid += paid_by_buyer
        unpaid_by_buyer = {buyer: sum(c.amount for c in residual_claims if c.buyer == buyer)
                           for buyer in borrowers}
        assert all(unpaid_by_buyer[buyer] > EPS and cash[buyer] <= EPS for buyer in borrowers), (
            wave_no, unpaid_by_buyer, {b: cash[b] for b in borrowers})
        after_buyer_settlement_total = sum(cash.values()) + sum(regional_reserves.values()) + federation_reserve
        buyer_settlement_residual = after_buyer_settlement_total - (initial_system_cash - cumulative_external_burn)
        max_abs_conservation_residual = max(max_abs_conservation_residual, abs(buyer_settlement_residual))
        assert abs(buyer_settlement_residual) < 1e-7

        payout = _payout_claims(residual_claims, regional_reserves, federation_reserve, federation_clearing)
        regional_reserves = payout["regional_reserves_after"]
        federation_reserve = payout["federation_reserve_after"]
        for claim in claims:
            received = buyer_cash_paid_by_claim[claim.claim_id] + payout["payouts"][claim.claim_id]
            cash[claim.seller] += payout["payouts"][claim.claim_id]
            cumulative_seller_receipts[claim.seller] += received
        wave_local_paid = payout["local_paid"]
        wave_fed_paid = payout["federation_paid"]
        wave_uncovered = sum(payout["uncovered"].values())
        for r in REGIONS:
            cumulative_local_paid[r] += wave_local_paid[r]
        cumulative_fed_paid += wave_fed_paid
        cumulative_uncovered += wave_uncovered
        for claim in claims:
            cumulative_seller_bad_debt[claim.seller] += payout["uncovered"][claim.claim_id]
        after_payout_total = sum(cash.values()) + sum(regional_reserves.values()) + federation_reserve
        payout_residual = after_payout_total - (initial_system_cash - cumulative_external_burn)
        max_abs_conservation_residual = max(max_abs_conservation_residual, abs(payout_residual))
        assert abs(payout_residual) < 1e-7
        wave_buyer_cash_paid = sum(buyer_cash_paid_by_claim.values())
        assert abs(wave_buyer_cash_paid + sum(payout["payouts"].values()) + wave_uncovered - claims_total) < 1e-7

        # Recovery capacity is measured from each member's opening cash for this
        # 30-day recovery period (after claim receipts and before any contributions).
        opening_cash = dict(cash)
        capacity = {}
        for cell in CELLS:
            if cell in defaulted or opening_cash[cell] < CASH_FLOOR - EPS:
                capacity[cell] = 0.0
            else:
                capacity[cell] = max(0.0, min(
                    PERIOD_CONTRIBUTION_CAP_FRACTION * opening_cash[cell],
                    opening_cash[cell] - CASH_FLOOR,
                ))
        contribution_map = {c: 0.0 for c in CELLS}
        eligible_recovery_members = sum(1 for c in CELLS if capacity[c] > EPS)
        regional_recovery = {}
        regional_shortfall = {}
        for region in REGIONS:
            need = max(0.0, REGIONAL_TARGETS[region] - regional_reserves[region])
            alloc, shortfall = _allocate(need, REGIONAL_MEMBERS[region] - defaulted, capacity, recovery_rule)
            regional_recovery[region] = sum(alloc.values())
            regional_shortfall[region] = shortfall
            for cell, amount in alloc.items():
                contribution_map[cell] += amount
                capacity[cell] -= amount
                regional_reserves[region] += amount
        fed_need = max(0.0, FEDERATION_TARGET - federation_reserve)
        fed_alloc, fed_shortfall = _allocate(fed_need, FEDERATION_MEMBERS - defaulted, capacity, recovery_rule)
        for cell, amount in fed_alloc.items():
            contribution_map[cell] += amount
            capacity[cell] -= amount
            federation_reserve += amount
        for cell, amount in contribution_map.items():
            cash[cell] -= amount
        wave_contributions = sum(contribution_map.values())
        cumulative_contributions += wave_contributions
        for cell, amount in contribution_map.items():
            cumulative_member_contributions[cell] += amount

        # Core invariants: member-to-reserve contributions and reserve-to-seller
        # payouts are internal transfers; only exogenous operating burn changes cash.
        system_cash = sum(cash.values()) + sum(regional_reserves.values()) + federation_reserve
        expected_cash = initial_system_cash - cumulative_external_burn
        residual = system_cash - expected_cash
        assert abs(residual) < 1e-7, (wave_no, system_cash, expected_cash, residual)
        max_abs_conservation_residual = max(max_abs_conservation_residual, abs(residual))
        assert all(v >= -EPS for v in cash.values())
        assert all(v >= -EPS for v in regional_reserves.values()) and federation_reserve >= -EPS
        assert all(cash[c] >= CASH_FLOOR - EPS for c in CELLS if c not in defaulted)
        assert all(contribution_map[c] <= PERIOD_CONTRIBUTION_CAP_FRACTION * opening_cash[c] + 1e-7 for c in CELLS)
        assert all(contribution_map[c] <= max(0.0, opening_cash[c] - CASH_FLOOR) + 1e-7 for c in CELLS)
        assert all(contribution_map[c] == 0.0 for c in defaulted)
        assert all(regional_reserves[r] <= REGIONAL_TARGETS[r] + 1e-7 for r in REGIONS)
        assert federation_reserve <= FEDERATION_TARGET + 1e-7

        rows.append({
            "wave": wave_no,
            "new_defaults": len(borrowers),
            "cumulative_defaults": len(defaulted),
            "claims": claims_total,
            "buyer_cash_paid": wave_buyer_cash_paid,
            "buyer_unpaid_claims": unpaid_by_buyer,
            "local_paid": sum(wave_local_paid.values()),
            "federation_paid": wave_fed_paid,
            "uncovered": wave_uncovered,
            "external_operating_burn": burn,
            "recovery_contributions": wave_contributions,
            "regional_recovery": regional_recovery,
            "regional_recovery_shortfall": regional_shortfall,
            "federation_recovery_shortfall": fed_shortfall,
            "regional_reserves_end": dict(regional_reserves),
            "federation_reserve_end": federation_reserve,
            "eligible_recovery_members": eligible_recovery_members,
            "member_contributions": {c: a for c, a in contribution_map.items() if a > EPS},
            "member_cash_end": sum(cash.values()),
            "system_cash_end": system_cash,
            "expected_system_cash": expected_cash,
            "cash_conservation_residual": residual,
            "minimum_nondefaulted_member_cash": min(cash[c] for c in CELLS if c not in defaulted),
        })

    total_paid = sum(cumulative_local_paid.values()) + cumulative_fed_paid
    total_claims_reconciled = cumulative_buyer_cash_paid + total_paid + cumulative_uncovered
    assert abs(total_claims_reconciled - cumulative_claims) < 1e-7
    return {
        "recovery_rule": recovery_rule,
        "federation_clearing": federation_clearing,
        "claim_multiplier": claim_multiplier,
        "cash_burn_per_default": cash_burn_per_default,
        "initial_system_cash": initial_system_cash,
        "external_operating_burn": cumulative_external_burn,
        "ending_system_cash": sum(cash.values()) + sum(regional_reserves.values()) + federation_reserve,
        "ending_member_cash": sum(cash.values()),
        "ending_regional_reserves": dict(regional_reserves),
        "ending_federation_reserve": federation_reserve,
        "ending_total_reserves": sum(regional_reserves.values()) + federation_reserve,
        "total_claims": cumulative_claims,
        "buyer_cash_paid": cumulative_buyer_cash_paid,
        "local_reserve_paid": cumulative_local_paid,
        "federation_reserve_paid": cumulative_fed_paid,
        "total_reserve_paid": total_paid,
        "uncovered_internal_claims": cumulative_uncovered,
        "claim_reconciliation_residual": total_claims_reconciled - cumulative_claims,
        "recovery_contributions": cumulative_contributions,
        "seller_receipts": {k: v for k, v in cumulative_seller_receipts.items() if v > EPS},
        "seller_bad_debt": {k: v for k, v in cumulative_seller_bad_debt.items() if v > EPS},
        "member_contributions": {k: v for k, v in cumulative_member_contributions.items() if v > EPS},
        "cash_nav_proxy_start": initial_system_cash,
        "cash_nav_proxy_end": sum(cash.values()) + sum(regional_reserves.values()) + federation_reserve,
        "cash_nav_proxy_change": -cumulative_external_burn,
        "nav_scope": "cash-only consolidated proxy; excludes internal claims and physical assets/liabilities",
        "max_abs_cash_conservation_residual": max_abs_conservation_residual,
        "defaulted_members": sorted(defaulted),
        "cash_conservation_residual": (sum(cash.values()) + sum(regional_reserves.values()) + federation_reserve)
                                        - (initial_system_cash - cumulative_external_burn),
        "waves": rows,
    }


def test_claims_include_cross_region_and_local():
    claims = make_wave_claims(0, ("W0", "E0"))
    assert len(claims) == 4
    assert any(CELL_REGION[c.seller] != c.buyer_region for c in claims)
    assert any(CELL_REGION[c.seller] == c.buyer_region for c in claims)


def test_local_first_federation_second_waterfall():
    claims = [Claim("a", "W0", "E5", "WEST", 100.0)]
    result = _payout_claims(claims, {"WEST": 30.0, "EAST": 45.0}, 40.0, "batch_pro_rata")
    assert result["payouts"]["a"] == 70.0
    assert result["local_paid"]["WEST"] == 30.0
    assert result["federation_paid"] == 40.0
    assert result["uncovered"]["a"] == 30.0


def test_batch_pro_rata_preserves_aggregate_federation_payout():
    claims = [Claim("a", "W0", "E5", "WEST", 100.0), Claim("b", "E0", "W5", "EAST", 100.0)]
    a = _payout_claims(claims, {"WEST": 0.0, "EAST": 0.0}, 100.0, "fcfs")
    b = _payout_claims(claims, {"WEST": 0.0, "EAST": 0.0}, 100.0, "batch_pro_rata")
    assert abs(a["federation_paid"] - b["federation_paid"]) < EPS
    assert a["payouts"] != b["payouts"]
    assert abs(sum(a["uncovered"].values()) - sum(b["uncovered"].values())) < EPS


def test_full_experiment_conserves_cash_and_claims():
    for recovery in ("pro_rata", "fcfs"):
        for clearing in ("fcfs", "batch_pro_rata"):
            r = run_experiment(recovery, clearing)
            assert abs(r["cash_conservation_residual"]) < 1e-7
            assert abs(r["claim_reconciliation_residual"]) < 1e-7
            assert abs(r["ending_system_cash"] - (r["initial_system_cash"] - r["external_operating_burn"])) < 1e-7


def test_defaulted_reserve_members_never_contribute():
    r = run_experiment()
    assert set(r["defaulted_members"]) == {c for wave in DEFAULT_WAVES for c in wave}
    # The ending cash of defaulted cells reflects only the exogenous burn and any
    # earlier seller receipts; none can be a recovery contributor after default.
    assert len(r["defaulted_members"]) == 10
    for wave in r["waves"]:
        assert all(cell not in wave["member_contributions"] for cell in r["defaulted_members"] if cell in set(sum((list(w) for w in DEFAULT_WAVES[:wave["wave"]]), [])))


def test_shared_member_capacity_across_local_and_federation_funds():
    # W2 is in both funds; it defaults in wave 2. In wave 1, its combined
    # contribution cannot exceed the one period cap, not one cap per fund.
    r = run_experiment()
    wave1 = r["waves"][0]
    assert wave1["recovery_contributions"] <= 20 * 100.0 + EPS
    per_member = wave1["member_contributions"]
    assert per_member.get("W2", 0.0) <= 100.0 + EPS
    assert per_member.get("W2", 0.0) <= 0.10 * 1000.0 + EPS
    assert wave1["regional_recovery"]["WEST"] <= 45.0 + EPS
    assert wave1["regional_recovery"]["EAST"] <= 45.0 + EPS


def test_no_nondefaulted_member_below_cash_floor():
    r = run_experiment()
    for wave in r["waves"]:
        assert wave["minimum_nondefaulted_member_cash"] >= CASH_FLOOR - EPS


def test_repeatable_seedless_determinism():
    a = run_experiment("pro_rata", "batch_pro_rata")
    b = run_experiment("pro_rata", "batch_pro_rata")
    assert a == b


def test_parameter_sweep_preserves_all_invariants():
    regimes = ((0.9, 780.0), (1.0, 800.0), (1.25, 850.0), (1.5, 900.0))
    for claim_multiplier, cash_burn in regimes:
        for recovery in ("pro_rata", "fcfs"):
            for clearing in ("fcfs", "batch_pro_rata"):
                result = run_experiment(recovery, clearing, claim_multiplier, cash_burn)
                assert abs(result["cash_conservation_residual"]) < 1e-7
                assert abs(result["claim_reconciliation_residual"]) < 1e-7
                assert abs(result["ending_system_cash"] -
                           (result["initial_system_cash"] - result["external_operating_burn"])) < 1e-7
                assert result["uncovered_internal_claims"] >= -EPS
                assert result["ending_total_reserves"] >= -EPS
                assert all(all(v > EPS for v in wave["buyer_unpaid_claims"].values())
                           for wave in result["waves"])


def main():
    tests = [
        test_claims_include_cross_region_and_local,
        test_local_first_federation_second_waterfall,
        test_batch_pro_rata_preserves_aggregate_federation_payout,
        test_full_experiment_conserves_cash_and_claims,
        test_defaulted_reserve_members_never_contribute,
        test_shared_member_capacity_across_local_and_federation_funds,
        test_no_nondefaulted_member_below_cash_floor,
        test_repeatable_seedless_determinism,
        test_parameter_sweep_preserves_all_invariants,
    ]
    for test in tests:
        test()
    print(f"LOCAL TESTS: {len(tests)}/{len(tests)} passed")
    print("Synthetic assumptions only; this is not the production CreditLedger or CI.")
    for recovery in ("pro_rata", "fcfs"):
        for clearing in ("fcfs", "batch_pro_rata"):
            result = run_experiment(recovery, clearing)
            print("\n===", recovery.upper(), "/", clearing.upper(), "===")
            for key in ("total_claims", "total_reserve_paid", "uncovered_internal_claims",
                        "external_operating_burn", "recovery_contributions", "ending_total_reserves",
                        "ending_member_cash", "ending_system_cash", "cash_conservation_residual"):
                print(f"{key}: {result[key]:.6f}")
            print("ending regional reserves:", result["ending_regional_reserves"])
            print("cash NAV proxy:", result["cash_nav_proxy_start"], "->", result["cash_nav_proxy_end"],
                  "scope:", result["nav_scope"])
            print("seller bad debt:", result["seller_bad_debt"])
            print("wave-by-wave:")
            for wave in result["waves"]:
                print(json.dumps(wave, sort_keys=True))


if __name__ == "__main__":
    main()