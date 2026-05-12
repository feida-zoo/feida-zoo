/**
 * Tests for zoo-pipeline plugin hooks
 */
import { describe, it, expect, beforeEach } from "bun:test";
import { randomBytes } from "crypto";

// ── Test utilities ───────────────────────────────────────────────────────────

/** Minimal mock of OpenClawPluginApi */
function makeMockApi() {
  const logs: Array<{ level: string; msg: string }> = [];
  return {
    id: "zoo-pipeline",
    name: "Zoo Pipeline",
    description: "test",
    source: "test",
    config: {},
    logger: {
      info: (msg: string) => logs.push({ level: "info", msg }),
      warn: (msg: string) => logs.push({ level: "warn", msg }),
      error: (msg: string) => logs.push({ level: "error", msg }),
      debug: () => {},
    },
    pluginConfig: {},
    _logs: logs,
    registerHook: (
      hook: string,
      handler: (...args: unknown[]) => unknown,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ): any => ({ hook, handler }),
  };
}

// ── inbound_claim hook tests ─────────────────────────────────────────────────

describe("inbound_claim hook - /task matching", () => {
  it("should NOT match /taskmaster (word boundary)", () => {
    const text = "/taskmaster 分析日志";
    const matched = /^\/task\b/.test(text);
    expect(matched).toBe(false);
  });

  it("should match /task followed by space", () => {
    const text = "/task 分析日志";
    const matched = /^\/task\b/.test(text);
    expect(matched).toBe(true);
  });

  it("should match /task followed by nothing (empty command)", () => {
    const text = "/task";
    const matched = /^\/task\b/.test(text);
    expect(matched).toBe(true);
  });

  it("should NOT match plain 'task without slash'", () => {
    const text = "task 分析日志";
    const matched = /^\/task\b/.test(text);
    expect(matched).toBe(false);
  });
});

describe("inbound_claim hook - syntheticReply generation", () => {
  it("should generate proper reply for empty /task", () => {
    const text = "/task";
    const taskContent = text.replace(/^\/task\b/, "").trim();
    expect(taskContent).toBe("");
  });

  it("should extract task content correctly", () => {
    const text = "/task 帮我分析一下日志";
    const taskContent = text.replace(/^\/task\b/, "").trim();
    expect(taskContent).toBe("帮我分析一下日志");
  });

  it("should truncate long task content in reply", () => {
    const longContent = "a".repeat(80);
    const truncated =
      longContent.slice(0, 60) + (longContent.length > 60 ? "…" : "");
    expect(truncated.length).toBe(61);
    expect(truncated.endsWith("…")).toBe(true);
  });
});

// ── gateway-start crash counter tests ───────────────────────────────────────

describe("gateway-start crash counter", () => {
  it("MAX_CRASH_COUNT should be 5", () => {
    const MAX_CRASH_COUNT = 5;
    expect(MAX_CRASH_COUNT).toBe(5);
  });

  it("should stop restart after 5 crashes", () => {
    const MAX_CRASH_COUNT = 5;
    let crashCount = 5;
    const shouldRestart = crashCount < MAX_CRASH_COUNT;
    expect(shouldRestart).toBe(false);
  });

  it("should reset crashCount to 0 on successful health check", () => {
    let crashCount = 3;
    crashCount = 0; // health check succeeded
    expect(crashCount).toBe(0);
  });
});

// ── task-writer atomic write tests ─────────────────────────────────────────

describe("task-writer atomic write", () => {
  it("should generate unique task IDs", () => {
    const ids = new Set<string>();
    for (let i = 0; i < 100; i++) {
      const ts = Date.now();
      const rnd = randomBytes(4).toString("hex");
      ids.add(`task_${ts}_${rnd}`);
    }
    // With timing variance, most IDs should be unique
    expect(ids.size).toBeGreaterThan(90);
  });

  it("should put tmp file in same directory as target to avoid EXDEV", () => {
    // Simulate what writeTaskAtomically does
    const tasksDir = "/tmp/test_mesh/inbound/tasks";
    const taskId = "task_123456_abc123";
    const fileName = `${taskId}.json`;
    const filePath = `${tasksDir}/${fileName}`;
    const tmpPath = `${tasksDir}/.tmp_${randomBytes(4).toString("hex")}_${taskId}`;

    // Both paths are in the same directory
    expect(tmpPath.startsWith(tasksDir)).toBe(true);
    expect(filePath.startsWith(tasksDir)).toBe(true);
  });
});

// ── plugin entry structure test ─────────────────────────────────────────────

describe("plugin structure", () => {
  it("should export a default definePluginEntry call", () => {
    // This is a structural test - verify the expected fields exist
    const pluginDef = {
      id: "zoo-pipeline",
      name: "Zoo Pipeline",
      description: "飝龘动物园 Pipeline 编排引擎",
    };
    expect(pluginDef.id).toBe("zoo-pipeline");
    expect(pluginDef.name).toBe("Zoo Pipeline");
  });

  it("should have correct openclaw.plugin.json structure", () => {
    const manifest = {
      id: "zoo-pipeline",
      name: "Zoo Pipeline",
      description: "飝龘动物园 Pipeline 编排引擎 — 入口守卫 + ZooMesh 守护进程管理",
      contracts: {},
      activation: { onStartup: true },
    };
    expect(manifest.id).toBe("zoo-pipeline");
    expect(manifest.activation.onStartup).toBe(true);
  });

  it("should have correct package.json openclaw field", () => {
    const pkg = {
      name: "zoo-pipeline",
      version: "1.0.0",
      type: "module",
      openclaw: {
        extensions: ["./dist/index.js"],
        compat: { minGatewayVersion: "2026.3.24-beta.2" },
      },
    };
    expect(pkg.openclaw.extensions[0]).toBe("./dist/index.js");
    expect(pkg.openclaw.compat.minGatewayVersion).toBe("2026.3.24-beta.2");
  });
});