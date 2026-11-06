"""CLI for a SYNERGY V7.2.1 trade-ledger JSON snapshot."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .trade_ledger import (TradeDocument, SettlementEvent, DocumentAdjustment,
    DisputeEvent, CreditRiskAssessment, build_trade_ledger)


def evaluate_document(document: dict, schema_path=None) -> dict:
    try: import jsonschema
    except ImportError as exc: raise RuntimeError("Install requirements to validate JSON Schema") from exc
    root=Path(__file__).resolve().parents[2]
    path=Path(schema_path) if schema_path else root/"interfaces"/"synergy_v7_trade_ledger.schema.json"
    with path.open(encoding="utf-8") as stream: schema=json.load(stream)
    jsonschema.validate(instance=document,schema=schema)
    docs=[TradeDocument(**x) for x in document["documents"]]
    settlements=[SettlementEvent(**x) for x in document["settlements"]]
    adjustments=[DocumentAdjustment(**x) for x in document["adjustments"]]
    disputes=[DisputeEvent(**x) for x in document["disputes"]]
    risks=[CreditRiskAssessment(**x) for x in document.get("credit_assessments",[])]
    return build_trade_ledger(docs,settlements,adjustments,disputes,document["as_of"],risks)


def main(argv=None):
    parser=argparse.ArgumentParser(description="Evaluate SYNERGY V7.2.1 receivables/payables")
    parser.add_argument("snapshot",help="Trade ledger JSON input")
    args=parser.parse_args(argv)
    try:
        with Path(args.snapshot).open(encoding="utf-8") as stream: document=json.load(stream)
        result=evaluate_document(document)
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
        return 0
    except Exception as exc:
        print(f"SYNERGY V7.2.1 ledger error: {exc}",file=sys.stderr)
        return 1


if __name__=="__main__": raise SystemExit(main())
