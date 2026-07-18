import { existsSync, mkdirSync, unlinkSync } from "fs";
import { homedir } from "os";
import { resolve } from "path";
import net from "net";
import { CDPConnection, getWsUrl } from "./client";

const CACHE_DIR = resolve(homedir(), ".cache", "jdy-url-to-markdown");
const SOCK_PATH = resolve(CACHE_DIR, "daemon.sock");
const IDLE_TIMEOUT = 30 * 60 * 1000;

try { mkdirSync(CACHE_DIR, { recursive: true, mode: 0o700 }); } catch {}

export class CDPDaemon {
  private cdp!: CDPConnection;
  private busy = false;
  private idleTimer: ReturnType<typeof setTimeout> | null = null;
  private networkResponses = new Map<string, { url: string; requestId: string }>();
  private networkEnabled = false;
  private server: net.Server | null = null;
  private currentSessionId: string | null = null;
  private currentTargetId: string | null = null;

  async start(): Promise<void> {
    const wsUrl = getWsUrl();
    this.cdp = new CDPConnection();

    let lastErr: Error | null = null;
    for (let i = 0; i < 20; i++) {
      try {
        await this.cdp.connect(wsUrl);
        lastErr = null;
        break;
      } catch (e) {
        lastErr = e as Error;
        await new Promise(r => setTimeout(r, 300));
      }
    }
    if (lastErr) throw lastErr;

    if (existsSync(SOCK_PATH)) unlinkSync(SOCK_PATH);
    this.server = net.createServer(this.handleConnection.bind(this));
    this.server.listen(SOCK_PATH);
    this.resetIdleTimer();
    console.error(`[daemon] Listening on ${SOCK_PATH}`);
  }

  private resetIdleTimer(): void {
    if (this.idleTimer) clearTimeout(this.idleTimer);
    this.idleTimer = setTimeout(() => {
      console.error("[daemon] Idle timeout, shutting down");
      this.shutdown();
    }, IDLE_TIMEOUT);
  }

