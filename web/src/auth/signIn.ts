import type { User } from "oidc-client-ts";

import { currentPath, safeReturnPath } from "./returnPath";
import { CALLBACK_PATH, userManager } from "./userManager";

let pending: Promise<User | null> | undefined;

// React runs effects twice in development. One callback may use the code only once.
export function resolveUser(): Promise<User | null> {
  pending ??= signedInUser();
  return pending;
}

export async function signInAgain(): Promise<void> {
  await userManager.removeUser();
  await userManager.signinRedirect({ state: currentPath(window.location) });
}

export async function signOut(): Promise<void> {
  await userManager.removeUser();
  await userManager.signinRedirect({ state: "/" });
}

async function signedInUser(): Promise<User | null> {
  if (window.location.pathname === CALLBACK_PATH) {
    const user = await userManager.signinRedirectCallback();
    window.history.replaceState(null, "", safeReturnPath(user.state));
    return user;
  }
  const user = await userManager.getUser();
  if (user && !user.expired) {
    return user;
  }
  await userManager.signinRedirect({ state: currentPath(window.location) });
  return null;
}
