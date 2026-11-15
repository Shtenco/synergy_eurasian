"""Topology, recipes and deterministic exogenous path for V6.6.2."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import random
from typing import Any

REGIONS = ("WEST", "EAST")
SECTORS = ("primary", "processing", "manufacturing")
DAYS_DEFAULT = 45
EPS = 1e-9

@dataclass(frozen=True)
class CellSpec:
    cell_id: str
    region: str
    sector: str
    role: str
    capacity: float
    warehouse_capacity: float = 0.0

@dataclass(frozen=True)
class Recipe:
    output_sku: str
    output_per_batch: float
    inputs: dict[str, float]
    capacity_per_batch: float = 1.0
    shelf_life_days: int = 30

@dataclass
class Lot:
    lot_id: str
    sku: str
    quantity: float
    born_day: int
    expires_day: int
    source: str

@dataclass
class Shipment:
    shipment_id: str
    origin: str
    destination: str
    sku: str
    quantity: float
    dispatch_day: int
    arrival_day: int
    expires_day: int

def build_cells() -> tuple[CellSpec, ...]:
    rows=[]
    for r in REGIONS:
        rows.extend((
            CellSpec(f"{r}-AG1",r,"primary","grain_farm",10),
            CellSpec(f"{r}-AG2",r,"primary","oilseed_farm",8),
            CellSpec(f"{r}-PR1",r,"processing","flour_mill",8),
            CellSpec(f"{r}-PR2",r,"processing","oil_press",6),
            CellSpec(f"{r}-MF1",r,"manufacturing","bakery",6),
            CellSpec(f"{r}-MF2",r,"manufacturing","food_factory",5),
            CellSpec(f"{r}-WH",r,"support","warehouse",0,450),
            CellSpec(f"{r}-LG",r,"support","logistics",30),
            CellSpec(f"{r}-EN",r,"support","energy",20),
            CellSpec(f"{r}-SV",r,"support","maintenance",10),
        ))
    assert len(rows)==20 and len({x.cell_id for x in rows})==20
    return tuple(rows)

CELLS=build_cells()
CELL_BY_ID={c.cell_id:c for c in CELLS}
RECIPES={
 "flour_mill":Recipe("flour",1.0,{"grain":1.25,"energy":0.04},shelf_life_days=90),
 "oil_press":Recipe("oil",1.0,{"oilseed":1.15,"energy":0.05},shelf_life_days=180),
 "bakery":Recipe("bread",1.0,{"flour":0.92,"energy":0.08},shelf_life_days=3),
 "food_factory":Recipe("packed_food",1.0,{"flour":0.55,"oil":0.22,"energy":0.10},shelf_life_days=120),
}
SUPPLIERS={}
for r in REGIONS:
    other="EAST" if r=="WEST" else "WEST"
    SUPPLIERS[f"{r}-PR1"]=(f"{r}-AG1",f"{other}-AG1")
    SUPPLIERS[f"{r}-PR2"]=(f"{r}-AG2",f"{other}-AG2")
    SUPPLIERS[f"{r}-MF1"]=(f"{r}-PR1",f"{other}-PR1")
    SUPPLIERS[f"{r}-MF2"]=(f"{r}-PR1",f"{other}-PR1",f"{r}-PR2",f"{other}-PR2")
TARGET_STOCK={"grain":12.0,"oilseed":10.0,"flour":8.0,"oil":5.0,"energy":12.0}
DEMAND_SKUS={"bread":"MF1","packed_food":"MF2"}
SKUS=("grain","oilseed","flour","oil","bread","packed_food","energy")

def make_environment(seed:int,days:int=DAYS_DEFAULT,regime:str="volatile")->list[dict[str,Any]]:
    if days<1: raise ValueError("days must be >= 1")
    if regime not in {"normal","volatile","severe"}: raise ValueError("invalid regime")
    rng=random.Random(seed); env=[]
    for day in range(days):
        if regime=="normal": scale,low,p=1.0,0.88,0.02
        elif regime=="volatile": scale,low,p=1.0,0.62,0.08
        else: scale,low,p=0.92,0.30,0.18
        common=rng.uniform(0.35,1.0) if rng.random()<p else 1.0
        demand={f"{r}-{sku}":max(0.0,rng.gauss(mu*scale,sd))
                for r in REGIONS for sku,mu,sd in (("bread",4.2,0.75),("packed_food",2.5,0.55))}
        capacity={c.cell_id:common*rng.uniform(low,1.08) for c in CELLS}
        leads={}
        for dest,sources in SUPPLIERS.items():
            for src in sources:
                cross=CELL_BY_ID[src].region!=CELL_BY_ID[dest].region
                leads[f"{src}>{dest}"]=(2 if cross else 1)+(1 if regime=="severe" and rng.random()<0.25 else 0)
        env.append({"day":day,"demand":demand,"capacity_factor":capacity,"lead_times":leads})
    return env

def _fingerprint(environment:list[dict[str,Any]])->str:
    raw=json.dumps(environment,sort_keys=True,separators=(",",":"),allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()

def _stock(lots:list[Lot],sku:str,day:int)->float:
    return sum(x.quantity for x in lots if x.sku==sku and x.quantity>EPS and x.expires_day>=day)

def _consume_fifo(lots:list[Lot],sku:str,quantity:float,day:int)->int:
    remaining=quantity; expiries=[]
    for lot in sorted((x for x in lots if x.sku==sku and x.quantity>EPS and x.expires_day>=day),
                      key=lambda x:(x.expires_day,x.born_day,x.lot_id)):
        take=min(lot.quantity,remaining); lot.quantity-=take
        if take>EPS: expiries.append(lot.expires_day)
        remaining-=take
        if remaining<=EPS: break
    if remaining>EPS: raise RuntimeError(f"inventory underflow for {sku}: {remaining}")
    return min(expiries) if expiries else day
