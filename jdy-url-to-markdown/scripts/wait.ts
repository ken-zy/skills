import type { QualityResult } from "./types";

interface WaitForValidContentOptions<T> {
  read: () => Promise<T>;
  validate: (content: T) => QualityResult;
  timeoutMs: number;
  intervalMs?: number;
  sleep?: (ms: number) => Promise<void>;
  now?: () => number;
}

export async function waitForValidContent<T>(
  options: WaitForValidContentOptions<T>,
): Promise<T> {
  const intervalMs = Math.max(0, options.intervalMs ?? 1000);
  const sleep = options.sleep ?? ((ms: number) => new Promise(resolve => setTimeout(resolve, ms)));
  const now = options.now ?? Date.now;
  const deadline = now() + Math.max(0, options.timeoutMs);
  let lastReason = "content did not pass quality validation";

  while (true) {
    const content = await options.read();
    const result = options.validate(content);
    if (result.pass) return content;
    lastReason = result.reason ?? lastReason;

    const remainingMs = deadline - now();
    if (remainingMs <= 0) {
      throw new Error(`Timed out waiting for valid content: ${lastReason}`);
    }

    await sleep(Math.min(intervalMs, remainingMs));
  }
}
