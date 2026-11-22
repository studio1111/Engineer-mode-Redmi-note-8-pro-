import { createClient } from "npm:@supabase/supabase-js@2";

const corsHeaders = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
};

function reply(status: number, body: unknown = null): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: corsHeaders,
  });
}

function hex(bytes: Uint8Array): string {
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return hex(new Uint8Array(digest));
}

Deno.serve(async (req: Request) => {
  if (req.method !== "GET" && req.method !== "POST") return reply(405, { error: "method_not_allowed" });

  const url = new URL(req.url);
  const action = url.pathname.split("/").filter(Boolean).pop();
  if (action !== "poll" && action !== "complete") return reply(404, { error: "not_found" });

  const deviceId = req.headers.get("x-device-id") ?? "";
  const authorization = req.headers.get("authorization") ?? "";
  const token = authorization.startsWith("Bearer ") ? authorization.slice(7) : "";
  if (!/^[0-9a-f-]{36}$/i.test(deviceId) || token.length < 40 || token.length > 256) {
    return reply(401, { error: "unauthorized" });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceKey) return reply(503, { error: "relay_not_configured" });

  const db = createClient(supabaseUrl, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  const { data: authorized, error: authError } = await db.rpc("relay_auth_device", {
    p_device_id: deviceId,
    p_token_sha256: await sha256(token),
  });
  if (authError || authorized !== true) return reply(401, { error: "unauthorized" });

  if (action === "poll") {
    if (req.method !== "GET") return reply(405, { error: "method_not_allowed" });
    const { data, error } = await db.rpc("relay_claim_command", { p_device_id: deviceId });
    if (error) return reply(503, { error: "queue_unavailable" });
    const command = Array.isArray(data) ? data[0] : null;
    return command ? reply(200, { command }) : reply(204);
  }

  if (req.method !== "POST") return reply(405, { error: "method_not_allowed" });
  let body: Record<string, unknown>;
  try {
    const raw = await req.text();
    if (raw.length > 65536) return reply(413, { error: "payload_too_large" });
    body = JSON.parse(raw);
  } catch {
    return reply(400, { error: "invalid_json" });
  }

  const commandId = typeof body.command_id === "string" ? body.command_id : "";
  const status = typeof body.status === "string" ? body.status : "";
  const result = body.result && typeof body.result === "object" ? body.result : {};
  if (!/^[0-9a-f-]{36}$/i.test(commandId) || !["ok","error","timeout","unavailable"].includes(status)) {
    return reply(400, { error: "invalid_completion" });
  }

  const { data, error } = await db.rpc("relay_complete_command", {
    p_device_id: deviceId,
    p_command_id: commandId,
    p_status: status,
    p_result: result,
  });
  if (error) return reply(503, { error: "completion_unavailable" });
  return data === true ? reply(200, { accepted: true }) : reply(409, { error: "command_not_claimed_or_expired" });
});
