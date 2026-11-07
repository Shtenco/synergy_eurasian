"""EIIOM-2045 research LP optimizer.

Real Economy OS only. This module does NOT mint money, issue securities,
approve financing, or recognize modelled GVA as cash.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
from scipy.optimize import linprog

COUNTRIES = ["RU", "KZ", "BY", "AM", "KG"]
SECTORS = [
    "PowerGen", "Grid", "MineralRefining", "AdvancedMaterials", "PowerElectronics",
    "DataCenterInfra", "Compute", "AICloud", "IndustrialAI", "Robotics",
    "MachineTools", "SemiDesign", "Logistics", "STEM", "AgroGenomics",
    "SeedProduction", "PrecisionAg", "AgroRobotics", "FoodProcessing",
    "WaterIrrigation", "RuralAIClusters", "UrbanRenovation", "RuralHousing",
    "ConstructionTech",
]

# Explicit research assumptions, not factual country ratings.
SUIT = {c: {s: 0.65 for s in SECTORS} for c in COUNTRIES}
SUIT["RU"].update({
    "PowerGen": 1.00, "Grid": 1.00, "MineralRefining": 0.90, "AdvancedMaterials": 0.95,
    "PowerElectronics": 0.95, "DataCenterInfra": 0.82, "Compute": 0.78, "AICloud": 0.92,
    "IndustrialAI": 1.00, "Robotics": 0.95, "MachineTools": 1.00, "SemiDesign": 0.86,
    "Logistics": 0.95, "STEM": 0.95, "AgroGenomics": 0.95, "SeedProduction": 0.95,
    "PrecisionAg": 0.95, "AgroRobotics": 0.95, "FoodProcessing": 0.95,
    "WaterIrrigation": 0.75, "RuralAIClusters": 0.88, "UrbanRenovation": 1.00,
    "RuralHousing": 0.90, "ConstructionTech": 1.00,
})
SUIT["KZ"].update({
    "PowerGen": 0.95, "Grid": 0.90, "MineralRefining": 1.00, "AdvancedMaterials": 0.90,
    "PowerElectronics": 0.72, "DataCenterInfra": 1.00, "Compute": 0.92, "AICloud": 0.85,
    "IndustrialAI": 0.86, "Robotics": 0.74, "MachineTools": 0.68, "SemiDesign": 0.67,
    "Logistics": 1.00, "STEM": 0.88, "AgroGenomics": 0.90, "SeedProduction": 0.95,
    "PrecisionAg": 1.00, "AgroRobotics": 0.90, "FoodProcessing": 0.90,
    "WaterIrrigation": 1.00, "RuralAIClusters": 1.00, "UrbanRenovation": 0.88,
    "RuralHousing": 1.00, "ConstructionTech": 0.85,
})
SUIT["BY"].update({
    "PowerGen": 0.72, "Grid": 0.85, "MineralRefining": 0.65, "AdvancedMaterials": 0.78,
    "PowerElectronics": 0.95, "DataCenterInfra": 0.70, "Compute": 0.62, "AICloud": 0.74,
    "IndustrialAI": 0.92, "Robotics": 1.00, "MachineTools": 1.00, "SemiDesign": 0.62,
    "Logistics": 0.80, "STEM": 0.87, "AgroGenomics": 0.90, "SeedProduction": 0.95,
    "PrecisionAg": 0.95, "AgroRobotics": 1.00, "FoodProcessing": 1.00,
    "WaterIrrigation": 0.70, "RuralAIClusters": 0.90, "UrbanRenovation": 0.90,
    "RuralHousing": 0.90, "ConstructionTech": 0.95,
})
SUIT["AM"].update({
    "PowerGen": 0.55, "Grid": 0.62, "MineralRefining": 0.40, "AdvancedMaterials": 0.58,
    "PowerElectronics": 0.72, "DataCenterInfra": 0.65, "Compute": 0.72, "AICloud": 0.96,
    "IndustrialAI": 0.90, "Robotics": 0.82, "MachineTools": 0.55, "SemiDesign": 1.00,
    "Logistics": 0.68, "STEM": 1.00, "AgroGenomics": 0.95, "SeedProduction": 0.85,
    "PrecisionAg": 0.88, "AgroRobotics": 0.75, "FoodProcessing": 0.80,
    "WaterIrrigation": 0.88, "RuralAIClusters": 0.90, "UrbanRenovation": 0.80,
    "RuralHousing": 0.85, "ConstructionTech": 0.75,
})
SUIT["KG"].update({
    "PowerGen": 0.84, "Grid": 0.72, "MineralRefining": 0.66, "AdvancedMaterials": 0.54,
    "PowerElectronics": 0.54, "DataCenterInfra": 0.56, "Compute": 0.50, "AICloud": 0.60,
    "IndustrialAI": 0.68, "Robotics": 0.60, "MachineTools": 0.52, "SemiDesign": 0.47,
    "Logistics": 0.80, "STEM": 0.78, "AgroGenomics": 0.80, "SeedProduction": 0.82,
    "PrecisionAg": 0.90, "AgroRobotics": 0.80, "FoodProcessing": 0.90,
    "WaterIrrigation": 0.95, "RuralAIClusters": 1.00, "UrbanRenovation": 0.75,
    "RuralHousing": 1.00, "ConstructionTech": 0.72,
})

MAX_STAGE_SHARE = {s: 0.20 for s in SECTORS}
MAX_STAGE_SHARE.update({
    "IndustrialAI": 0.15, "Robotics": 0.12, "PowerElectronics": 0.11,
    "PrecisionAg": 0.065, "AgroRobotics": 0.055, "AICloud": 0.14, "Compute": 0.14,
    "MachineTools": 0.11, "UrbanRenovation": 0.22, "RuralHousing": 0.05,
    "RuralAIClusters": 0.08, "AgroGenomics": 0.03, "SeedProduction": 0.04,
    "FoodProcessing": 0.08, "WaterIrrigation": 0.07, "ConstructionTech": 0.08,
    "STEM": 0.08, "SemiDesign": 0.06, "DataCenterInfra": 0.12, "PowerGen": 0.18,
    "Grid": 0.12, "AdvancedMaterials": 0.10, "MineralRefining": 0.08, "Logistics": 0.07,
})
COUNTRY_MIN = {"RU": 0.35, "KZ": 0.15, "BY": 0.07, "AM": 0.03, "KG": 0.02}
COUNTRY_MAX = {"RU": 0.65, "KZ": 0.30, "BY": 0.20, "AM": 0.10, "KG": 0.08}
RENOVATION_EFF = {"2026-30": 1.11, "2031-40": 1.25, "2041-45": 1.35}
RURAL_HOUSING_EFF = {"2026-30": 1.43, "2031-40": 1.60, "2041-45": 1.80}
PRECISION_AG_EFF = {"2026-30": 1.667, "2031-40": 1.818, "2041-45": 2.00}
AGRO_ROBOTICS_EFF = {"2026-30": 0.50, "2031-40": 0.70, "2041-45": 0.90}
CLUSTER_EFF = {"2026-30": 4.0, "2031-40": 5.0, "2041-45": 6.0}
TARGETS = {
    "2026-30": {"reno": 12, "rural_h": 3, "precision": 5, "agro_robot": 1, "clusters": 30},
    "2031-40": {"reno": 65, "rural_h": 6, "precision": 18, "agro_robot": 4, "clusters": 100},
    "2041-45": {"reno": 100, "rural_h": 8, "precision": 30, "agro_robot": 7, "clusters": 160},
}


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def solve(config: dict) -> dict:
    stages = list(config["stages"])
    yields = config["annual_gva_equivalent_yield"]
    tech = config["technology_curves"]
    head_power = config["existing_headroom_mw"]["power"]
    head_grid = config["existing_headroom_mw"]["grid"]
    max_compute_share = config["policy_constraints"]["max_country_compute_share"]
    max_dc_share = config["policy_constraints"]["max_country_dc_share"]

    variables = [(c, s, t) for c in COUNTRIES for s in SECTORS for t in stages]
    idx = {v: i for i, v in enumerate(variables)}
    n = len(variables)
    objective = np.zeros(n)
    for v, i in idx.items():
        c, s, t = v
        objective[i] = -(yields[s] * SUIT[c][s] * config["stages"][t]["time_weight"])

    A_ub, b_ub, A_eq, b_eq = [], [], [], []

    def row(parts: Iterable[Tuple[Tuple[str, str, str], float]]) -> np.ndarray:
        r = np.zeros(n)
        for key, coeff in parts:
            r[idx[key]] += coeff
        return r

    def ub(parts, rhs):
        A_ub.append(row(parts)); b_ub.append(float(rhs))

    def eq(parts, rhs):
        A_eq.append(row(parts)); b_eq.append(float(rhs))

    total_budget = sum(config["stages"][t]["budget_bn_usd"] for t in stages)
    for t in stages:
        eq((((c, s, t), 1.0) for c in COUNTRIES for s in SECTORS), config["stages"][t]["budget_bn_usd"])

    for t in stages:
        stage_budget = config["stages"][t]["budget_bn_usd"]
        for s in SECTORS:
            ub((((c, s, t), 1.0) for c in COUNTRIES), MAX_STAGE_SHARE[s] * stage_budget)

    for c in COUNTRIES:
        ub((((c, s, t), -1.0) for s in SECTORS for t in stages), -COUNTRY_MIN[c] * total_budget)
        ub((((c, s, t), 1.0) for s in SECTORS for t in stages), COUNTRY_MAX[c] * total_budget)

    dc_eff = tech["dc_shell_mw_per_bn"]
    comp_eff = tech["compute_it_mw_per_bn"]
    power_eff = tech["power_mw_per_bn"]
    grid_eff = tech["grid_mw_per_bn"]
    overhead = tech["power_overhead_multiplier"]

    def cumulative(k, sector, coeff_by_stage=None, country=None):
        ts = stages[:k + 1]
        out = []
        for t in ts:
            coeff = coeff_by_stage[t] if coeff_by_stage else 1.0
            for c in ([country] if country else COUNTRIES):
                out.append(((c, sector, t), coeff))
        return out

    for k, milestone in enumerate(stages):
        ts = stages[:k + 1]
        for c in COUNTRIES:
            ub(cumulative(k, "Compute", comp_eff, c) + [((c, "DataCenterInfra", t), -dc_eff[t]) for t in ts], 0)
            ub([((c, "Compute", t), overhead * comp_eff[t]) for t in ts] + [((c, "PowerGen", t), -power_eff[t]) for t in ts], head_power[c])
            ub([((c, "Compute", t), overhead * comp_eff[t]) for t in ts] + [((c, "Grid", t), -grid_eff[t]) for t in ts], head_grid[c])

            parts = []
            for t in ts:
                parts.append(((c, "Compute", t), (1 - max_compute_share) * comp_eff[t]))
                for cc in COUNTRIES:
                    if cc != c:
                        parts.append(((cc, "Compute", t), -max_compute_share * comp_eff[t]))
            ub(parts, 0)

            parts = []
            for t in ts:
                parts.append(((c, "DataCenterInfra", t), (1 - max_dc_share) * dc_eff[t]))
                for cc in COUNTRIES:
                    if cc != c:
                        parts.append(((cc, "DataCenterInfra", t), -max_dc_share * dc_eff[t]))
            ub(parts, 0)

        allc = lambda sector, coeff=1.0: [((c, sector, t), coeff) for c in COUNTRIES for t in ts]
        ub(allc("AICloud") + allc("Compute", -1.2), 2.0)
        ub(allc("IndustrialAI") + allc("AICloud", -1.8) + allc("Robotics", -0.5), 3.0)
        ub(allc("SemiDesign") + allc("Compute", -0.5), 3.0)
        ub(allc("Robotics", 0.25) + allc("MachineTools", -1.0), 0.0)
        ub(allc("Robotics") + allc("MachineTools", -2.0) + allc("PowerElectronics", -1.5), 2.0)
        ub(allc("UrbanRenovation", 0.12) + allc("RuralHousing", 0.12) + allc("ConstructionTech", -1.0), 0.0)
        ub(allc("AgroGenomics", 0.7) + allc("SeedProduction", -1.0), 0.0)
        ub(allc("PrecisionAg") + allc("AICloud", -2.5), 3.0)
        ub(allc("AgroRobotics") + allc("Robotics", -1.5) + allc("MachineTools", -1.0), 3.0)

        target = TARGETS[milestone]
        ub([((c, "UrbanRenovation", t), -RENOVATION_EFF[t]) for c in COUNTRIES for t in ts], -target["reno"])
        ub([((c, "RuralHousing", t), -RURAL_HOUSING_EFF[t]) for c in COUNTRIES for t in ts], -target["rural_h"])
        ub([((c, "PrecisionAg", t), -PRECISION_AG_EFF[t]) for c in COUNTRIES for t in ts], -target["precision"])
        ub([((c, "AgroRobotics", t), -AGRO_ROBOTICS_EFF[t]) for c in COUNTRIES for t in ts], -target["agro_robot"])
        ub([((c, "RuralAIClusters", t), -CLUSTER_EFF[t]) for c in COUNTRIES for t in ts], -target["clusters"])

    ub([((c, "PrecisionAg", t), PRECISION_AG_EFF[t]) for c in COUNTRIES for t in stages], 60.0)
    ub([((c, "AgroRobotics", t), AGRO_ROBOTICS_EFF[t]) for c in COUNTRIES for t in stages], 15.0)
    ub([((c, "RuralAIClusters", t), CLUSTER_EFF[t]) for c in COUNTRIES for t in stages], 220.0)

    floor_map = {
        "STEM": "minimum_stem_bn", "FoodProcessing": "minimum_food_processing_bn",
        "WaterIrrigation": "minimum_water_irrigation_bn", "Logistics": "minimum_logistics_bn",
        "AdvancedMaterials": "minimum_advanced_materials_bn", "MineralRefining": "minimum_mineral_refining_bn",
        "ConstructionTech": "minimum_construction_tech_bn", "AgroGenomics": "minimum_agro_genomics_bn",
        "SeedProduction": "minimum_seed_production_bn",
    }
    for sector, key in floor_map.items():
        ub((((c, sector, t), -1.0) for c in COUNTRIES for t in stages), -config["policy_constraints"][key])

    result = linprog(
        objective,
        A_ub=np.asarray(A_ub), b_ub=np.asarray(b_ub),
        A_eq=np.asarray(A_eq), b_eq=np.asarray(b_eq),
        bounds=(0, None), method="highs",
    )
    if not result.success:
        raise RuntimeError(result.message)

    allocation = []
    for v, i in idx.items():
        if result.x[i] > 1e-8:
            allocation.append({"country": v[0], "sector": v[1], "stage": v[2], "capex_bn_usd": float(result.x[i])})

    capex_by_stage, capex_by_country, capex_by_sector = defaultdict(float), defaultdict(float), defaultdict(float)
    compute_by_country, dc_by_country = defaultdict(float), defaultdict(float)
    gva_equiv = compute_mw = dc_mw = 0.0
    for item in allocation:
        c, s, t, x = item["country"], item["sector"], item["stage"], item["capex_bn_usd"]
        capex_by_stage[t] += x; capex_by_country[c] += x; capex_by_sector[s] += x
        gva_equiv += x * yields[s] * SUIT[c][s]
        if s == "Compute": compute_mw += x * comp_eff[t]; compute_by_country[c] += x * comp_eff[t]
        if s == "DataCenterInfra": dc_mw += x * dc_eff[t]; dc_by_country[c] += x * dc_eff[t]

    return {
        "status": "optimal", "objective_minimized": float(result.fun),
        "total_capex_bn_usd": float(sum(capex_by_stage.values())),
        "annual_gva_equivalent_2045_bn_usd": float(gva_equiv),
        "compute_it_mw": float(compute_mw), "dc_shell_mw": float(dc_mw),
        "capex_by_stage": dict(capex_by_stage), "capex_by_country": dict(capex_by_country),
        "capex_by_sector": dict(capex_by_sector), "compute_mw_by_country": dict(compute_by_country),
        "dc_mw_by_country": dict(dc_by_country), "allocation": allocation,
    }


def validate_invariants(config: dict, solution: dict, tol: float = 1e-5) -> None:
    """Independently re-check the returned allocation; never rely on assert."""
    if isinstance(tol, bool) or not isinstance(tol, (int, float)) or not np.isfinite(tol) or tol <= 0:
        raise ValueError("Invariant tolerance must be finite and positive")
    if solution.get("status") != "optimal":
        raise ValueError("Only an optimal solution can pass invariant validation")
    if config.get("productive_escrow", {}).get("implemented_in_this_repo") is not False:
        raise ValueError("Productive escrow minting must remain disabled in this repository")

    stages = list(config["stages"])
    expected_by_stage = {
        stage: float(config["stages"][stage]["budget_bn_usd"]) for stage in stages
    }
    if any(not np.isfinite(v) or v <= 0 for v in expected_by_stage.values()):
        raise ValueError("Every stage budget must be finite and positive")
    expected_total = sum(expected_by_stage.values())

    capex_by_stage = defaultdict(float)
    capex_by_country = defaultdict(float)
    capex_by_sector = defaultdict(float)
    capex_by_sector_stage = defaultdict(float)
    compute_by_country = defaultdict(float)
    dc_by_country = defaultdict(float)
    power_by_country = defaultdict(float)
    grid_by_country = defaultdict(float)
    gva_equiv = 0.0

    allocation = solution.get("allocation")
    if not isinstance(allocation, list):
        raise ValueError("Solution allocation must be a list")
    for item in allocation:
        if not isinstance(item, dict):
            raise ValueError("Every allocation row must be an object")
        country, sector, stage = item.get("country"), item.get("sector"), item.get("stage")
        if country not in COUNTRIES or sector not in SECTORS or stage not in stages:
            raise ValueError("Allocation row contains an unknown country, sector or stage")
        amount = item.get("capex_bn_usd")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not np.isfinite(amount) or amount < -tol:
            raise ValueError("Allocation CAPEX must be finite and non-negative")
        amount = max(0.0, float(amount))
        capex_by_stage[stage] += amount
        capex_by_country[country] += amount
        capex_by_sector[sector] += amount
        capex_by_sector_stage[(sector, stage)] += amount
        gva_equiv += amount * float(yields[sector]) * SUIT[country][sector]
        if sector == "Compute":
            compute_by_country[country] += amount * float(config["technology_curves"]["compute_it_mw_per_bn"][stage])
        if sector == "DataCenterInfra":
            dc_by_country[country] += amount * float(config["technology_curves"]["dc_shell_mw_per_bn"][stage])
        if sector == "PowerGen":
            power_by_country[country] += amount * float(config["technology_curves"]["power_mw_per_bn"][stage])
        if sector == "Grid":
            grid_by_country[country] += amount * float(config["technology_curves"]["grid_mw_per_bn"][stage])

    for stage, budget in expected_by_stage.items():
        if abs(capex_by_stage[stage] - budget) > tol:
            raise ValueError(f"Stage {stage} allocation does not equal its budget envelope")
    if abs(sum(capex_by_stage.values()) - expected_total) > tol:
        raise ValueError("Total CAPEX does not equal the stage budget envelopes")

    for country in COUNTRIES:
        if capex_by_country[country] < COUNTRY_MIN[country] * expected_total - tol:
            raise ValueError(f"Country {country} allocation is below its minimum share")
        if capex_by_country[country] > COUNTRY_MAX[country] * expected_total + tol:
            raise ValueError(f"Country {country} allocation exceeds its maximum share")

    for stage, budget in expected_by_stage.items():
        for sector in SECTORS:
            if capex_by_sector_stage[(sector, stage)] > MAX_STAGE_SHARE[sector] * budget + tol:
                raise ValueError(f"Sector {sector} exceeds its stage allocation cap in {stage}")

    tech = config["technology_curves"]
    head_power = config["existing_headroom_mw"]["power"]
    head_grid = config["existing_headroom_mw"]["grid"]
    overhead = float(tech["power_overhead_multiplier"])
    max_compute_share = float(config["policy_constraints"]["max_country_compute_share"])
    max_dc_share = float(config["policy_constraints"]["max_country_dc_share"])
    total_compute = sum(compute_by_country.values())
    total_dc = sum(dc_by_country.values())
    if total_compute > total_dc + tol:
        raise ValueError("Compute IT load exceeds data-center shell capacity")
    if total_compute > tol and max(compute_by_country.values()) / total_compute > max_compute_share + tol:
        raise ValueError("Country compute concentration exceeds policy limit")
    if total_dc > tol and max(dc_by_country.values()) / total_dc > max_dc_share + tol:
        raise ValueError("Country data-center concentration exceeds policy limit")

    for country in COUNTRIES:
        if compute_by_country[country] > dc_by_country[country] + tol:
            raise ValueError(f"Country {country} compute load exceeds its own data-center shell capacity")
        power_demand = sum(
            float(item["capex_bn_usd"]) * overhead
            * float(tech["compute_it_mw_per_bn"][item["stage"]])
            for item in allocation if item["country"] == country and item["sector"] == "Compute"
        )
        grid_demand = power_demand
        if power_demand > float(head_power[country]) + power_by_country[country] + tol:
            raise ValueError(f"Country {country} compute load exceeds available power")
        if grid_demand > float(head_grid[country]) + grid_by_country[country] + tol:
            raise ValueError(f"Country {country} compute load exceeds available grid capacity")

    # Recheck cumulative cross-sector dependencies and milestone targets.
    for k, milestone in enumerate(stages):
        ts = stages[:k + 1]
        cumulative = {
            sector: sum(capex_by_sector_stage[(sector, t)] for t in ts)
            for sector in SECTORS
        }
        target = TARGETS[milestone]
        checks = [
            (cumulative["AICloud"], 2.0 + 1.2 * cumulative["Compute"], "AICloud/Compute dependency"),
            (cumulative["IndustrialAI"], 3.0 + 1.8 * cumulative["AICloud"] + 0.5 * cumulative["Robotics"], "IndustrialAI dependency"),
            (cumulative["SemiDesign"], 3.0 + 0.5 * cumulative["Compute"], "SemiDesign dependency"),
            (0.25 * cumulative["Robotics"], cumulative["MachineTools"], "Robotics/MachineTools dependency"),
            (cumulative["Robotics"], 2.0 + 2.0 * cumulative["MachineTools"] + 1.5 * cumulative["PowerElectronics"], "Robotics capacity dependency"),
            (0.12 * (cumulative["UrbanRenovation"] + cumulative["RuralHousing"]), cumulative["ConstructionTech"], "ConstructionTech dependency"),
            (0.7 * cumulative["AgroGenomics"], cumulative["SeedProduction"], "SeedProduction dependency"),
            (cumulative["PrecisionAg"], 3.0 + 2.5 * cumulative["AICloud"], "PrecisionAg dependency"),
            (cumulative["AgroRobotics"], 3.0 + 1.5 * cumulative["Robotics"] + cumulative["MachineTools"], "AgroRobotics dependency"),
        ]
        for value, upper, label in checks:
            if value > upper + tol:
                raise ValueError(f"Cumulative {label} constraint is violated")
        target_checks = (
            ("UrbanRenovation", RENOVATION_EFF, target["reno"]),
            ("RuralHousing", RURAL_HOUSING_EFF, target["rural_h"]),
            ("PrecisionAg", PRECISION_AG_EFF, target["precision"]),
            ("AgroRobotics", AGRO_ROBOTICS_EFF, target["agro_robot"]),
            ("RuralAIClusters", CLUSTER_EFF, target["clusters"]),
        )
        for sector, efficiency, required in target_checks:
            delivered = sum(
                capex_by_sector_stage[(sector, t)] * efficiency[t] for t in ts
            )
            if delivered < required - tol:
                raise ValueError(f"Cumulative {sector} milestone target is not met")

    global_caps = (
        ("PrecisionAg", 60.0),
        ("AgroRobotics", 15.0),
        ("RuralAIClusters", 220.0),
    )
    for sector, cap in global_caps:
        if capex_by_sector[sector] > cap + tol:
            raise ValueError(f"Global {sector} allocation cap is exceeded")

    floors = {
        "STEM": "minimum_stem_bn", "FoodProcessing": "minimum_food_processing_bn",
        "WaterIrrigation": "minimum_water_irrigation_bn", "Logistics": "minimum_logistics_bn",
        "AdvancedMaterials": "minimum_advanced_materials_bn", "MineralRefining": "minimum_mineral_refining_bn",
        "ConstructionTech": "minimum_construction_tech_bn", "AgroGenomics": "minimum_agro_genomics_bn",
        "SeedProduction": "minimum_seed_production_bn",
    }
    for sector, key in floors.items():
        if capex_by_sector[sector] < float(config["policy_constraints"][key]) - tol:
            raise ValueError(f"Sector {sector} is below its configured minimum allocation")

    expected_metrics = {
        "total_capex_bn_usd": expected_total,
        "compute_it_mw": total_compute,
        "dc_shell_mw": total_dc,
        "annual_gva_equivalent_2045_bn_usd": gva_equiv,
    }
    for key, expected_value in expected_metrics.items():
        actual = solution.get(key)
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not np.isfinite(actual):
            raise ValueError(f"Solution metric {key} must be finite")
        if abs(float(actual) - expected_value) > tol:
            raise ValueError(f"Solution metric {key} does not reconcile to allocation")


def export(solution: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {k: v for k, v in solution.items() if k != "allocation"}
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    with (output_dir / "allocation.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["country", "sector", "stage", "capex_bn_usd"])
        writer.writeheader(); writer.writerows(solution["allocation"])


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config/base_scenario.json"))
    p.add_argument("--output", type=Path, default=Path("outputs/base"))
    args = p.parse_args()
    config = load_config(args.config)
    solution = solve(config)
    validate_invariants(config, solution)
    export(solution, args.output)
    print(json.dumps({
        "status": solution["status"],
        "total_capex_bn_usd": round(solution["total_capex_bn_usd"], 4),
        "annual_gva_equivalent_2045_bn_usd": round(solution["annual_gva_equivalent_2045_bn_usd"], 4),
        "compute_it_mw": round(solution["compute_it_mw"], 2),
        "dc_shell_mw": round(solution["dc_shell_mw"], 2),
    }, indent=2))


if __name__ == "__main__":
    main()
