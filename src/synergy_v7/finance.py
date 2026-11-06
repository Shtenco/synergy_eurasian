"""Cash waterfall and operating working-capital primitives for SYNERGY V7.2."""
from __future__ import annotations
from dataclasses import dataclass
import math


def _nonnegative(value,name):
    if not math.isfinite(value) or value<0:
        raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True)
class WorkingCapitalSnapshot:
    accounts_receivable: float
    inventory_at_cost: float
    accounts_payable: float
    other_operating_current_liabilities: float
    annual_external_revenue: float
    annual_cost_of_goods_sold: float
    day_count: int = 365
    def __post_init__(self):
        for name in ("accounts_receivable","inventory_at_cost","accounts_payable",
            "other_operating_current_liabilities","annual_external_revenue","annual_cost_of_goods_sold"):
            _nonnegative(getattr(self,name),name)
        if not isinstance(self.day_count,int) or self.day_count<=0:
            raise ValueError("day_count must be a positive integer")
    @property
    def net_operating_working_capital(self):
        return self.accounts_receivable+self.inventory_at_cost-self.accounts_payable-self.other_operating_current_liabilities
    @property
    def dso_days(self):
        return self.accounts_receivable/self.annual_external_revenue*self.day_count if self.annual_external_revenue else None
    @property
    def dio_days(self):
        return self.inventory_at_cost/self.annual_cost_of_goods_sold*self.day_count if self.annual_cost_of_goods_sold else None
    @property
    def dpo_days(self):
        return self.accounts_payable/self.annual_cost_of_goods_sold*self.day_count if self.annual_cost_of_goods_sold else None
    @property
    def cash_conversion_cycle_days(self):
        if self.dso_days is None or self.dio_days is None or self.dpo_days is None: return None
        return self.dso_days+self.dio_days-self.dpo_days
    def summary(self):
        return {"net_operating_working_capital":self.net_operating_working_capital,
            "dso_days":self.dso_days,"dio_days":self.dio_days,"dpo_days":self.dpo_days,
            "cash_conversion_cycle_days":self.cash_conversion_cycle_days}


def working_capital_cash_impact(previous: WorkingCapitalSnapshot,current: WorkingCapitalSnapshot) -> float:
    """Positive means cash released; negative means cash absorbed by higher NWC."""
    return previous.net_operating_working_capital-current.net_operating_working_capital


@dataclass(frozen=True)
class CashWaterfallInput:
    opening_cash: float
    customer_collections: float
    other_external_operating_receipts: float
    financing_proceeds: float
    internal_transfers_received: float
    opening_reserve: float
    reserve_target: float
    opex_due: float
    replacement_due: float
    debt_service_due: float
    growth_capex_requested: float
    distributions_requested: float
    allow_reserve_draw: bool = True
    def __post_init__(self):
        for name in ("opening_cash","customer_collections","other_external_operating_receipts",
            "financing_proceeds","internal_transfers_received","opening_reserve","reserve_target",
            "opex_due","replacement_due","debt_service_due","growth_capex_requested","distributions_requested"):
            _nonnegative(getattr(self,name),name)


def run_cash_waterfall(x: CashWaterfallInput) -> dict:
    """Allocate liquidity by explicit priority; financing is never operating revenue.

    Priority: OPEX -> replacement obligation -> debt service -> reserve top-up
    -> growth CAPEX -> distribution. Existing reserve may cover mandatory
    shortfalls if enabled. Distributions require all mandatory obligations paid
    and the reserve target fully funded.
    """
    cash_sources={
        "opening_cash":x.opening_cash,
        "customer_collections":x.customer_collections,
        "other_external_operating_receipts":x.other_external_operating_receipts,
        "financing_proceeds":x.financing_proceeds,
        "internal_transfers_received":x.internal_transfers_received
    }
    cash=sum(cash_sources.values()); reserve=x.opening_reserve; reserve_draw=0.0
    allocations={}; unpaid={}
    def pay(name,due,mandatory=True):
        nonlocal cash,reserve,reserve_draw
        from_cash=min(cash,due); cash-=from_cash
        remaining=due-from_cash; from_reserve=0.0
        if remaining>1e-9 and mandatory and x.allow_reserve_draw:
            from_reserve=min(reserve,remaining); reserve-=from_reserve; reserve_draw+=from_reserve; remaining-=from_reserve
        allocations[name]={"due":due,"from_cash":from_cash,"from_reserve":from_reserve,
            "funded":due-remaining,"unfunded":remaining}
        unpaid[name]=remaining
    pay("opex",x.opex_due)
    pay("replacement",x.replacement_due)
    pay("debt_service",x.debt_service_due)

    mandatory_unfunded=sum(unpaid.values())
    reserve_gap=max(0.0,x.reserve_target-reserve)
    reserve_topup=min(cash,reserve_gap); cash-=reserve_topup; reserve+=reserve_topup
    allocations["reserve_topup"]={"target_gap_before":reserve_gap,"funded":reserve_topup,
        "unfunded":reserve_gap-reserve_topup}

    growth=min(cash,x.growth_capex_requested); cash-=growth
    allocations["growth_capex"]={"requested":x.growth_capex_requested,"funded":growth,
        "unfunded":x.growth_capex_requested-growth}

    distributions_allowed=mandatory_unfunded<=1e-9 and reserve+1e-9>=x.reserve_target
    distribution=min(cash,x.distributions_requested) if distributions_allowed else 0.0
    cash-=distribution
    allocations["distribution"]={"requested":x.distributions_requested,"funded":distribution,
        "unfunded":x.distributions_requested-distribution,
        "blocked_by_mandatory_or_reserve_gate":not distributions_allowed}

    external_operating_generation=x.customer_collections+x.other_external_operating_receipts
    return {"cash_sources":cash_sources,
        "external_operating_cash_generation":external_operating_generation,
        "financing_proceeds_excluded_from_operating_generation":x.financing_proceeds,
        "internal_transfers_excluded_from_consolidated_operating_generation":x.internal_transfers_received,
        "allocations":allocations,"unpaid_mandatory_obligations":unpaid,
        "mandatory_obligation_shortfall":mandatory_unfunded,
        "reserve":{"opening":x.opening_reserve,"draw":reserve_draw,"topup":reserve_topup,"ending":reserve,"target":x.reserve_target,
            "target_funded":reserve+1e-9>=x.reserve_target},
        "growth_capex_funded":growth,"distribution_funded":distribution,
        "ending_unrestricted_cash":cash,
        "solvent_for_listed_mandatory_obligations":mandatory_unfunded<=1e-9,
        "distribution_gate_passed":distributions_allowed,
        "priority":["opex","replacement","debt_service","reserve_topup","growth_capex","distribution"]}
