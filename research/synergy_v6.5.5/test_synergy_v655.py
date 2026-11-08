import unittest
import numpy as np
from synergy_v655_kernel import make_net, simulate, POLICIES

class SelfHealingTests(unittest.TestCase):
    def test_topology_indices_and_no_self_supplier(self):
        sec, sup = make_net(17)
        self.assertEqual(sup.shape, (80, 2))
        self.assertTrue(np.all((sup >= 0) & (sup < 80)))
        self.assertTrue(all(i not in sup[i] for i in range(80)))

    def test_repeatability(self):
        a = simulate(12, "systemic", "network_optimizer")
        b = simulate(12, "systemic", "network_optimizer")
        for key in ("defaults", "external_sales", "production_lost", "recovery_days"):
            self.assertAlmostEqual(a[key], b[key])

    def test_pool_conservation(self):
        for policy in POLICIES:
            r = simulate(5, "systemic", policy)
            self.assertAlmostEqual(
                r["repair_spend"] + r["liquidity_transfers"] + r["capital_remaining"],
                180.0, places=7
            )

    def test_default_bounds_and_survival_identity(self):
        r = simulate(9, "severe", "liquidity_first")
        self.assertGreaterEqual(r["defaults"], 0)
        self.assertLessEqual(r["defaults"], 80)
        self.assertAlmostEqual(r["survival_rate"], 1-r["defaults"]/80)

    def test_finite_nonnegative_production_metrics(self):
        r = simulate(22, "systemic", "random_rescue")
        for key in ("external_sales", "production", "production_lost", "operating_surplus"):
            self.assertTrue(np.isfinite(r[key]))
        self.assertGreaterEqual(r["external_sales"], 0)
        self.assertGreaterEqual(r["production"], 0)
        self.assertGreaterEqual(r["production_lost"], 0)

    def test_all_policies_and_regimes_execute(self):
        for regime in ("severe", "systemic"):
            for policy in POLICIES:
                r = simulate(3, regime, policy)
                self.assertIn("recovery_ratio", r)
                self.assertGreaterEqual(r["recovery_days"], 0)
                self.assertLessEqual(r["recovery_days"], 70)

if __name__ == "__main__":
    unittest.main()