  private handleConnection(socket: net.Socket): void {
    let buffer = "";
    socket.on("data", (chunk) => {
      buffer += chunk.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        this.handleRequest(JSON.parse(line), socket);
      }
    });
  }

  private async handleRequest(req: any, socket: net.Socket): Promise<void> {
    this.resetIdleTimer();
    if (this.busy) {
      socket.write(JSON.stringify({ error: "busy" }) + "\n");
      return;
    }
    this.busy = true;
    try {
      let result: any;
      switch (req.method) {
        case "health": result = { ok: true }; break;
        case "navigate": result = await this.navigate(req.params.url, req.params.timeout); break;
        case "getHTML": result = await this.getHTML(req.params); break;
        case "evaluate": result = await this.evaluate(req.params.expression); break;
        case "enableNetwork": result = await this.enableNetwork(); break;
        case "getNetworkResponses": result = this.getNetworkResponsesByPattern(req.params.urlPattern); break;
        case "getResponseBody": result = await this.getResponseBody(req.params.requestId); break;
        case "setCookies": result = await this.setCookies(req.params.cookies); break;
        case "getCookies": result = await this.getCookies(req.params.domain); break;
        default: result = { error: `Unknown method: ${req.method}` };
      }
      // Ensure result is always a non-null object for JSON serialization
      const response = (result !== null && result !== undefined && typeof result === "object") ? result : { value: result ?? null };
      socket.write(JSON.stringify(response) + "\n");
    } catch (e) {
      socket.write(JSON.stringify({ error: (e as Error).message }) + "\n");
    } finally {
      this.busy = false;
    }
  }

  private async navigate(url: string, timeout = 30000): Promise<{ ok: true }> {
    // Close previous tab if any
    if (this.currentTargetId) {
      try { await this.cdp.send("Target.closeTarget", { targetId: this.currentTargetId }); } catch {}
      this.currentTargetId = null;
      this.currentSessionId = null;
    }

    const { targetId } = await this.cdp.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await this.cdp.send("Target.attachToTarget", { targetId, flatten: true });
    this.currentTargetId = targetId;
    this.currentSessionId = sessionId;

    await this.cdp.send("Page.enable", {}, sessionId);

    // Re-enable network monitoring on new session if it was previously enabled
    if (this.networkEnabled) {
      await this.cdp.send("Network.enable", {}, sessionId);
      this.networkResponses.clear();
    }

    await this.cdp.send("Page.navigate", { url }, sessionId);
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Navigation timeout")), timeout);
      const handler = () => {
        clearTimeout(timer);
        this.cdp.off("Page.loadEventFired", handler);
        setTimeout(resolve, 1500);
      };
      this.cdp.on("Page.loadEventFired", handler);
    });
    return { ok: true };
  }

  private async getHTML(params?: { waitForSelector?: string }): Promise<{ html: string }> {
    const sid = this.currentSessionId!;
    if (params?.waitForSelector) {
      const parts = params.waitForSelector.split(":");
      const timeoutStr = parts.pop();
      const selector = parts.join(":");
      const timeout = timeoutStr ? parseInt(timeoutStr) : 5000;
      await this.cdp.send("Runtime.evaluate", {
        expression: `new Promise((resolve, reject) => {
          const el = document.querySelector('${selector}');
          if (el) return resolve(true);
          const observer = new MutationObserver(() => {
            if (document.querySelector('${selector}')) { observer.disconnect(); resolve(true); }
          });
          observer.observe(document.body, { childList: true, subtree: true });
          setTimeout(() => { observer.disconnect(); reject(new Error('timeout')); }, ${timeout});
        })`,
        awaitPromise: true,
      }, sid);
    }
    const { result } = await this.cdp.send("Runtime.evaluate", {
      expression: "document.documentElement.outerHTML",
      returnByValue: true,
    }, sid);
    return { html: result.value };
  }

  private async evaluate(expression: string): Promise<any> {
    const { result } = await this.cdp.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    }, this.currentSessionId!);
    return result.value ?? null;
  }

  private async enableNetwork(): Promise<{ ok: true }> {
    this.networkEnabled = true;
    this.networkResponses.clear();
    // If a session already exists, enable immediately; otherwise navigate will enable it
    if (this.currentSessionId) {
      await this.cdp.send("Network.enable", {}, this.currentSessionId);
    }
    this.cdp.on("Network.responseReceived", (params: any) => {
      this.networkResponses.set(params.requestId, {
        url: params.response.url,
        requestId: params.requestId,
      });
    });
    return { ok: true };
  }

  private getNetworkResponsesByPattern(urlPattern: string): { responses: { url: string; requestId: string }[] } {
    const regex = new RegExp(urlPattern);
    const matches = [...this.networkResponses.values()].filter(r => regex.test(r.url));
    return { responses: matches };
  }

  private async getResponseBody(requestId: string): Promise<{ body: string }> {
    const { body, base64Encoded } = await this.cdp.send("Network.getResponseBody", { requestId }, this.currentSessionId!);
    return { body: base64Encoded ? Buffer.from(body, "base64").toString() : body };
  }

  private async setCookies(cookies: any[]): Promise<{ ok: true }> {
    for (const cookie of cookies) {
      await this.cdp.send("Network.setCookie", cookie, this.currentSessionId!);
    }
    return { ok: true };
  }

  private async getCookies(domain: string): Promise<{ cookies: any[] }> {
    const { cookies } = await this.cdp.send("Network.getCookies", { urls: [`https://${domain}`] }, this.currentSessionId!);
    return { cookies };
  }

  shutdown(): void {
    if (this.idleTimer) clearTimeout(this.idleTimer);
    if (this.currentTargetId) {
      try { this.cdp.send("Target.closeTarget", { targetId: this.currentTargetId }); } catch {}
    }
    if (this.server) {
      this.server.close();
      try { unlinkSync(SOCK_PATH); } catch {}
    }
    this.cdp.close();
    process.exit(0);
  }
}

export async function connectDaemon(): Promise<net.Socket> {
  return new Promise((resolve, reject) => {
    const sock = net.connect(SOCK_PATH);
    sock.on("connect", () => resolve(sock));
    sock.on("error", () => reject(new Error("Daemon not running")));
  });
}

export function sendDaemonRequest(sock: net.Socket, method: string, params: any = {}): Promise<any> {
  return new Promise((resolve, reject) => {
    let buffer = "";
    const onData = (chunk: Buffer) => {
      buffer += chunk.toString();
      const idx = buffer.indexOf("\n");
      if (idx !== -1) {
        sock.off("data", onData);
        const line = buffer.slice(0, idx);
        const result = JSON.parse(line);
        if (result.error) reject(new Error(result.error));
        else resolve(result);
      }
    };
    sock.on("data", onData);
    sock.write(JSON.stringify({ method, params }) + "\n");
  });
}

export async function ensureDaemon(): Promise<net.Socket> {
  try {
    return await connectDaemon();
  } catch {
    const daemonScript = resolve(import.meta.dir, "daemon-entry.ts");
    const proc = Bun.spawn(["bun", "run", daemonScript], {
      stdio: ["ignore", "ignore", "ignore"],
    });
    proc.unref();

    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 300));
      try {
        const sock = await connectDaemon();
        await sendDaemonRequest(sock, "health");
        return sock;
      } catch {}
    }
    throw new Error("Failed to start CDP daemon");
  }
}
