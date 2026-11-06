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


from synergy_v7 import (WorkingCapitalSnapshot, working_capital_cash_impact,
    CashWaterfallInput, run_cash_waterfall)


def test_working_capital_and_cash_conversion_cycle():
    w=WorkingCapitalSnapshot(100,200,50,10,1000,730,365)
    assert w.net_operating_working_capital==240
    assert w.dso_days==pytest.approx(36.5)
    assert w.dio_days==pytest.approx(100)
    assert w.dpo_days==pytest.approx(25)
    assert w.cash_conversion_cycle_days==pytest.approx(111.5)


def test_reduction_in_net_working_capital_releases_cash():
    old=WorkingCapitalSnapshot(100,200,50,10,1000,730)
    new=WorkingCapitalSnapshot(80,180,60,10,1000,730)
    assert working_capital_cash_impact(old,new)==50


def test_cash_waterfall_respects_replacement_reserve_and_distribution_gates():
    x=CashWaterfallInput(opening_cash=50,customer_collections=100,
      other_external_operating_receipts=0,financing_proceeds=25,internal_transfers_received=10,
      opening_reserve=20,reserve_target=50,opex_due=70,replacement_due=40,
      debt_service_due=20,growth_capex_requested=20,distributions_requested=10)
    r=run_cash_waterfall(x)
    assert r["solvent_for_listed_mandatory_obligations"]
    assert r["reserve"]["ending"]==50
    assert r["growth_capex_funded"]==20
    assert r["distribution_funded"]==5
    assert r["external_operating_cash_generation"]==100
    assert r["financing_proceeds_excluded_from_operating_generation"]==25
    assert r["internal_transfers_excluded_from_consolidated_operating_generation"]==10


def test_cash_waterfall_uses_reserve_for_mandatory_shortfall_and_blocks_distributions():
    x=CashWaterfallInput(opening_cash=10,customer_collections=0,
      other_external_operating_receipts=0,financing_proceeds=0,internal_transfers_received=0,
      opening_reserve=5,reserve_target=5,opex_due=20,replacement_due=10,
      debt_service_due=0,growth_capex_requested=50,distributions_requested=10)
    r=run_cash_waterfall(x)
    assert r["allocations"]["opex"]["funded"]==15
    assert r["allocations"]["replacement"]["unfunded"]==10
    assert r["distribution_funded"]==0
    assert not r["distribution_gate_passed"]
    assert r["growth_capex_funded"]==0


def test_cash_waterfall_funds_reserve_before_growth_and_distribution():
    x=CashWaterfallInput(opening_cash=100,customer_collections=0,
      other_external_operating_receipts=0,financing_proceeds=0,internal_transfers_received=0,
      opening_reserve=0,reserve_target=80,opex_due=0,replacement_due=0,
      debt_service_due=0,growth_capex_requested=50,distributions_requested=50)
    r=run_cash_waterfall(x)
    assert r["reserve"]["ending"]==80
    assert r["growth_capex_funded"]==20
    assert r["distribution_funded"]==0


def test_working_capital_rejects_negative_balances():
    with pytest.raises(ValueError,match="non-negative"):
        WorkingCapitalSnapshot(-1,0,0,0,0,0)


from synergy_v7 import (TradeDocument, SettlementEvent, DocumentAdjustment,
    DisputeEvent, CreditRiskAssessment, build_trade_ledger)


def trade_doc(document_id="inv1",side="RECEIVABLE",amount=100,counterparty="buyer1"):
    return TradeDocument(document_id,side,"enterprise1",counterparty,"2026-01-01",
      "2026-01-31","USD",amount,"erp:invoice:"+document_id)


def test_trade_ledger_partial_settlement_and_aging():
    doc=trade_doc()
    settlement=SettlementEvent("s1","inv1","2026-02-10",40,"USD","bank1","bank:tx1")
    r=build_trade_ledger([doc],[settlement],[],[],"2026-03-05")
    row=r["documents"][0]
    assert row["outstanding"]==60
    assert row["days_past_due"]==33
    assert row["aging_bucket"]=="DUE_31_60"
    assert r["totals_by_side_and_currency"]["RECEIVABLE::USD"]==60


