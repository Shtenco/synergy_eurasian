
import unittest
import numpy as np
from synergy_v654_kernel import simulate, N

class TestV654(unittest.TestCase):
    def test_deterministic_replay(self):
        a=simulate(123,"systemic","adaptive_synergy",100,100)
        b=simulate(123,"systemic","adaptive_synergy",100,100)
        self.assertEqual(a,b)

    def test_default_count_within_network_size(self):
        r=simulate(123,"moderate","isolated")
        self.assertGreaterEqual(r["defaults"],0)
        self.assertLessEqual(r["defaults"],N)

    def test_prefunded_transfers_do_not_exceed_capital(self):
        r=simulate(123,"systemic","adaptive_synergy",100,100)
        self.assertLessEqual(r["pool_transfers"],200+1e-8)

    def test_no_negative_remaining_pool(self):
        r=simulate(456,"systemic","adaptive_synergy",100,100)
        self.assertGreaterEqual(r["pool_remaining"],-1e-8)
        self.assertGreaterEqual(r["reserve_remaining"],-1e-8)

    def test_survival_bounds(self):
        r=simulate(789,"severe","firewall")
        self.assertGreaterEqual(r["survival_rate"],0)
        self.assertLessEqual(r["survival_rate"],1)

    def test_financial_outputs_finite(self):
        r=simulate(321,"systemic","liquidity_pool",100,0)
        for key in ("external_sales","operating_surplus","pool_transfers","pool_remaining"):
            self.assertTrue(np.isfinite(r[key]))

if __name__=="__main__":
    unittest.main()
