from dataclasses import replace
from decimal import Decimal
import sqlite3
import pytest

from synergy_sues.authority_scope import (
    AuthorityScope, AuthorityScopeEngine, ScopeRoleRequirement,
)
from synergy_sues.federation_authorization import AuthorizationDecision
from synergy_sues.federation_identity import SignedEventEnvelope
from synergy_sues.federation_execution import AuthorizedActionExecutor


def scope(**overrides):
    values = dict(
        scope_id="scope:treasury", tenant_id="tenant:one", action="PAYMENT_RELEASE",
        resource_type="BANK_ACCOUNT", subject_ids=("user:treasurer",),
        currencies=("USD", "EUR"), max_per_transaction="10000.00",
        period_limit="50000.00", period_window="MONTH",
        resource_id="account:operating",
        allowed_organization_ids=("org:synergy-kz",),
        allowed_account_ids=("account:operating",),
        allowed_counterparty_ids=("vendor:approved",),
        initiator_role="TREASURER",
        approval_roles=(ScopeRoleRequirement("FINANCE_DIRECTOR", 1),
                        ScopeRoleRequirement("RISK_OFFICER", 1)),
    )
    values.update(overrides)
    return AuthorityScope(**values)


def request(**overrides):
    payload = dict(
        request_id="req:1", action="PAYMENT_RELEASE",
        resource_type="BANK_ACCOUNT", resource_id="account:operating",
        amount="1250.00", currency="USD", period_key="2026-11",
        organization_id="org:synergy-kz", account_id="account:operating",
        counterparty_id="vendor:approved",
    )
    payload.update(overrides)
    return SignedEventEnvelope(
        schema_version="1", algorithm="Ed25519", identity_id="user:treasurer",
        tenant_id="tenant:one", key_id="key:1",
        signed_at="2026-11-06T10:00:00+00:00",
        event={"event_type": "AUTHORIZATION_REQUEST", "event_id": "evt:1",
               "event_hash": "a" * 64, "payload": payload},
        signature_b64="c2lnbmF0dXJl",
    )


def decision(**overrides):
    values = dict(
        allowed=True, reason="authorized_by_policy", request_id="req:1",
        requester_identity_id="user:treasurer",
        approval_identity_ids=("user:finance", "user:risk"),
        request_event_id="evt:1", request_event_hash="a" * 64,
        action="PAYMENT_RELEASE", resource_type="BANK_ACCOUNT",
        resource_id="account:operating", tenant_id="tenant:one",
    )
    values.update(overrides)
    return AuthorizationDecision(**values)




def evaluate_scope(engine_instance, signed_request, authorization_decision, total,
                   period_at="2026-11-06T10:02:00+00:00",
                   period_key="2026-11", currency="USD"):
    return engine_instance.evaluate(
        signed_request, authorization_decision, total,
        period_reference_at=period_at,
        committed_period_key=period_key,
        committed_period_currency=currency,
    )


def engine():
    return AuthorityScopeEngine(
        [scope()],
        {
            "user:treasurer": ("TREASURER",),
            "user:finance": ("FINANCE_DIRECTOR",),
            "user:risk": ("RISK_OFFICER",),
        },
    )


def test_valid_scope_passes_with_independent_role_quorums():
    result = evaluate_scope(engine(), request(), decision(), "1000.00")
    assert result.allowed
    assert result.reason == "within_authority_scope"
    assert result.scope_id == "scope:treasury"
    assert Decimal(result.amount) == Decimal("1250.00")


def test_transaction_and_period_limits_fail_closed():
    assert evaluate_scope(engine(), request(amount="10000.01"), decision(), "0").reason == "transaction_limit_exceeded"
    assert evaluate_scope(engine(), request(amount="1000"), decision(), "49500").reason == "period_limit_exceeded"


def test_currency_organization_account_and_counterparty_are_bounded():
    for change, reason in (
        ({"currency": "BTC"}, "currency_not_permitted"),
        ({"organization_id": "org:other"}, "organization_id_not_permitted"),
        ({"account_id": "account:other"}, "account_id_not_permitted"),
        ({"counterparty_id": "vendor:unknown"}, "counterparty_id_not_permitted"),
    ):
        result = evaluate_scope(
            engine(), request(**change), decision(), "0",
            currency=change.get("currency", "USD"),
        )
        assert not result.allowed and result.reason == reason


