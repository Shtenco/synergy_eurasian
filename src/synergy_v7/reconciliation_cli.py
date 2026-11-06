"""CLI for explicit bank statement reconciliation (SYNERGY V7.2.2)."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .trade_ledger import TradeDocument,SettlementEvent
from .cash_reconciliation import BankStatementLine,CashAllocation,reconcile_bank_statement


def evaluate_document(document,schema_path=None):
    try: import jsonschema
    except ImportError as exc: raise RuntimeError("Install requirements to validate JSON Schema") from exc
    root=Path(__file__).resolve().parents[2]
    path=Path(schema_path) if schema_path else root/"interfaces"/"synergy_v7_cash_reconciliation.schema.json"
    with path.open(encoding="utf-8") as stream: schema=json.load(stream)
    jsonschema.validate(instance=document,schema=schema)
    docs=[TradeDocument(**x) for x in document["documents"]]
    prior=[SettlementEvent(**x) for x in document["prior_settlements"]]
    lines=[BankStatementLine(**x) for x in document["statement_lines"]]
    allocs=[CashAllocation(**x) for x in document["allocations"]]
    return reconcile_bank_statement(docs,prior,lines,allocs,document["as_of"])


def main(argv=None):
    parser=argparse.ArgumentParser(description="Reconcile SYNERGY V7.2.2 bank statement lines")
    parser.add_argument("snapshot",help="Reconciliation JSON input")
    args=parser.parse_args(argv)
    try:
        with Path(args.snapshot).open(encoding="utf-8") as stream: doc=json.load(stream)
        result=evaluate_document(doc)
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
        return 0 if result["fully_reconciled"] else 2
    except Exception as exc:
        print(f"SYNERGY V7.2.2 reconciliation error: {exc}",file=sys.stderr)
        return 1


if __name__=="__main__": raise SystemExit(main())