def test_trade_ledger_replays_disputes_and_settlements_chronologically():
    doc=trade_doc(amount=100)
    dispute=DisputeEvent("d1","inv1","2026-01-15",80,"USD","OPEN","case:1")
    settlement=SettlementEvent("s1","inv1","2026-02-01",80,"USD","bank1","bank:1")
    r=build_trade_ledger([doc],[settlement],[],[dispute],"2026-02-02")
    row=r["documents"][0]
    assert row["outstanding"]==20
    assert row["disputed_outstanding"]==20


def test_trade_ledger_rejects_settlement_over_open_balance():
    doc=trade_doc(amount=100)
    payments=[SettlementEvent("s1","inv1","2026-01-10",60,"USD","bank","tx1"),
      SettlementEvent("s2","inv1","2026-01-11",50,"USD","bank","tx2")]
    with pytest.raises(ValueError,match="exceeds open balance"):
        build_trade_ledger([doc],payments,[],[],"2026-01-12")


def test_trade_ledger_credit_adjustment_reduces_open_balance_once():
    doc=trade_doc(amount=100)
    adjustment=DocumentAdjustment("cn1","inv1","2026-01-15",25,"USD","credit note","erp:cn1")
    r=build_trade_ledger([doc],[],[adjustment],[],"2026-01-20")
    assert r["documents"][0]["outstanding"]==75


def test_trade_ledger_dispute_resolution_and_limits():
    doc=trade_doc(amount=100)
    events=[DisputeEvent("d1","inv1","2026-01-10",60,"USD","OPEN","case:1"),
      DisputeEvent("d2","inv1","2026-01-20",20,"USD","RESOLVE","case:2")]
    r=build_trade_ledger([doc],[],[],events,"2026-01-25")
    assert r["documents"][0]["disputed_outstanding"]==40
    too_much=events+[DisputeEvent("d3","inv1","2026-01-21",50,"USD","RESOLVE","case:3")]
    with pytest.raises(ValueError,match="exceeds disputed"):
        build_trade_ledger([doc],[],[],too_much,"2026-01-25")


def test_trade_ledger_expected_credit_loss_is_separate_from_cash():
    doc=trade_doc(amount=200)
    risk=CreditRiskAssessment("buyer1","USD",0.1,0.5,"2026-01-15","risk:rating1")
    r=build_trade_ledger([doc],[],[],[],"2026-02-01",[risk])
    exposure=r["counterparty_exposure"][0]
    assert exposure["expected_credit_loss"]==10
    assert r["expected_credit_loss_is_estimate_not_cash_or_provision"]


def test_trade_ledger_future_settlements_and_risk_assessments_are_not_looked_ahead():
    doc=trade_doc(amount=100)
    future=SettlementEvent("s1","inv1","2026-02-01",100,"USD","bank","tx1")
    future_risk=CreditRiskAssessment("buyer1","USD",1,1,"2026-02-01","risk:future")
    r=build_trade_ledger([doc],[future],[],[],"2026-01-31",[future_risk])
    assert r["documents"][0]["outstanding"]==100
    assert r["counterparty_exposure"][0]["expected_credit_loss"] is None


def test_trade_ledger_keeps_payable_and_receivable_gross_without_netting():
    docs=[trade_doc("ar1","RECEIVABLE",100,"partner"),
      trade_doc("ap1","PAYABLE",70,"partner")]
    r=build_trade_ledger(docs,[],[],[],"2026-01-15")
    assert r["totals_by_side_and_currency"]=={"PAYABLE::USD":70,"RECEIVABLE::USD":100}
    assert r["internal_netting_applied"] is False


def test_trade_ledger_rejects_currency_mismatch_and_unknown_document():
    doc=trade_doc()
    bad=SettlementEvent("s1","inv1","2026-01-10",10,"EUR","bank","tx")
    with pytest.raises(ValueError,match="currency mismatch"):
        build_trade_ledger([doc],[bad],[],[],"2026-01-11")
    orphan=SettlementEvent("s2","missing","2026-01-10",10,"USD","bank","tx")
    with pytest.raises(ValueError,match="Unknown document"):
        build_trade_ledger([doc],[orphan],[],[],"2026-01-11")


