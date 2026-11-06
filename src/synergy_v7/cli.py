"""CLI for validating and evaluating a SYNERGY V7.1 production-plan JSON document."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from .core import ResourceCapacity
from .production import (MaterialRequirement, ResourceRequirement, ProductionRecipe,
    ProductionOrder, InventoryReceipt, ProductDemand, evaluate_production_plan)


def evaluate_document(document: dict, schema_path: str | Path | None = None) -> dict:
    """Validate a plan against the checked-in JSON Schema and evaluate feasibility."""
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("Install project requirements to validate JSON Schema") from exc
    root=Path(__file__).resolve().parents[2]
    path=Path(schema_path) if schema_path else root/"interfaces"/"synergy_v7_production_plan.schema.json"
    with path.open(encoding="utf-8") as stream:
        schema=json.load(stream)
    jsonschema.validate(instance=document,schema=schema)

    recipes=[]
    for row in document["recipes"]:
        recipes.append(ProductionRecipe(
            recipe_id=row["recipe_id"], output_product_id=row["output_product_id"],
            output_quantity_per_batch=row["output_quantity_per_batch"], output_unit=row["output_unit"],
            input_requirements=tuple(MaterialRequirement(**x) for x in row["input_requirements"]),
            resource_requirements=tuple(ResourceRequirement(**x) for x in row["resource_requirements"]),
            lead_time_periods=row["lead_time_periods"], node_id=row.get("node_id","")))
    orders=[ProductionOrder(**x) for x in document["orders"]]
    receipts=[InventoryReceipt(**x) for x in document["inventory_receipts"]]
    demands=[ProductDemand(**x) for x in document["demands"]]
    capacities=[ResourceCapacity(**x) for x in document["resource_capacities"]]
    return evaluate_production_plan(recipes,orders,receipts,demands,capacities,
        include_nonfirm_receipts=document.get("include_nonfirm_receipts",False))


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Evaluate a SYNERGY V7.1 time-expanded production plan")
    parser.add_argument("plan",help="Path to a production-plan JSON file")
    args=parser.parse_args(argv)
    try:
        with Path(args.plan).open(encoding="utf-8") as stream:
            document=json.load(stream)
        result=evaluate_document(document)
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
        return 0 if result["feasible"] else 2
    except Exception as exc:
        print(f"SYNERGY V7.1 plan error: {exc}",file=sys.stderr)
        return 1


if __name__=="__main__":
    raise SystemExit(main())
