# SYNERGY V6.6.4-E — regional guarantee loss waterfall

**Status:** optional capped member-assessment mechanism implemented and covered by tests.  
**Purpose:** compare who bears a local trade-credit default after the regional guarantee reserve is used.

## 1. Waterfall order

For a matured same-region internal trade-credit default:

1. The defaulting buyer is frozen and all its open payables are resolved in stable due-date/invoice-ID order.
2. The regional guarantee reserve pays the seller up to its available cash balance.
3. If configured, solvent members of the same region other than the defaulting buyer and claimant seller are assessed pro rata.
4. Any residual amount becomes seller-side trade bad debt.

Cross-region and external-supplier claims are outside this local mechanism.

## 2. Member assessment rule

The assessment is an actual cash transfer from contributing member accounts to the claimant seller. It does not create cash or increase the reserve. For each eligible member, the maximum contribution for a default event is:

`min(member_cash × regional_assessment_rate, regional_assessment_limit_per_cell)`

The absolute cap is optional. If omitted, only the cash-fraction limit applies. Assessments are allocated pro rata to eligible members' available assessment capacities, bounded by the outstanding loss. Defaulted members, the buyer and the claimant seller are excluded.

Defaults are resolved in deterministic invoice order. Therefore, an earlier default may reduce cash available for a later assessment. This path dependence is intentional and must be included in stress testing.

## 3. Configuration

```python
CreditLedger(
    regional_pool_reserve_per_region=20.0,
    regional_assessment_rate=0.10,
    regional_assessment_limit_per_cell=2.0,
)
```

The mechanism is disabled by default (`regional_assessment_rate=0`). The credit snapshot reports regional assessment totals and per-cell contributions; payable invoices record guarantee paid, member assessment paid and final write-off separately.

## 4. Experiment

`compare_regional_loss_waterfalls(...)` compares:
- reserve only;
- reserve plus capped pro-rata member assessment.

Both cases use the same seed-specific environment and financing-mode replay. Compare reserve use, member assessments, seller bad debt, defaults, service level, bank debt and cash/physical conservation. An assessment can reduce seller loss while shifting liquidity costs to other members; it is not a free reduction in system risk.

## 5. Governance and legal boundary

This is a synthetic accounting rule, not a legally enforceable guarantee or assessment authority. It does not specify member voting, notice, appeal, exemptions, hardship treatment, dispute resolution, insolvency priority or jurisdiction-specific recovery. A production institution would need an explicit membership contract, transparent assessment policy, audited data, caps, due process and independent oversight.

No fairness or policy superiority claim follows from the existence of this mechanism.


The audit trail records each assessment attempt, requested loss amount, eligible member assessment capacity and amount actually paid. A zero assessment payment can therefore be distinguished from a zero eligible capacity or from a case where no assessment was required.

The credit snapshot identifies this implementation as `SYNERGY_V6.6.4E_REGIONAL_LOSS_WATERFALL_LEDGER`.


## 6. CI smoke-sample observation

The three-seed, 20-day severe-regime sample ran both loss-waterfall settings. In this particular sample, the model recorded **zero regional assessment attempts, zero requested assessment amount and zero eligible assessment capacity** in both mutual-credit and hybrid modes. Consequently, reserve-only and reserve-plus-assessment outputs were identical. This does not show that assessments are ineffective; it shows that this sample did not generate a local same-region residual claim eligible for the mechanism.

The unit tests separately construct same-region defaults and verify that assessments are triggered, allocated pro rata, capped per member, and reconciled in the consolidated cash balance. Future policy experiments should include deliberately generated local supplier-default paths, not rely only on naturally occurring defaults in a small synthetic sample.
