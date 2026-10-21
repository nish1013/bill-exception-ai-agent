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
  // psql reads the variables only from a script, not from -c.
  const psql = ["exec", "-T", "postgres", "psql", "-U", "payables", "-d", "payables"];
  const variables = ["-v", "ON_ERROR_STOP=1", "-v", `tenant=${tenant.id}`, "-v", `count=${count}`];
  compose([...psql, ...variables, "-f", "-"], FILL_QUOTA_SLOTS);
}