def test_trade_ledger_rejects_duplicate_documents_and_conflicting_same_day_risk():
    doc=trade_doc()
    risk1=CreditRiskAssessment("buyer1","USD",0.1,0.5,"2026-01-15","risk:1")
    risk2=CreditRiskAssessment("buyer1","USD",0.2,0.5,"2026-01-15","risk:2")
    with pytest.raises(ValueError,match="Duplicate document"):
        build_trade_ledger([doc,doc],[],[],[],"2026-01-20")
    with pytest.raises(ValueError,match="Conflicting credit assessments"):
        build_trade_ledger([doc],[],[],[],"2026-01-20",[risk1,risk2])


def test_trade_ledger_cli_fixture_is_schema_valid_and_reconciles():
    import json
    from synergy_v7.trade_cli import evaluate_document
    fixture=ROOT/"examples"/"synergy_v7_2_1_trade_ledger_demo.json"
    with fixture.open(encoding="utf-8") as stream:
        document=json.load(stream)
    result=evaluate_document(document)
    assert result["totals_by_side_and_currency"]=={"PAYABLE::USD":30000,"RECEIVABLE::USD":60000}
    ar=result["documents"][0]
    assert ar["disputed_outstanding"]==10000
    buyer=next(x for x in result["counterparty_exposure"] if x["counterparty_id"]=="buyer-01")
    assert buyer["expected_credit_loss"]==pytest.approx(810)


from synergy_v7 import (BankStatementLine, CashAllocation, reconcile_bank_statement)


def test_bank_reconciliation_matches_partial_receipt_to_invoice():
    doc=trade_doc("ar1","RECEIVABLE",1000,"buyer")
    line=BankStatementLine("bank1","usd-account","2026-02-01",600,"USD","ref-1","bank:line:1")
    alloc=CashAllocation("alloc1","bank1","ar1",600,"operator:match:1")
    r=reconcile_bank_statement([doc],[],[line],[alloc],"2026-02-02")
    assert r["fully_reconciled"]
    assert r["trade_ledger"]["documents"][0]["outstanding"]==400
    assert r["currency_control_totals"]["USD"]["allocated_net"]==600


def test_bank_reconciliation_reports_unmatched_residual_without_guessing():
    doc=trade_doc("ar1","RECEIVABLE",1000,"buyer")
    line=BankStatementLine("bank1","usd-account","2026-02-01",700,"USD","ref-1","bank:line:1")
    alloc=CashAllocation("alloc1","bank1","ar1",500,"operator:match:1")
    r=reconcile_bank_statement([doc],[],[line],[alloc],"2026-02-02")
    assert not r["fully_reconciled"]
    assert r["bank_lines"][0]["unmatched_amount"]==200
    assert r["bank_lines"][0]["status"]=="PARTIALLY_RECONCILED"


def test_bank_reconciliation_rejects_overallocation_and_wrong_direction():
    doc=trade_doc("ap1","PAYABLE",1000,"supplier")
    line=BankStatementLine("bank1","usd-account","2026-02-01",500,"USD","ref-1","bank:line:1")
    alloc=CashAllocation("alloc1","bank1","ap1",100,"operator:match:1")
    with pytest.raises(ValueError,match="Inflow cannot settle payable"):
        reconcile_bank_statement([doc],[],[line],[alloc],"2026-02-02")
    ar=trade_doc("ar1","RECEIVABLE",1000,"buyer")
    too_much=CashAllocation("alloc2","bank1","ar1",600,"operator:match:2")
    with pytest.raises(ValueError,match="Allocations exceed"):
        reconcile_bank_statement([ar],[],[line],[too_much],"2026-02-02")


def test_bank_reconciliation_handles_supplier_outflow_and_payable_balance():
    doc=trade_doc("ap1","PAYABLE",900,"supplier")
    line=BankStatementLine("bank1","usd-account","2026-02-01",-300,"USD","ref-1","bank:line:1")
    alloc=CashAllocation("alloc1","bank1","ap1",300,"operator:match:1")
    r=reconcile_bank_statement([doc],[],[line],[alloc],"2026-02-02")
    assert r["fully_reconciled"]
    assert r["trade_ledger"]["documents"][0]["outstanding"]==600
    assert r["currency_control_totals"]["USD"]["allocated_net"]==-300


