// Private stdio transport. URLs/response tokens never enter argv or diagnostic logs.
try {
  const request = await Bun.stdin.json();
  if (typeof request.url !== "string" || typeof request.proxy !== "string") throw new Error();
  const response = await fetch(request.url, {
    method: request.method,
    headers: request.headers,
    body: request.body === undefined ? undefined : Buffer.from(request.body, "base64"),
    proxy: request.proxy,
    redirect: "error",
    signal: AbortSignal.timeout(60_000),
  });
  const body = Buffer.from(await response.arrayBuffer()).toString("base64");
  process.stdout.write(JSON.stringify({ status: response.status, headers: [...response.headers], body }));
} catch {
  // Never print raw fetch errors: they can contain AppSecret/access_token URLs.
  process.stdout.write('{"error":true}');
  process.exitCode = 1;
}
