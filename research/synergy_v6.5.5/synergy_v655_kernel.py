import numpy as np
N, DAYS, SECTORS, PER = 80, 100, 4, 20
POLICIES = ("isolated", "liquidity_first", "random_rescue", "network_optimizer")

def make_net(seed):
    rng = np.random.default_rng(seed)
    sec = np.repeat(np.arange(SECTORS), PER)
    sup = np.zeros((N, 2), dtype=int)
    for i in range(N):
        cand = np.where((sec == max(0, sec[i]-1)) | ((sec == sec[i]) & (np.arange(N) != i)))[0]
        cand = cand[cand != i]
        sup[i] = rng.choice(cand, 2, replace=False)
    return sec, sup

def downstream_weights(sec, sup):
    W = np.zeros((N, N))
    for buyer in range(N):
        for supplier in sup[buyer]:
            W[supplier, buyer] += 0.5
    influence = np.eye(N)
    power = np.eye(N)
    for j in range(4):
        power = power @ W
        influence += 0.55**(j+1) * power
    return influence.sum(axis=1)-1

def simulate(seed, regime, policy, capital=180.0):
    if regime not in ("severe", "systemic") or policy not in POLICIES:
        raise ValueError("Unknown regime or policy")
    sec, sup = make_net(seed); sup = sup.copy()
    rng = np.random.default_rng(seed + (100000 if regime == "severe" else 200000))
    decision_rng = np.random.default_rng(seed+900000)
    cash = np.full(N, 40.0); alive = np.ones(N, bool); disrupted = np.zeros(N, bool)
    shock_size = 18 if regime == "severe" else 24
    importance0 = downstream_weights(sec, sup)
    shock_nodes = np.argsort(importance0+rng.normal(0, 0.03, N))[::-1][:shock_size]
    shock_start = 30; shock_duration = 25 if regime == "severe" else 38
    disruption_until = np.zeros(N, int); disruption_until[shock_nodes] = shock_start+shock_duration
    pool = float(capital); repair_spend = transfers = 0.0; reroutes = 0
    sales_total = prod_total = lost_total = operating_surplus = 0.0
    daily_prod = []; importance = downstream_weights(sec, sup)
    macro_mu = -0.10 if regime == "severe" else -0.20
    macro_sd = 0.11 if regime == "severe" else 0.18
    persistent = rng.normal(macro_mu, macro_sd)
    sector_shock = rng.normal(0, 0.10 if regime == "severe" else 0.18, SECTORS)
    for day in range(DAYS):
        for i in np.where(disrupted & (disruption_until <= day))[0]: disrupted[i] = False
        if day == shock_start: disrupted[shock_nodes] = True
        macro = persistent+rng.normal(0, 0.035)
        secshock = sector_shock+rng.normal(0, 0.045, SECTORS)
        demand = np.clip(1+macro+secshock[sec]+rng.normal(0, 0.05, N), 0.05, 1.2)
        if policy != "isolated":
            downstream = np.bincount(sup.ravel(), minlength=N)
            for buyer in range(N):
                if not alive[buyer] or disrupted[buyer]: continue
                for k in range(2):
                    old = sup[buyer, k]
                    if (not alive[old] or disrupted[old]) and downstream[old] > 0:
                        candidates = np.where(alive & ~disrupted & (np.abs(sec-sec[buyer]) <= 1))[0]
                        candidates = candidates[candidates != buyer]
                        candidates = candidates[downstream[candidates] < 5]
                        if len(candidates):
                            new = candidates[np.argmin(np.abs(sec[candidates]-sec[buyer])+downstream[candidates]*0.03)]
                            downstream[old] -= 1; downstream[new] += 1; sup[buyer, k] = new; reroutes += 1
        supplier_fraction = (alive[sup] & ~disrupted[sup]).mean(axis=1)
        capacity_factor = np.where(alive & ~disrupted, 0.35+0.65*supplier_fraction, 0.0)
        production = demand*capacity_factor
        cash += 4.5*production-1.8*alive
        sales_total += float((10*production).sum())
        prod_total += float(production.sum())
        operating_surplus += float((4.5*production-1.8*alive).sum())
        lost_total += float(np.maximum(0, demand-production).sum())
        if policy in ("random_rescue", "network_optimizer", "liquidity_first") and pool >= 18:
            repairable = np.where(alive & disrupted & (disruption_until > day+2))[0] if day >= shock_start else np.array([], dtype=int)
            if len(repairable):
                if policy == "random_rescue": target = int(decision_rng.choice(repairable))
                elif policy == "liquidity_first": target = int(repairable[np.argmin(cash[repairable])])
                else:
                    scores = []
                    for i in repairable:
                        dependent = np.where((sup == i).any(axis=1))[0]
                        downstream_loss = float((~disrupted[dependent] & alive[dependent]).sum())
                        scores.append((1+importance[i]*0.08+downstream_loss*0.12)*max(0.2, demand[i]))
                    target = int(repairable[int(np.argmax(scores))])
                disrupted[target] = False; disruption_until[target] = day
                pool -= 18; repair_spend += 18
        if policy in ("liquidity_first", "random_rescue", "network_optimizer") and pool > 0:
            needy = np.where(alive & (cash < 5))[0]
            if len(needy):
                if policy == "random_rescue": order = decision_rng.permutation(needy)
                elif policy == "liquidity_first": order = needy[np.argsort(cash[needy])]
                else:
                    scores = []
                    for i in needy:
                        need = max(0, 8-cash[i])
                        scores.append((1+importance[i]*0.10)/max(need, 1))
                    order = needy[np.argsort(scores)[::-1]]
                for i in order:
                    amount = min(max(0, 8-cash[i]), pool)
                    cash[i] += amount; pool -= amount; transfers += amount
                    if pool <= 0: break
        alive[alive & (cash < 0)] = False
        daily_prod.append(float(production.sum()))
    pre = float(np.mean(daily_prod[10:30])); post = float(np.mean(daily_prod[70:100]))
    recovery_ratio = post/pre if pre > 0 else 0.0
    recovery_days = DAYS-shock_start
    for day in range(shock_start+1, DAYS-4):
        if np.mean(daily_prod[day:day+5]) >= 0.9*pre:
            recovery_days = day-shock_start; break
    return {
        "seed": seed, "regime": regime, "policy": policy, "defaults": int((~alive).sum()),
        "survival_rate": float(alive.mean()), "external_sales": sales_total,
        "production": prod_total, "production_lost": lost_total,
        "operating_surplus": operating_surplus, "net_after_repair": operating_surplus-repair_spend,
        "recovery_ratio": recovery_ratio, "recovery_days": recovery_days,
        "repair_spend": repair_spend, "liquidity_transfers": transfers,
        "capital_remaining": pool, "reroutes": reroutes,
        "pre_shock_production": pre, "post_shock_production": post
    }
