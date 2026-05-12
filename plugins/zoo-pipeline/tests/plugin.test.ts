import { describe, it } from "node:test";
import assert from "node:assert";
import { resolveConfig, DEFAULTS, LOG_PREFIX } from "../src/config.js";
import { writeTaskFile } from "../src/hooks/task-writer.js";
import { tmpdir } from "node:os";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";

describe("config", () => {
  it("should use defaults when no config provided", () => {
    const config = resolveConfig();
    assert.strictEqual(config.daemonPath, DEFAULTS.DAEMON_PATH);
    assert.strictEqual(config.meshDir, DEFAULTS.MESH_DIR);
    assert.strictEqual(config.frameworkDir, DEFAULTS.FRAMEWORK_DIR);
    assert.strictEqual(config.httpPort, DEFAULTS.HTTP_PORT);
  });

  it("should override defaults with plugin config", () => {
    const config = resolveConfig({
      httpPort: "9999",
      meshDir: "/custom/mesh",
    });
    assert.strictEqual(config.httpPort, "9999");
    assert.strictEqual(config.meshDir, "/custom/mesh");
    assert.strictEqual(config.daemonPath, DEFAULTS.DAEMON_PATH);
    assert.strictEqual(config.frameworkDir, DEFAULTS.FRAMEWORK_DIR);
  });

  it("should have correct log prefix", () => {
    assert.strictEqual(LOG_PREFIX, "[ZooPipeline]");
  });
});

describe("task-writer", () => {
  it("should atomically write task file", async () => {
    const tmpDir = mkdtempSync(join(tmpdir(), "zoo-pipeline-test-"));

    const task = {
      type: "task_incoming",
      content: "测试任务内容",
      sender: "test-sender",
      sessionKey: "test-session",
      timestamp: new Date().toISOString(),
      id: "test_task_123",
    };

    const filePath = await writeTaskFile(task, tmpDir);

    // 验证文件存在且内容正确
    const content = readFileSync(filePath, "utf-8");
    const parsed = JSON.parse(content);
    assert.strictEqual(parsed.id, "test_task_123");
    assert.strictEqual(parsed.content, "测试任务内容");
    assert.strictEqual(parsed.type, "task_incoming");

    // 清理
    rmSync(tmpDir, { recursive: true, force: true });
  });
});
