"""SYNERGY V6.4 auditable supply-chain research kernel.

Deterministic paired-scenario prototype using synthetic assumptions.
Not a forecast, production accounting system, or investment model.
"""
from __future__ import annotations
import collections
import math
import random
from dataclasses import dataclass

NODES = ["R1","R2","C1","C2","A1","A2","L"]
FIXED = {"R1":2.0,"R2":2.0,"C1":3.0,"C2":3.0,"A1":4.0,"A2":4.0,"L":3.0}
INITIAL_CASH = 200.0
INITIAL_DEBT = 50.0
RAW_INPUT_COST = 1.20
RAW_TRANSFER_PRICE = 4.00
COMP_PROCESS_COST = 2.20
COMP_TRANSFER_PRICE = 7.50
ASSEMBLY_COST = 2.50
FREIGHT_PER_UNIT = 0.25
LOGISTICS_FUEL_PER_UNIT = 0.10
FINAL_PRICE = 15.0
FINAL_BATCH = 0.25
RAW_PER_FINAL = 1.25 * 1.15
COMP_PER_FINAL = 1.25
DAILY_DEBT_PRINCIPAL = 0.50
DAILY_DEBT_INTEREST = 0.05
DEFAULT_ARREARS_LIMIT = 12.0

@dataclass
class Lot:
    qty: float
    unit_cost: float
    lot_id: int

class FIFOInventory:
    def __init__(self):
        self.lots = collections.deque()
        self.next_id = 0
        self.qty_in = 0.0
        self.qty_out = 0.0

    def add(self, qty, unit_cost):
        if qty <= 1e-12:
            return
        self.lots.append(Lot(float(qty), float(unit_cost), self.next_id))
        self.next_id += 1
        self.qty_in += qty

    def consume(self, qty):
        if qty < -1e-12 or self.quantity + 1e-9 < qty:
            raise ValueError("FIFO inventory underflow")
        remaining = float(qty)
        cost = 0.0
        while remaining > 1e-10:
            lot = self.lots[0]
            take = min(remaining, lot.qty)
            cost += take * lot.unit_cost
            lot.qty -= take
            remaining -= take
            if lot.qty <= 1e-10:
                self.lots.popleft()
        self.qty_out += qty
        return cost

    @property
    def quantity(self):
        return sum(x.qty for x in self.lots)

    @property
    def book_value(self):
        return sum(x.qty*x.unit_cost for x in self.lots)


def make_environment(seed, regime, days=60):
    rng = random.Random(seed)
    env = []
    node_cost_factor = {n:rng.uniform(0.94,1.08) for n in NODES}
    node_capacity_factor = {n:rng.uniform(0.90,1.10) for n in NODES}
    for _ in range(days):
        if regime == "normal":
            demand = [max(0.0, rng.gauss(4.0,0.55)) for _ in range(2)]
            shock_scale = (0.78,1.0)
            common = 1.0 if rng.random() > 0.03 else rng.uniform(0.35,0.65)
        elif regime == "volatile":
            demand = [max(0.0, rng.gauss(4.0,1.0)) for _ in range(2)]
            shock_scale = (0.50,1.0)
            common = 1.0 if rng.random() > 0.10 else rng.uniform(0.20,0.55)
        elif regime == "severe":
            demand = [max(0.0, rng.gauss(3.7,1.35)) for _ in range(2)]
            shock_scale = (0.10,1.0)
            common = 1.0 if rng.random() > 0.18 else rng.uniform(0.0,0.30)
        else:
            raise ValueError("regime must be normal, volatile, or severe")
        caps = {}
        for n in NODES:
            local = rng.uniform(*shock_scale)
            if regime == "severe" and n in ("R1","R2") and rng.random() < 0.12:
                local *= rng.uniform(0.0,0.20)
            caps[n] = node_capacity_factor[n] * local * common
        env.append({"demand":demand, "caps":caps, "cost_factor":node_cost_factor.copy()})
    return env


def choose_supplier(policy, buyer, candidates, capacities_left, costs, primary):
    avail = [s for s in candidates if capacities_left.get(s,0.0) > 1e-9]
    if not avail:
        return None
    if policy == "independent":
        return primary if primary in avail else None
    if policy == "ca":
        return primary if primary in avail else next((s for s in candidates if s != primary and s in avail), None)
    if policy == "market":
        max_left = max(capacities_left[s] for s in avail)
        return min(avail, key=lambda s:(costs[s] + 3.0*(1.0-capacities_left[s]/max_left), -capacities_left[s]))
    if policy == "dao":
        return max(avail, key=lambda s:(capacities_left[s], -costs[s]))
    if policy == "hybrid":
        total_left = sum(max(0.0,capacities_left.get(s,0.0)) for s in candidates)
        if primary in avail and capacities_left[primary] >= 0.35*total_left:
            return primary
        max_left = max(capacities_left[s] for s in avail)
        return min(avail, key=lambda s:(costs[s] + 3.0*(1.0-capacities_left[s]/max_left), -capacities_left[s]))
    raise ValueError(policy)


