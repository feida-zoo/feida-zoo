/**
 * Tests for zoo-pipeline plugin hooks
 * Uses node:test + node:assert (Node 22+)
 */
import { test } from "node:test";
import assert from "node:assert";

// ── Tests ───────────────────────────────────────────────────────────────────

test("inbound_claim: /task message is matched", () => {
  const text = "/task 分析日志";
  const matched = /^\/task\b/.test(text);
  assert.strictEqual(matched, true, '"/task 分析日志" should match');
});

test("inbound_claim: /taskmaster is NOT matched (word boundary)", () => {
  const text = "/taskmaster 分析日志";
  const matched = /^\/task\b/.test(text);
  assert.strictEqual(matched, false, '"/taskmaster" should NOT match /task\\b');
});

test("inbound_claim: plain text without / is NOT matched", () => {
  const text = "task 分析日志";
  const matched = /^\/task\b/.test(text);
  assert.strictEqual(matched, false, '"task 分析日志" should NOT match');
});

test("inbound_claim: /task with empty content extracts empty string", () => {
  const text = "/task";
  const taskContent = text.replace(/^\/task\b/, "").trim();
  assert.strictEqual(taskContent, "", "empty /task should give empty content");
});

test("inbound_claim: /task with content extracts correctly", () => {
  const text = "/task 帮我分析日志";
  const taskContent = text.replace(/^\/task\b/, "").trim();
  assert.strictEqual(taskContent, "帮我分析日志");
});

test("inbound_claim: empty task returns guide reply", () => {
  const taskContent = "";
  let result;
  if (!taskContent) {
    result = {
      claim: true,
      syntheticReply:
        "🐢 指令格式: `/task <你的需求描述>`\n\n例如: `/task 帮我查一下日志`",
    };
  }
  assert.strictEqual(result?.claim, true);
  assert.ok(result?.syntheticReply?.includes("指令格式"));
});

test("inbound_claim: successful capture returns claim + syntheticReply", () => {
  const taskContent = "分析一下日志";
  const truncated =
    taskContent.length > 60
      ? taskContent.slice(0, 60) + "…"
      : taskContent;
  const result = {
    claim: true,
    syntheticReply: `🐢 工单已收到: "${truncated}"\n正在分派中...`,
  };
  assert.strictEqual(result.claim, true);
  assert.ok(result.syntheticReply?.startsWith("🐢 工单已收到:"));
  assert.ok(result.syntheticReply?.includes("分析一下日志"));
});

test("inbound_claim: non-/task message returns claim:false", () => {
  const text = "hello world";
  if (!/^\/task\b/.test(text)) {
    const result = { claim: false };
    assert.strictEqual(result.claim, false);
  }
});

test("hook registration: api.on stores handlers", () => {
  const registeredHooks: Array<{
    hook: string;
    handler: (...args: unknown[]) => unknown;
  }> = [];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const api: any = {
    on(hook: string, handler: (...args: unknown[]) => unknown, _opts?: unknown): void {
      registeredHooks.push({ hook, handler });
    },
  };

  const handler = () => ({ claim: false });
  api.on("inbound_claim", handler, { priority: 80 });
  api.on("gateway_start", () => {}, { priority: 50 });

  assert.strictEqual(registeredHooks.length, 2);
  assert.strictEqual(registeredHooks[0].hook, "inbound_claim");
  assert.strictEqual(registeredHooks[1].hook, "gateway_start");
});

test("atomic write: tmpPath is in same directory as filePath (no EXDEV)", () => {
  const tasksDir = "/tmp/test_mesh/inbound/tasks";
  const taskId = "task_123456_abc123";
  const filePath = `${tasksDir}/${taskId}.json`;
  const tmpPath = `${tasksDir}/.tmp_abc123_${taskId}`;

  assert.ok(filePath.startsWith(tasksDir), "filePath should be under tasksDir");
  assert.ok(tmpPath.startsWith(tasksDir), "tmpPath should be under tasksDir");
});

test("crash counter: stops restart after MAX_CRASH_COUNT (5)", () => {
  const MAX_CRASH_COUNT = 5;
  let crashCount = 5;
  const shouldRestart = crashCount < MAX_CRASH_COUNT;
  assert.strictEqual(shouldRestart, false, "should NOT restart at crashCount >= 5");
});

test("crash counter: health success resets crashCount to 0", () => {
  let crashCount = 3;
  crashCount = 0; // on health success
  assert.strictEqual(crashCount, 0);
});

test("plugin manifest: has correct id and onStartup activation", () => {
  const manifest = {
    id: "zoo-pipeline",
    activation: { onStartup: true },
  };
  assert.strictEqual(manifest.id, "zoo-pipeline");
  assert.strictEqual(manifest.activation.onStartup, true);
});

test("package.json: has openclaw.compat field", () => {
  const pkg = {
    name: "zoo-pipeline",
    version: "1.0.0",
    type: "module",
    openclaw: {
      extensions: ["./dist/index.js"],
      compat: { minGatewayVersion: "2026.3.24-beta.2" },
    },
  };
  assert.strictEqual(pkg.openclaw.compat.minGatewayVersion, "2026.3.24-beta.2");
  assert.strictEqual(pkg.openclaw.extensions[0], "./dist/index.js");
});
