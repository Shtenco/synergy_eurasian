"""CLI for Monte Carlo stress testing a fixed V7.1 production schedule."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .production import (MaterialRequirement,ResourceRequirement,ProductionRecipe,
    ProductionOrder,InventoryReceipt,ProductDemand)
from .core import ResourceCapacity
from .stress import ResourceShock,ReceiptDelay,stress_test_fixed_schedule


def evaluate_document(document):
    recipes=[ProductionRecipe(x["recipe_id"],x["output_product_id"],x["output_quantity_per_batch"],
      x["output_unit"],tuple(MaterialRequirement(**r) for r in x["input_requirements"]),
      tuple(ResourceRequirement(**r) for r in x["resource_requirements"]),x["lead_time_periods"],x.get("node_id",""))
      for x in document["recipes"]]
    orders=[ProductionOrder(**x) for x in document["orders"]]
    receipts=[InventoryReceipt(**x) for x in document["inventory_receipts"]]
    demands=[ProductDemand(**x) for x in document["demands"]]
    caps=[ResourceCapacity(**x) for x in document["resource_capacities"]]
    shocks=[ResourceShock(**x) for x in document.get("resource_shocks",[])]
    delays=[ReceiptDelay(**x) for x in document.get("receipt_delays",[])]
    return stress_test_fixed_schedule(recipes,orders,receipts,demands,caps,
      document.get("scenarios",1000),document.get("seed",42),
      document.get("common_shock_probability",0.0),document.get("common_capacity_factor",0.5),
      shocks,delays,document.get("demand_weights",{}),document.get("alpha",0.95))


def main(argv=None):
    parser=argparse.ArgumentParser(description="Stress-test a SYNERGY production schedule")
    parser.add_argument("snapshot",help="Monte Carlo stress input JSON")
    args=parser.parse_args(argv)
    try:
        with Path(args.snapshot).open(encoding="utf-8") as stream: doc=json.load(stream)
        result=evaluate_document(doc)
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
        return 0
    except Exception as exc:
        print(f"SYNERGY V7.5 stress error: {exc}",file=sys.stderr)
        return 1


if __name__=="__main__": raise SystemExit(main())
