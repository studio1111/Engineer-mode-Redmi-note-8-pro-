import unittest

from agent import redact, validate_task, build_report


class AgentSafetyTests(unittest.TestCase):
    def test_redacts_common_subscriber_identifiers(self):
        text = "IMEI: 123456789012345 IMSI=310260123456789 ICCID: 89014103211118510720"
        result = redact(text)
        self.assertNotIn("123456789012345", result)
        self.assertNotIn("310260123456789", result)
        self.assertNotIn("89014103211118510720", result)
        self.assertIn("[REDACTED]", result)

    def test_only_known_read_only_tasks_are_accepted(self):
        self.assertTrue(validate_task("inventory"))
        self.assertTrue(validate_task("radio"))
        self.assertFalse(validate_task("set_world_mode"))
        self.assertFalse(validate_task("shell"))

    def test_report_has_schema_and_task_status(self):
        report = build_report("inventory", "ok", "device=begonia")
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["task"], "inventory")
        self.assertEqual(report["status"], "ok")
        self.assertIn("generated_at", report)


if __name__ == "__main__":
    unittest.main()
