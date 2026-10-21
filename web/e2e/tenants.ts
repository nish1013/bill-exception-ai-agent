export interface Tenant {
  id: string;
  name: string;
}

export interface SpecTenants {
  home: Tenant;
  other: Tenant;
}

function specTenants(spec: number, label: string): SpecTenants {
  const id = (n: number) => `e2e00000-0000-4000-8000-${String(spec * 10 + n).padStart(12, "0")}`;
  return {
    home: { id: id(1), name: `E2E ${label} home` },
    other: { id: id(2), name: `E2E ${label} other` },
  };
}

// Each spec writes only to its own tenants, so the specs run in parallel on one stack.
export const SPEC_TENANTS = {
  auth: specTenants(1, "auth"),
  checkSlice: specTenants(2, "check slice"),
  rulesIgnore: specTenants(3, "rules ignore"),
} satisfies Record<string, SpecTenants>;

export const ALL_SPEC_TENANTS: Tenant[] = Object.values(SPEC_TENANTS).flatMap((t) => [
  t.home,
  t.other,
]);
