"""CLI for matched-pair difference-in-differences (SYNERGY V7.3.1)."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .causal import CausalObservation,matched_pair_difference_in_differences


def evaluate_document(document,schema_path=None):
    try: import jsonschema
    except ImportError as exc: raise RuntimeError("Install requirements to validate JSON Schema") from exc
    root=Path(__file__).resolve().parents[2]
    path=Path(schema_path) if schema_path else root/"interfaces"/"synergy_v7_causal_observations.schema.json"
    with path.open(encoding="utf-8") as stream: schema=json.load(stream)
    jsonschema.validate(instance=document,schema=schema)
    rows=[CausalObservation(**x) for x in document["observations"]]
    return matched_pair_difference_in_differences(rows,document["confidence_level"],document["outcome_direction"])


def main(argv=None):
    parser=argparse.ArgumentParser(description="Estimate matched-pair DiD for SYNERGY")
    parser.add_argument("snapshot",help="Causal observations JSON input")
    args=parser.parse_args(argv)
    try:
        with Path(args.snapshot).open(encoding="utf-8") as stream: doc=json.load(stream)
        print(json.dumps(evaluate_document(doc),ensure_ascii=False,indent=2,sort_keys=True))
        return 0
    except Exception as exc:
        print(f"SYNERGY V7.3.1 causal analysis error: {exc}",file=sys.stderr)
        return 1


if __name__=="__main__": raise SystemExit(main())
