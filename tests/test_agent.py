import signal
import subprocess
import unittest
from unittest.mock import patch

from agent import ALLOWED_TASKS, TASK_COMMANDS, MAX_OUTPUT, redact, validate_task, build_report, collect


class AgentSafetyTests(unittest.TestCase):
    def test_redacts_common_subscriber_identifiers(self):
        text = (
            "IMEI: 123456789012345 IMSI=310260123456789 "
            "ICCID: 89014103211118510720"
        )
        result = redact(text)
        self.assertNotIn("123456789012345", result)
        self.assertNotIn("310260123456789", result)
        self.assertNotIn("89014103211118510720", result)
        self.assertIn("[REDACTED]", result)

    def test_redacts_labeled_phone_numbers(self):
        result = redact("subscriber number: +4915112345678")
        self.assertNotIn("4915112345678", result)
        self.assertIn("[REDACTED]", result)

    def test_only_fixed_read_only_tasks_are_accepted(self):
        self.assertTrue(
            {"inventory", "telephony", "radio", "source", "connectivity", "engineermode_audit"}
            .issubset(ALLOWED_TASKS)
        )
        self.assertTrue(validate_task("inventory"))
        self.assertTrue(validate_task("radio"))
        self.assertTrue(validate_task("engineermode_audit"))
        self.assertFalse(validate_task("set_world_mode"))
        self.assertFalse(validate_task("shell"))
        self.assertFalse(validate_task("rm -rf /"))

    def test_inventory_collects_both_worldmode_properties_read_only(self):
        command = " ".join(TASK_COMMANDS["inventory"])
        self.assertIn("getprop vendor.ril.active.md", command)
        self.assertIn("getprop vendor.ril.nw.worldmode.activemode", command)
        self.assertIn("WORLD MODE PROPERTIES", command)
        self.assertNotIn("setprop", command)

    def test_radio_collector_captures_engineermode_worldmode_events(self):
        command = " ".join(TASK_COMMANDS["radio"])
        self.assertIn("logcat -b all", command)
        for marker in (
            "mBandMode",
            "checkWmCapab",
            "setWorldModeWithBand",
            "EPBSE",
            "WorldMode",
            "BandSelect",
        ):
            self.assertIn(marker, command)

    def test_engineermode_audit_is_scoped_read_only_and_covers_component_flow(self):
        command = " ".join(TASK_COMMANDS["engineermode_audit"])
        for marker in (
            "WorldModeUtil.java",
            "WorldModeActivity.java",
            "BandSelect.java",
            "BandModeContent.java",
            "ModemSwitch.java",
            "RadioStateManager.java",
            "EmRadioHidl.java",
            "MtkRadioResponseBase.java",
            "MtkRadioIndication.java",
            "CROSS-COMPONENT REFERENCES",
            "MANIFEST COMPONENTS",
        ):
            self.assertIn(marker, command)
        self.assertNotIn("setprop", command)
        self.assertNotIn("reboot ", command)
        self.assertNotIn("reboot;", command)

    def test_rish_collectors_start_outside_termux_private_home_and_in_own_process_group(self):
        process = unittest.mock.Mock()
        process.communicate.return_value = ("radio-log", "")
        process.returncode = 0
        with patch("agent.subprocess.Popen", return_value=process) as popen:
            status, output = collect("radio")

        self.assertEqual(status, "ok")
        self.assertEqual(output, "radio-log")
        self.assertEqual(popen.call_args.kwargs["cwd"], "/")
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    def test_timeout_kills_entire_collector_process_group(self):
        process = unittest.mock.Mock()
        timeout = subprocess.TimeoutExpired(cmd="rish", timeout=25)
        process.communicate.side_effect = [timeout, timeout, ("", "")]
        process.pid = 4242
        with patch("agent.subprocess.Popen", return_value=process), patch("agent.os.killpg") as killpg:
            status, output = collect("radio")

        self.assertEqual(status, "timeout")
        self.assertIn("Collection exceeded", output)
        self.assertEqual(killpg.call_args_list[0].args, (4242, signal.SIGTERM))
        self.assertEqual(killpg.call_args_list[1].args, (4242, signal.SIGKILL))

    def test_report_has_schema_and_task_status(self):
        report = build_report("inventory", "ok", "device=begonia")
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["task"], "inventory")
        self.assertEqual(report["status"], "ok")
        self.assertTrue(report["read_only"])
        self.assertIn("generated_at", report)


    def test_report_marks_output_truncation_explicitly(self):
        report = build_report("source", "ok", "x" * (MAX_OUTPUT + 10))
        self.assertTrue(report["truncated"])
        self.assertEqual(len(report["output"]), MAX_OUTPUT)
        self.assertEqual(report["output_length"], MAX_OUTPUT + 10)

    def test_focused_audit_tasks_are_fixed_and_read_only(self):
        expected = {
            "worldmode_audit", "band_audit", "ril_audit",
            "network_audit", "component_audit", "safety_audit",
        }
        self.assertTrue(expected.issubset(ALLOWED_TASKS))
        for task in expected:
            self.assertTrue(validate_task(task), task)
            command = " ".join(TASK_COMMANDS[task]).lower()
            self.assertNotIn("setprop ", command)
            self.assertNotIn("reboot ", command)
            self.assertNotIn("dd if=", command)
            self.assertNotIn("dd of=", command)

if __name__ == "__main__":
    unittest.main()
