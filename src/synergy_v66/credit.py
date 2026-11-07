"""Stateful cell-level credit and liquidity authorization kernel.

V6.6.3-A: deterministic financial control layer. It is deliberately separate
from the physical simulator until its credit and cash invariants pass tests.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .network import CELLS

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
    trade_payable: float = 0.0
    trade_receivable: float = 0.0
    customer_receivable: float = 0.0
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


@dataclass
class CustomerInvoice:
    invoice_id: str
    seller: str
    amount: float
    remaining: float
    due_day: int
    issued_day: int
    status: str = "open"


class CreditLedger:
    """Cash-safe mutual-credit ledger with explicit buyer limits and bank lines."""

    def __init__(
        self,
        initial_cash_per_cell: float = 200.0,
        bank_limit_per_cell: float = 0.0,
        trade_credit_limit_per_cell: float = 100.0,
        grace_days: int = 2,
    ) -> None:
        limits = (initial_cash_per_cell, bank_limit_per_cell, trade_credit_limit_per_cell)
        if any(not math.isfinite(float(x)) or float(x) < 0 for x in limits):
            raise ValueError("cash and credit limits must be finite and >= 0")
        if grace_days < 0:
            raise ValueError("grace_days must be >= 0")
        self.accounts = {
            c.cell_id: CellAccount(
                cash=float(initial_cash_per_cell),
                bank_limit=float(bank_limit_per_cell),
                trade_credit_limit=float(trade_credit_limit_per_cell),
            )
            for c in CELLS
        }
        self.payables: dict[str, PayableInvoice] = {}
        self.customer_invoices: dict[str, CustomerInvoice] = {}
        self.grace_days = int(grace_days)
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

    def authorize_purchase(
        self,
        buyer: str,
        seller: str | None,
        amount: float,
        due_day: int,
        day: int,
        invoice_id: str,
    ) -> dict[str, Any]:
        """Authorize a purchase only if the buyer has unused trade-credit capacity."""
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
        if account.trade_payable + amount > account.trade_credit_limit + EPS:
            self.events.append({"day": day, "type": "purchase_rejected", "buyer": buyer, "amount": amount, "reason": "trade_credit_limit"})
            return {"authorized": False, "reason": "trade_credit_limit"}
        invoice = PayableInvoice(invoice_id, buyer, seller, float(amount), float(amount), int(due_day), int(day))
        self.payables[invoice_id] = invoice
        account.trade_payable += float(amount)
        if seller is not None:
            self.accounts[seller].trade_receivable += float(amount)
        self.events.append({"day": day, "type": "purchase_authorized", "invoice_id": invoice_id, "buyer": buyer, "seller": seller, "amount": float(amount), "due_day": int(due_day)})
        return {"authorized": True, "reason": None, "invoice_id": invoice_id}

    def issue_customer_invoice(
        self, seller: str, amount: float, due_day: int, day: int, invoice_id: str
    ) -> None:
        self._cell(seller)
        if not isinstance(day, int) or isinstance(day, bool) or not math.isfinite(float(amount)) or amount <= 0 or not isinstance(due_day, int) or isinstance(due_day, bool) or due_day < day:
            raise ValueError("day and due_day must be integers; amount must be finite and > 0; due_day must be >= issue day")
        if not invoice_id or invoice_id in self.payables or invoice_id in self.customer_invoices:
            raise ValueError("invoice_id must be non-empty and unique")
        self._day(day)
        account = self.accounts[seller]
        if account.defaulted:
            raise ValueError("defaulted cell cannot issue new customer invoices")
        self.customer_invoices[invoice_id] = CustomerInvoice(
            invoice_id, seller, float(amount), float(amount), int(due_day), int(day)
        )
        account.customer_receivable += float(amount)
        self.events.append({"day": day, "type": "customer_invoice_issued", "invoice_id": invoice_id, "seller": seller, "amount": float(amount), "due_day": int(due_day)})

    def process_day(self, day: int) -> None:
        """Collect customer invoices first, then settle payables in stable ID order."""
        if not isinstance(day, int) or isinstance(day, bool) or day < self.current_day:
            raise ValueError("days must be integers and non-decreasing")
        self.current_day = day
        for invoice in sorted(self.customer_invoices.values(), key=lambda x: (x.due_day, x.invoice_id)):
            if invoice.remaining > EPS and invoice.due_day <= day:
                amount = invoice.remaining
                self.accounts[invoice.seller].cash += amount
                self.accounts[invoice.seller].customer_receivable -= amount
                invoice.remaining = 0.0
                invoice.status = "paid"
                self.customer_collections += amount
                self.events.append({"day": day, "type": "customer_collection", "invoice_id": invoice.invoice_id, "seller": invoice.seller, "amount": amount})

        for invoice in sorted(self.payables.values(), key=lambda x: (x.due_day, x.invoice_id)):
            if invoice.remaining <= EPS or invoice.due_day > day or invoice.status == "defaulted":
                continue
            account = self.accounts[invoice.buyer]
            if account.defaulted:
                continue
            ok, draw = self._fund(invoice.buyer, invoice.remaining, day)
            if ok:
                amount = invoice.remaining
                account.cash -= amount
                account.trade_payable -= amount
                invoice.remaining = 0.0
                invoice.status = "paid"
                if invoice.seller is None:
                    self.external_supplier_payments += amount
                else:
                    seller = self.accounts[invoice.seller]
                    seller.cash += amount
                    seller.trade_receivable -= amount
                    self.internal_transfer_out += amount
                    self.internal_transfer_in += amount
                self.events.append({"day": day, "type": "payable_settled", "invoice_id": invoice.invoice_id, "buyer": invoice.buyer, "seller": invoice.seller, "amount": amount, "bank_draw": draw})
            elif day >= invoice.due_day + self.grace_days:
                invoice.status = "defaulted"
                account.defaulted = True
                self.events.append({"day": day, "type": "default", "cell_id": invoice.buyer, "invoice_id": invoice.invoice_id, "remaining": invoice.remaining})

    def snapshot(self) -> dict[str, Any]:
        cash = {cell: account.cash for cell, account in self.accounts.items()}
        bank_debt = {cell: account.bank_debt for cell, account in self.accounts.items()}
        expected_cash = self.opening_cash + self.bank_draws + self.customer_collections - self.external_supplier_payments - self.bank_repayments
        return {
            "model_id": "SYNERGY_V6.6.3A_MUTUAL_CREDIT_KERNEL",
            "current_day": self.current_day,
            "cell_count": len(self.accounts),
            "cash_by_cell": cash,
            "bank_debt_by_cell": bank_debt,
            "trade_payable_by_cell": {k: v.trade_payable for k, v in self.accounts.items()},
            "trade_receivable_by_cell": {k: v.trade_receivable for k, v in self.accounts.items()},
            "customer_receivable_by_cell": {k: v.customer_receivable for k, v in self.accounts.items()},
            "defaulted_cells": sorted(k for k, v in self.accounts.items() if v.defaulted),
            "open_payables": {k: v.remaining for k, v in self.payables.items() if v.remaining > EPS},
            "bank_draws": self.bank_draws,
            "customer_collections": self.customer_collections,
            "external_supplier_payments": self.external_supplier_payments,
            "bank_repayments": self.bank_repayments,
            "internal_transfer_in": self.internal_transfer_in,
            "internal_transfer_out": self.internal_transfer_out,
            "internal_transfer_net": self.internal_transfer_in - self.internal_transfer_out,
            "cash_conservation_error": sum(cash.values()) - expected_cash,
            "events": list(self.events),
        }
