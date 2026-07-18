import { readFileSync, existsSync, mkdirSync, unlinkSync } from "fs";
import { spawnSync, spawn } from "child_process";
import { homedir } from "os";
import { resolve } from "path";
import net from "net";

const TIMEOUT = 15000;
const CHROME_PROFILE_DIR = resolve(homedir(), "chrome_profiles", "profile_1001");
const CHROME_PORT_FILE = resolve(CHROME_PROFILE_DIR, "DevToolsActivePort");
const CHROME_APP = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

function launchChrome(): void {
  mkdirSync(CHROME_PROFILE_DIR, { recursive: true });
  console.error("[cdp] Launching Chrome with profile_1001...");
  const proc = spawn(CHROME_APP, [
    `--user-data-dir=${CHROME_PROFILE_DIR}`,
    "--remote-debugging-port=0",
    "--no-first-run",
    "--no-default-browser-check",
    `--disk-cache-dir=${CHROME_PROFILE_DIR}/cache`,
  ], { detached: true, stdio: "ignore" });
  proc.unref();
}

function waitForPortFile(maxWaitMs = 15000): string {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    if (existsSync(CHROME_PORT_FILE)) {
      const content = readFileSync(CHROME_PORT_FILE, "utf-8").trim();
      const lines = content.split("\n");
      if (lines.length >= 2 && lines[0] && lines[1]) return CHROME_PORT_FILE;
    }
    spawnSync("sleep", ["0.5"]);
  }
  throw new Error(`Chrome failed to start within ${maxWaitMs / 1000}s`);
}

function isPortAlive(port: number, host = "127.0.0.1", timeoutMs = 2000): boolean {
  try {
    const result = spawnSync("curl", ["-s", "-o", "/dev/null", "-w", "%{http_code}",
      `http://${host}:${port}/json/version`], { timeout: timeoutMs });
    return result.stdout?.toString().trim() === "200";
  } catch {
    return false;
  }
}

export function getWsUrl(): string {
  let portFile = existsSync(CHROME_PORT_FILE) ? CHROME_PORT_FILE : null;

  // 活性检查：文件存在但端口已死 → 删除过期文件
  if (portFile) {
    const lines = readFileSync(portFile, "utf-8").trim().split("\n");
    const port = parseInt(lines[0], 10);
    if (!port || !isPortAlive(port)) {
      console.error(`[cdp] Stale DevToolsActivePort (port ${lines[0]}), removing`);
      unlinkSync(portFile);
      portFile = null;
    }
  }

  if (!portFile) {
    launchChrome();
    portFile = waitForPortFile();
  }

  const lines = readFileSync(portFile, "utf-8").trim().split("\n");
  if (lines.length < 2 || !lines[0] || !lines[1]) {
    throw new Error(`Invalid DevToolsActivePort: ${portFile}`);
  }

  const host = process.env.CDP_HOST || "127.0.0.1";
  return `ws://${host}:${lines[0]}${lines[1]}`;
}

export class CDPConnection {
  private ws!: WebSocket;
  private nextId = 1;
  private pending = new Map<number, { resolve: (v: any) => void; reject: (e: Error) => void }>();
  private eventHandlers = new Map<string, ((params: any) => void)[]>();

  async connect(wsUrl: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(wsUrl);
      this.ws.onopen = () => resolve();
      this.ws.onerror = (e) => reject(new Error(`CDP WebSocket error: ${e}`));
      this.ws.onmessage = (event) => {
        const msg = JSON.parse(String(event.data));
        if (msg.id !== undefined) {
          const p = this.pending.get(msg.id);
          if (p) {
            this.pending.delete(msg.id);
            if (msg.error) p.reject(new Error(msg.error.message));
            else p.resolve(msg.result);
          }
        } else if (msg.method) {
          const handlers = this.eventHandlers.get(msg.method) || [];
          for (const h of handlers) h(msg.params);
        }
      };
      this.ws.onclose = () => {
        for (const p of this.pending.values()) {
          p.reject(new Error("CDP connection closed"));
        }
        this.pending.clear();
      };
    });
  }

  async send(method: string, params: any = {}, sessionId?: string): Promise<any> {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`CDP timeout: ${method}`));
      }, TIMEOUT);

      this.pending.set(id, {
        resolve: (v) => { clearTimeout(timer); resolve(v); },
        reject: (e) => { clearTimeout(timer); reject(e); },
      });

      const msg: any = { id, method, params };
      if (sessionId) msg.sessionId = sessionId;
      this.ws.send(JSON.stringify(msg));
    });
  }

  on(event: string, handler: (params: any) => void): void {
    const list = this.eventHandlers.get(event) || [];
    list.push(handler);
    this.eventHandlers.set(event, list);
  }

  off(event: string, handler: (params: any) => void): void {
    const list = this.eventHandlers.get(event);
    if (!list) return;
    const idx = list.indexOf(handler);
    if (idx !== -1) list.splice(idx, 1);
  }

  close(): void {
    this.ws.close();
  }
}
