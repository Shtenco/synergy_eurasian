# SYNERGY V6.6.4-M — adversarial claim-class relabeling sensitivity

**Status:** synthetic incentive sensitivity implemented; no automatic class validation or legal eligibility engine is claimed.  
**Purpose:** show how a priority-class rule can create incentives to misclassify a lower-priority claim.

## 1. Mechanism

`analyze_claim_class_relabeling_incentives(...)` compares a baseline priority allocation with a counterfactual in which each non-highest-class claim is relabeled into the highest class. It reports:
- claimant payout before and after relabeling;
- claimant payout delta;
- total payout delta imposed on all other claims.

The function supports the two analytical priority rules:
- priority class then FCFS;
- priority class then batch pro-rata.

It does not change claim data or the operational ledger. It is a sensitivity calculation only.

## 2. Synthetic example

Claims: an ordinary 30-unit claim due day 0 and an essential 10-unit claim due day 1. Available reserve: 20 units. Priority order: essential, then ordinary.

| Rule | Ordinary payout before relabeling | After relabeling as essential | Claimant gain | Other claims' combined change |
|---|---:|---:|---:|---:|
| Priority then FCFS | 10.0 | 20.0 | +10.0 | −10.0 |
| Priority then batch pro-rata | 10.0 | 15.0 | +5.0 | −5.0 |

The same reserve amount is paid in both cases. Relabeling does not create additional reserve capital; it transfers coverage away from other claims. FCFS within a priority class can produce a larger timing advantage than pro-rata within the class.

## 3. Governance implications

Any real priority-class system needs robust controls against strategic relabeling:
- objective, published eligibility definitions;
- contemporaneous documentary evidence and immutable timestamps;
- independent classification and conflict-of-interest controls;
- audit trails and sanctions for misrepresentation;
- appeals and correction procedures;
- review of whether class membership changes over time.

The model does not decide which claims deserve priority. It demonstrates that priority labels can have measurable economic value and therefore need governance.

All values and classes are synthetic. No legal creditor priority or EAEU guarantee policy is recommended.


## 4. CI validation

The targeted tests verify that relabeling the ordinary claim increases its payout by 10 units under priority-class FCFS and by 5 units under priority-class batch pro-rata, with equal and opposite combined payout changes to other claims. The CI runner wrote `outputs/synergy_v66_claim_class_relabeling_sensitivity.json`.

The full EIIOM CI run on code commit `d9c1f37664614f46353a320071b345669e049dd2` passed **172 pytest tests**. The report is an adversarial incentive demonstration, not evidence that any real participant would or could successfully relabel a claim.
