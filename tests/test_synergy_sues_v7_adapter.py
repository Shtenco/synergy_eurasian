from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json

import pytest

from synergy_sues.v7_adapter import adapt_v7_event_store, adapt_v7_realization_chain


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    aggregate_type: str
    aggregate_id: str
    sequence: int
    event_type: str
    effective_at: str
    recorded_at: str
    payload: dict
    source_ref: str
    evidence_ids: tuple = ()
    idempotency_key: str = ""
    previous_hash: str = ""
    event_hash: str = ""


class EventStore:
    def __init__(self, events):
        self.events = tuple(events)

    def verify(self):
        return True


def sealed_event(event_id, aggregate_id, sequence, event_type, payload, previous_hash=""):
    event = DomainEvent(
        event_id, "PROJECT", aggregate_id, sequence, event_type,
        "2026-11-06T08:00:00+00:00", "2026-11-06T08:01:00+00:00",
        payload, f"source:{event_id}", ("evidence:1",), f"idem:{event_id}",
        previous_hash, "",
    )
    unsigned = {
        "event_id": event.event_id, "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id, "sequence": event.sequence,
        "event_type": event.event_type, "effective_at": event.effective_at,
        "recorded_at": event.recorded_at, "payload": event.payload,
        "source_ref": event.source_ref, "evidence_ids": event.evidence_ids,
        "idempotency_key": event.idempotency_key, "previous_hash": previous_hash,
    }
    digest = sha256(canonical(unsigned).encode("utf-8")).hexdigest()
    return DomainEvent(**{**event.__dict__, "event_hash": digest})


def test_v7_event_store_adapter_preserves_hash_chain_and_event_lineage():
    first = sealed_event("event-1", "project-1", 1, "PRODUCTION_ORDER_CREATED", {"order_id": "batch-1"})
    second = sealed_event("event-2", "project-1", 2, "PRODUCTION_COMPLETED",
                          {"order_id": "batch-1", "quantity": "10"}, first.event_hash)
    adapted = adapt_v7_event_store(EventStore([first, second]))

    assert len(adapted) == 2
    assert adapted[0].source_event_id == "event-1"
    assert adapted[1].previous_hash == adapted[0].source_event_hash
    assert adapted[1].event_type == "PRODUCTION_COMPLETED"
    assert json.loads(adapted[1].payload_json)["quantity"] == "10"
    assert adapted[1].evidence_ids == ("evidence:1",)


def test_v7_event_adapter_rejects_modified_payload_and_hash():
    event = sealed_event("event-1", "project-1", 1, "PRODUCTION_COMPLETED", {"quantity": "10"})
    tampered = DomainEvent(**{**event.__dict__, "payload": {"quantity": "11"}})
    with pytest.raises(ValueError, match="hash mismatch"):
        adapt_v7_event_store(EventStore([tampered]))


def test_v7_event_adapter_rejects_sequence_gap_and_duplicate_idempotency():
    first = sealed_event("event-1", "project-1", 1, "A", {})
    gap = sealed_event("event-3", "project-1", 3, "B", {}, first.event_hash)
    with pytest.raises(ValueError, match="sequence gap"):
        adapt_v7_event_store(EventStore([first, gap]))

    event_a = sealed_event("event-a", "project-a", 1, "A", {})
    event_b = sealed_event("event-b", "project-b", 1, "B", {})
    event_b = DomainEvent(**{**event_b.__dict__, "idempotency_key": event_a.idempotency_key})
    # Re-seal because the idempotency key is part of the hash.
    event_b = sealed_event("event-b", "project-b", 1, "B", {})
    event_b = DomainEvent(**{**event_b.__dict__, "idempotency_key": event_a.idempotency_key, "event_hash": ""})
    unsigned = {**event_b.__dict__}
    unsigned.pop("event_hash")
    event_b = DomainEvent(**{**event_b.__dict__, "event_hash": sha256(canonical(unsigned).encode()).hexdigest()})
    with pytest.raises(ValueError, match="Duplicate V7 idempotency_key"):
        adapt_v7_event_store(EventStore([event_a, event_b]))


@dataclass(frozen=True)
class Output:
    output_id: str = "out-1"
    enterprise_id: str = "co-1"
    project_id: str = "factory-1"
    benefit_stream_id: str = "stream-1"
    period: str = "2026-11"
    product_id: str = "part"
    observed_quantity: float = 100.0
    baseline_quantity: float = 80.0
    unit: str = "unit"
    evidence_method: str = "PRE_POST"
    evidence_id: str = "meter:out-1"
    source_class: str = "OBSERVED"


