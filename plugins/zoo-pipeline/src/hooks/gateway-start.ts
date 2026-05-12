/**
 * gateway_start Hook — 启动 ZooMesh daemon 并管理其生命周期
 *
 * 行为:
 * 1. 启动 daemon 子进程
 * 2. 健康检查轮询 (最多 30 秒)
 * 3. 崩溃自动重启 (crashCount 计数器, 连续 5 次以上停止 + 日志报警)
 * 4. crashCount 在健康检查成功时重置
 */
import { spawn, type ChildProcess } from "child_process";
import type {
  OpenClawPluginApi,
  PluginHookGatewayStartEvent,
} from "../types.js";

const LOG_PREFIX = "[ZooPipeline:daemon]";
const MAX_CRASH_COUNT = 5;
const HEALTH_CHECK_INTERVAL_MS = 2000;
const HEALTH_CHECK_TIMEOUT_MS = 30000;
const RESTART_DELAY_MS = 5000;

// ── Daemon 全局状态 ─────────────────────────────────────────────────────────────
let daemonProcess: ChildProcess | null = null;
let crashCount = 0;
let isRunning = false;

// ── 注册 hook ──────────────────────────────────────────────────────────────────
export function registerGatewayStart(api: OpenClawPluginApi): void {
  api.registerHook(
    "gateway_start",
    async (_event: PluginHookGatewayStartEvent) => {
      const pluginConfig =
        (api.pluginConfig as Record<string, unknown>) || {};
      const daemonPath =
        (pluginConfig.daemonPath as string | undefined) ||
        process.env.ZOO_MESH_DAEMON ||
        "/Users/zoo/workspace/code/feida_zoo/framework/core/mesh/zoo_mesh_daemon.py";
      const meshDir =
        (pluginConfig.meshDir as string | undefined) ||
        process.env.ZOO_MESH_DIR ||
        "/Users/zoo/workspace/members/panda/zoo_mesh";
      const frameworkDir =
        (pluginConfig.frameworkDir as string | undefined) ||
        process.env.ZOO_FRAMEWORK_DIR ||
        "/Users/zoo/workspace/code/feida_zoo/framework";
      const httpPort =
        (pluginConfig.httpPort as string | undefined) ||
        process.env.ZOO_MESH_HTTP_PORT ||
        "18793";

      api.logger.info(
        `${LOG_PREFIX} 🚀 启动 ZooMesh daemon: ${daemonPath}`,
      );
      api.logger.info(
        `${LOG_PREFIX}    meshDir=${meshDir} port=${httpPort}`,
      );

      await startDaemon(api, { daemonPath, meshDir, frameworkDir, httpPort });
    },
    { priority: 50 },
  );
}

// ── 启动 daemon ────────────────────────────────────────────────────────────────
interface DaemonConfig {
  daemonPath: string;
  meshDir: string;
  frameworkDir: string;
  httpPort: string;
}

async function startDaemon(
  api: OpenClawPluginApi,
  cfg: DaemonConfig,
): Promise<void> {
  if (crashCount >= MAX_CRASH_COUNT) {
    api.logger.error(
      `${LOG_PREFIX} 🚨 连续崩溃 ${crashCount} 次，停止自动重启。请手动检查 daemon。`,
    );
    return;
  }

  const env = {
    ...process.env,
    PYTHONPATH: cfg.frameworkDir,
    ZOO_MESH_DIR: cfg.meshDir,
    ZOO_MESH_HTTP_PORT: cfg.httpPort,
  };

  daemonProcess = spawn("python3", [cfg.daemonPath], {
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  daemonProcess.stdout?.on("data", (data: Buffer) => {
    const lines = data.toString().trim().split("\n");
    for (const line of lines) {
      if (line) api.logger.info(`${LOG_PREFIX} ${line}`);
    }
  });

  daemonProcess.stderr?.on("data", (data: Buffer) => {
    const lines = data.toString().trim().split("\n");
    for (const line of lines) {
      if (line) api.logger.warn(`${LOG_PREFIX}:err ${line}`);
    }
  });

  daemonProcess.on("exit", (code: number | null, signal: string | null) => {
    if (!isRunning) return;
    isRunning = false;

    if (code !== 0 && code !== null) {
      crashCount++;
      api.logger.warn(
        `${LOG_PREFIX} ⚠️ ZooMesh 异常退出 (code=${code} signal=${signal})，` +
          `crashCount=${crashCount}/${MAX_CRASH_COUNT}，${RESTART_DELAY_MS}ms 后重启`,
      );

      if (crashCount < MAX_CRASH_COUNT) {
        setTimeout(() => startDaemon(api, cfg), RESTART_DELAY_MS);
      } else {
        api.logger.error(
          `${LOG_PREFIX} 🚨 连续崩溃 ${crashCount} 次，停止自动重启。`,
        );
      }
    }
  });

  isRunning = true;
  const healthOk = await waitForHealth(
    `http://127.0.0.1:${cfg.httpPort}/health`,
    HEALTH_CHECK_TIMEOUT_MS,
    api,
  );

  if (healthOk) {
    crashCount = 0;
    api.logger.info(
      `${LOG_PREFIX} ✅ ZooMesh 守护进程就绪 (port=${cfg.httpPort})`,
    );
  } else {
    api.logger.warn(
      `${LOG_PREFIX} ⚠️ ZooMesh 健康检查超时 (${HEALTH_CHECK_TIMEOUT_MS}ms)`,
    );
  }
}

// ── 健康检查轮询 ──────────────────────────────────────────────────────────────
async function waitForHealth(
  url: string,
  timeoutMs: number,
  api: OpenClawPluginApi,
): Promise<boolean> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {
      // daemon 还没启动，继续等
    }
    await new Promise((r) => setTimeout(r, HEALTH_CHECK_INTERVAL_MS));
  }

  return false;
}