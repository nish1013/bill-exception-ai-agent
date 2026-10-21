import { UserManager, WebStorageStateStore } from "oidc-client-ts";

import { consoleConfig } from "../config";

export const CALLBACK_PATH = "/callback";

export const userManager = new UserManager({
  authority: consoleConfig.oidcAuthority,
  client_id: consoleConfig.oidcClientId,
  redirect_uri: `${window.location.origin}${CALLBACK_PATH}`,
  response_type: "code",
  scope: "openid",
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
  automaticSilentRenew: false,
  loadUserInfo: false,
});
