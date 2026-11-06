import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from synergy_v7 import (DomainEvent,EventStore,GraphNode,GraphEdge,EconomicGraph,
    PhysicalFlow,physical_flow_summary,ResourceCapacity,ResourceCommitment,
    validate_resource_capacity,graph_from_events,BenefitClaim,BenefitLedger,
    cashflow_npv,empirical_cvar,pareto_frontier)


def event(seq=1,**kw):
    d=dict(event_id=f"e{seq}",aggregate_type="PROJECT",aggregate_id="p1",sequence=seq,
      event_type="PROJECT_CREATED" if seq==1 else "PROJECT_UPDATED",
      effective_at="2026-01-01T00:00:00Z",recorded_at="2026-01-01T00:01:00Z",
      payload={"amount":100},source_ref="test-fixture",idempotency_key=f"key{seq}")
    d.update(kw); return DomainEvent(**d)


def test_event_store_hash_chain_and_sequence():
    s=EventStore(); a=s.append(event()); b=s.append(event(2))
    assert b.previous_hash==a.event_hash and s.verify()


def test_event_store_rejects_duplicate_and_sequence_gap():
    s=EventStore(); s.append(event())
    with pytest.raises(ValueError,match="sequence"): s.append(event(3))
    with pytest.raises(ValueError,match="idempotency"): s.append(event(2,idempotency_key="key1"))


def test_event_store_requires_timezone_and_finite_json():
    with pytest.raises(ValueError,match="timezone"): EventStore().append(event(effective_at="2026-01-01T00:00:00"))
    with pytest.raises(ValueError): EventStore().append(event(payload={"bad":float("nan")}))


def test_graph_rejects_dangling_edges_and_duplicate_nodes():
    with pytest.raises(ValueError,match="Dangling"): EconomicGraph.build([GraphNode("a","PROJECT")],[GraphEdge("e","a","b","SUPPLIES")])
    with pytest.raises(ValueError,match="Duplicate"): EconomicGraph.build([GraphNode("a","PROJECT"),GraphNode("a","ASSET")],[])


def test_dependency_graph_must_be_acyclic():
    ns=[GraphNode("a","PROJECT"),GraphNode("b","PROJECT")]
    es=[GraphEdge("e1","a","b","DEPENDS_ON"),GraphEdge("e2","b","a","DEPENDS_ON")]
    with pytest.raises(ValueError,match="cycle"): EconomicGraph.build(ns,es)


def test_physical_flow_does_not_promote_internal_transfer_to_output():
    fs=[PhysicalFlow("f1","a","b","steel",10,"tonne","2026-Q1","INTERNAL"),
        PhysicalFlow("f2","b","customer","steel",7,"tonne","2026-Q1","EXPORT")]
    r=physical_flow_summary(fs)
    assert r["internal_transfer_volume"]==10 and r["external_exports"]["steel::tonne"]==7
    assert r["internal_transfer_is_new_output"] is False


def claim(**kw):
    d=dict(enterprise_id="co1",benefit_stream_id="energy_saving",period="2026-Q1",
      gross_incremental_benefit=100,incremental_opex=20,replacement_obligation=15,
      evidence_id="meter:123",source_class="VERIFIED")
    d.update(kw); return BenefitClaim(**d)


def test_benefit_ledger_rejects_double_counting_and_nets_costs():
    l=BenefitLedger(); l.add(claim())
    assert l.consolidated()["net_reproducible_benefit"]==65
    with pytest.raises(ValueError,match="Duplicate"): l.add(claim())


def test_scenario_is_separated_from_observed():
    l=BenefitLedger(); l.add(claim(source_class="SCENARIO"))
    assert l.consolidated()["by_evidence_class"]["SCENARIO"]==65
    assert l.consolidated()["scenario_values_are_not_observed_cash"]


def test_npv_and_cvar():
    assert cashflow_npv([-100,60,60],0.0)==20
    assert empirical_cvar([0,1,2,3,100],0.8)==100


def test_pareto_frontier_keeps_tradeoffs_and_removes_dominated():
    rows=[{"name":"a","npv":10,"resilience":5},{"name":"b","npv":8,"resilience":8},{"name":"c","npv":7,"resilience":4}]
    assert {r["name"] for r in pareto_frontier(rows,("npv","resilience"))}=={"a","b"}


def test_resource_capacity_rejects_overcommitment():
    caps=[ResourceCapacity("power","2026-Q2",100,"MWh","OBSERVED","meter:power")]
    commits=[ResourceCommitment("c1","power","p1","2026-Q2",60,"MWh"),ResourceCommitment("c2","power","p2","2026-Q2",50,"MWh")]
    r=validate_resource_capacity(caps,commits)
    assert not r["feasible"] and r["violations"][0]["excess"]==10


def test_unverified_capacity_cannot_be_used_as_firm_supply():
    caps=[ResourceCapacity("grid","2027-Q1",100,"MW","UNDER_CONSTRUCTION","permit")]
    commits=[ResourceCommitment("c1","grid","p1","2027-Q1",10,"MW")]
    with pytest.raises(ValueError,match="not firm"): validate_resource_capacity(caps,commits)


def test_proposed_commitments_are_excluded_by_default():
    caps=[ResourceCapacity("water","2026-Q2",100,"m3","OBSERVED","meter")]
    cs=[ResourceCommitment("c1","water","p1","2026-Q2",90,"m3"),
        ResourceCommitment("c2","water","p2","2026-Q2",90,"m3","PROPOSED")]
    assert validate_resource_capacity(caps,cs)["feasible"]
    assert not validate_resource_capacity(caps,cs,include_proposed=True)["feasible"]


