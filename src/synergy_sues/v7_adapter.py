"""Explicit, non-posting adapters for the SYNERGY V7 → SUES boundary.

The V7 research package may live in a separate pull request. This module therefore
uses structural contracts and does not import synergy_v7 or mutate SUES ledgers.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
import weakref
from typing import Any, Callable, Iterable, Mapping

from .contracts import EvidenceStatus, Money, _decimal


_EVENT_FIELDS = (
    "event_id", "aggregate_type", "aggregate_id", "sequence", "event_type",
    "effective_at", "recorded_at", "payload", "source_ref", "evidence_ids",
    "idempotency_key", "previous_hash", "event_hash",
)


def _value(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 string")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid ISO-8601 timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone offset")
    return result


def _date(value: Any, field: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO YYYY-MM-DD date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO YYYY-MM-DD date") from exc


def _record_dict(row: Any) -> dict[str, Any]:
    if is_dataclass(row):
        return {field.name: getattr(row, field.name) for field in fields(row)}
    if isinstance(row, Mapping):
        return dict(row)
    raise ValueError("Source record must be a dataclass or mapping")


def _source_class(value: Any) -> EvidenceStatus | None:
    if value is None:
        return None
    try:
        return EvidenceStatus(str(value))
    except ValueError as exc:
        raise ValueError(f"Unsupported V7 evidence class: {value}") from exc


@dataclass(frozen=True)
class SUESSourceEvent:
    """Verified V7 event envelope; payload is canonical JSON, never executable."""

    source_event_id: str
    source_event_hash: str
    previous_hash: str
    aggregate_type: str
    aggregate_id: str
    sequence: int
    event_type: str
    effective_at: datetime
    recorded_at: datetime
    source_ref: str
    evidence_ids: tuple[str, ...]
    idempotency_key: str
    payload_json: str


# In-process provenance gate: only the exact object instances emitted by the
# verified adapter may cross into the projector registry. Structural dataclass
# construction or copying must not confer verified-source status.
_VERIFIED_SOURCE_EVENT_REFS: dict[int, weakref.ReferenceType] = {}


def _mark_source_event_verified(event: SUESSourceEvent) -> None:
    identity = id(event)
    def discard(reference, identity=identity):
        current = _VERIFIED_SOURCE_EVENT_REFS.get(identity)
        if current is reference:
            _VERIFIED_SOURCE_EVENT_REFS.pop(identity, None)
    _VERIFIED_SOURCE_EVENT_REFS[identity] = weakref.ref(event, discard)


def is_verified_source_event(event: Any) -> bool:
    reference = _VERIFIED_SOURCE_EVENT_REFS.get(id(event))
    return reference is not None and reference() is event


def adapt_v7_event_store(event_store: Any) -> tuple[SUESSourceEvent, ...]:
    """Verify a complete V7 EventStore and preserve its event chain without posting.

    The input must expose .events and .verify(), as the V7 reference EventStore does.
    Full per-aggregate history is required; partial slices cannot prove their first hash.
    """
    events = getattr(event_store, "events", None)
    verify = getattr(event_store, "verify", None)
    if events is None or not callable(verify):
        raise ValueError("V7 event store must expose events and verify()")
    if verify() is not True:
        raise ValueError("V7 event store hash-chain verification failed")

    sequences: dict[tuple[str, str], int] = {}
    heads: dict[tuple[str, str], str] = {}
    event_ids: set[str] = set()
    idempotency_keys: set[str] = set()
    adapted: list[SUESSourceEvent] = []

    for source in events:
        row = _record_dict(source)
        missing = [name for name in _EVENT_FIELDS[:10] if name not in row]
        if missing:
            raise ValueError(f"V7 event missing required fields: {', '.join(missing)}")
        if event_ids.intersection({str(row["event_id"])}):
            raise ValueError(f"Duplicate V7 event_id: {row['event_id']}")
        event_id = str(row["event_id"])
        aggregate_type, aggregate_id = str(row["aggregate_type"]), str(row["aggregate_id"])
        if not aggregate_type or not aggregate_id or not str(row["event_type"]) or not str(row["source_ref"]):
            raise ValueError("V7 event identity, type and source_ref are required")
        if not isinstance(row["payload"], dict):
            raise ValueError("V7 event payload must be an object")
        _canonical(row["payload"])
        _timestamp(row["effective_at"], "effective_at")
        _timestamp(row["recorded_at"], "recorded_at")
        sequence = row["sequence"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise ValueError("V7 event sequence must be an integer >= 1")
        key = (aggregate_type, aggregate_id)
        expected_sequence = sequences.get(key, 0) + 1
        if sequence != expected_sequence:
            raise ValueError(f"V7 aggregate sequence gap for {key}: expected {expected_sequence}, got {sequence}")
        expected_previous = heads.get(key, "")
        supplied_previous = row.get("previous_hash", "")
        if supplied_previous != expected_previous:
            raise ValueError(f"V7 previous_hash mismatch for event {event_id}")

        unsigned = {name: row.get(name, () if name == "evidence_ids" else "")
                    for name in _EVENT_FIELDS[:-1]}
        unsigned["previous_hash"] = expected_previous
        digest = sha256(_canonical(unsigned).encode("utf-8")).hexdigest()
        if row.get("event_hash") != digest:
            raise ValueError(f"V7 event hash mismatch for event {event_id}")

        evidence_ids = tuple(row.get("evidence_ids") or ())
        if any(not isinstance(x, str) or not x for x in evidence_ids):
            raise ValueError(f"Invalid evidence_ids in event {event_id}")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError(f"Duplicate evidence_ids in event {event_id}")
        idempotency_key = row.get("idempotency_key") or ""
        if idempotency_key and idempotency_key in idempotency_keys:
            raise ValueError(f"Duplicate V7 idempotency_key: {idempotency_key}")

        adapted_event = SUESSourceEvent(
            event_id, digest, expected_previous, aggregate_type, aggregate_id,
            sequence, str(row["event_type"]), _timestamp(row["effective_at"], "effective_at"),
            _timestamp(row["recorded_at"], "recorded_at"), str(row["source_ref"]),
            evidence_ids, str(idempotency_key), _canonical(row["payload"]),
        )
        _mark_source_event_verified(adapted_event)
        adapted.append(adapted_event)
        event_ids.add(event_id)
        if idempotency_key:
            idempotency_keys.add(idempotency_key)
        sequences[key] = sequence
        heads[key] = digest
    return tuple(adapted)


@dataclass(frozen=True)
class SUESRealizationLink:
    """One source record from the V7 realization chain, with explicit lineage."""

    source_record_id: str
    record_type: str
    effective_date: date | None
    source_ref: str
    evidence_refs: tuple[str, ...]
    related_record_ids: tuple[str, ...]
    entity_id: str = ""
    project_id: str = ""
    benefit_stream_id: str = ""
    period_id: str = ""
    quantity: Decimal | None = None
    unit: str = ""
    amount: Money | None = None
    evidence_status: EvidenceStatus | None = None
    payload_json: str = ""


@dataclass(frozen=True)
class SUESRealizationBridge:
    as_of: str
    links: tuple[SUESRealizationLink, ...]
    validated_report_json: str


def adapt_v7_realization_chain(
    evaluator: Callable[..., dict],
    outputs: Iterable[Any],
    deliveries: Iterable[Any],
    invoice_allocations: Iterable[Any],
    invoices: Iterable[Any],
    settlements: Iterable[Any],
    collection_attributions: Iterable[Any],
    costs: Iterable[Any],
    as_of: str,
) -> SUESRealizationBridge:
    """Run the V7 realization validator, then preserve every source link in SUES.

    This is an evidence/interchange adapter only. It does not recognize revenue,
    infer cash, create GL entries, or turn pre/post output deltas into causal claims.
    """
    try:
        date.fromisoformat(as_of)
    except (TypeError, ValueError) as exc:
        raise ValueError("as_of must be ISO YYYY-MM-DD") from exc
    if not callable(evaluator):
        raise ValueError("A V7 evaluate_realization_chain function is required")

    output_rows, delivery_rows = list(outputs), list(deliveries)
    allocation_rows, invoice_rows = list(invoice_allocations), list(invoices)
    settlement_rows, collection_rows, cost_rows = (
        list(settlements), list(collection_attributions), list(costs)
    )
    def unique_index(rows: list[Any], field: str, label: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for item in rows:
            identifier = str(_value(item, field, ""))
            if not identifier or identifier in result:
                raise ValueError(f"{label} contains a missing or duplicate {field}: {identifier}")
            result[identifier] = item
        return result

    output_map = unique_index(output_rows, "output_id", "outputs")
    delivery_map = unique_index(delivery_rows, "delivery_id", "deliveries")
    invoice_map = unique_index(invoice_rows, "document_id", "invoices")
    settlement_map = unique_index(settlement_rows, "settlement_id", "settlements")
    allocation_map = unique_index(allocation_rows, "allocation_id", "invoice allocations")

    links: list[SUESRealizationLink] = []

    def add(row: Any, record_type: str, id_field: str, date_field: str | None,
            source_field: str, evidence_fields: tuple[str, ...], related: tuple[str, ...],
            entity: str = "", project: str = "", benefit: str = "", period: str = "",
            quantity_field: str | None = None, unit_field: str = "",
            amount_field: str | None = None, currency_field: str = "",
            status_field: str = "", numeric_fields: tuple[str, ...] = ()) -> None:
        data = _record_dict(row)
        for numeric_field in numeric_fields:
            if data.get(numeric_field) is not None:
                _decimal(data[numeric_field], f"{record_type} {numeric_field}")
        record_id = str(data.get(id_field, ""))
        if not record_id:
            raise ValueError(f"{record_type} is missing {id_field}")
        effective = _date(data.get(date_field), date_field) if date_field else None
        source_ref = str(data.get(source_field, ""))
        if not source_ref:
            raise ValueError(f"{record_type} source_ref is required")
        evidence = tuple(str(data[x]) for x in evidence_fields if data.get(x))
        related_ids = tuple(str(data[x]) for x in related if data.get(x))
        quantity = (
            _decimal(data[quantity_field], f"{record_type} quantity")
            if quantity_field and data.get(quantity_field) is not None else None
        )
        if quantity is not None and quantity <= 0:
            raise ValueError(f"{record_type} quantity must be finite and positive")
        amount = (
            Money(_decimal(data[amount_field], f"{record_type} amount"), str(data[currency_field]))
            if amount_field and data.get(amount_field) is not None else None
        )
        if amount is not None and amount.amount <= 0:
            raise ValueError(f"{record_type} amount must be positive")
        status = _source_class(data.get(status_field)) if status_field else None
        payload = _canonical(data)
        links.append(SUESRealizationLink(
            record_id, record_type, effective, source_ref, evidence, related_ids,
            str(data.get(entity, "")) if entity else "",
            str(data.get(project, "")) if project else "",
            str(data.get(benefit, "")) if benefit else "",
            str(data.get(period, "")) if period else "",
            quantity, str(data.get(unit_field, "")) if unit_field else "",
            amount, status, payload,
        ))

    for row in output_rows:
        add(row, "OUTPUT_OBSERVATION", "output_id", None, "evidence_id", ("evidence_id",), (),
            "enterprise_id", "project_id", "benefit_stream_id", "period",
            "observed_quantity", "unit", status_field="source_class",
            numeric_fields=("baseline_quantity",))
    for row in delivery_rows:
        output = output_map.get(str(_value(row, "output_id")))
        if output is None:
            raise ValueError(f"Delivery references unknown output: {_value(row, 'delivery_id')}")
        add(row, "DELIVERY_ACCEPTANCE", "delivery_id", "accepted_date", "acceptance_ref",
            ("acceptance_ref",), ("output_id",),
            quantity_field="accepted_quantity", unit_field="unit", status_field="source_class")
        links[-1] = SUESRealizationLink(**{
            **links[-1].__dict__,
            "entity_id": str(_value(output, "enterprise_id", "")),
            "project_id": str(_value(output, "project_id", "")),
            "benefit_stream_id": str(_value(output, "benefit_stream_id", "")),
            "period_id": str(_value(output, "period", "")),
        })
    for row in invoice_rows:
        add(row, "TRADE_DOCUMENT", "document_id", "issue_date", "source_ref",
            ("source_ref",), ("counterparty_id",),
            "enterprise_id", amount_field="original_amount", currency_field="currency")
    for row in allocation_rows:
        delivery = delivery_map.get(str(_value(row, "delivery_id")))
        if delivery is None:
            raise ValueError(f"Invoice allocation references unknown delivery: {_value(row, 'allocation_id')}")
        invoice_id = str(_value(row, "invoice_document_id", ""))
        if invoice_id not in invoice_map:
            raise ValueError(f"Invoice allocation references unknown invoice: {_value(row, 'allocation_id')}")
        output = output_map.get(str(_value(delivery, "output_id")))
        add(row, "INVOICE_DELIVERY_ALLOCATION", "allocation_id", None, "source_ref",
            ("source_ref",), ("delivery_id", "invoice_document_id"),
            "enterprise_id" if output else "", "project_id" if output else "",
            "benefit_stream_id" if output else "", "period" if output else "",
            "invoiced_quantity", "unit", "invoiced_amount", "currency")
        if output is not None:
            # Replace the just-added link with dimensions resolved through delivery → output.
            links[-1] = SUESRealizationLink(**{
                **links[-1].__dict__,
                "entity_id": str(_value(output, "enterprise_id")),
                "project_id": str(_value(output, "project_id")),
                "benefit_stream_id": str(_value(output, "benefit_stream_id")),
                "period_id": str(_value(output, "period")),
            })
    for row in settlement_rows:
        add(row, "SETTLEMENT", "settlement_id", "settlement_date", "source_ref",
            ("source_ref",), ("document_id",), amount_field="amount", currency_field="currency")
    for row in collection_rows:
        settlement = settlement_map.get(str(_value(row, "settlement_id")))
        allocation = allocation_map.get(str(_value(row, "invoice_allocation_id")))
        if settlement is None or allocation is None:
            raise ValueError(f"Collection attribution references an unknown settlement/allocation: {_value(row, 'attribution_id')}")
        effective = _value(settlement, "settlement_date")
        add(row, "COLLECTION_ATTRIBUTION", "attribution_id", None, "source_ref",
            ("source_ref",), ("settlement_id", "invoice_allocation_id"),
            amount_field="amount", currency_field="currency")
        if effective:
            links[-1] = SUESRealizationLink(**{
                **links[-1].__dict__, "effective_date": _date(effective, "settlement_date")
            })
        if allocation is not None:
            linked_delivery = delivery_map.get(str(_value(allocation, "delivery_id")))
            linked_output = output_map.get(str(_value(linked_delivery, "output_id"))) if linked_delivery is not None else None
            if linked_output is not None:
                links[-1] = SUESRealizationLink(**{
                    **links[-1].__dict__,
                    "entity_id": str(_value(linked_output, "enterprise_id", "")),
                    "project_id": str(_value(linked_output, "project_id", "")),
                    "benefit_stream_id": str(_value(linked_output, "benefit_stream_id", "")),
                    "period_id": str(_value(linked_output, "period", "")),
                })
    for row in cost_rows:
        add(row, "COST_OBSERVATION", "cost_id", None, "evidence_id", ("evidence_id",), (),
            "enterprise_id", "project_id", "benefit_stream_id", "period",
            amount_field="amount", currency_field="currency", status_field="source_class")

    # Do not invoke the evaluator until all source identities, references,
    # dates and numeric contracts have passed validation. A failing input must
    # not trigger evaluator-side effects before the bridge rejects it.
    report = evaluator(
        output_rows, delivery_rows, allocation_rows, invoice_rows,
        settlement_rows, collection_rows, cost_rows, as_of,
    )
    if not isinstance(report, dict):
        raise ValueError("V7 realization evaluator must return a report object")
    report_json = _canonical(report)

    # Preserve the complete source set. The V7 evaluator owns as-of semantics;
    # dropping source rows here would make the bridge incomplete and non-replayable.
    return SUESRealizationBridge(as_of, tuple(links), report_json)