def test_initiator_and_approver_roles_are_independent():
    no_finance = decision(approval_identity_ids=("user:risk",))
    result = evaluate_scope(engine(), request(), no_finance, "0")
    assert result.reason == "approval_role_quorum_not_met:FINANCE_DIRECTOR"
    self_approval = decision(approval_identity_ids=("user:treasurer", "user:finance", "user:risk"))
    assert evaluate_scope(engine(), request(), self_approval, "0").reason == "initiator_cannot_approve"


def test_untrusted_or_malformed_amounts_and_missing_fields_fail_closed():
    for amount in ("NaN", "Infinity", "-1", "1.2.3", 100):
        result = evaluate_scope(engine(), request(amount=amount), decision(), "0")
        assert not result.allowed
    assert not evaluate_scope(engine(), request(), decision(), "NaN").allowed
    payload = request().event["payload"].copy()
    del payload["period_key"]
    broken = replace(request(), event={**request().event, "payload": payload})
    assert not evaluate_scope(engine(), broken, decision(), "0").allowed


def test_missing_scope_and_denied_authorization_never_pass():
    missing = AuthorityScopeEngine([scope(action="TOKEN_MINT")], {})
    assert evaluate_scope(missing, request(), decision(), "0").reason == "no_matching_authority_scope"
    denied = decision(allowed=False)
    assert evaluate_scope(missing, request(), denied, "0").reason == "authorization_not_allowed"


def test_scope_configuration_rejects_ambiguous_limits_and_duplicate_roles():
    with pytest.raises(ValueError):
        AuthorityScopeEngine([scope(max_per_transaction="0")], {})
    with pytest.raises(ValueError):
        AuthorityScopeEngine([scope(approval_roles=(
            ScopeRoleRequirement("RISK", 1), ScopeRoleRequirement("RISK", 2)))], {})


def test_one_identity_cannot_fill_two_distinct_control_roles():
    engine_with_shared_identity = AuthorityScopeEngine(
        [scope()],
        {
            "user:treasurer": ("TREASURER",),
            "user:dual": ("FINANCE_DIRECTOR", "RISK_OFFICER"),
        },
    )
    result = evaluate_scope(engine_with_shared_identity,
        request(), decision(approval_identity_ids=("user:dual",)), "0"
    )
    assert result.reason == "approval_role_quorum_not_met:RISK_OFFICER"


def test_equal_specificity_matching_scopes_are_rejected_as_ambiguous():
    first = scope(scope_id="scope:a")
    second = scope(scope_id="scope:b")
    result = evaluate_scope(AuthorityScopeEngine([first, second], {
        "user:treasurer": ("TREASURER",),
        "user:finance": ("FINANCE_DIRECTOR",),
        "user:risk": ("RISK_OFFICER",),
    }), request(), decision(), "0")
    assert result.reason == "ambiguous_authority_scope"


def test_decision_must_be_bound_to_the_exact_signed_request():
    assert evaluate_scope(engine(),
        request(), decision(request_id="req:other"), "0"
    ).reason == "authorization decision request_id does not match signed request"
    assert evaluate_scope(engine(),
        request(), decision(requester_identity_id="user:other"), "0"
    ).reason == "authorization decision requester does not match signed request"


def test_scope_period_key_is_derived_from_trusted_execution_time():
    day_engine = AuthorityScopeEngine([scope(period_window="DAY")], {
        "user:treasurer": ("TREASURER",),
        "user:finance": ("FINANCE_DIRECTOR",),
        "user:risk": ("RISK_OFFICER",),
    })
    # Payload claims yesterday, but the trusted execution clock is today.
    assert evaluate_scope(
        day_engine, request(period_key="2026-11-05"), decision(), "0",
        period_at="2026-11-06T10:02:00+00:00", period_key="2026-11-05",
    ).reason == "period_key does not match authoritative execution period"
    assert evaluate_scope(
        day_engine, request(period_key="2026-11-06"), decision(), "0",
        period_at="2026-11-06T10:02:00+00:00", period_key="2026-11-06",
    ).allowed


def test_scope_requires_period_usage_for_exact_authoritative_key_and_currency():
    assert evaluate_scope(
        engine(), request(), decision(), "0", period_key="2026-10"
    ).reason == "period_key does not match authoritative execution period"
    assert evaluate_scope(
        engine(), request(), decision(), "0", currency="EUR"
    ).reason == "committed period currency does not match request currency"


def test_scope_rejects_decision_reused_for_same_request_id_but_different_action():
    result = evaluate_scope(engine(), request(), decision(action="TOKEN_MINT"), "0")
    assert result.reason == "authorization decision is not bound to this signed event and exact action/resource"


