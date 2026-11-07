from synergy_v66.compatibility import POLICIES, make_environment, run_paired, simulate


def test_environment_is_deterministic():
    assert make_environment(17, "severe", 12) == make_environment(17, "severe", 12)


def test_all_policies_share_same_environment_and_conserve_cash():
    report = run_paired(seed=17, regime="severe", days=30)
    assert len(report["paired_environment_hash"]) == 64
    assert {row["policy"] for row in report["policies"]} == set(POLICIES)
    for row in report["policies"]:
        assert abs(row["conservation_error"]) < 1e-7
        assert row["internal_transfer_net_at_system_level"] == 0.0
        assert row["closing_cash"] >= -1e-9
        assert row["output_units"] >= 0
        assert row["unmet_demand_units"] >= -1e-9


def test_same_policy_and_environment_replay_identically():
    env = make_environment(123, "volatile", 20)
    assert simulate("market", env) == simulate("market", env)


def test_invalid_regime_and_policy_are_rejected():
    try:
        make_environment(1, "imaginary")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid regime must fail")
    try:
        simulate("magic", make_environment(1, "normal", 2))
    except ValueError:
        pass
    else:
        raise AssertionError("invalid policy must fail")
