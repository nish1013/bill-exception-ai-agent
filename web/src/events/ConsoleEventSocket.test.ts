import {
  ConsoleEventSocket,
  type ConsoleEventListener,
  type SocketLike,
} from "./ConsoleEventSocket";

class FakeSocket {
  onopen: SocketLike["onopen"] = null;
  onmessage: SocketLike["onmessage"] = null;
  onclose: SocketLike["onclose"] = null;
  closed = false;

  constructor(readonly token: string) {}

  close(): void {
    this.closed = true;
  }

  open(): void {
    this.onopen?.call(this as unknown as WebSocket, new Event("open"));
  }

  receive(data: string): void {
    this.onmessage?.call(this as unknown as WebSocket, new MessageEvent("message", { data }));
  }

  drop(): void {
    this.onclose?.call(this as unknown as WebSocket, new CloseEvent("close"));
  }
}

function listener(): ConsoleEventListener {
  return { onEvent: vi.fn(), onOpen: vi.fn() };
}

const PROGRESS = JSON.stringify({ type: "BillCheckProgress", jobId: "j1", seq: 3, percent: 40 });

describe("console event socket", () => {
  let sockets: FakeSocket[];
  let token: string | null;

  function eventSocket(): ConsoleEventSocket {
    return new ConsoleEventSocket({
      connect: (t) => {
        const socket = new FakeSocket(t);
        sockets.push(socket);
        return socket as unknown as SocketLike;
      },
      token: async () => token,
      retryDelaysMs: [100, 200],
    });
  }

  beforeEach(() => {
    vi.useFakeTimers();
    sockets = [];
    token = "t1";
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("us7: opens with the token and passes each event on", async () => {
    const l = listener();
    eventSocket().subscribe(l);
    await vi.advanceTimersByTimeAsync(0);
    sockets[0]?.open();
    sockets[0]?.receive(PROGRESS);

    expect(sockets.map((s) => s.token)).toEqual(["t1"]);
    expect(l.onOpen).toHaveBeenCalledTimes(1);
    expect(l.onEvent).toHaveBeenCalledWith({
      type: "BillCheckProgress",
      jobId: "j1",
      seq: 3,
      percent: 40,
    });
  });

  it("d18: a dropped socket reconnects and calls onOpen again", async () => {
    const l = listener();
    eventSocket().subscribe(l);
    await vi.advanceTimersByTimeAsync(0);
    sockets[0]?.open();
    sockets[0]?.drop();
    await vi.advanceTimersByTimeAsync(100);
    sockets[1]?.open();

    expect(sockets).toHaveLength(2);
    expect(l.onOpen).toHaveBeenCalledTimes(2);
  });

  it("d18: with no token it tries again later", async () => {
    token = null;
    eventSocket().subscribe(listener());
    await vi.advanceTimersByTimeAsync(0);
    token = "t2";
    await vi.advanceTimersByTimeAsync(100);

    expect(sockets.map((s) => s.token)).toEqual(["t2"]);
  });

  it("us7: an unknown or bad message is skipped", async () => {
    const l = listener();
    eventSocket().subscribe(l);
    await vi.advanceTimersByTimeAsync(0);
    sockets[0]?.receive("not json");
    sockets[0]?.receive(JSON.stringify({ type: "Unknown", jobId: "j1" }));

    expect(l.onEvent).not.toHaveBeenCalled();
  });

  it("us7: the last unsubscribe closes the socket and stops the retries", async () => {
    const unsubscribe = eventSocket().subscribe(listener());
    await vi.advanceTimersByTimeAsync(0);
    unsubscribe();
    sockets[0]?.drop();
    await vi.advanceTimersByTimeAsync(1000);

    expect(sockets).toHaveLength(1);
    expect(sockets[0]?.closed).toBe(true);
  });

  it("us7: subscribe, unsubscribe, subscribe opens one socket", async () => {
    const events = eventSocket();
    events.subscribe(listener())();
    events.subscribe(listener());
    await vi.advanceTimersByTimeAsync(0);

    expect(sockets).toHaveLength(1);
  });
});
