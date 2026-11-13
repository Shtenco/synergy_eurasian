"""CLI for SYNERGY V7.3 production-to-cash evidence chain."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .realization import (OutputObservation,DeliveryAcceptance,InvoiceDeliveryAllocation,
    CollectionAttribution,CostObservation,evaluate_realization_chain)
from .trade_ledger import TradeDocument,SettlementEvent


def evaluate_document(document,schema_path=None):
    try: import jsonschema
    except ImportError as exc: raise RuntimeError("Install requirements to validate JSON Schema") from exc
    root=Path(__file__).resolve().parents[2]
    path=Path(schema_path) if schema_path else root/"interfaces"/"synergy_v7_realization_chain.schema.json"
    with path.open(encoding="utf-8") as stream: schema=json.load(stream)
    jsonschema.validate(instance=document,schema=schema)
    outputs=[OutputObservation(**x) for x in document["outputs"]]
    deliveries=[DeliveryAcceptance(**x) for x in document["deliveries"]]
    allocations=[InvoiceDeliveryAllocation(**x) for x in document["invoice_allocations"]]
    invoices=[TradeDocument(**x) for x in document["invoices"]]
    settlements=[SettlementEvent(**x) for x in document["settlements"]]
    collections=[CollectionAttribution(**x) for x in document["collection_attributions"]]
    costs=[CostObservation(**x) for x in document["costs"]]
    return evaluate_realization_chain(outputs,deliveries,allocations,invoices,settlements,collections,costs,document["as_of"])


def main(argv=None):
    parser=argparse.ArgumentParser(description="Evaluate SYNERGY V7.3 realization evidence")
    parser.add_argument("snapshot",help="Evidence chain JSON input")
    args=parser.parse_args(argv)
    try:
        with Path(args.snapshot).open(encoding="utf-8") as stream: doc=json.load(stream)
        result=evaluate_document(doc)
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
        return 0
    except Exception as exc:
        print(f"SYNERGY V7.3 realization error: {exc}",file=sys.stderr)
        return 1


if __name__=="__main__": raise SystemExit(main())
