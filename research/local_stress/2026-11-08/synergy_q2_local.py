"""
SYNERGY EURASIAN — Q2 local reserve-membership control model
All inputs in this file are an explicit synthetic test fixture, not production balances.
Run: python synergy_q2_local.py
"""
from dataclasses import dataclass
from typing import Dict, FrozenSet, Mapping

REGIONS = ("WEST", "EAST")
CELLS = tuple([f"W{i}" for i in range(10)] + [f"E{i}" for i in range(10)])

CASH = {c: 1000.0 for c in CELLS}
FLOOR = {c: 900.0 for c in CELLS}
ALPHA = {c: 0.10 for c in CELLS}
CAP_30D = {c: 80.0 for c in CELLS}
ALREADY_PAID_30D = {c: 0.0 for c in CELLS}

REGIONAL_MEMBERS = {
    "WEST": frozenset({"W0", "W1", "W2"}),
    "EAST": frozenset({"E0", "E1", "E2"}),
}
FEDERATION_MEMBERS = frozenset({"W2", "W3", "W4", "W5",
                                "E2", "E3", "E4", "E5"})
DEFAULTED = frozenset({"W0"})

REGIONAL_DEFICITS = {"WEST": 200.0, "EAST": 200.0}
FEDERATION_DEFICIT = 300.0


def validate_membership(cells, regions, regional_members, federation_members):
    known = set(cells)
    if set(regional_members) != set(regions):
        raise ValueError("Regional membership must define every region exactly once")
    for region, members in regional_members.items():
        if len(members) != len(set(members)):
            raise ValueError(f"Duplicate regional member in {region}")
        unknown = set(members) - known
        if unknown:
            raise ValueError(f"Unknown regional member(s): {sorted(unknown)}")
        wrong_region = [c for c in members if c[0] != region[0]]
        if wrong_region:
            raise ValueError(f"Cross-region local member(s) in {region}: {wrong_region}")
    unknown_fed = set(federation_members) - known
    if unknown_fed:
        raise ValueError(f"Unknown federation member(s): {sorted(unknown_fed)}")


def available_capacity(cells, cash, floor, alpha, cap30, already30, defaulted):
    out = {}
    for c in cells:
        if c in defaulted:
            out[c] = 0.0
            continue
        if cash[c] < 0 or floor[c] < 0 or alpha[c] < 0 or cap30[c] < 0:
            raise ValueError(f"Negative financial parameter for {c}")
        if cash[c] + 1e-9 < floor[c]:
            raise ValueError(f"Cash already below protected floor for {c}")
        out[c] = max(0.0, min(
            alpha[c] * cash[c],
            cash[c] - floor[c],
            max(0.0, cap30[c] - already30[c])
        ))
    return out


def allocate(demand, members, remaining, method):
    eligible = sorted(c for c in members if remaining.get(c, 0.0) > 1e-12)
    total_capacity = sum(remaining[c] for c in eligible)
    paid = min(demand, total_capacity)
    result = {c: 0.0 for c in eligible}
    if method == "pro_rata":
        if total_capacity:
            for c in eligible:
                result[c] = paid * remaining[c] / total_capacity
    elif method == "fcfs":
        left = paid
        for c in eligible:
            amount = min(left, remaining[c])
            result[c] = amount
            left -= amount
    else:
        raise ValueError("method must be pro_rata or fcfs")
    return result, demand - paid


