import { signInAgain } from "../auth/signIn";
import { userManager } from "../auth/userManager";
import { ConsoleEventSocket } from "./ConsoleEventSocket";

export const EVENTS_PATH = "/ws/events/";

function eventsUrl(token: string): string {
  const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${window.location.host}${EVENTS_PATH}?token=${encodeURIComponent(token)}`;
}

// An expired token cannot open the socket. The clerk signs in again, so the board never stalls.
async function currentToken(): Promise<string | null> {
  const user = await userManager.getUser();
  if (!user || user.expired) {
    void signInAgain();
    return null;
  }
  return user.access_token;
}

export const consoleEvents = new ConsoleEventSocket({
  connect: (token) => new WebSocket(eventsUrl(token)),
  token: currentToken,
});
