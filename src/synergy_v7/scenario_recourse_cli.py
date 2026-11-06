"""CLI for SYNERGY V7.7 scenario recourse evaluation."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .scenario_recourse import evaluate_scenario_set


def main(argv=None):
    parser=argparse.ArgumentParser(description="Evaluate scenario-wise adaptive recourse and mean-CVaR risk")
    parser.add_argument("scenario_document",help="JSON with base_plan and scenarios")
    args=parser.parse_args(argv)
    try:
        path=Path(args.scenario_document)
        with path.open(encoding="utf-8") as stream: document=json.load(stream)
        try: import jsonschema
        except ImportError as exc: raise RuntimeError("Install requirements to validate JSON Schema") from exc
        root=Path(__file__).resolve().parents[2]
        with (root/"interfaces"/"synergy_v7_scenario_recourse.schema.json").open(encoding="utf-8") as stream:
            schema=json.load(stream)
        jsonschema.validate(instance=document,schema=schema)
        result=evaluate_scenario_set(document["base_plan"],document["scenarios"],
            document.get("risk_alpha",0.95),document.get("risk_weight",0.5))
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
        return 0 if result["complete"] else 2
    except Exception as exc:
        print(f"SYNERGY V7.7 scenario recourse error: {exc}",file=sys.stderr)
        return 1

if __name__=="__main__": raise SystemExit(main())
