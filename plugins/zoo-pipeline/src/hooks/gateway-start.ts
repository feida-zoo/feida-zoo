/**
 * gateway_start Hook — 启动 ZooMesh 守护进程
 */
import { spawn, type ChildProcess } from "node:child_process";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";

const LOG_PREFIX = "[ZooPipeline]";

interface ZooPipelineConfig {
  daemonPath: string;
  meshDir: string;
  frameworkDir: string;
  httpPort: string;
}

const DEFAULT_CONFIG: ZooPipelineConfig = {
  daemonPath:
    process.env.ZOO_MESH_DAEMON ||
    "/Users/zoo/workspace/code/feida_zoo/framework/core/mesh/zoo_mesh_daemon.py",
  meshDir:
    process.env.ZOO_MESH_DIR ||
    "/Users/zoo/workspace/members/panda/zoo_mesh",
  frameworkDir:
    process.env.ZOO_FRAMEWORK_DIR ||
    "/Users/zoo/workspace/code/feida_zoo/framework",
  httpPort: process.env.ZOO_MESH_HTTP_PORT || "18793",
};

const MAX_CRASH_COUNT = 5;
const CRASH_RESTART_DELAY_MS = 5000;
const HEALTH_POLL_INTERVAL_MS = 2000;
const HEALTH_TIMEOUT_MS = 30000;

let daemonProcess: ChildProcess | null = null;
let crashCount = 0;

export function registerGatewayStart(api: OpenClawPluginApi): void {
  api.on(
    "gateway_start",
    async (): Promise<void> => {
      startDaemon(api, DEFAULT_CONFIG);
    },
    { priority: 50 },
  );
}

function startDaemon(api: OpenClawPluginApi, config: ZooPipelineConfig): void {
  if (crashCount >= MAX_CRASH_COUNT) {
    api.logger.error(
      `${LOG_PREFIX} 🚨 ZooMesh 连续崩溃 ${crashCount} 次，停止自动重启，请人工排查！`,
    );
    return;
  }

  const env = {
    ...process.env,
    PYTHONPATH: config.frameworkDir,
    ZOO_MESH_DIR: config.meshDir,
    ZOO_MESH_HTTP_PORT: config.httpPort,
    ZOO_FRAMEWORK_DIR: config.frameworkDir,
  };

  api.logger.info(
    `${LOG_PREFIX} 启动 ZooMesh 守护进程: ${config.daemonPath} (端口 ${config.httpPort})`,
  );

  // 使用 venv 的 Python（安装有 yaml 等依赖）
  const pythonBin = process.env.ZOO_PYTHON || "/tmp/venv/bin/python3";
  daemonProcess = spawn(pythonBin, [config.daemonPath], {
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  daemonProcess.stdout?.on("data", (data: Buffer) => {
    for (const line of data.toString().split("\n")) {
      if (line.trim()) {
        api.logger.info(`${LOG_PREFIX} [ZooMesh] ${line.trim()}`);
      }
    }
  });

  daemonProcess.stderr?.on("data", (data: Buffer) => {
    for (const line of data.toString().split("\n")) {
      if (line.trim()) {
        api.logger.warn(`${LOG_PREFIX} [ZooMesh:err] ${line.trim()}`);
      }
    }
  });

  daemonProcess.on("exit", (code: number | null) => {
    if (code !== 0 && code !== null) {
      crashCount++;
      api.logger.warn(
        `${LOG_PREFIX} ⚠️ ZooMesh 异常退出 (code=${code})，崩溃次数=${crashCount}/${MAX_CRASH_COUNT}，${CRASH_RESTART_DELAY_MS}ms 后重启`,
      );
      setTimeout(() => startDaemon(api, config), CRASH_RESTART_DELAY_MS);
    } else {
      crashCount = 0;
    }
  });

  daemonProcess.on("error", (err: Error) => {
    crashCount++;
    api.logger.error(
      `${LOG_PREFIX} 🚨 ZooMesh 启动失败: ${err.message}，崩溃次数=${crashCount}/${MAX_CRASH_COUNT}`,
    );
    if (crashCount < MAX_CRASH_COUNT) {
      setTimeout(() => startDaemon(api, config), CRASH_RESTART_DELAY_MS);
    }
  });

  const healthUrl = `http://127.0.0.1:${config.httpPort}/health`;
  waitForHealth(healthUrl, HEALTH_TIMEOUT_MS, api).catch(() => {});
}

async function waitForHealth(
  url: string,
  timeoutMs: number,
  api: OpenClawPluginApi,
): Promise<void> {
  const startTime = Date.now();
  while (Date.now() - startTime < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) {
        api.logger.info(`${LOG_PREFIX} ✅ ZooMesh 守护进程健康就绪: ${url}`);
        crashCount = 0;
        return;
      }
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, HEALTH_POLL_INTERVAL_MS));
  }
  api.logger.warn(
    `${LOG_PREFIX} ⚠️ ZooMesh 健康检查超时 (${timeoutMs}ms): ${url}`,
  );
}
