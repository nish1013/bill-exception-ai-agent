import { parseConsoleEvent, type ConsoleEvent } from "./consoleEvent";

export interface ConsoleEventListener {
  onEvent: (event: ConsoleEvent) => void;
  // Each open, the first and each reconnect. Events sent while the socket was down are lost.
  onOpen: () => void;
}

export type SocketLike = Pick<WebSocket, "onopen" | "onmessage" | "onclose" | "close">;

export interface ConsoleEventSocketOptions {
  connect: (token: string) => SocketLike;
  token: () => Promise<string | null>;
  retryDelaysMs?: number[];
}

const RETRY_DELAYS_MS = [500, 1000, 2000, 5000, 10_000];

export class ConsoleEventSocket {
  private readonly listeners = new Set<ConsoleEventListener>();
  private readonly retryDelaysMs: number[];
  private socket: SocketLike | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private opening = false;
  private failures = 0;

  constructor(private readonly options: ConsoleEventSocketOptions) {
    this.retryDelaysMs = options.retryDelaysMs ?? RETRY_DELAYS_MS;
  }

  subscribe(listener: ConsoleEventListener): () => void {
    this.listeners.add(listener);
    if (this.listeners.size === 1) {
      void this.open();
    }
    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0) {
        this.stop();
      }
    };
  }

  private async open(): Promise<void> {
    if (this.opening || this.socket) {
      return;
    }
    this.opening = true;
    const token = await this.options.token().finally(() => {
      this.opening = false;
    });
    if (this.listeners.size === 0) {
      return;
    }
    if (!token) {
      this.retryLater();
      return;
    }
    const socket = this.options.connect(token);
    this.socket = socket;
    socket.onopen = () => {
      this.failures = 0;
      this.listeners.forEach((listener) => listener.onOpen());
    };
    socket.onmessage = (message) => {
      const event = typeof message.data === "string" ? parseConsoleEvent(message.data) : null;
      if (event) {
        this.listeners.forEach((listener) => listener.onEvent(event));
      }
    };
    socket.onclose = () => {
      if (this.socket === socket) {
        this.socket = null;
        this.retryLater();
      }
    };
  }

  private retryLater(): void {
    if (this.listeners.size === 0 || this.retryTimer !== null) {
      return;
    }
    const delay = this.retryDelaysMs[Math.min(this.failures, this.retryDelaysMs.length - 1)];
    this.failures += 1;
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      void this.open();
    }, delay);
  }

  private stop(): void {
    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    const socket = this.socket;
    this.socket = null;
    socket?.close();
    this.failures = 0;
  }
}
