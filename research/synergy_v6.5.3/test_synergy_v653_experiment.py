
import unittest
import numpy as np
from synergy_v653_experiment import simulate_three_policies, CONC

class TestSynergyV653(unittest.TestCase):
    def test_deterministic_replay(self):
        w=np.asarray(CONC["top50pct_10"])
        a=simulate_three_policies(123,0.05,0.30,0.005,w)
        b=simulate_three_policies(123,0.05,0.30,0.005,w)
        self.assertEqual(a,b)

    def test_zero_default_has_no_bad_debt(self):
        r=simulate_three_policies(123,0.0,0.30,0.005,np.asarray([1.0]))
        self.assertAlmostEqual(r["baseline_bad_debt"],0.0,places=8)

    def test_cash_gap_nonnegative(self):
        r=simulate_three_policies(123,0.05,0.30,0.005,np.asarray([1.0]))
        self.assertGreaterEqual(r["baseline_gap"],0.0)
        self.assertGreaterEqual(r["earlypay_gap"],0.0)
        self.assertGreaterEqual(r["factoring_gap"],0.0)

    def test_accelerated_policies_reduce_gap(self):
        r=simulate_three_policies(123,0.05,0.30,0.005,np.asarray([1.0]))
        self.assertLessEqual(r["earlypay_gap"],r["baseline_gap"]+1e-8)
        self.assertLessEqual(r["factoring_gap"],r["baseline_gap"]+1e-8)

    def test_fee_reduces_factoring_profit(self):
        w=np.asarray([1.0])
        a=simulate_three_policies(123,0.05,0.30,0.0,w)
        b=simulate_three_policies(123,0.05,0.30,0.01,w)
        self.assertGreater(a["factoring_profit"],b["factoring_profit"])

    def test_recovery_reduces_baseline_bad_debt(self):
        w=np.asarray([1.0])
        a=simulate_three_policies(123,0.05,0.10,0.0,w)
        b=simulate_three_policies(123,0.05,0.90,0.0,w)
        self.assertGreaterEqual(a["baseline_bad_debt"],b["baseline_bad_debt"])

if __name__=="__main__":
    unittest.main()