def test_bank_reconciliation_ignores_future_bank_lines_and_allocations():
    doc=trade_doc("ar1","RECEIVABLE",1000,"buyer")
    line=BankStatementLine("bank1","usd-account","2026-02-01",500,"USD","ref-1","bank:line:1")
    alloc=CashAllocation("alloc1","bank1","ar1",500,"operator:match:1")
    r=reconcile_bank_statement([doc],[],[line],[alloc],"2026-01-31")
    assert r["bank_lines"]==[]
    assert r["trade_ledger"]["documents"][0]["outstanding"]==1000


def test_bank_reconciliation_cli_fixture_is_schema_valid_and_balances_gross_cash():
    import json
    from synergy_v7.reconciliation_cli import evaluate_document
    fixture=ROOT/"examples"/"synergy_v7_2_2_reconciliation_demo.json"
    with fixture.open(encoding="utf-8") as stream:
        document=json.load(stream)
    result=evaluate_document(document)
    assert result["fully_reconciled"]
    assert result["currency_control_totals"]["USD"]["statement_net"]==35000
    assert result["currency_control_totals"]["USD"]["allocated_net"]==35000
    balances={x["document_id"]:x["outstanding"] for x in result["trade_ledger"]["documents"]}
    assert balances=={"AR-FACTORY-001":40000,"AP-FACTORY-001":15000}


def test_bank_reconciliation_rejects_duplicate_statement_and_allocations():
    doc=trade_doc("ar1","RECEIVABLE",1000,"buyer")
    line=BankStatementLine("bank1","account","2026-02-01",500,"USD","ref","bank:1")
    alloc=CashAllocation("alloc1","bank1","ar1",500,"match:1")
    with pytest.raises(ValueError,match="Duplicate bank line"):
        reconcile_bank_statement([doc],[],[line,line],[alloc],"2026-02-02")
    with pytest.raises(ValueError,match="Duplicate cash allocation"):
        reconcile_bank_statement([doc],[],[line],[alloc,alloc],"2026-02-02")


from synergy_v7 import (OutputObservation, DeliveryAcceptance, InvoiceDeliveryAllocation,
    CollectionAttribution, CostObservation, evaluate_realization_chain)


def realization_fixture():
    output=OutputObservation("out1","factory","project1","energy-efficiency","2026-Q1",
      "machine_part",100,80,"unit","PRE_POST","meter:output","OBSERVED")
    delivery=DeliveryAcceptance("del1","out1","buyer","2026-02-01",90,"unit","acceptance:del1")
    invoice=trade_doc("invoice1","RECEIVABLE",9000,"buyer")
    allocation=InvoiceDeliveryAllocation("ial1","del1","invoice1",80,"unit",8000,"USD","erp:invoice-line")
    settlement=SettlementEvent("settle1","invoice1","2026-02-10",5000,"USD","bank-usd","bank:line")
    collection=CollectionAttribution("ca1","settle1","ial1",5000,"USD","bank:allocation")
    costs=[CostObservation("cost1","factory","project1","energy-efficiency","2026-Q1","DIRECT_COST",2000,"USD","erp:cost"),
      CostObservation("cost2","factory","project1","energy-efficiency","2026-Q1","INCREMENTAL_OPEX",500,"USD","erp:opex"),
      CostObservation("cost3","factory","project1","energy-efficiency","2026-Q1","REPLACEMENT_OBLIGATION",300,"USD","asset:replacement")]
    return output,delivery,invoice,allocation,settlement,collection,costs


def test_realization_chain_links_output_acceptance_invoice_and_collected_cash():
    o,d,i,a,s,c,costs=realization_fixture()
    r=evaluate_realization_chain([o],[d],[a],[i],[s],[c],costs,"2026-02-15")
    report=r["benefit_stream_reports"][0]
    assert report["observed_delta_vs_baseline"]==20
    assert report["accepted_quantity"]==90
    assert report["invoiced_quantity"]==80
    assert report["invoiced_amount_by_currency"]["USD"]==8000
    assert report["collected_cash_by_currency"]["USD"]==5000
    assert report["costs_by_currency"]["USD"]["DIRECT_COST"]==2000
    assert report["output_delta_is_not_causal_proof"]


