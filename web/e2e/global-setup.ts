import { createTenants } from "./compose";
import { ALL_SPEC_TENANTS } from "./tenants";

// Tenants are created outside the product, so the specs create theirs with the owner role.
export default function globalSetup(): void {
  createTenants(ALL_SPEC_TENANTS);
}
