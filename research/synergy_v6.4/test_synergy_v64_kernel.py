"""Tests for the SYNERGY V6.4 research kernel."""
import unittest
import synergy_v64_kernel as k


class TestFIFO(unittest.TestCase):
    def test_fifo_consumes_oldest_lot_first(self):
        inv = k.FIFOInventory()
        inv.add(2.0, 1.0)
        inv.add(3.0, 2.0)
        self.assertAlmostEqual(inv.consume(3.0), 4.0)
        self.assertAlmostEqual(inv.quantity, 2.0)
        self.assertAlmostEqual(inv.book_value, 4.0)

    def test_inventory_underflow_is_rejected(self):
        inv = k.FIFOInventory()
        inv.add(1.0, 1.0)
        with self.assertRaises(ValueError):
            inv.consume(1.1)


class TestSimulationInvariants(unittest.TestCase):
    def test_cash_conservation_and_nonnegative_balances(self):
        for regime in ("normal", "volatile", "severe"):
            for seed in range(20):
                env = k.make_environment(7000 + seed, regime)
                for policy in ("independent", "market", "dao", "ca", "hybrid"):
                    result = k.simulate(policy, env, final_price=15.0, return_trace=True)
                    self.assertLess(abs(result["conservation_error"]), 1e-7)
                    self.assertGreaterEqual(min(result["cash_by_node"].values()), -1e-9)
                    self.assertGreaterEqual(result["inventory_qty"], -1e-9)
                    self.assertAlmostEqual(result["fifo_qty_in"], result["fifo_qty_out"], places=7)
                    self.assertGreaterEqual(result["fixed_arrears"], -1e-9)

    def test_seed_is_deterministic(self):
        env = k.make_environment(99123, "severe")
        first = k.simulate("market", env, final_price=15.0, return_trace=True)
        second = k.simulate("market", env, final_price=15.0, return_trace=True)
        self.assertEqual(first["sales"], second["sales"])
        self.assertEqual(first["final_cash"], second["final_cash"])
        self.assertEqual(first["trace"], second["trace"])

    def test_environment_is_paired_across_policies(self):
        env = k.make_environment(333, "volatile")
        results = [k.simulate(p, env, final_price=15.0) for p in
                   ("independent", "market", "dao", "ca", "hybrid")]
        self.assertEqual(len({r["initial_cash"] for r in results}), 1)


if __name__ == "__main__":
    unittest.main()
