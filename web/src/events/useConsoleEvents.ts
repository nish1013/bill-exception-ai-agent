import { useEffect, useRef } from "react";

import type { ConsoleEventListener } from "./ConsoleEventSocket";
import { consoleEvents } from "./consoleEvents";

export function useConsoleEvents(listener: ConsoleEventListener): void {
  const latest = useRef(listener);
  latest.current = listener;

  useEffect(
    () =>
      consoleEvents.subscribe({
        onEvent: (event) => latest.current.onEvent(event),
        onOpen: () => latest.current.onOpen(),
      }),
    [],
  );
}
