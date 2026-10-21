export interface ConsoleConfig {
  oidcAuthority: string;
  oidcClientId: string;
}

// A public client with PKCE: the bundle holds no client secret.
export const consoleConfig: ConsoleConfig = {
  oidcAuthority: import.meta.env.VITE_OIDC_AUTHORITY ?? "http://localhost:8080/payables",
  oidcClientId: import.meta.env.VITE_OIDC_CLIENT_ID ?? "payables-console",
};
