"""CLI for the SYNERGY V7.8 non-anticipative two-stage MILP prototype."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .two_stage_optimizer import optimize_two_stage_recourse


def main(argv=None):
    parser=argparse.ArgumentParser(description="Solve the SYNERGY V7.8 two-stage mean-CVaR MILP prototype")
    parser.add_argument("scenario_document",help="JSON with model parameters and discrete scenarios")
    args=parser.parse_args(argv)
    try:
        path=Path(args.scenario_document)
        with path.open(encoding="utf-8") as stream: document=json.load(stream)
        import jsonschema
        root=Path(__file__).resolve().parents[2]
        with (root/"interfaces"/"synergy_v7_8_two_stage_optimizer.schema.json").open(encoding="utf-8") as stream:
            schema=json.load(stream)
        jsonschema.validate(instance=document,schema=schema)
        result=optimize_two_stage_recourse(**document)
        print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
        return 0 if result.get("complete") else 2
    except Exception as exc:
        print(f"SYNERGY V7.8 two-stage optimizer error: {exc}",file=sys.stderr)
        return 1

if __name__=="__main__": raise SystemExit(main())
