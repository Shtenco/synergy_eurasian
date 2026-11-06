"""SYNERGY Unified Economic System — foundational economic contracts."""
from .benefits import BenefitAttribution, BenefitAttributionRegistry, BenefitEvent
from .contracts import EconomicPeriod, EvidenceRecord, EvidenceStatus, FXRate, Money, Quantity
from .consolidation import IntercompanyRecord, IntercompanyRecordType, reconcile_intercompany
from .journal import Account, AccountType, Journal, JournalEntry, JournalLine, NormalBalance
from .physical import FlowBoundary, PhysicalFlow, summarize_physical_flows

__all__ = [
    "Account", "AccountType", "BenefitAttribution", "BenefitAttributionRegistry",
    "BenefitEvent", "EconomicPeriod", "EvidenceRecord", "EvidenceStatus",
    "FlowBoundary", "FXRate", "IntercompanyRecord", "IntercompanyRecordType", "Journal", "JournalEntry", "JournalLine",
    "Money", "NormalBalance", "PhysicalFlow", "Quantity",
    "reconcile_intercompany", "summarize_physical_flows",
]
