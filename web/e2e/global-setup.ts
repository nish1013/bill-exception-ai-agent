import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { ALL_SPEC_TENANTS } from "./tenants";

const REPO_ROOT = fileURLToPath(new URL("../..", import.meta.url));

// Tenants are created outside the product, so the specs create theirs with the owner role.
export default function globalSetup(): void {
  const items = ALL_SPEC_TENANTS.map((tenant) => `${tenant.id}=${tenant.name}`);
  execFileSync(
    "docker",
    ["compose", "exec", "-T", "api", "python", "manage.py", "create_tenants", ...items],
    { cwd: REPO_ROOT, stdio: "inherit" },
  );
}