@dataclass(frozen=True)
class Delivery:
    delivery_id: str = "delivery-1"
    output_id: str = "out-1"
    customer_id: str = "customer-1"
    accepted_date: str = "2026-11-05"
    accepted_quantity: float = 60.0
    unit: str = "unit"
    acceptance_ref: str = "acceptance:1"
    source_class: str = "VERIFIED"


@dataclass(frozen=True)
class Allocation:
    allocation_id: str = "alloc-1"
    delivery_id: str = "delivery-1"
    invoice_document_id: str = "invoice-1"
    invoiced_quantity: float = 60.0
    unit: str = "unit"
    invoiced_amount: float = 600.0
    currency: str = "USD"
    source_ref: str = "invoice-allocation:1"


@dataclass(frozen=True)
class Invoice:
    document_id: str = "invoice-1"
    side: str = "RECEIVABLE"
    enterprise_id: str = "co-1"
    counterparty_id: str = "customer-1"
    issue_date: str = "2026-11-05"
    due_date: str = "2026-12-05"
    currency: str = "USD"
    original_amount: float = 600.0
    source_ref: str = "invoice:1"
    contract_ref: str = "contract:1"


@dataclass(frozen=True)
class Settlement:
    settlement_id: str = "settlement-1"
    document_id: str = "invoice-1"
    settlement_date: str = "2026-11-06"
    amount: float = 400.0
    currency: str = "USD"
    cash_account_id: str = "bank:usd"
    source_ref: str = "bank-statement:line-1"


@dataclass(frozen=True)
class Collection:
    attribution_id: str = "collection-1"
    settlement_id: str = "settlement-1"
    invoice_allocation_id: str = "alloc-1"
    amount: float = 400.0
    currency: str = "USD"
    source_ref: str = "remittance:1"


@dataclass(frozen=True)
class Cost:
    cost_id: str = "cost-1"
    enterprise_id: str = "co-1"
    project_id: str = "factory-1"
    benefit_stream_id: str = "stream-1"
    period: str = "2026-11"
    cost_type: str = "DIRECT_COST"
    amount: float = 250.0
    currency: str = "USD"
    evidence_id: str = "supplier-invoice:steel"
    source_class: str = "VERIFIED"


def test_v7_realization_adapter_preserves_output_to_cash_lineage_without_gl_posting():
    calls = []

    def evaluator(*args):
        calls.append(args)
        return {"as_of": args[-1], "revenue_is_not_cash": True, "cash": {"USD": 400.0}}

    bridge = adapt_v7_realization_chain(
        evaluator, [Output()], [Delivery()], [Allocation()], [Invoice()],
        [Settlement()], [Collection()], [Cost()], "2026-11-06",
    )
    assert len(calls) == 1
    by_type = {row.record_type: row for row in bridge.links}
    assert by_type["OUTPUT_OBSERVATION"].quantity == 100
    assert by_type["DELIVERY_ACCEPTANCE"].related_record_ids == ("out-1",)
    assert by_type["INVOICE_DELIVERY_ALLOCATION"].project_id == "factory-1"
    assert by_type["COLLECTION_ATTRIBUTION"].effective_date == date(2026, 11, 6)
    assert by_type["COLLECTION_ATTRIBUTION"].related_record_ids == ("settlement-1", "alloc-1")
    assert by_type["COLLECTION_ATTRIBUTION"].amount.amount == 400
    assert by_type["COST_OBSERVATION"].evidence_status.value == "VERIFIED"
    assert json.loads(bridge.validated_report_json)["revenue_is_not_cash"] is True
    assert not hasattr(bridge, "journal_entries")


def test_realization_adapter_does_not_build_bridge_when_v7_validation_fails():
    def reject(*args):
        raise ValueError("accepted delivery exceeds observed output")

    with pytest.raises(ValueError, match="accepted delivery exceeds"):
        adapt_v7_realization_chain(
            reject, [Output()], [Delivery()], [Allocation()], [Invoice()],
            [Settlement()], [Collection()], [Cost()], "2026-11-06",
        )



def test_realization_adapter_preserves_future_source_rows_for_complete_replay():
    future_delivery = Delivery(
        delivery_id="delivery-future",
        accepted_date="2026-12-01",
        accepted_quantity=10.0,
    )
    bridge = adapt_v7_realization_chain(
        lambda *args: {"as_of": args[-1], "future_rows_preserved": True},
        [Output()], [Delivery(), future_delivery], [Allocation()], [Invoice()],
        [Settlement()], [Collection()], [Cost()], "2026-11-06",
    )
    delivery_ids = {
        row.source_record_id for row in bridge.links
        if row.record_type == "DELIVERY_ACCEPTANCE"
    }
    assert delivery_ids == {"delivery-1", "delivery-future"}
