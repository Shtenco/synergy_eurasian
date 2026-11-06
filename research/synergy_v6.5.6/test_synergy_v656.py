import unittest
from synergy_v656_kernel import run_path, POLICIES, topology
import numpy as np
class V656Tests(unittest.TestCase):
    def test_topology(self):
        s,p=topology(1); self.assertEqual(p.shape,(80,2)); self.assertTrue(np.all((p>=0)&(p<80)))
        self.assertTrue(all(i not in p[i] for i in range(80)))
    def test_reproducibility(self):
        a=run_path(7,"systemic","cvar_robust"); b=run_path(7,"systemic","cvar_robust")
        self.assertEqual(a,b)
    def test_pool_conservation(self):
        for pol in POLICIES:
            r=run_path(4,"systemic",pol)
            self.assertAlmostEqual(r["repair_cost"]+r["liquidity_support"]+r["reserve_remaining"],180.,places=7)
    def test_bounds(self):
        r=run_path(3,"severe","network_greedy")
        self.assertTrue(0<=r["defaults"]<=80)
        self.assertAlmostEqual(r["survival_rate"],1-r["defaults"]/80)
    def test_nonnegative_output(self):
        r=run_path(9,"systemic","rolling_horizon")
        self.assertGreaterEqual(r["external_gross_sales"],0); self.assertGreaterEqual(r["production"],0)
    def test_policy_regime_coverage(self):
        for rg in ("severe","systemic"):
            for pol in POLICIES:
                self.assertIn("recovery_days",run_path(2,rg,pol))
if __name__=="__main__": unittest.main()