def simulate(policy, env, final_price=FINAL_PRICE, days=60, return_trace=False):
    cash = {n:INITIAL_CASH for n in NODES}
    debt = {n:INITIAL_DEBT for n in NODES}
    fixed_arrears = {n:0.0 for n in NODES}
    principal_arrears = {n:0.0 for n in NODES}
    interest_arrears = {n:0.0 for n in NODES}
    defaulted = {n:False for n in NODES}
    inv = {(n,sku):FIFOInventory() for n in NODES for sku in ("raw","comp","final")}
    ext_costs_paid = fixed_due_total = fixed_paid_total = 0.0
    debt_due_total = debt_paid_total = 0.0
    interest_due_total = interest_paid_total = 0.0
    sales_total = output_total = unmet_total = 0.0
    trace = []
    for day, e in enumerate(env):
        base_caps = {"R1":9.0,"R2":9.0,"C1":8.0,"C2":8.0,"A1":5.0,"A2":5.0,"L":40.0}
        caps = {n:base_caps[n]*e["caps"][n] if not defaulted[n] else 0.0 for n in NODES}
        used = {n:0.0 for n in NODES}
        day_sales = day_var_cost = day_output = day_unmet = 0.0

        for ai, assembler in enumerate(("A1","A2")):
            demand = e["demand"][ai]
            day_unmet += demand
            batches = int(math.floor(demand/FINAL_BATCH + 1e-9))
            for _ in range(batches):
                qf = FINAL_BATCH
                qc = qf*COMP_PER_FINAL
                qr = qf*RAW_PER_FINAL
                if defaulted[assembler] or defaulted["L"]:
                    break
                if caps[assembler]-used[assembler] + 1e-9 < qf:
                    break
                if caps["L"]-used["L"] + 1e-9 < (qc+qr):
                    break

                comp_costs = {c:2.20*e["cost_factor"][c] for c in ("C1","C2")}
                raw_costs = {r:1.20*e["cost_factor"][r] for r in ("R1","R2")}
                comp_primary = "C1" if assembler=="A1" else "C2"
                comp_left = {c:caps[c]-used[c] for c in ("C1","C2")}
                comp_supplier = choose_supplier(policy, assembler, ["C1","C2"], comp_left, comp_costs, comp_primary)
                if comp_supplier is None or defaulted[comp_supplier] or comp_left[comp_supplier]+1e-9 < qc:
                    break
                raw_primary = "R1" if comp_supplier=="C1" else "R2"
                raw_left = {r:caps[r]-used[r] for r in ("R1","R2")}
                raw_supplier = choose_supplier(policy, comp_supplier, ["R1","R2"], raw_left, raw_costs, raw_primary)
                if raw_supplier is None or defaulted[raw_supplier] or raw_left[raw_supplier]+1e-9 < qr:
                    break

                raw_unit_cost = raw_costs[raw_supplier]
                comp_process_unit_cost = comp_costs[comp_supplier]
                assembly_unit_cost = 2.50*e["cost_factor"][assembler]
                fuel_cost = LOGISTICS_FUEL_PER_UNIT*(qr+qc)*e["cost_factor"]["L"]
                freight_raw, freight_comp = qr*FREIGHT_PER_UNIT, qc*FREIGHT_PER_UNIT
                raw_purchase, comp_purchase = qr*RAW_TRANSFER_PRICE, qc*COMP_TRANSFER_PRICE
                raw_external_cost, comp_external_cost = qr*raw_unit_cost, qc*comp_process_unit_cost
                assembly_external_cost = qf*assembly_unit_cost

                if cash[assembler]+1e-9 < comp_purchase+freight_comp+assembly_external_cost:
                    break
                if cash[comp_supplier]+comp_purchase+1e-9 < raw_purchase+freight_raw+comp_external_cost:
                    break
                if cash[raw_supplier]+raw_purchase+1e-9 < raw_external_cost:
                    break
                if cash["L"]+freight_raw+freight_comp+1e-9 < fuel_cost:
                    break

                inv[(raw_supplier,"raw")].add(qr, raw_unit_cost)
                inv[(raw_supplier,"raw")].consume(qr)
                inv[(comp_supplier,"raw")].add(qr, RAW_TRANSFER_PRICE+FREIGHT_PER_UNIT)
                raw_cogs = inv[(comp_supplier,"raw")].consume(qr)
                inv[(comp_supplier,"comp")].add(qc, (raw_cogs+comp_external_cost)/qc)
                inv[(comp_supplier,"comp")].consume(qc)
                inv[(assembler,"comp")].add(qc, COMP_TRANSFER_PRICE+FREIGHT_PER_UNIT)
                comp_cogs = inv[(assembler,"comp")].consume(qc)
                inv[(assembler,"final")].add(qf, (comp_cogs+assembly_external_cost)/qf)
                inv[(assembler,"final")].consume(qf)

                cash[assembler] -= comp_purchase+freight_comp+assembly_external_cost
                cash[comp_supplier] += comp_purchase
                cash[comp_supplier] -= raw_purchase+freight_raw+comp_external_cost
                cash[raw_supplier] += raw_purchase
                cash["L"] += freight_raw+freight_comp
                cash[raw_supplier] -= raw_external_cost
                cash["L"] -= fuel_cost
                cash[assembler] += qf*final_price

                ext_costs_paid += raw_external_cost+comp_external_cost+assembly_external_cost+fuel_cost
                day_var_cost += raw_external_cost+comp_external_cost+assembly_external_cost+fuel_cost
                sales_total += qf*final_price
                day_sales += qf*final_price
                used[raw_supplier] += qr
                used[comp_supplier] += qc
                used[assembler] += qf
                used["L"] += qr+qc
                day_output += qf
                day_unmet -= qf

        for n in NODES:
            if defaulted[n]:
                continue
            fixed_due_total += FIXED[n]
            total_fixed_due = fixed_arrears[n]+FIXED[n]
            fixed_pay = min(cash[n], total_fixed_due)
            cash[n] -= fixed_pay
            fixed_paid_total += fixed_pay
            fixed_arrears[n] = total_fixed_due-fixed_pay

            current_interest = min(debt[n], DAILY_DEBT_INTEREST)
            interest_due_total += current_interest
            interest_due = interest_arrears[n]+current_interest
            current_principal = min(max(0.0,debt[n]-principal_arrears[n]), DAILY_DEBT_PRINCIPAL)
            principal_due = principal_arrears[n]+current_principal
            debt_due_total += current_interest+current_principal
            pay_total = min(cash[n], interest_due+principal_due)
            cash[n] -= pay_total
            interest_pay = min(pay_total, interest_due)
            principal_pay = min(max(0.0,pay_total-interest_pay), principal_due)
            interest_paid_total += interest_pay
            debt_paid_total += interest_pay+principal_pay
            interest_arrears[n] = interest_due-interest_pay
            principal_arrears[n] = principal_due-principal_pay
            debt[n] = max(0.0,debt[n]-principal_pay)

            if fixed_arrears[n]+principal_arrears[n]+interest_arrears[n] > DEFAULT_ARREARS_LIMIT:
                defaulted[n] = True

        output_total += day_output
        unmet_total += day_unmet
        if return_trace:
            trace.append({"day":day+1,"output":day_output,"sales":day_sales,"variable_costs":day_var_cost,
                          "unmet":day_unmet,"cash":sum(cash.values()),"defaults":sum(defaulted.values())})

    final_cash = sum(cash.values())
    initial_cash = INITIAL_CASH*len(NODES)
    operating_cash_result = sales_total-ext_costs_paid-fixed_paid_total
    operating_accrual_result = sales_total-ext_costs_paid-fixed_due_total-interest_due_total
    cash_after_financing = initial_cash+sales_total-ext_costs_paid-fixed_paid_total-debt_paid_total
    conservation_error = final_cash-cash_after_financing
    return {
        "policy":policy,"sales":sales_total,"variable_external_costs":ext_costs_paid,
        "fixed_due":fixed_due_total,"fixed_paid":fixed_paid_total,
        "debt_due":debt_due_total,"debt_paid":debt_paid_total,
        "interest_due":interest_due_total,"interest_paid":interest_paid_total,
        "operating_result_accrual":operating_accrual_result,
        "operating_cash_result":operating_cash_result,
        "cash_after_financing_change":cash_after_financing-initial_cash,
        "final_cash":final_cash,"initial_cash":initial_cash,
        "output":output_total,"unmet":unmet_total,
        "defaults":sum(defaulted.values()),
        "defaulted_nodes":[n for n,v in defaulted.items() if v],
        "cash_by_node":cash.copy(),"debt_remaining":sum(debt.values()),
        "fixed_arrears":sum(fixed_arrears.values()),
        "principal_arrears":sum(principal_arrears.values()),
        "interest_arrears":sum(interest_arrears.values()),
        "inventory_qty":sum(x.quantity for x in inv.values()),
        "inventory_value":sum(x.book_value for x in inv.values()),
        "conservation_error":conservation_error,
        "trace":trace if return_trace else None,
        "fifo_lots_created":sum(x.next_id for x in inv.values()),
        "fifo_qty_in":sum(x.qty_in for x in inv.values()),
        "fifo_qty_out":sum(x.qty_out for x in inv.values()),
    }
