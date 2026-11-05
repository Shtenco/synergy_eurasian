# Adaptive CA threshold sensitivity

This note documents the additional local-rule experiment in V6.4.

The original `ca` rule keeps the preferred local supplier until it is fully
unavailable. The adaptive variants switch to the alternate when the preferred
supplier's remaining capacity falls below a threshold share of the total
remaining capacity of the two eligible suppliers:

- `ca_t40`: 40%
- `ca_t50`: 50%
- `ca_t60`: 60%
- `ca_t75`: 75%

Each of 100 seeds in the volatile and severe regimes was replayed against the
same exogenous environment for each policy. The 800 policy-seed combinations
are included in the audit manifest.

In the severe regime, mean output was 138.03 units for Independent, 170.03 for
Market, and 170.03 for CA thresholds 50%, 60%, and 75%. Mean accrued operating
result was -221.56 for Independent, +23.92 for Market, and +23.65 for CA at
50–75%.

This is evidence that a simple local switching threshold can approximate the
global allocation result in this small two-supplier network. It is not proof
that cellular automata generally reproduce market coordination: the network
has only two suppliers per stage, and the threshold is tuned within a
synthetic model. Larger heterogeneous networks and independent validation
remain necessary.
