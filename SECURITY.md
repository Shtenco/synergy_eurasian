# Security & Economic Safety

## Scope

Security in SYNERGY includes software security **and economic/accounting integrity**.

## Never commit

- private keys;
- seed phrases;
- exchange/API secrets;
- database passwords;
- personal KYC data;
- production wallet addresses with sensitive operational metadata;
- unpublished investor personal data.

## Economic-security invariants

A vulnerability includes any path that allows:

- double-counting collateral;
- booking modelled GVA as cash;
- booking own-token appreciation as external income;
- bypassing evidence review;
- bypassing country/sector concentration limits;
- negative or hidden liabilities;
- unbounded Productive Escrow release;
- internal circular trading to appear as external PnL;
- bridge accounting that violates conservation;
- unauthorized modification of source/assumption metadata.

## Responsible reporting

Open a private security report through the repository owner's preferred GitHub security channel where available. Do not publish exploitable production details before remediation.

## Production boundary

This repository is research/architecture software. It must not be connected directly to production payment, minting, securities issuance or custody systems without separate security review, legal review, access control, audit logging and operational approval.

## CI gate

A failed invariant/security test blocks production use. No exception should be inferred from a successful economic simulation.