def test_realization_chain_rejects_accepted_delivery_above_observed_output():
    o,d,i,a,s,c,costs=realization_fixture()
    bad=DeliveryAcceptance("del2","out1","buyer","2026-02-01",110,"unit","acceptance:bad")
    with pytest.raises(ValueError,match="exceeds observed output"):
        evaluate_realization_chain([o],[bad],[a],[i],[s],[c],costs,"2026-02-15")


def test_realization_chain_rejects_invoicing_more_than_customer_accepted():
    o,d,i,a,s,c,costs=realization_fixture()
    bad=InvoiceDeliveryAllocation("ial2","del1","invoice1",91,"unit",8000,"USD","erp:bad")
    with pytest.raises(ValueError,match="exceeds accepted delivery"):
        evaluate_realization_chain([o],[d],[bad],[i],[s],[c],costs,"2026-02-15")


def test_realization_chain_rejects_invoice_value_above_invoice_document():
    o,d,i,a,s,c,costs=realization_fixture()
    bad=InvoiceDeliveryAllocation("ial2","del1","invoice1",80,"unit",9500,"USD","erp:bad")
    with pytest.raises(ValueError,match="exceeds document amount"):
        evaluate_realization_chain([o],[d],[bad],[i],[s],[c],costs,"2026-02-15")


def test_realization_chain_rejects_collection_attribution_above_bank_settlement():
    o,d,i,a,s,c,costs=realization_fixture()
    bad=CollectionAttribution("ca2","settle1","ial1",6000,"USD","bank:bad")
    with pytest.raises(ValueError,match="exceeds settlement"):
        evaluate_realization_chain([o],[d],[a],[i],[s],[bad],costs,"2026-02-15")


def test_realization_chain_rejects_collection_attribution_above_invoiced_line():
    o,d,i,a,s,c,costs=realization_fixture()
    bad=CollectionAttribution("ca2","settle1","ial1",8500,"USD","bank:bad")
    settlement=SettlementEvent("settle1","invoice1","2026-02-10",9000,"USD","bank-usd","bank:line")
    with pytest.raises(ValueError,match="exceeds invoice allocation"):
        evaluate_realization_chain([o],[d],[a],[i],[settlement],[bad],costs,"2026-02-15")


def test_realization_chain_rejects_future_delivery_invoicing_and_unknown_links():
    o,d,i,a,s,c,costs=realization_fixture()
    future=DeliveryAcceptance("del2","out1","buyer","2026-03-01",5,"unit","acceptance:future")
    future_allocation=InvoiceDeliveryAllocation("ial2","del2","invoice1",1,"unit",100,"USD","erp:future")
    with pytest.raises(ValueError,match="exceeds accepted delivery"):
        evaluate_realization_chain([o],[future],[future_allocation],[i],[],[],[],"2026-02-15")
    orphan=InvoiceDeliveryAllocation("ial3","missing","invoice1",1,"unit",100,"USD","erp:orphan")
    with pytest.raises(ValueError,match="Unknown delivery"):
        evaluate_realization_chain([o],[d],[orphan],[i],[],[],[],"2026-02-15")


def test_realization_chain_excludes_future_collections_from_cash_metric():
    o,d,i,a,s,c,costs=realization_fixture()
    future=SettlementEvent("future-settle","invoice1","2026-03-01",1000,"USD","bank","bank:future")
    future_attr=CollectionAttribution("future-ca","future-settle","ial1",1000,"USD","bank:future")
    r=evaluate_realization_chain([o],[d],[a],[i],[future],[future_attr],costs,"2026-02-15")
    assert r["benefit_stream_reports"][0]["collected_cash_by_currency"]["USD"]==0


def test_realization_chain_rejects_cost_without_matching_output_group():
    o,d,i,a,s,c,costs=realization_fixture()
    orphan=CostObservation("orphan","factory","other-project","stream","2026-Q1","DIRECT_COST",10,"USD","erp:orphan")
    with pytest.raises(ValueError,match="no matching output"):
        evaluate_realization_chain([o],[d],[a],[i],[s],[c],costs+[orphan],"2026-02-15")


