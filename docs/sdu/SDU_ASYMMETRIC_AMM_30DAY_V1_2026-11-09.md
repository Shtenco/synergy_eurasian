# SYNERGY DIGITAL UNIT (SDU) — immutable research snapshot v1.0 (2026-11-09)

**Status:** Research simulator, NOT deployed monetary policy, audited contract, live AMM, or price guarantee.

## Constitutional parameters
- Minting: ALL (users, AI and DAO may initiate, independent proof validation required)
- Governance: HYBRID (AI + DAO + independent validators)
- AI: AUTONOMOUS only within bounded constitutional limits
- Supply: UNLIMITED total, bounded per epoch
- Burn: UNIVERSAL (owner's own tokens; protocol-held reserve tokens only under explicit rules)
- No issuer redemption promise, guaranteed return, or guaranteed rising price.

## Canonical asymmetric AMM model
Preserve original asymmetric design; DO NOT replace with constant-product x*y=k.

BUY: P_terminal=P*(1+u/y)^gamma; P_average=(P+P_terminal)/2; q=u*(1-buyFee)/P_average.
SELL: z=q-burn (where applicable); impact=sellImpact*z/(x-q); P_sell=P_terminal*(1-impact). Apply fee and reserve liquidity constraints.
Reference curve mint: P_target=P*(x/(x+m))^gamma; P_next=P+softFactor*(P_target-P); x_next=x+m.
Reference curve burn: P_target=P*(x/(x-b))^gamma; P_next=P+softFactor*(P_target-P); x_next=x-b; 0<=b<x.
Mint/burn MUST correspond to actual reserve token movements; external voluntary burns reduce supply but not pool x. Never fabricate USDC.
Default research parameters: gamma=5, sellImpact=0.15, softFactor=0.5, buy/sell fee=0.003, flash fee=0.0005.
Keep AMM quoted reference price, USDC reserve, SDU reserve, external reference, and mark-to-market TVL separately.

## 30-day agent simulation snapshot
Starting state: 10,000,000 total SDU; 1,000,000 SDU in pool; 1,000,000 USDC; quoted P=1.
Agents: users, validators, AI, DAO, holders, buyers, sellers, arbitrageurs.
Three seeded scenarios were executed in the ChatGPT research workspace (base/bull/stress); simplified market, NOT empirical forecast.

| Scenario | Day-30 AMM reference price | Day-30 USDC reserve | Day-30 TVL marked at reference price | Supply |
|---|---:|---:|---:|---:|
| base | 1.8561 | 920081.9129 | 3008542.5227 | ~10055583 |
| bull | 2.2992 | 948873.5390 | 3422582.4047 | ~10034202 |
| stress | 1.4940 | 850291.2750 | 2591890.6281 | ~10038109 |

**Critical warning:** reference price/TVL increased in these examples while the USDC reserve DECREASED in every scenario. Price growth and TVL mark-to-market do not prove growth in cash liquidity. This model is research-grade and contains simplified arbitrage and fee accounting; do not present these figures as production-verified economics or guaranteed outcomes.

## Integration policy
This file is an additive cross-repository reference. Preserve every existing AMM and trading core, do not auto-enable mint/burn on mainnet, do not change token supply or reserve accounting in deployed systems without audits. Implement contracts, unit/property tests, agent simulator and security review in a separate integration PR before activation.

## Reproducibility
Source simulator artifact from research workspace: sdu_asymmetric_agent_simulator.py
Outputs: sdu_30day_agent_simulation.csv, sdu_30day_scenario_summary.csv.
The original full Python artifact must be imported and reviewed separately; this snapshot deliberately does not pretend to contain its full source.
