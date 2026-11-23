import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "supabase/migrations/202611230001_relay.sql").read_text()
AUDIT_MIGRATION = (ROOT / "supabase/migrations/202611240001_read_only_audit_tasks_and_expiry.sql").read_text()
EDGE = (ROOT / "supabase/functions/device-relay/index.ts").read_text()


class RelaySecurityTests(unittest.TestCase):
    def test_private_tables_are_not_granted_to_client_roles(self):
        self.assertIn("alter table private.relay_devices enable row level security", MIGRATION)
        self.assertIn("alter table private.relay_commands enable row level security", MIGRATION)
        self.assertIn("revoke all on schema private from public, anon, authenticated", MIGRATION)
        self.assertIn("revoke all on all tables in schema private from public, anon, authenticated, service_role", MIGRATION)

    def test_rpc_execution_is_limited_to_service_role(self):
        self.assertIn("grant execute on function public.relay_auth_device(uuid,text) to service_role", MIGRATION)
        self.assertIn("grant execute on function public.relay_claim_command(uuid) to service_role", MIGRATION)
        self.assertIn("grant execute on function public.relay_complete_command(uuid,uuid,text,jsonb) to service_role", MIGRATION)
        self.assertNotIn("to anon", MIGRATION.lower())
        self.assertNotIn("to authenticated", MIGRATION.lower())

    def test_edge_function_uses_per_device_authentication(self):
        self.assertIn("x-device-id", EDGE.lower())
        self.assertIn('authorization', EDGE.lower())
        self.assertIn('relay_auth_device', EDGE)
        self.assertIn('relay_claim_command', EDGE)
        self.assertIn('relay_complete_command', EDGE)
        self.assertIn('crypto.subtle.digest', EDGE)

    def test_edge_function_does_not_accept_shell_payload(self):
        self.assertNotIn("shell_command", EDGE)
        self.assertNotIn("exec(", EDGE)
        self.assertNotIn("Deno.Command", EDGE)

    def test_database_allowlist_includes_every_fixed_read_only_audit_task(self):
        expected = {
            "inventory", "telephony", "radio", "source", "connectivity",
            "engineermode_audit", "worldmode_audit", "band_audit",
            "ril_audit", "network_audit", "component_audit", "safety_audit",
        }
        for task in expected:
            with self.subTest(task=task):
                self.assertIn(f"'{task}'", AUDIT_MIGRATION)
        self.assertIn("check (task in (", AUDIT_MIGRATION)

    def test_claim_function_expires_stale_pending_and_claimed_commands(self):
        self.assertIn("status in ('pending', 'claimed')", AUDIT_MIGRATION)
        self.assertIn("expires_at <= now()", AUDIT_MIGRATION)
        self.assertIn("status = 'expired'", AUDIT_MIGRATION)


if __name__ == "__main__":
    unittest.main()
