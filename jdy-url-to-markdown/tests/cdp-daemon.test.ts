import { describe, expect, test } from "bun:test";
import { EventEmitter } from "events";
import type net from "net";
import { CDPDaemon, sendDaemonRequest } from "../scripts/cdp/daemon";

describe("CDPDaemon", () => {
  test("preserves a UTF-8 character split across request chunks", () => {
    const request = Buffer.from(`${JSON.stringify({ method: "evaluate", params: { expression: "中文" } })}\n`, "utf8");
    const characterStart = request.indexOf(Buffer.from("中", "utf8"));
    const splitAt = characterStart + 1;
    const socket = new EventEmitter() as net.Socket;
    const daemon = new CDPDaemon();
    let received: unknown;

    (daemon as any).handleRequest = (value: unknown) => {
      received = value;
    };
    (daemon as any).handleConnection(socket);

    socket.emit("data", request.subarray(0, splitAt));
    expect(received).toBeUndefined();
    socket.emit("data", request.subarray(splitAt));

    expect(received).toEqual({ method: "evaluate", params: { expression: "中文" } });
  });
});

describe("sendDaemonRequest", () => {
  test("preserves a UTF-8 character split across socket chunks", async () => {
    const text = "中文内容保持完整";
    const response = Buffer.from(`${JSON.stringify({ value: text })}\n`, "utf8");
    const characterStart = response.indexOf(Buffer.from("中", "utf8"));
    const splitAt = characterStart + 1;
    const socket = new EventEmitter() as net.Socket;

    socket.write = (() => {
      queueMicrotask(() => {
        socket.emit("data", response.subarray(0, splitAt));
        socket.emit("data", response.subarray(splitAt));
      });
      return true;
    }) as net.Socket["write"];

    const result = await sendDaemonRequest(socket, "evaluate");

    expect(result.value).toBe(text);
    expect(result.value).not.toContain("\uFFFD");
  });
});