def test_realization_chain_cli_fixture_is_schema_valid_and_reproducible():
    import json
    from synergy_v7.realization_cli import evaluate_document
    fixture=ROOT/"examples"/"synergy_v7_3_realization_chain_demo.json"
    with fixture.open(encoding="utf-8") as stream:
        document=json.load(stream)
    r=evaluate_document(document)
    report=r["benefit_stream_reports"][0]
    assert report["observed_delta_vs_baseline"]==20
    assert report["invoiced_amount_by_currency"]["USD"]==8000
    assert report["collected_cash_by_currency"]["USD"]==5000
    assert report["costs_by_currency"]["USD"]["REPLACEMENT_OBLIGATION"]==300


from synergy_v7 import CausalObservation, matched_pair_difference_in_differences


def did_fixture():
    rows=[]
    effects=[5,4,6,5]
    for idx,effect in enumerate(effects):
        pair=f"pair{idx}"
        rows.extend([
          CausalObservation(f"{pair}-tp",pair,f"treated-{idx}","TREATED","PRE",100,"meter:t0"),
          CausalObservation(f"{pair}-tq",pair,f"treated-{idx}","TREATED","POST",110+effect,"meter:t1"),
          CausalObservation(f"{pair}-cp",pair,f"control-{idx}","CONTROL","PRE",90,"meter:c0"),
          CausalObservation(f"{pair}-cq",pair,f"control-{idx}","CONTROL","POST",100,"meter:c1")])
    return rows


def test_matched_pair_did_estimates_average_treatment_effect():
    r=matched_pair_difference_in_differences(did_fixture())
    assert r["matched_pair_count"]==4
    assert r["effect_estimate"]==pytest.approx(5)
    assert r["beneficial_effect_estimate"]==pytest.approx(5)
    assert r["confidence_interval"][0]<=5<=r["confidence_interval"][1]
    assert r["parallel_trends_testable_with_one_pre_period"] is False


def test_matched_pair_did_reverses_benefit_sign_for_lower_is_better():
    r=matched_pair_difference_in_differences(did_fixture(),0.95,"LOWER_IS_BETTER")
    assert r["effect_estimate"]==pytest.approx(5)
    assert r["beneficial_effect_estimate"]==pytest.approx(-5)


def test_matched_pair_did_rejects_incomplete_and_duplicate_observations():
    rows=did_fixture()
    with pytest.raises(ValueError,match="Incomplete"):
        matched_pair_difference_in_differences(rows[:-1])
    with pytest.raises(ValueError,match="Duplicate observation"):
        matched_pair_difference_in_differences(rows+[rows[0]])


def test_matched_pair_did_rejects_changed_unit_identity():
    rows=did_fixture()
    rows[1]=CausalObservation("pair0-tq","pair0","different-treated","TREATED","POST",115,"meter:t1")
    with pytest.raises(ValueError,match="identity"):
        matched_pair_difference_in_differences(rows)


def test_matched_pair_did_requires_multiple_pairs_and_valid_confidence():
    rows=did_fixture()[:4]
    with pytest.raises(ValueError,match="At least two"):
        matched_pair_difference_in_differences(rows)
    with pytest.raises(ValueError,match="confidence_level"):
        matched_pair_difference_in_differences(did_fixture(),1.0)


def test_matched_pair_did_cli_fixture_is_schema_valid_and_returns_expected_effect():
    import json
    from synergy_v7.causal_cli import evaluate_document
    fixture=ROOT/"examples"/"synergy_v7_3_1_matched_did_demo.json"
    with fixture.open(encoding="utf-8") as stream:
        document=json.load(stream)
    r=evaluate_document(document)
    assert r["matched_pair_count"]==4
    assert r["effect_estimate"]==pytest.approx(5)


from synergy_v7 import PlanDemand, optimize_production_schedule


def test_v74_milp_optimizer_finds_feasible_integrated_factory_schedule():
    recipes=[
      ProductionRecipe("smelt","steel",80,"kg",(MaterialRequirement("ore",100,"kg"),),
        (ResourceRequirement("electricity",40,"MWh"),),1),
      ProductionRecipe("machine","machine_part",4,"unit",(MaterialRequirement("steel",20,"kg"),),
        (ResourceRequirement("electricity",10,"MWh"),),1)]
    demands=[PlanDemand("customer","machine_part",12,"unit",2,100,"USD")]
    receipts=[InventoryReceipt("ore1","ore",100,"kg",0,"OBSERVED")]
    caps=[ResourceCapacity("electricity","0",40,"MWh","OBSERVED","meter:p0"),
      ResourceCapacity("electricity","1",30,"MWh","OBSERVED","meter:p1")]
    r=optimize_production_schedule(recipes,demands,receipts,caps,3,
      {"smelt":1,"machine":3},{"smelt":10,"machine":5},{"steel":0.1},"USD")
    assert r["feasible"] and r["optimality_proven"]
    assert r["demand"][0]["fulfilled"]==12
    assert {x["recipe_id"]:x["batch_count"] for x in r["schedule"]}=={"smelt":1,"machine":3}
    assert r["resource_usage"][0]["used"]==40
    assert r["objective_value"]==pytest.approx(1171)


