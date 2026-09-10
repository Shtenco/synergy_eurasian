import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from federation_audit import audit


def load_config():
    return json.loads((ROOT / "config" / "federation_v4.json").read_text(encoding="utf-8"))


def test_federation_v4_passes_static_authority_audit():
    config = load_config()
    assert audit(config) == []


def test_federation_registry_has_46_observed_repositories():
    config = load_config()
    repos = config["repositories"]
    assert len(repos) == 46
    assert len({r["repo"] for r in repos}) == 46


def test_accounting_settlement_and_real_economy_are_separate_authorities():
    config = load_config()
    authorities = {
        config["accounting_authority"],
        config["settlement_authority"],
        config["real_economy_authority"],
        config["architecture_root"],
    }
    assert len(authorities) == 4


def test_project_proposal_cannot_be_financial_authorization():
    config = load_config()
    assert config["canonical_objects"]["ProjectProposal"]["authority"] == "Shtenco/synergy_eurasian"
    assert config["canonical_objects"]["CapitalAuthorization"]["authority"] == "Shtenco/synergy_financial_os"
    assert config["canonical_objects"]["ProjectProposal"]["authority"] != config["canonical_objects"]["CapitalAuthorization"]["authority"]


def test_settlement_receipt_and_accounting_snapshot_are_separate():
    config = load_config()
    assert config["canonical_objects"]["SettlementReceipt"]["authority"] == "Shtenco/synergy_pay_system"
    assert config["canonical_objects"]["AccountingSnapshot"]["authority"] == "Shtenco/synergy_financial_os"


def test_forbidden_value_promotions_remain_explicit():
    config = load_config()
    forbidden = set(config["forbidden_cross_domain_promotions"])
    assert "modelled_gva_to_cash" in forbidden
    assert "own_token_market_cap_to_collateral" in forbidden
    assert "internal_amm_mark_to_external_profit" in forbidden
    assert "flash_principal_to_owned_capital" in forbidden
    assert "ai_recommendation_to_capital_authorization" in forbidden
    assert "blockchain_commitment_to_economic_truth" in forbidden
