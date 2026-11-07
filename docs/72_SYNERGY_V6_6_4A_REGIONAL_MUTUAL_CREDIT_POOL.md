# SYNERGY V6.6.4-A — regional mutual-credit clearing positions

**Status:** executable memorandum ledger integrated into the V6.6.3 credit kernel.  
**Purpose:** track regional net debit/credit positions and cap mutual-credit expansion without treating those positions as cash.

## 1. What the regional pool represents

For local internal trade-credit invoices, the buyer receives a negative regional credit position and the seller receives an equal positive position. The sum of member positions in a region must remain zero.

- Negative balance: net debtor to the regional network.
- Positive balance: net creditor to the regional network.
- Regional pool outstanding: sum of absolute negative member positions (equal to the sum of positive positions).
- Settlement reduces the buyer debit and seller credit by the same amount.
- Cross-region invoices remain bilateral in this increment and are not posted to either local pool.

These are accounting positions representing mutual-credit claims. They are not cash, bank deposits, a token, legal tender or newly created external wealth.

## 2. Limits

Three independent limits can be configured:
- `regional_pool_limit_per_region`: maximum aggregate net debit outstanding in each region;
- `regional_member_debit_limit_per_cell`: maximum negative net position of one member;
- `regional_member_credit_limit_per_cell`: maximum positive net position of one member.

The existing gross buyer trade-payable limit and seller receivable-exposure limit continue to apply as separate constraints. A local purchase that cannot fit within these limits may still be funded immediately by a sufficient approved bank line. If no permitted funding route exists, it is rejected before cash, stock or shipment state is mutated.

## 3. Settlement and default

Partial settlement reverses the corresponding amount of the buyer's negative position and seller's positive position. An unpaid invoice that reaches default remains represented as an outstanding claim in the pool; this increment does not erase the position or socialize the loss. Loss allocation, pool reserve, member assessments and legal recovery require a separate governance and solvency design.

## 4. Snapshot invariants

The credit snapshot reports:
- member regional credit balances;
- regional outstanding amounts;
- regional net-position sums;
- pool and member utilization;
- regional-pool rejection counts.

For every region:

`sum(member regional credit balances) = 0`

and:

`regional pool outstanding = sum(max(0, -member balance))`

When a pool limit is configured, utilization must not exceed 1.0 (within numerical tolerance). The pool ledger does not enter the consolidated cash equation.

## 5. Current boundary

Only same-region internal credit invoices enter a regional pool. Cross-border trades remain bilateral and need a separate cross-border clearing design. There is no multilateral invoice novation, automatic net cash settlement, pooled guarantee reserve, loss waterfall, voting or member governance. A regional pool limit is a risk ceiling, not an automatic credit issuance decision.

The paired financing experiment enables the regional pool in mutual-credit and hybrid modes so its effects can be tested under common shocks.


## 6. Member-funded guarantee reserve extension

The integrated credit ledger can hold a separate regional guarantee reserve. Its initial balance is transferred from member opening cash (equal contribution per cell in the current synthetic fixture); it is not minted or added on top of system cash. When a same-region buyer defaults on a trade-credit invoice, the reserve covers the seller up to the available reserve balance. Any uncovered residual is written off as seller trade bad debt. Buyer AP, seller AR and the corresponding regional net positions are reduced symmetrically.

The reserve balance is included in consolidated cash conservation. A reserve payment moves cash from the reserve account to the seller; it does not create new system cash. Cross-region defaults are not covered by a local regional reserve. The reserve is a guarantee mechanism, distinct from the memorandum mutual-credit positions.


A matured payable default currently triggers a cell-level cross-default: all other open payables of that buyer are resolved at the same time. The regional reserve is applied in due-date/invoice-ID order; once depleted, the remaining losses are written off to the respective sellers. This is a deliberately simple insolvency rule, not a jurisdiction-specific legal waterfall.