def run_scenario(method):
    validate_membership(CELLS, REGIONS, REGIONAL_MEMBERS, FEDERATION_MEMBERS)
    remaining = available_capacity(
        CELLS, CASH, FLOOR, ALPHA, CAP_30D, ALREADY_PAID_30D, DEFAULTED
    )
    contributions = {c: 0.0 for c in CELLS}
    regional_shortfall = {}

    # Regional funds are processed first.
    for region in REGIONS:
        allocation, shortfall = allocate(
            REGIONAL_DEFICITS[region],
            REGIONAL_MEMBERS[region],
            remaining,
            method,
        )
        regional_shortfall[region] = shortfall
        for cell, amount in allocation.items():
            contributions[cell] += amount
            remaining[cell] -= amount

    # Federation is independent membership, but shares each member's remaining cap.
    federation_allocation, federation_shortfall = allocate(
        FEDERATION_DEFICIT, FEDERATION_MEMBERS, remaining, method
    )
    for cell, amount in federation_allocation.items():
        contributions[cell] += amount
        remaining[cell] -= amount

    # Invariants: no creation, no protected-floor breach, no cap breach.
    for c, amount in contributions.items():
        assert amount <= CAP_30D[c] - ALREADY_PAID_30D[c] + 1e-8
        assert CASH[c] - amount >= FLOOR[c] - 1e-8
        assert amount >= -1e-9
        if c in DEFAULTED:
            assert amount == 0.0

    return {
        "method": method,
        "contributions": contributions,
        "regional_shortfall": regional_shortfall,
        "federation_shortfall": federation_shortfall,
        "total_contributed": sum(contributions.values()),
        "ending_cash": {c: CASH[c] - contributions[c] for c in CELLS},
        "remaining_30d_cap": {
            c: CAP_30D[c] - ALREADY_PAID_30D[c] - contributions[c]
            for c in CELLS
        },
    }


def test_membership_boundaries():
    validate_membership(CELLS, REGIONS, REGIONAL_MEMBERS, FEDERATION_MEMBERS)
    try:
        validate_membership(
            CELLS, REGIONS,
            {"WEST": frozenset({"E1"}), "EAST": frozenset({"E0"})},
            FEDERATION_MEMBERS
        )
        raise AssertionError("Cross-region membership was not rejected")
    except ValueError:
        pass
    try:
        validate_membership(
            CELLS, REGIONS, REGIONAL_MEMBERS,
            frozenset({"NOT_A_CELL"})
        )
        raise AssertionError("Unknown federation member was not rejected")
    except ValueError:
        pass


def test_defaulted_member_excluded():
    result = run_scenario("pro_rata")
    assert result["contributions"]["W0"] == 0.0


def test_independent_federation_membership():
    # W3 is not a WEST regional member, but is a federation member.
    assert "W3" not in REGIONAL_MEMBERS["WEST"]
    assert "W3" in FEDERATION_MEMBERS
    result = run_scenario("pro_rata")
    assert result["contributions"]["W3"] > 0.0


def test_shared_cap_and_cash_floor():
    result = run_scenario("pro_rata")
    for c, amount in result["contributions"].items():
        assert amount <= 80.0 + 1e-8
        assert result["ending_cash"][c] >= 900.0 - 1e-8


def test_no_cross_region_local_funding():
    # Only W0/W1/W2 can fund WEST; E cells cannot contribute to WEST.
    result = run_scenario("fcfs")
    # EAST participants' contributions can only be caused by EAST or federation.
    # The WEST regional allocation is independently capped at 160 because W0 defaulted.
    assert result["regional_shortfall"]["WEST"] == 40.0


def main():
    test_membership_boundaries()
    test_defaulted_member_excluded()
    test_independent_federation_membership()
    test_shared_cap_and_cash_floor()
    test_no_cross_region_local_funding()

    for method in ("pro_rata", "fcfs"):
        r = run_scenario(method)
        print(f"\\n=== {method.upper()} ===")
        print("Total contributed:", round(r["total_contributed"], 6))
        print("Regional shortfall:", {k: round(v, 6) for k, v in r["regional_shortfall"].items()})
        print("Federation shortfall:", round(r["federation_shortfall"], 6))
        print("Contributions:")
        for c, amount in sorted(r["contributions"].items()):
            if amount > 1e-9:
                print(f"  {c}: {amount:.6f}; ending_cash={r['ending_cash'][c]:.6f}; "
                      f"remaining_30d_cap={r['remaining_30d_cap'][c]:.6f}")
    print("\\nCONTROL TESTS: 5/5 passed")
    print("NOTE: synthetic fixture only; this is not a production-code or CI result.")


