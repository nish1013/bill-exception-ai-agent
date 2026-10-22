import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import type { Tenant } from "./tenants";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));

// Rows that only the owner can write: tenants, and quota slots used earlier in the day.
const FILL_QUOTA_SLOTS = `
INSERT INTO proposal (id, tenant_id, requested_by, status, quota_day, quota_slot, created_at,
                      updated_at)
SELECT gen_random_uuid(), :'tenant', 'seed', 'pending', (now() AT TIME ZONE 'UTC')::date, slot,
       now(), now()
FROM generate_series(1, :count) AS slot;`;

// The demo accounting stub answers each tenant by its stub_mode row (D51).
const SET_STUB_MODE = `
INSERT INTO stub_mode (tenant_id, mode) VALUES (:'tenant', :'mode')
ON CONFLICT (tenant_id) DO UPDATE SET mode = EXCLUDED.mode;`;

function compose(args: string[], input?: string): void {
  execFileSync("docker", ["compose", ...args], {
    cwd: REPO_ROOT,
    input,
    stdio: [input === undefined ? "inherit" : "pipe", "inherit", "inherit"],
  });
}

export function createTenants(tenants: Tenant[]): void {
  const items = tenants.map((tenant) => `${tenant.id}=${tenant.name}`);
  compose(["exec", "-T", "api", "python", "manage.py", "create_tenants", ...items]);
}

export function fillQuotaSlots(tenant: Tenant, count: number): void {
  psql(FILL_QUOTA_SLOTS, { tenant: tenant.id, count: String(count) });
}

export function setStubMode(tenant: Tenant, mode: "ok" | "fail" | "callback"): void {
  psql(SET_STUB_MODE, { tenant: tenant.id, mode });
}

// psql reads the variables only from a script, not from -c.
function psql(script: string, variables: Record<string, string>): void {
  const command = ["exec", "-T", "postgres", "psql", "-U", "payables", "-d", "payables"];
  const options = Object.entries(variables).flatMap(([name, value]) => ["-v", `${name}=${value}`]);
  compose([...command, "-v", "ON_ERROR_STOP=1", ...options, "-f", "-"], script);
}
