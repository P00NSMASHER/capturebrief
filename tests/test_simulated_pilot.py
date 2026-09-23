import unittest

from scripts.run_simulated_pilot import run_simulation


class SimulatedPilotTests(unittest.TestCase):
    def test_fictional_customer_matrix_and_delivery_path_pass(self):
        report = run_simulation()
        self.assertTrue(report["simulated"])
        self.assertTrue(report["not_customer_evidence"])
        self.assertEqual(report["customers_tested"], 12)
        self.assertEqual(report["intake_outcomes"], {
            "ACCEPTED_FOR_REVIEW": 6,
            "REFUND_BEFORE_WORK": 4,
            "DECLINED_BEFORE_PAYMENT": 2,
        })
        self.assertEqual(report["golden_delivery_check"]["file_count"], 7)
        self.assertFalse(report["golden_delivery_check"]["external_send_authorized"])
        self.assertTrue(report["passed"], report["failures"])


if __name__ == "__main__":
    unittest.main()