if __name__ == "__main__":
    main()


# 100-cycle stress extension:
# A cycle is treated as one 30-day replenishment period.
# Inflow is explicit and identical per cell; this is a sensitivity assumption,
# not a claim about SYNERGY's actual revenue or payroll.
def simulate_100_cycles(method, west_members, recurring_inflow_per_cell, cycles=100):
    balances = dict(CASH)
    records = []
    for cycle in range(1, cycles + 1):
        for cell in CELLS:
            balances[cell] += recurring_inflow_per_cell

        remaining = {}
        for cell in CELLS:
            if cell in DEFAULTED:
                remaining[cell] = 0.0
            else:
                remaining[cell] = max(0.0, min(
                    ALPHA[cell] * balances[cell],
                    balances[cell] - FLOOR[cell],
                    CAP_30D[cell],
                ))

        contributed = {cell: 0.0 for cell in CELLS}
        regional_short = {}
        for region, members in (
            ("WEST", west_members),
            ("EAST", REGIONAL_MEMBERS["EAST"]),
        ):
            allocation, shortfall = allocate(
                REGIONAL_DEFICITS[region], members, remaining, method
            )
            regional_short[region] = shortfall
            for cell, amount in allocation.items():
                contributed[cell] += amount
                remaining[cell] -= amount

        allocation, federation_short = allocate(
            FEDERATION_DEFICIT, FEDERATION_MEMBERS, remaining, method
        )
        for cell, amount in allocation.items():
            contributed[cell] += amount
            remaining[cell] -= amount

        for cell, amount in contributed.items():
            balances[cell] -= amount
            assert balances[cell] >= FLOOR[cell] - 1e-8

        records.append({
            "cycle": cycle,
            "contributed": sum(contributed.values()),
            "WEST_shortfall": regional_short["WEST"],
            "EAST_shortfall": regional_short["EAST"],
            "federation_shortfall": federation_short,
            "cash_above_floors": sum(balances[c] - FLOOR[c] for c in CELLS),
        })

    return records, balances


print("\\n=== 100-CYCLE RECURRING-NEED STRESS ===")
for method in ("pro_rata", "fcfs"):
    # Baseline membership: W0 is defaulted, so only W1 and W2 can fund WEST.
    rows, balances = simulate_100_cycles(
        method, REGIONAL_MEMBERS["WEST"], recurring_inflow_per_cell=80.0
    )
    print(method, "baseline membership:",
          "total_contributed=", round(sum(r["contributed"] for r in rows), 2),
          "WEST_shortfall=", round(sum(r["WEST_shortfall"] for r in rows), 2),
          "EAST_shortfall=", round(sum(r["EAST_shortfall"] for r in rows), 2),
          "federation_shortfall=", round(sum(r["federation_shortfall"] for r in rows), 2))

    # Controlled membership correction: add W3 to WEST, while preserving its
    # independent federation membership and one shared cash/capacity constraint.
    expanded_west = frozenset({"W0", "W1", "W2", "W3"})
    rows2, balances2 = simulate_100_cycles(
        method, expanded_west, recurring_inflow_per_cell=80.0
    )
    print(method, "W3 added to WEST:",
          "total_contributed=", round(sum(r["contributed"] for r in rows2), 2),
          "WEST_shortfall=", round(sum(r["WEST_shortfall"] for r in rows2), 2),
          "EAST_shortfall=", round(sum(r["EAST_shortfall"] for r in rows2), 2),
          "federation_shortfall=", round(sum(r["federation_shortfall"] for r in rows2), 2),
          "minimum_final_cash=", round(min(balances2.values()), 2))
