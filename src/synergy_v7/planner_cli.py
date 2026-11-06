"""CLI for the V7.6.5 collateral-aware borrowing-base and maturity-aware credit-aware cash-constrained production scheduler."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .core import ResourceCapacity
from .production import MaterialRequirement,ResourceRequirement,ProductionRecipe,InventoryReceipt
from .planner import PlanDemand,optimize_production_schedule
from .supplier_payments import SupplierPaymentCommitment,aggregate_supplier_payment_commitments
from .collateral import (ReceivableCollateral,InventoryCollateral,BorrowingBasePolicy,calculate_borrowing_base)


def evaluate_document(document,schema_path=None):
    try: import jsonschema
    except ImportError as exc: raise RuntimeError("Install requirements to validate JSON Schema") from exc
    root=Path(__file__).resolve().parents[2]
    path=Path(schema_path) if schema_path else root/"interfaces"/"synergy_v7_production_optimizer.schema.json"
    with path.open(encoding="utf-8") as stream: schema=json.load(stream)
    jsonschema.validate(instance=document,schema=schema)
    recipes=[ProductionRecipe(x["recipe_id"],x["output_product_id"],x["output_quantity_per_batch"],
      x["output_unit"],tuple(MaterialRequirement(**r) for r in x["input_requirements"]),
      tuple(ResourceRequirement(**r) for r in x["resource_requirements"]),x["lead_time_periods"],x.get("node_id",""))
      for x in document["recipes"]]
    demands=[PlanDemand(**x) for x in document["demands"]]
    receipts=[InventoryReceipt(**x) for x in document["inventory_receipts"]]
    capacities=[ResourceCapacity(**x) for x in document["resource_capacities"]]
    cash_floor=document.get("cash_minimum_balance")
    if isinstance(cash_floor,dict):
        cash_floor={int(k):v for k,v in cash_floor.items()}
    supplier_payments=[SupplierPaymentCommitment(**x) for x in document.get("supplier_payment_commitments",[])]
    supplier_report=aggregate_supplier_payment_commitments(supplier_payments,document["horizon_periods"],
      document.get("objective_currency","USD"),document.get("include_scenario_supplier_payments",False))
    cash_outflows={int(k):v for k,v in document.get("cash_outflows_by_period",{}).items()}
    credit_draws={int(k):v for k,v in document["credit_draw_limits_by_period"].items()} if "credit_draw_limits_by_period" in document else None
    credit_repayments={int(k):v for k,v in document["credit_repayment_limits_by_period"].items()} if "credit_repayment_limits_by_period" in document else None
    credit_rates={int(k):v for k,v in document["credit_interest_rates_by_period"].items()} if "credit_interest_rates_by_period" in document else None
    borrowing_base={int(k):v for k,v in document["credit_borrowing_base_by_period"].items()} if "credit_borrowing_base_by_period" in document else {}
    collateral_report=None
    if any(k in document for k in ("receivable_collateral","inventory_collateral","collateral_policy")):
        if "credit_limit" not in document: raise ValueError("Collateral borrowing-base calculation requires credit_limit")
        policy=BorrowingBasePolicy(**document["collateral_policy"])
        ar=[ReceivableCollateral(**x) for x in document.get("receivable_collateral",[])]
        stock=[InventoryCollateral(**x) for x in document.get("inventory_collateral",[])]
        collateral_report=calculate_borrowing_base(ar,stock,policy,document.get("objective_currency","USD"))
        for period,row in collateral_report["periods"].items():
            amount=row["net_borrowing_base"]
            borrowing_base[period]=min(borrowing_base.get(period,document["credit_limit"]),amount)
    for period,amount in supplier_report["cash_outflows_by_period"].items():
        cash_outflows[period]=cash_outflows.get(period,0.0)+amount
    result=optimize_production_schedule(recipes,demands,receipts,capacities,
      document["horizon_periods"],document["batch_limits"],document.get("batch_costs",{}),
      document.get("holding_costs",{}),document.get("objective_currency","USD"),
      document.get("mip_rel_gap",0.0),document.get("time_limit_seconds",30.0),document.get("minimum_inventory",{}),document.get("storage_limits",{}),
      document.get("cash_opening_balance"),cash_floor,
      ({int(k):v for k,v in document["cash_inflows_by_period"].items()} if "cash_inflows_by_period" in document else None),
      cash_outflows if ("cash_outflows_by_period" in document or supplier_payments) else None,
      document.get("collection_lag_by_demand"),document.get("collection_fraction_by_demand"),
      document.get("credit_limit"),document.get("credit_opening_balance",0.0),
      credit_draws,credit_repayments,credit_rates,document.get("terminal_credit_balance_limit"),
      document.get("credit_maturity_period"),borrowing_base if borrowing_base else None)
    result["supplier_payment_commitments"]=supplier_report
    result["collateral_borrowing_base"]=collateral_report
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description="Optimize a SYNERGY V7.6.2 credit-aware cash-constrained production schedule")
    parser.add_argument("plan",help="MILP production plan JSON")
    args=parser.parse_args(argv)
    try:
        with Path(args.plan).open(encoding="utf-8") as stream: doc=json.load(stream)
        result=evaluate_document(doc)
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
        return 0 if result["feasible"] and result["optimality_proven"] else 2
    except Exception as exc:
        print(f"SYNERGY V7.6.5 optimizer error: {exc}",file=sys.stderr)
        return 1


if __name__=="__main__": raise SystemExit(main())