def test_sqlite_scope_reservations_prevent_two_requests_spending_same_headroom(tmp_path):
    configured = scope(max_per_transaction="100", period_limit="100")
    scoped_engine = AuthorityScopeEngine(
        [configured],
        {
            "user:treasurer": ("TREASURER",),
            "user:finance": ("FINANCE_DIRECTOR",),
            "user:risk": ("RISK_OFFICER",),
        },
    )
    path = str(tmp_path / "scope-reservations.db")
    AuthorizedActionExecutor(path)

    first_request = request(amount="15", request_id="req:reserve-1")
    first_decision = decision(request_id="req:reserve-1")
    first_evaluation = evaluate_scope(scoped_engine, first_request, first_decision, "80")
    assert first_evaluation.allowed

    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN IMMEDIATE")
        assert scoped_engine.reserve_in_transaction(
            db, first_evaluation, "80", "signed-event:reserve-1"
        )
        db.commit()

    second_request = request(amount="15", request_id="req:reserve-2")
    second_request = replace(
        second_request,
        event={**second_request.event, "event_id": "evt:reserve-2"},
    )
    second_decision = decision(
        request_id="req:reserve-2", request_event_id="evt:reserve-2"
    )
    second_evaluation = evaluate_scope(scoped_engine, second_request, second_decision, "80")
    assert second_evaluation.allowed  # Stateless check alone sees 80 + 15 <= 100.

    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError, match="including_active_reservations"):
            scoped_engine.reserve_in_transaction(
                db, second_evaluation, "80", "signed-event:reserve-2"
            )
        db.rollback()

    with sqlite3.connect(path) as db:
        rows = db.execute(
            "SELECT request_id,event_type,amount FROM authority_scope_reservation_events ORDER BY rowid"
        ).fetchall()
        assert rows == [("req:reserve-1", "RESERVED", "15")]


def test_scope_reservation_release_is_append_only_and_reuses_only_settled_headroom(tmp_path):
    configured = scope(max_per_transaction="100", period_limit="100")
    scoped_engine = AuthorityScopeEngine(
        [configured],
        {
            "user:treasurer": ("TREASURER",),
            "user:finance": ("FINANCE_DIRECTOR",),
            "user:risk": ("RISK_OFFICER",),
        },
    )
    path = str(tmp_path / "scope-release.db")
    AuthorizedActionExecutor(path)
    first = evaluate_scope(
        scoped_engine, request(amount="15", request_id="req:release-1"),
        decision(request_id="req:release-1"), "80",
    )
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN IMMEDIATE")
        scoped_engine.reserve_in_transaction(db, first, "80", "signed-event:1")
        db.execute("""CREATE TABLE settlement_records (
            settlement_ref TEXT PRIMARY KEY, request_id TEXT NOT NULL,
            scope_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
            currency TEXT NOT NULL, amount TEXT NOT NULL
        )""")
        db.execute(
            "INSERT INTO settlement_records VALUES(?,?,?,?,?,?)",
            ("bank:settlement-1", "req:release-1", configured.scope_id,
             configured.tenant_id, "USD", "15"),
        )

        def verify_settlement(connection, request_id, settlement_ref,
                              scope_id, tenant_id, currency, amount):
            row = connection.execute(
                "SELECT request_id,scope_id,tenant_id,currency,amount "
                "FROM settlement_records WHERE settlement_ref=?",
                (settlement_ref,),
            ).fetchone()
            return row is not None and (
                row[0] == request_id and row[1] == scope_id
                and row[2] == tenant_id and row[3] == currency
                and Decimal(row[4]) == Decimal(amount)
            )

        with pytest.raises(ValueError, match="settlement_verifier"):
            scoped_engine.release_in_transaction(
                db, "req:release-1", "bank:settlement-1"
            )
        scoped_engine.release_in_transaction(
            db, "req:release-1", "bank:settlement-1",
            settlement_verifier=verify_settlement,
        )
        db.commit()

    next_evaluation = evaluate_scope(
        scoped_engine, request(amount="5", request_id="req:release-2"),
        decision(request_id="req:release-2"), "95",
    )
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN IMMEDIATE")
        assert scoped_engine.reserve_in_transaction(
            db, next_evaluation, "95", "signed-event:2"
        )
        db.commit()
    with sqlite3.connect(path) as db:
        events = db.execute(
            "SELECT event_type FROM authority_scope_reservation_events "
            "WHERE request_id='req:release-1' ORDER BY rowid"
        ).fetchall()
        assert events == [("RESERVED",), ("RELEASED",)]
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute(
                "UPDATE authority_scope_reservation_events SET amount='0' "
                "WHERE request_id='req:release-1'"
            )
