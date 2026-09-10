"""Static federation-boundary audit for SYNERGY v4.

The audit checks architecture metadata only. It does not grant real runtime,
financial, settlement, regulatory, or blockchain authority.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


REQUIRED_CANONICAL_OBJECTS = {
    "DemandSignal",
    "ResourceState",
    "TechnologyCandidate",
    "ProjectProposal",
    "CapitalAuthorization",
    "PaymentIntent",
    "SettlementReceipt",
    "EvidencePackage",
    "AccountingSnapshot",
}

REQUIRED_REPOS = {
    "Shtenco/synergy_system",
    "Shtenco/synergy_eurasian",
    "Shtenco/synergy_financial_os",
    "Shtenco/synergy_pay_system",
    "Shtenco/synergy_project",
    "Shtenco/synergynet",
    "Shtenco/synergy_meta_os",
    "Shtenco/midas_ai",
    "Shtenco/nexus_science_agent",
}

FORBIDDEN_ACCOUNTING_AUTHORITIES = {
    "Shtenco/midas_ai",
    "Shtenco/print_money_synergychain",
    "Shtenco/synergy_graph_print_money",
    "Shtenco/synergy_pay_system",
    "Shtenco/synergy_eurasian",
    "Shtenco/synergy_metachain",
    "Shtenco/synergy_ai_blockchain",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(config: dict) -> list[str]:
    errors: list[str] = []

    objects = config.get("canonical_objects", {})
    missing_objects = REQUIRED_CANONICAL_OBJECTS - set(objects)
    if missing_objects:
        errors.append(f"missing canonical objects: {sorted(missing_objects)}")

    repos = config.get("repositories", [])
    repo_names = [r.get("repo") for r in repos]
    duplicates = [name for name, count in Counter(repo_names).items() if count > 1]
    if duplicates:
        errors.append(f"duplicate repository entries: {sorted(duplicates)}")

    missing_repos = REQUIRED_REPOS - set(repo_names)
    if missing_repos:
        errors.append(f"missing required repositories: {sorted(missing_repos)}")

    accounting = config.get("accounting_authority")
    settlement = config.get("settlement_authority")
    real_economy = config.get("real_economy_authority")
    architecture = config.get("architecture_root")

    if accounting != "Shtenco/synergy_financial_os":
        errors.append("canonical accounting authority must be synergy_financial_os")
    if settlement != "Shtenco/synergy_pay_system":
        errors.append("canonical settlement authority must be synergy_pay_system")
    if real_economy != "Shtenco/synergy_eurasian":
        errors.append("real economy authority must be synergy_eurasian")
    if architecture != "Shtenco/synergy_system":
        errors.append("architecture root must be synergy_system")

    if objects.get("AccountingSnapshot", {}).get("authority") != accounting:
        errors.append("AccountingSnapshot authority mismatch")
    if objects.get("SettlementReceipt", {}).get("authority") != settlement:
        errors.append("SettlementReceipt authority mismatch")
    if objects.get("ProjectProposal", {}).get("authority") != real_economy:
        errors.append("ProjectProposal authority mismatch")
    if objects.get("ResourceState", {}).get("authority") != real_economy:
        errors.append("ResourceState authority mismatch")

    if accounting in FORBIDDEN_ACCOUNTING_AUTHORITIES:
        errors.append("forbidden component selected as accounting authority")

    promotions = set(config.get("forbidden_cross_domain_promotions", []))
    expected_promotions = {
        "modelled_gva_to_cash",
        "own_token_market_cap_to_collateral",
        "internal_amm_mark_to_external_profit",
        "flash_principal_to_owned_capital",
        "ai_recommendation_to_capital_authorization",
        "blockchain_commitment_to_economic_truth",
    }
    missing_promotions = expected_promotions - promotions
    if missing_promotions:
        errors.append(f"missing forbidden promotions: {sorted(missing_promotions)}")

    # Runtime authority must be explicitly bounded.
    for repo in repos:
        if repo.get("runtime_authority") and not repo.get("authority_scope"):
            errors.append(f"runtime authority has no scope: {repo.get('repo')}")

    # Research engines may never be declared canonical accounting authority.
    for repo in repos:
        if repo.get("repo") in FORBIDDEN_ACCOUNTING_AUTHORITIES:
            scope = str(repo.get("authority_scope", ""))
            if "hardnav" in scope.lower() or "profit_recognition" in scope.lower():
                errors.append(f"research/non-accounting repo claims accounting scope: {repo.get('repo')}")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/federation_v4.json"))
    args = parser.parse_args()
    config = load(args.config)
    errors = audit(config)
    summary = {
        "version": config.get("version"),
        "status": "PASS" if not errors else "FAIL",
        "repository_count": len(config.get("repositories", [])),
        "canonical_object_count": len(config.get("canonical_objects", {})),
        "errors": errors,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