def test_graph_projection_rebuilt_from_domain_events():
    s=EventStore()
    s.append(event(event_type="NODE_REGISTERED",payload={"node_id":"p1","node_type":"PROJECT"}))
    s.append(event(2,event_type="NODE_REGISTERED",payload={"node_id":"a1","node_type":"ASSET"}))
    s.append(event(3,event_type="EDGE_REGISTERED",payload={"edge_id":"e1","source_id":"p1","target_id":"a1","relation":"OWNS"}))
    g=graph_from_events(s.events)
    assert set(g.nodes)=={"p1","a1"} and g.edges[0].relation=="OWNS"


from synergy_v7 import (MaterialRequirement, ResourceRequirement, ProductionRecipe,
    ProductionOrder, InventoryReceipt, ProductDemand, evaluate_production_plan)


def test_production_plan_completes_after_lead_time_and_serves_demand():
    recipe=ProductionRecipe("r1","finished",10,"unit",(MaterialRequirement("raw",5,"kg"),),
      (ResourceRequirement("power",2,"MWh"),),1)
    orders=[ProductionOrder("o1","r1",0,2)]
    receipts=[InventoryReceipt("i1","raw",10,"kg",0,"OBSERVED")]
    demands=[ProductDemand("d1","finished",20,"unit",1)]
    caps=[ResourceCapacity("power","0",4,"MWh","OBSERVED","meter")]
    r=evaluate_production_plan([recipe],orders,receipts,demands,caps)
    assert r["feasible"] and r["demand"]["finished"]["fulfilled"]==20
    assert r["orders"]["o1"]["finish_period"]==1


def test_production_blocks_order_when_input_material_is_missing():
    recipe=ProductionRecipe("r1","finished",10,"unit",(MaterialRequirement("raw",5,"kg"),),(),1)
    r=evaluate_production_plan([recipe],[ProductionOrder("o1","r1",0,1)],[],[],[])
    assert not r["feasible"] and r["orders"]["o1"]["status"]=="BLOCKED"
    assert r["violations"][0]["type"]=="MATERIAL_SHORTAGE"


def test_production_detects_competing_orders_for_same_resource():
    recipes=[ProductionRecipe("r1","a",1,"unit",(),(ResourceRequirement("power",6,"MWh"),),1),
      ProductionRecipe("r2","b",1,"unit",(),(ResourceRequirement("power",6,"MWh"),),1)]
    orders=[ProductionOrder("o1","r1",0,1),ProductionOrder("o2","r2",0,1)]
    caps=[ResourceCapacity("power","0",10,"MWh","OBSERVED","meter")]
    r=evaluate_production_plan(recipes,orders,[],[],caps)
    assert not r["feasible"] and r["orders"]["o2"]["status"]=="BLOCKED"


def test_production_excludes_planned_material_supply_by_default():
    recipe=ProductionRecipe("r1","finished",1,"unit",(MaterialRequirement("raw",1,"kg"),),(),1)
    receipt=InventoryReceipt("i1","raw",1,"kg",0,"PLANNED")
    r=evaluate_production_plan([recipe],[ProductionOrder("o1","r1",0,1)],[receipt],[],[])
    assert not r["feasible"] and r["excluded_nonfirm_receipts"]==["i1"]


def test_production_tracks_inventory_across_periods_and_priorities():
    recipe=ProductionRecipe("r1","finished",10,"unit",(MaterialRequirement("raw",5,"kg"),),(),1)
    orders=[ProductionOrder("o1","r1",0,1),ProductionOrder("o2","r1",1,1)]
    receipts=[InventoryReceipt("i1","raw",10,"kg",0)]
    demands=[ProductDemand("d1","finished",5,"unit",1,priority=1),
      ProductDemand("d2","finished",5,"unit",1,priority=2),
      ProductDemand("d3","finished",10,"unit",2)]
    r=evaluate_production_plan([recipe],orders,receipts,demands,[])
    assert r["feasible"] and r["demand"]["finished"]["fulfilled"]==20
    assert r["inventory_trace"][-1]["inventory"]["raw"]==0


def test_recipe_rejects_zero_lead_time_and_duplicate_inputs():
    with pytest.raises(ValueError,match="lead_time"): ProductionRecipe("r","x",1,"u",(),(),0)
    with pytest.raises(ValueError,match="Duplicate"): ProductionRecipe("r","x",1,"u",
      (MaterialRequirement("raw",1,"kg"),MaterialRequirement("raw",2,"kg")),(),1)


def test_production_rejects_product_unit_mismatch():
    recipe=ProductionRecipe("r1","finished",1,"unit",(MaterialRequirement("raw",1,"kg"),),(),1)
    receipt=InventoryReceipt("i1","raw",1,"tonne",0)
    with pytest.raises(ValueError,match="Unit mismatch"):
        evaluate_production_plan([recipe],[],[receipt],[],[])


def test_integrated_factory_fixture_is_schema_valid_and_feasible():
    import json
    from synergy_v7.cli import evaluate_document
    fixture=ROOT/"examples"/"synergy_v7_1_integrated_factory_demo.json"
    with fixture.open(encoding="utf-8") as stream:
        document=json.load(stream)
    result=evaluate_document(document)
    assert result["feasible"]
    assert result["demand"]["machine_part"]["fulfilled"]==12
    assert result["completed_output"]["steel"]==80
    assert result["completed_output"]["machine_part"]==12
