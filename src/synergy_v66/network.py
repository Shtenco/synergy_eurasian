"""Deterministic 20-cell physical inventory network for SYNERGY V6.6.2."""
from __future__ import annotations
from typing import Any
from .network_topology import (
    CELLS, CELL_BY_ID, REGIONS, SECTORS, RECIPES, SUPPLIERS, TARGET_STOCK,
    DEMAND_SKUS, SKUS, Lot, Shipment, make_environment, _fingerprint,
    _stock, _consume_fifo,
)

def simulate(environment:list[dict[str,Any]],initial_inventory:float=6.0)->dict[str,Any]:
    if not environment: raise ValueError("environment must not be empty")
    if initial_inventory<0: raise ValueError("initial_inventory must be >= 0")
    inventory={c.cell_id:[] for c in CELLS}
    for c in CELLS:
        if c.role in RECIPES:
            for sku in RECIPES[c.role].inputs:
                qty=initial_inventory if sku!="energy" else initial_inventory*2
                inventory[c.cell_id].append(Lot(f"INIT-{c.cell_id}-{sku}",sku,qty,0,9999,"initial"))
        if c.role in {"grain_farm","oilseed_farm"}:
            sku="grain" if c.role=="grain_farm" else "oilseed"
            inventory[c.cell_id].append(Lot(f"INIT-{c.cell_id}-{sku}",sku,initial_inventory*2,0,9999,"initial"))
    shipments:list[Shipment]=[]
    initial={sku:sum(x.quantity for lots in inventory.values() for x in lots if x.sku==sku) for sku in SKUS}
    produced={s:0.0 for s in SKUS}; delivered={s:0.0 for s in SKUS}
    consumed={s:0.0 for s in SKUS}; sold={s:0.0 for s in SKUS}
    expired={s:0.0 for s in SKUS}; unmet={s:0.0 for s in DEMAND_SKUS}
    daily=[]; max_wh={r:0.0 for r in REGIONS}; max_transport={r:0.0 for r in REGIONS}
    dispatch_audit=[]; arrival_audit=[]; serial=0

    def regional_load(region:str)->float:
        return (sum(x.quantity for cid,lots in inventory.items() if CELL_BY_ID[cid].region==region
                    for x in lots if x.quantity>1e-9)
                +sum(s.quantity for s in shipments if CELL_BY_ID[s.destination].region==region))

    for row in environment:
        day=int(row["day"]); p0=produced.copy(); d0=delivered.copy(); s0=sold.copy()
        arrived=[s for s in shipments if s.arrival_day<=day]
        shipments=[s for s in shipments if s.arrival_day>day]
        for s in arrived:
            inventory[s.destination].append(Lot(s.shipment_id,s.sku,s.quantity,day,s.expires_day,s.origin))
            delivered[s.sku]+=s.quantity
            arrival_audit.append({"shipment_id":s.shipment_id,"dispatch_day":s.dispatch_day,
                "arrival_day":day,"origin":s.origin,"destination":s.destination,"sku":s.sku,"quantity":s.quantity})

        for lots in inventory.values():
            for lot in lots:
                if lot.quantity>1e-9 and lot.expires_day<day:
                    expired[lot.sku]+=lot.quantity; lot.quantity=0.0

        # Harvest and energy generation are constrained by regional storage headroom.
        for region in REGIONS:
            for role,sku in (("grain_farm","grain"),("oilseed_farm","oilseed")):
                farm=next(c for c in CELLS if c.region==region and c.role==role)
                room=max(0.0,CELL_BY_ID[f"{region}-WH"].warehouse_capacity-regional_load(region))
                qty=min(farm.capacity*0.55*row["capacity_factor"][farm.cell_id],room)
                inventory[farm.cell_id].append(Lot(f"H-{farm.cell_id}-{day}",sku,qty,day,day+365,farm.cell_id))
                produced[sku]+=qty
            energy=f"{region}-EN"
            room=max(0.0,CELL_BY_ID[f"{region}-WH"].warehouse_capacity-regional_load(region))
            qty=min(18.0*row["capacity_factor"][energy],room)
            inventory[energy].append(Lot(f"E-{region}-{day}","energy",qty,day,day+1,energy))
            produced["energy"]+=qty

        # Production consumes only inventory already received by this day.
        for cell in CELLS:
            recipe=RECIPES.get(cell.role)
            if recipe is None: continue
            batches=cell.capacity*row["capacity_factor"][cell.cell_id]/recipe.capacity_per_batch
            for sku,per_batch in recipe.inputs.items():
                batches=min(batches,_stock(inventory[cell.cell_id],sku,day)/per_batch)
            room=max(0.0,CELL_BY_ID[f"{cell.region}-WH"].warehouse_capacity-regional_load(cell.region))
            batches=max(0.0,min(batches,room/recipe.output_per_batch))
            if batches<=1e-9: continue
            for sku,per_batch in recipe.inputs.items():
                qty=batches*per_batch; _consume_fifo(inventory[cell.cell_id],sku,qty,day); consumed[sku]+=qty
            output=batches*recipe.output_per_batch
            inventory[cell.cell_id].append(Lot(f"P-{cell.cell_id}-{day}",recipe.output_sku,output,day,day+recipe.shelf_life_days,cell.cell_id))
            produced[recipe.output_sku]+=output

        transport={r:0.0 for r in REGIONS}
        # Replenishment orders: local supplier first, then the other region.
        for dest,sources in SUPPLIERS.items():
            region=CELL_BY_ID[dest].region
            for sku in RECIPES[CELL_BY_ID[dest].role].inputs:
                if sku=="energy": continue
                need=max(0.0,TARGET_STOCK[sku]-_stock(inventory[dest],sku,day)
                         -sum(s.quantity for s in shipments if s.destination==dest and s.sku==sku))
                for src in sources:
                    if need<=1e-9: break
                    available=_stock(inventory[src],sku,day)
                    lead=int(row["lead_times"][f"{src}>{dest}"])
                    cap=CELL_BY_ID[f"{region}-LG"].capacity*row["capacity_factor"][f"{region}-LG"]
                    transport_room=max(0.0,cap-transport[region])
                    storage_room=max(0.0,CELL_BY_ID[f"{region}-WH"].warehouse_capacity-regional_load(region))
                    qty=min(need,available,transport_room,storage_room)
                    if qty<=1e-9: continue
                    expiry_day=_consume_fifo(inventory[src],sku,qty,day); serial+=1
                    sh=Shipment(f"S{serial:06d}",src,dest,sku,qty,day,day+lead,expiry_day)
                    shipments.append(sh)
                    dispatch_audit.append({"shipment_id":sh.shipment_id,"dispatch_day":day,
                        "arrival_day":sh.arrival_day,"origin":src,"destination":dest,"sku":sku,"quantity":qty})
                    transport[region]+=qty; need-=qty

        # Energy is a local, one-day shipment and uses the same logistics budget.
        for region in REGIONS:
            src=f"{region}-EN"
            for cell in (c for c in CELLS if c.region==region and c.role in RECIPES):
                need=max(0.0,8.0-_stock(inventory[cell.cell_id],"energy",day))
                available=_stock(inventory[src],"energy",day)
                room=max(0.0,cell.capacity*2.0-_stock(inventory[cell.cell_id],"energy",day))
                cap=CELL_BY_ID[f"{region}-LG"].capacity*row["capacity_factor"][f"{region}-LG"]
                qty=min(need,available,room,max(0.0,cap-transport[region]))
                if qty>1e-9:
                    expiry_day=_consume_fifo(inventory[src],"energy",qty,day); serial+=1
                    sh=Shipment(f"S{serial:06d}",src,cell.cell_id,"energy",qty,day,day+1,expiry_day)
                    shipments.append(sh)
                    dispatch_audit.append({"shipment_id":sh.shipment_id,"dispatch_day":day,
                        "arrival_day":day+1,"origin":src,"destination":cell.cell_id,"sku":"energy","quantity":qty})
                    transport[region]+=qty

        # Sales serve current demand only; there is no future-demand lookahead.
        for region in REGIONS:
            for sku,role in DEMAND_SKUS.items():
                cell=f"{region}-{role}"; demand=float(row["demand"][f"{region}-{sku}"])
                qty=min(demand,_stock(inventory[cell],sku,day))
                if qty>1e-9: _consume_fifo(inventory[cell],sku,qty,day)
                sold[sku]+=qty; unmet[sku]+=demand-qty

        for region in REGIONS:
            max_wh[region]=max(max_wh[region],regional_load(region))
            max_transport[region]=max(max_transport[region],transport[region])
        daily.append({"day":day,
            "produced":{s:produced[s]-p0[s] for s in SKUS},
            "delivered":{s:delivered[s]-d0[s] for s in SKUS},
            "sold":{s:sold[s]-s0[s] for s in SKUS},
            "pending_shipments":len(shipments)})

    transit={s:sum(x.quantity for x in shipments if x.sku==s) for s in SKUS}
    closing={s:sum(x.quantity for lots in inventory.values() for x in lots if x.sku==s and x.quantity>1e-9) for s in SKUS}
    balance={s:initial[s]+produced[s]-consumed[s]-sold[s]-expired[s]-closing[s]-transit[s] for s in SKUS}
    return {
        "model_id":"SYNERGY_V6.6.2_20_CELL_INVENTORY_NETWORK","days":len(environment),
        "cell_count":len(CELLS),"regions":list(REGIONS),"sector_count":len(SECTORS),
        "environment_hash":_fingerprint(environment),"initial_stock_by_sku":initial,
        "produced_by_sku":produced,"delivered_by_sku":delivered,"consumed_by_sku":consumed,
        "sold_by_sku":sold,"unmet_demand_by_sku":unmet,"expired_by_sku":expired,
        "closing_stock":sum(closing.values()),"closing_stock_by_sku":closing,
        "in_transit_stock":sum(transit.values()),"in_transit_by_sku":transit,
        "physical_balance_error_by_sku":balance,"physical_balance_error":sum(balance.values()),
        "max_warehouse_load_by_region":max_wh,"max_transport_load_by_region":max_transport,
        "transport_capacity_by_region":{r:CELL_BY_ID[f"{r}-LG"].capacity for r in REGIONS},
        "warehouse_capacity_by_region":{r:CELL_BY_ID[f"{r}-WH"].warehouse_capacity for r in REGIONS},
        "pending_shipments":len(shipments),"shipment_dispatch_audit":dispatch_audit,
        "shipment_arrival_audit":arrival_audit,"daily_ledger":daily,
    }


def run(seed:int,days:int=DAYS_DEFAULT,regime:str="volatile")->dict[str,Any]:
    env=make_environment(seed,days,regime)
    return {"seed":seed,"regime":regime,"environment_hash":_fingerprint(env),"result":simulate(env)}