def test_v74_milp_optimizer_respects_shared_resource_scarcity():
    recipe=ProductionRecipe("machine","parts",1,"unit",(),
      (ResourceRequirement("power",10,"MWh"),),1)
    demand=[PlanDemand("d1","parts",2,"unit",1,100,"USD")]
    caps=[ResourceCapacity("power","0",10,"MWh","OBSERVED","meter")]
    r=optimize_production_schedule([recipe],demand,[],caps,2,{"machine":2},{"machine":1})
    assert r["feasible"]
    assert r["demand"][0]["fulfilled"]==1
    assert r["resource_usage"][0]["used"]==10


def test_v74_milp_optimizer_excludes_nonfirm_inventory_and_capacity():
    recipe=ProductionRecipe("r","finished",1,"unit",(MaterialRequirement("raw",1,"kg"),),
      (ResourceRequirement("power",1,"MWh"),),1)
    demand=[PlanDemand("d1","finished",1,"unit",1,100,"USD")]
    receipts=[InventoryReceipt("i1","raw",1,"kg",0,"PLANNED")]
    caps=[ResourceCapacity("power","0",1,"MWh","PLANNED","plan")]
    r=optimize_production_schedule([recipe],demand,receipts,caps,2,{"r":1})
    assert r["feasible"] and r["schedule"]==[]
    assert r["demand"][0]["fulfilled"]==0
    assert r["excluded_nonfirm_receipts"]==["i1"]


def test_v74_milp_optimizer_does_not_produce_when_economic_value_is_below_cost():
    recipe=ProductionRecipe("r","finished",1,"unit",(),(),1)
    demand=[PlanDemand("d1","finished",10,"unit",1,1,"USD")]
    r=optimize_production_schedule([recipe],demand,[],[],2,{"r":10},{"r":100})
    assert r["feasible"] and r["schedule"]==[]
    assert r["demand"][0]["fulfilled"]==0


def test_v74_milp_optimizer_rejects_missing_limits_and_unit_mismatch():
    recipe=ProductionRecipe("r","finished",1,"unit",(),(ResourceRequirement("power",1,"MWh"),),1)
    demand=[PlanDemand("d1","finished",1,"unit",1,10,"USD")]
    with pytest.raises(ValueError,match="batch_limits"):
        optimize_production_schedule([recipe],demand,[],[],2,{})
    caps=[ResourceCapacity("power","0",1,"kWh","OBSERVED","meter")]
    with pytest.raises(ValueError,match="unit mismatch"):
        optimize_production_schedule([recipe],demand,[],caps,2,{"r":1})


def test_v74_milp_cli_fixture_is_schema_valid_and_reproducible():
    import json
    from synergy_v7.planner_cli import evaluate_document
    fixture=ROOT/"examples"/"synergy_v7_4_milp_factory_plan.json"
    with fixture.open(encoding="utf-8") as stream:
        document=json.load(stream)
    r=evaluate_document(document)
    assert r["feasible"] and r["optimality_proven"]
    assert r["demand"][0]["fulfilled"]==12
    assert r["objective_value"]==pytest.approx(1171)


def test_v74_milp_optimizer_rejects_non_numeric_capacity_period():
    recipe=ProductionRecipe("r","finished",1,"unit",(),(ResourceRequirement("power",1,"MWh"),),1)
    demand=[PlanDemand("d1","finished",1,"unit",1,10,"USD")]
    cap=[ResourceCapacity("power","2026-Q1",10,"MWh","OBSERVED","meter")]
    with pytest.raises(ValueError,match="integer bucket"):
        optimize_production_schedule([recipe],demand,[],cap,2,{"r":1})
