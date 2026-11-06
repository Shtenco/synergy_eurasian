"""CLI for the V7.4 MILP production scheduler."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .core import ResourceCapacity
from .production import MaterialRequirement,ResourceRequirement,ProductionRecipe,InventoryReceipt
from .planner import PlanDemand,optimize_production_schedule


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
    return optimize_production_schedule(recipes,demands,receipts,capacities,
      document["horizon_periods"],document["batch_limits"],document.get("batch_costs",{}),
      document.get("holding_costs",{}),document.get("objective_currency","USD"),
      document.get("mip_rel_gap",0.0),document.get("time_limit_seconds",30.0),document.get("minimum_inventory",{}),document.get("storage_limits",{}))


def main(argv=None):
    parser=argparse.ArgumentParser(description="Optimize a SYNERGY V7.4 production schedule")
    parser.add_argument("plan",help="MILP production plan JSON")
    args=parser.parse_args(argv)
    try:
        with Path(args.plan).open(encoding="utf-8") as stream: doc=json.load(stream)
        result=evaluate_document(doc)
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
        return 0 if result["feasible"] and result["optimality_proven"] else 2
    except Exception as exc:
        print(f"SYNERGY V7.4 optimizer error: {exc}",file=sys.stderr)
        return 1


if __name__=="__main__": raise SystemExit(main())
