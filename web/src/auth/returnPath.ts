const HOME = "/";

export function currentPath(location: Location): string {
  return `${location.pathname}${location.search}`;
}

// Only a same-origin path, so a crafted state cannot send the user to another site.
export function safeReturnPath(state: unknown): string {
  if (typeof state !== "string" || !state.startsWith("/") || state.startsWith("//")) {
    return HOME;
  }
  return state;
}
