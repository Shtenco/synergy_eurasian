"""Stateful cell-level credit and liquidity authorization kernel.

V6.6.3-A: deterministic financial control layer. It is deliberately separate
from the physical simulator until its credit and cash invariants pass tests.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .network_topology import CELLS, CELL_BY_ID, REGIONS

EPS = 1e-9

# Synthetic commercial parameters; not observed EAEU prices or cost benchmarks.
TRANSFER_PRICE = {"grain": 2.0, "oilseed": 2.5, "flour": 4.0, "oil": 5.0, "energy": 0.8}
EXTERNAL_SALE_PRICE = {"bread": 10.0, "packed_food": 15.0}
# Conversion overhead paid to external suppliers before production authorization.
EXTERNAL_PRODUCTION_COST = {
    "grain": 0.8, "oilseed": 0.9, "energy": 0.5, "flour": 2.0,
    "oil": 2.5, "bread": 3.2, "packed_food": 4.0,
}


@dataclass
class CellAccount:
    cash: float
    bank_limit: float
    bank_debt: float = 0.0
    trade_credit_limit: float = 0.0
    trade_receivable_limit: float | None = None
    trade_payable: float = 0.0
    trade_receivable: float = 0.0
    customer_receivable: float = 0.0
    customer_receivable_limit: float | None = None
    regional_credit_balance: float = 0.0
    defaulted: bool = False


@dataclass
class PayableInvoice:
    invoice_id: str
    buyer: str
    seller: str | None
    amount: float
    remaining: float
    due_day: int
    issued_day: int
    status: str = "open"
    guarantee_paid: float = 0.0
    member_assessment_paid: float = 0.0
    written_off: float = 0.0


@dataclass
class CustomerInvoice:
    invoice_id: str
    seller: str
    amount: float
    remaining: float
    due_day: int
    issued_day: int
    status: str = "open"
    collection_attempted: bool = False


class CreditLedger:
    """Cash-safe mutual-credit ledger with explicit buyer limits and bank lines."""

    def __init__(
        self,
        initial_cash_per_cell: float = 200.0,
        bank_limit_per_cell: float = 0.0,
        trade_credit_limit_per_cell: float = 100.0,
        trade_receivable_limit_per_cell: float | None = None,
        customer_receivable_limit_per_cell: float | None = None,
        customer_recovery_rate: float = 1.0,
        customer_grace_days: int = 0,
        regional_pool_limit_per_region: float | None = None,
        regional_pool_reserve_per_region: float = 0.0,
        regional_reserve_contributions_by_cell: dict[str, float] | None = None,
        regional_assessment_rate: float = 0.0,
        regional_assessment_limit_per_cell: float | None = None,
        regional_member_debit_limit_per_cell: float | None = None,
        regional_member_credit_limit_per_cell: float | None = None,
        grace_days: int = 2,
    ) -> None:
        limits = (initial_cash_per_cell, bank_limit_per_cell, trade_credit_limit_per_cell)
        if any(not math.isfinite(float(x)) or float(x) < 0 for x in limits):
            raise ValueError("cash and credit limits must be finite and >= 0")
        if trade_receivable_limit_per_cell is not None and (
            not math.isfinite(float(trade_receivable_limit_per_cell)) or trade_receivable_limit_per_cell < 0
        ):
            raise ValueError("trade receivable limit must be finite and >= 0")
        if customer_receivable_limit_per_cell is not None and (
            not math.isfinite(float(customer_receivable_limit_per_cell)) or customer_receivable_limit_per_cell < 0
        ):
            raise ValueError("customer receivable limit must be finite and >= 0")
        if not math.isfinite(float(customer_recovery_rate)) or not 0.0 <= customer_recovery_rate <= 1.0:
            raise ValueError("customer_recovery_rate must be between 0 and 1")
        if not isinstance(customer_grace_days, int) or isinstance(customer_grace_days, bool) or customer_grace_days < 0:
            raise ValueError("customer_grace_days must be a non-negative integer")
        regional_limits = (
            regional_pool_limit_per_region,
            regional_member_debit_limit_per_cell,
            regional_member_credit_limit_per_cell,
        )
        if any(x is not None and (not math.isfinite(float(x)) or x < 0) for x in regional_limits):
            raise ValueError("regional pool and member limits must be finite and >= 0")
        if not math.isfinite(float(regional_pool_reserve_per_region)) or regional_pool_reserve_per_region < 0:
            raise ValueError("regional_pool_reserve_per_region must be finite and >= 0")
        if not math.isfinite(float(regional_assessment_rate)) or not 0.0 <= regional_assessment_rate <= 1.0:
            raise ValueError("regional_assessment_rate must be between 0 and 1")
        if regional_assessment_limit_per_cell is not None and (
            isinstance(regional_assessment_limit_per_cell, bool)
            or not math.isfinite(float(regional_assessment_limit_per_cell))
            or regional_assessment_limit_per_cell < 0
        ):
            raise ValueError("regional_assessment_limit_per_cell must be finite and >= 0")
        cells_per_region = {r: sum(c.region == r for c in CELLS) for r in REGIONS}
        if regional_reserve_contributions_by_cell is None:
            reserve_contributions = {
                cell.cell_id: float(regional_pool_reserve_per_region) / cells_per_region[cell.region]
                for cell in CELLS
            }
        else:
            if set(regional_reserve_contributions_by_cell) != set(CELL_BY_ID):
                raise ValueError("reserve contribution map must contain every known cell exactly once")
            reserve_contributions = {}
            for cell_id, contribution in regional_reserve_contributions_by_cell.items():
                if isinstance(contribution, bool) or not isinstance(contribution, (int, float)):
                    raise ValueError("reserve contributions must be finite non-negative numbers")
                if not math.isfinite(float(contribution)) or contribution < 0:
                    raise ValueError("reserve contributions must be finite non-negative numbers")
                if contribution > float(initial_cash_per_cell) + EPS:
                    raise ValueError("a member contribution cannot exceed its initial cash")
                reserve_contributions[cell_id] = float(contribution)
            for region in REGIONS:
                contributed = sum(
                    reserve_contributions[cell.cell_id]
                    for cell in CELLS if cell.region == region
                )
                if abs(contributed - float(regional_pool_reserve_per_region)) > EPS:
                    raise ValueError(
                        f"regional contributions for {region} must sum to regional_pool_reserve_per_region"
                    )
        if any(contribution > float(initial_cash_per_cell) + EPS for contribution in reserve_contributions.values()):
            raise ValueError("a member contribution cannot exceed its initial cash")
        if grace_days < 0:
            raise ValueError("grace_days must be >= 0")
        self.accounts = {
            c.cell_id: CellAccount(
                cash=float(initial_cash_per_cell) - reserve_contributions[c.cell_id],
                bank_limit=float(bank_limit_per_cell),
                trade_credit_limit=float(trade_credit_limit_per_cell),
                trade_receivable_limit=(
                    float(trade_receivable_limit_per_cell)
                    if trade_receivable_limit_per_cell is not None else None
                ),
                customer_receivable_limit=(
                    float(customer_receivable_limit_per_cell)
                    if customer_receivable_limit_per_cell is not None else None
                ),
            )
            for c in CELLS
        }
        self.payables: dict[str, PayableInvoice] = {}
        self.customer_invoices: dict[str, CustomerInvoice] = {}
        self.grace_days = int(grace_days)
        self.customer_recovery_rate = float(customer_recovery_rate)
        self.customer_grace_days = int(customer_grace_days)
        self.customer_bad_debt = 0.0
        self.regional_pool_limit_per_region = (
            float(regional_pool_limit_per_region)
            if regional_pool_limit_per_region is not None else None
        )
        self.regional_member_debit_limit_per_cell = (
            float(regional_member_debit_limit_per_cell)
            if regional_member_debit_limit_per_cell is not None else None
        )
        self.regional_member_credit_limit_per_cell = (
            float(regional_member_credit_limit_per_cell)
            if regional_member_credit_limit_per_cell is not None else None
        )
        self.regional_reserve_contributions_by_cell = dict(reserve_contributions)
        self.regional_assessment_rate = float(regional_assessment_rate)
        self.regional_assessment_limit_per_cell = (
            float(regional_assessment_limit_per_cell)
            if regional_assessment_limit_per_cell is not None else None
        )
        self.regional_assessment_paid_by_region = {r: 0.0 for r in REGIONS}
        self.regional_assessment_contributed_by_cell = {cell.cell_id: 0.0 for cell in CELLS}
        self.regional_pool_reserve_initial_by_region = {
            r: float(regional_pool_reserve_per_region) for r in REGIONS
        }
        self.regional_pool_reserve_by_region = dict(self.regional_pool_reserve_initial_by_region)
        self.regional_pool_guarantee_paid_by_region = {r: 0.0 for r in REGIONS}
        self.trade_bad_debt_by_cell = {c.cell_id: 0.0 for c in CELLS}
        self.external_supplier_bad_debt = 0.0
        self.current_day = -1
        self.opening_cash = float(initial_cash_per_cell) * len(CELLS)
        self.bank_draws = 0.0
        self.customer_collections = 0.0
        self.external_supplier_payments = 0.0
        self.bank_repayments = 0.0
        self.internal_transfer_in = 0.0
        self.internal_transfer_out = 0.0
        self.events: list[dict[str, Any]] = []

    def _cell(self, cell_id: str) -> CellAccount:
        if cell_id not in self.accounts:
            raise ValueError(f"unknown cell: {cell_id}")
        return self.accounts[cell_id]

    def _day(self, day: int) -> None:
        if not isinstance(day, int) or isinstance(day, bool) or day < self.current_day:
            raise ValueError("days must be integers and non-decreasing")
        if day > self.current_day:
            self.process_day(day)

    def _fund(self, cell_id: str, amount: float, day: int) -> tuple[bool, float]:
        account = self._cell(cell_id)
        if amount < -EPS:
            raise ValueError("amount must be >= 0")
        need = max(0.0, amount - account.cash)
        available_line = max(0.0, account.bank_limit - account.bank_debt)
        if need > available_line + EPS:
            return False, 0.0
        draw = min(need, available_line)
        account.bank_debt += draw
        account.cash += draw
        self.bank_draws += draw
        if draw > EPS:
            self.events.append({"day": day, "type": "bank_draw", "cell_id": cell_id, "amount": draw})
        return True, draw

    def authorize_production(self, cell_id: str, variable_cost: float, day: int) -> dict[str, Any]:
        """Charge the modeled external variable cost before authorizing output."""
        account = self._cell(cell_id)
        if not math.isfinite(float(variable_cost)) or variable_cost < 0:
            raise ValueError("variable_cost must be finite and >= 0")
        self._day(day)
        if account.defaulted:
            return {"authorized": False, "reason": "cell_defaulted", "bank_draw": 0.0}
        ok, draw = self._fund(cell_id, float(variable_cost), day)
        if not ok:
            self.events.append({"day": day, "type": "production_rejected", "cell_id": cell_id, "cost": variable_cost, "reason": "insufficient_liquidity"})
            return {"authorized": False, "reason": "insufficient_liquidity", "bank_draw": 0.0}
        account.cash -= float(variable_cost)
        self.external_supplier_payments += float(variable_cost)
        self.events.append({"day": day, "type": "production_cost_paid", "cell_id": cell_id, "amount": float(variable_cost)})
        return {"authorized": True, "reason": None, "bank_draw": draw}

    def repay_bank_credit(self, cell_id: str, amount: float, day: int) -> dict[str, Any]:
        """Repay drawn bank credit from available cash without creating overdraft."""
        account = self._cell(cell_id)
        if not math.isfinite(float(amount)) or amount <= 0:
            raise ValueError("repayment amount must be finite and > 0")
        self._day(day)
        if amount > account.cash + EPS:
            return {"repaid": False, "reason": "insufficient_cash", "amount": 0.0}
        if amount > account.bank_debt + EPS:
            return {"repaid": False, "reason": "repayment_exceeds_bank_debt", "amount": 0.0}
        account.cash -= float(amount)
        account.bank_debt -= float(amount)
        self.bank_repayments += float(amount)
        self.events.append({"day": day, "type": "bank_repayment", "cell_id": cell_id, "amount": float(amount)})
        return {"repaid": True, "reason": None, "amount": float(amount)}

    def _regional_pool_outstanding(self, region: str) -> float:
        return sum(
            max(0.0, -account.regional_credit_balance)
            for cell_id, account in self.accounts.items()
            if CELL_BY_ID[cell_id].region == region
        )

    def authorize_purchase(
        self,
        buyer: str,
        seller: str | None,
        amount: float,
        due_day: int,
        day: int,
        invoice_id: str,
    ) -> dict[str, Any]:
        """Authorize cash, bilateral trade credit, regional pool credit, or bank-funded procurement."""
        account = self._cell(buyer)
        if seller is not None:
            self._cell(seller)
            if seller == buyer:
                raise ValueError("buyer and seller must differ for internal trade")
        if not isinstance(day, int) or isinstance(day, bool) or not math.isfinite(float(amount)) or amount <= 0 or not isinstance(due_day, int) or isinstance(due_day, bool) or due_day < day:
            raise ValueError("day and due_day must be integers; amount must be finite and > 0; due_day must be >= issue day")
        if not invoice_id or invoice_id in self.payables or invoice_id in self.customer_invoices:
            raise ValueError("invoice_id must be non-empty and unique")
        self._day(day)
        if account.defaulted:
            return {"authorized": False, "reason": "buyer_defaulted"}
        if seller is not None and self.accounts[seller].defaulted:
            return {"authorized": False, "reason": "seller_defaulted"}

        cash_part = min(account.cash, float(amount))
        credit_part = float(amount) - cash_part
        available_trade = max(0.0, account.trade_credit_limit - account.trade_payable)
        credit_reason = None
        same_region = seller is not None and CELL_BY_ID[buyer].region == CELL_BY_ID[seller].region
        seller_account = self.accounts[seller] if seller is not None else None

        if credit_part > available_trade + EPS:
            credit_reason = "buyer_trade_credit_limit"
        elif seller_account is not None and credit_part > EPS:
            exposure_limit = seller_account.trade_receivable_limit
            if exposure_limit is not None and seller_account.trade_receivable + credit_part > exposure_limit + EPS:
                credit_reason = "seller_exposure_limit"

        new_buyer_balance = account.regional_credit_balance
        new_seller_balance = seller_account.regional_credit_balance if seller_account is not None else 0.0
        if credit_reason is None and same_region and credit_part > EPS:
            new_buyer_balance -= credit_part
            new_seller_balance += credit_part
            debit_limit = self.regional_member_debit_limit_per_cell
            credit_limit = self.regional_member_credit_limit_per_cell
            if debit_limit is not None and max(0.0, -new_buyer_balance) > debit_limit + EPS:
                credit_reason = "regional_member_debit_limit"
            elif credit_limit is not None and max(0.0, new_seller_balance) > credit_limit + EPS:
                credit_reason = "regional_member_credit_limit"
            else:
                pool_limit = self.regional_pool_limit_per_region
                if pool_limit is not None:
                    current = self._regional_pool_outstanding(CELL_BY_ID[buyer].region)
                    revised = (
                        current
                        - max(0.0, -account.regional_credit_balance)
                        - max(0.0, -seller_account.regional_credit_balance)
                        + max(0.0, -new_buyer_balance)
                        + max(0.0, -new_seller_balance)
                    )
                    if revised > pool_limit + EPS:
                        credit_reason = "regional_pool_limit"

        bank_draw = 0.0
        funding_mode = "cash"
        if credit_reason is not None:
            # A bank line can replace the entire unsecured credit portion with immediate payment.
            required_draw = max(0.0, float(amount) - account.cash)
            available_bank = max(0.0, account.bank_limit - account.bank_debt)
            if required_draw > available_bank + EPS:
                self.events.append({"day": day, "type": "purchase_rejected", "buyer": buyer, "seller": seller, "amount": float(amount), "reason": credit_reason})
                return {"authorized": False, "reason": credit_reason}
            ok, bank_draw = self._fund(buyer, float(amount), day)
            if not ok:
                raise RuntimeError("bank funding pre-check and draw disagreed")
            account.cash -= float(amount)
            funding_mode = "bank_funded_cash"
            cash_part = float(amount)
            credit_part = 0.0
        else:
            # Cash is paid immediately; only the uncovered remainder is carried as credit.
            if cash_part > EPS:
                account.cash -= cash_part
            funding_mode = "cash_and_trade_credit" if credit_part > EPS else "cash"

        invoice = PayableInvoice(
            invoice_id, buyer, seller, float(amount), credit_part,
            int(due_day), int(day), "paid" if credit_part <= EPS else "open",
        )
        self.payables[invoice_id] = invoice

        if cash_part > EPS:
            if seller is None:
                self.external_supplier_payments += cash_part
            else:
                seller_account.cash += cash_part
                self.internal_transfer_out += cash_part
                self.internal_transfer_in += cash_part
            self.events.append({
                "day": day, "type": "purchase_cash_settled", "invoice_id": invoice_id,
                "buyer": buyer, "seller": seller, "amount": cash_part,
            })

        if credit_part > EPS:
            account.trade_payable += credit_part
            if seller is not None:
                seller_account.trade_receivable += credit_part
                if same_region:
                    account.regional_credit_balance = new_buyer_balance
                    seller_account.regional_credit_balance = new_seller_balance

        self.events.append({
            "day": day, "type": "purchase_authorized", "invoice_id": invoice_id,
            "buyer": buyer, "seller": seller, "amount": float(amount),
            "cash_paid": cash_part, "trade_credit_extended": credit_part,
            "bank_draw": bank_draw, "funding_mode": funding_mode, "due_day": int(due_day),
        })
        return {
            "authorized": True, "reason": None, "invoice_id": invoice_id,
            "cash_paid": cash_part, "trade_credit_extended": credit_part,
            "bank_draw": bank_draw, "funding_mode": funding_mode,
            "regional_pool_credit": credit_part if same_region and funding_mode != "bank_funded_cash" else 0.0,
        }

    def issue_customer_invoice(
        self, seller: str, amount: float, due_day: int, day: int, invoice_id: str
    ) -> dict[str, Any]:
        self._cell(seller)
        if not isinstance(day, int) or isinstance(day, bool) or not math.isfinite(float(amount)) or amount <= 0 or not isinstance(due_day, int) or isinstance(due_day, bool) or due_day < day:
            raise ValueError("day and due_day must be integers; amount must be finite and > 0; due_day must be >= issue day")
        if not invoice_id or invoice_id in self.payables or invoice_id in self.customer_invoices:
            raise ValueError("invoice_id must be non-empty and unique")
        self._day(day)
        account = self.accounts[seller]
        if account.defaulted:
            return {"authorized": False, "reason": "seller_defaulted"}
        exposure_limit = account.customer_receivable_limit
        if exposure_limit is not None and account.customer_receivable + amount > exposure_limit + EPS:
            self.events.append({"day": day, "type": "customer_invoice_rejected", "seller": seller, "amount": float(amount), "reason": "customer_exposure_limit"})
            return {"authorized": False, "reason": "customer_exposure_limit"}
        self.customer_invoices[invoice_id] = CustomerInvoice(
            invoice_id, seller, float(amount), float(amount), int(due_day), int(day)
        )
        account.customer_receivable += float(amount)
        self.events.append({"day": day, "type": "customer_invoice_issued", "invoice_id": invoice_id, "seller": seller, "amount": float(amount), "due_day": int(due_day)})
        return {"authorized": True, "reason": None, "invoice_id": invoice_id}

    def _assess_regional_members(
        self,
        region: str,
        buyer_id: str,
        seller_id: str,
        amount: float,
        day: int,
        invoice_id: str,
    ) -> float:
        """Collect a capped, cash-funded pro-rata assessment from other solvent members."""
        if amount <= EPS or self.regional_assessment_rate <= EPS:
            return 0.0
        capacities: dict[str, float] = {}
        for cell in CELLS:
            if cell.region != region or cell.cell_id in {buyer_id, seller_id}:
                continue
            account = self.accounts[cell.cell_id]
            if account.defaulted:
                continue
            capacity = account.cash * self.regional_assessment_rate
            if self.regional_assessment_limit_per_cell is not None:
                capacity = min(capacity, self.regional_assessment_limit_per_cell)
            if capacity > EPS:
                capacities[cell.cell_id] = capacity
        total_capacity = sum(capacities.values())
        if total_capacity <= EPS:
            self.events.append({
                "day": day, "type": "regional_member_assessment_attempt",
                "invoice_id": invoice_id, "region": region,
                "requested_amount": amount, "eligible_capacity": 0.0,
                "paid_amount": 0.0,
            })
            return 0.0

        target = min(amount, total_capacity)
        paid_total = 0.0
        remaining_target = target
        ordered = sorted(capacities)
        for index, cell_id in enumerate(ordered):
            capacity = capacities[cell_id]
            if index == len(ordered) - 1:
                payment = min(capacity, remaining_target)
            else:
                payment = min(capacity, target * capacity / total_capacity)
            if payment <= EPS:
                continue
            self.accounts[cell_id].cash -= payment
            self.accounts[seller_id].cash += payment
            self.regional_assessment_contributed_by_cell[cell_id] += payment
            self.regional_assessment_paid_by_region[region] += payment
            paid_total += payment
            remaining_target -= payment
            self.events.append({
                "day": day, "type": "regional_member_assessment_paid",
                "invoice_id": invoice_id, "region": region,
                "contributor": cell_id, "seller": seller_id,
                "amount": payment,
            })
        self.events.append({
            "day": day, "type": "regional_member_assessment_attempt",
            "invoice_id": invoice_id, "region": region,
            "requested_amount": amount, "eligible_capacity": total_capacity,
            "paid_amount": paid_total,
        })
        return paid_total

    def _resolve_payable_default(self, invoice: PayableInvoice, day: int) -> None:
        """Resolve a matured default: use local reserve first, then write off residual."""
        buyer = self.accounts[invoice.buyer]
        remaining = invoice.remaining
        if remaining <= EPS:
            invoice.remaining = 0.0
            invoice.status = "defaulted"
            buyer.defaulted = True
            return

        guarantee = 0.0
        seller = self.accounts[invoice.seller] if invoice.seller is not None else None
        same_region = (
            invoice.seller is not None
            and CELL_BY_ID[invoice.buyer].region == CELL_BY_ID[invoice.seller].region
        )
        if same_region:
            region = CELL_BY_ID[invoice.buyer].region
            guarantee = min(remaining, self.regional_pool_reserve_by_region[region])
            if guarantee > EPS:
                self.regional_pool_reserve_by_region[region] -= guarantee
                self.regional_pool_guarantee_paid_by_region[region] += guarantee
                seller.cash += guarantee
                self.events.append({
                    "day": day, "type": "regional_pool_guarantee_paid",
                    "invoice_id": invoice.invoice_id, "region": region,
                    "seller": invoice.seller, "amount": guarantee,
                })

        uncovered = max(0.0, remaining - guarantee)
        assessment_paid = 0.0
        if same_region and seller is not None and uncovered > EPS:
            assessment_paid = self._assess_regional_members(
                CELL_BY_ID[invoice.buyer].region,
                invoice.buyer,
                invoice.seller,
                uncovered,
                day,
                invoice.invoice_id,
            )
        residual_loss = max(0.0, uncovered - assessment_paid)

        buyer.trade_payable -= remaining
        if seller is not None:
            seller.trade_receivable -= remaining
            if same_region:
                buyer.regional_credit_balance += remaining
                seller.regional_credit_balance -= remaining
            self.trade_bad_debt_by_cell[invoice.seller] += residual_loss
        else:
            self.external_supplier_bad_debt += residual_loss

        invoice.guarantee_paid += guarantee
        invoice.member_assessment_paid += assessment_paid
        invoice.written_off += residual_loss
        invoice.remaining = 0.0
        invoice.status = "defaulted"
        buyer.defaulted = True
        self.events.append({
            "day": day, "type": "default_resolution",
            "cell_id": invoice.buyer, "invoice_id": invoice.invoice_id,
            "remaining_before_resolution": remaining,
            "guarantee_paid": guarantee,
            "member_assessment_paid": assessment_paid,
            "written_off": residual_loss,
        })

    def _resolve_buyer_default(self, buyer_id: str, day: int) -> None:
        """Apply cross-default to all open payables of the failed buyer."""
        self.accounts[buyer_id].defaulted = True
        for invoice in sorted(self.payables.values(), key=lambda x: (x.due_day, x.invoice_id)):
            if invoice.buyer == buyer_id and invoice.remaining > EPS and invoice.status != "defaulted":
                self._resolve_payable_default(invoice, day)

    def process_day(self, day: int) -> None:
        """Collect customer invoices first, then settle payables in stable ID order."""
        if not isinstance(day, int) or isinstance(day, bool) or day < self.current_day:
            raise ValueError("days must be integers and non-decreasing")
        self.current_day = day
        for invoice in sorted(self.customer_invoices.values(), key=lambda x: (x.due_day, x.invoice_id)):
            if invoice.remaining > EPS and invoice.due_day <= day and not invoice.collection_attempted:
                amount = invoice.remaining * self.customer_recovery_rate
                invoice.collection_attempted = True
                if amount > EPS:
                    self.accounts[invoice.seller].cash += amount
                    self.accounts[invoice.seller].customer_receivable -= amount
                    invoice.remaining -= amount
                    self.customer_collections += amount
                    self.events.append({"day": day, "type": "customer_collection", "invoice_id": invoice.invoice_id, "seller": invoice.seller, "amount": amount, "remaining": invoice.remaining})
                if invoice.remaining <= EPS:
                    invoice.remaining = 0.0
                    invoice.status = "paid"
                else:
                    invoice.status = "partial"
            if invoice.remaining > EPS and day > invoice.due_day:
                invoice.status = "overdue"
            if invoice.remaining > EPS and day >= invoice.due_day + self.customer_grace_days:
                bad_debt = invoice.remaining
                self.accounts[invoice.seller].customer_receivable -= bad_debt
                self.customer_bad_debt += bad_debt
                invoice.remaining = 0.0
                invoice.status = "defaulted"
                self.events.append({"day": day, "type": "customer_default", "invoice_id": invoice.invoice_id, "seller": invoice.seller, "bad_debt": bad_debt})

        for invoice in sorted(self.payables.values(), key=lambda x: (x.due_day, x.invoice_id)):
            if invoice.remaining <= EPS or invoice.due_day > day or invoice.status == "defaulted":
                continue
            account = self.accounts[invoice.buyer]
            if account.defaulted:
                continue
            available_liquidity = account.cash + max(0.0, account.bank_limit - account.bank_debt)
            amount = min(invoice.remaining, available_liquidity)
            draw = 0.0
            if amount > EPS:
                ok, draw = self._fund(invoice.buyer, amount, day)
                if not ok:
                    raise RuntimeError("partial settlement liquidity pre-check and draw disagreed")
                account.cash -= amount
                account.trade_payable -= amount
                invoice.remaining -= amount
                if invoice.seller is None:
                    self.external_supplier_payments += amount
                else:
                    seller = self.accounts[invoice.seller]
                    seller.cash += amount
                    seller.trade_receivable -= amount
                    if CELL_BY_ID[invoice.buyer].region == CELL_BY_ID[invoice.seller].region:
                        account.regional_credit_balance += amount
                        seller.regional_credit_balance -= amount
                    self.internal_transfer_out += amount
                    self.internal_transfer_in += amount
                if invoice.remaining <= EPS:
                    invoice.remaining = 0.0
                    invoice.status = "paid"
                else:
                    invoice.status = "overdue" if day > invoice.due_day else "partial"
                self.events.append({"day": day, "type": "payable_partial_or_full_settlement", "invoice_id": invoice.invoice_id, "buyer": invoice.buyer, "seller": invoice.seller, "amount": amount, "remaining": invoice.remaining, "bank_draw": draw})
            if invoice.remaining > EPS and day > invoice.due_day:
                invoice.status = "overdue"
            if invoice.remaining > EPS and day >= invoice.due_day + self.grace_days:
                self._resolve_buyer_default(invoice.buyer, day)

    def snapshot(self) -> dict[str, Any]:
        cash = {cell: account.cash for cell, account in self.accounts.items()}
        bank_debt = {cell: account.bank_debt for cell, account in self.accounts.items()}
        expected_cash = self.opening_cash + self.bank_draws + self.customer_collections - self.external_supplier_payments - self.bank_repayments
        return {
            "model_id": "SYNERGY_V6.6.4C_REGIONAL_GUARANTEE_CREDIT_LEDGER",
            "current_day": self.current_day,
            "cell_count": len(self.accounts),
            "cash_by_cell": cash,
            "bank_debt_by_cell": bank_debt,
            "trade_payable_by_cell": {k: v.trade_payable for k, v in self.accounts.items()},
            "trade_receivable_by_cell": {k: v.trade_receivable for k, v in self.accounts.items()},
            "customer_receivable_by_cell": {k: v.customer_receivable for k, v in self.accounts.items()},
            "customer_receivable_limit_by_cell": {k: v.customer_receivable_limit for k, v in self.accounts.items()},
            "customer_receivable_utilization_by_cell": {
                k: (v.customer_receivable / v.customer_receivable_limit if v.customer_receivable_limit is not None and v.customer_receivable_limit > EPS else 0.0)
                for k, v in self.accounts.items()
            },
            "customer_bad_debt": self.customer_bad_debt,
            "trade_bad_debt_by_cell": dict(self.trade_bad_debt_by_cell),
            "regional_assessment_rate": self.regional_assessment_rate,
            "regional_assessment_limit_per_cell": self.regional_assessment_limit_per_cell,
            "regional_assessment_paid_by_region": dict(self.regional_assessment_paid_by_region),
            "regional_assessment_contributed_by_cell": dict(self.regional_assessment_contributed_by_cell),
            "regional_assessment_attempt_count": sum(
                e["type"] == "regional_member_assessment_attempt" for e in self.events
            ),
            "regional_assessment_requested_by_region": {
                r: sum(
                    e["requested_amount"] for e in self.events
                    if e["type"] == "regional_member_assessment_attempt" and e["region"] == r
                )
                for r in REGIONS
            },
            "regional_assessment_eligible_capacity_by_region": {
                r: sum(
                    e["eligible_capacity"] for e in self.events
                    if e["type"] == "regional_member_assessment_attempt" and e["region"] == r
                )
                for r in REGIONS
            },
            "external_supplier_bad_debt": self.external_supplier_bad_debt,
            "regional_reserve_contributions_by_cell": dict(self.regional_reserve_contributions_by_cell),
            "regional_pool_reserve_initial_by_region": dict(self.regional_pool_reserve_initial_by_region),
            "regional_pool_reserve_by_region": dict(self.regional_pool_reserve_by_region),
            "regional_pool_guarantee_paid_by_region": dict(self.regional_pool_guarantee_paid_by_region),
            "defaulted_cells": sorted(k for k, v in self.accounts.items() if v.defaulted),
            "production_rejection_count": sum(e["type"] == "production_rejected" for e in self.events),
            "purchase_rejection_count": sum(e["type"] == "purchase_rejected" for e in self.events),
            "customer_invoice_rejection_count": sum(e["type"] == "customer_invoice_rejected" for e in self.events),
            "regional_pool_rejection_count": sum(
                e.get("reason") in {"regional_member_debit_limit", "regional_member_credit_limit", "regional_pool_limit"}
                for e in self.events if e["type"] == "purchase_rejected"
            ),
            "default_event_count": sum(e["type"] == "default_resolution" for e in self.events),
            "customer_default_count": sum(e["type"] == "customer_default" for e in self.events),
            "bank_line_utilization_by_cell": {
                k: (v.bank_debt / v.bank_limit if v.bank_limit > EPS else 0.0)
                for k, v in self.accounts.items()
            },
            "trade_credit_utilization_by_cell": {
                k: (v.trade_payable / v.trade_credit_limit if v.trade_credit_limit > EPS else 0.0)
                for k, v in self.accounts.items()
            },
            "trade_receivable_limit_by_cell": {k: v.trade_receivable_limit for k, v in self.accounts.items()},
            "trade_receivable_utilization_by_cell": {
                k: (v.trade_receivable / v.trade_receivable_limit if v.trade_receivable_limit is not None and v.trade_receivable_limit > EPS else 0.0)
                for k, v in self.accounts.items()
            },
            "regional_credit_balance_by_cell": {k: v.regional_credit_balance for k, v in self.accounts.items()},
            "regional_pool_outstanding_by_region": {
                r: self._regional_pool_outstanding(r) for r in REGIONS
            },
            "regional_pool_net_position_by_region": {
                r: sum(v.regional_credit_balance for k, v in self.accounts.items() if CELL_BY_ID[k].region == r)
                for r in REGIONS
            },
            "regional_pool_limit_by_region": {
                r: self.regional_pool_limit_per_region for r in REGIONS
            },
            "regional_pool_utilization_by_region": {
                r: (
                    self._regional_pool_outstanding(r) / self.regional_pool_limit_per_region
                    if self.regional_pool_limit_per_region is not None and self.regional_pool_limit_per_region > EPS
                    else 0.0
                )
                for r in REGIONS
            },
            "regional_member_debit_utilization_by_cell": {
                k: (
                    max(0.0, -v.regional_credit_balance) / self.regional_member_debit_limit_per_cell
                    if self.regional_member_debit_limit_per_cell is not None and self.regional_member_debit_limit_per_cell > EPS
                    else 0.0
                )
                for k, v in self.accounts.items()
            },
            "regional_member_credit_utilization_by_cell": {
                k: (
                    max(0.0, v.regional_credit_balance) / self.regional_member_credit_limit_per_cell
                    if self.regional_member_credit_limit_per_cell is not None and self.regional_member_credit_limit_per_cell > EPS
                    else 0.0
                )
                for k, v in self.accounts.items()
            },
            "open_payables": {k: v.remaining for k, v in self.payables.items() if v.remaining > EPS},
            "bank_draws": self.bank_draws,
            "customer_collections": self.customer_collections,
            "external_supplier_payments": self.external_supplier_payments,
            "bank_repayments": self.bank_repayments,
            "internal_transfer_in": self.internal_transfer_in,
            "internal_transfer_out": self.internal_transfer_out,
            "internal_transfer_net": self.internal_transfer_in - self.internal_transfer_out,
            "cash_conservation_error": sum(cash.values()) + sum(self.regional_pool_reserve_by_region.values()) - expected_cash,
            "events": list(self.events),
        }
