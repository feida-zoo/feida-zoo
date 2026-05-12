import { spawn, type ChildProcess } from "node:child_process";
import type { PluginAPI, GatewayStartEvent } from "../types.js";
import {
  resolveConfig,
  LOG_PREFIX,
  MAX_CRASH_COUNT,
  CRASH_RESTART_DELAY_MS,
  HEALTH_POLL_INTERVAL_MS,
  HEALTH_TIMEOUT_MS,
} from "../config.js";

let daemonProcess: ChildProcess | null = null;
let crashCount = 0;

export function registerGatewayStart(api: PluginAPI): void {
  api.on(
    "gateway_start",
    async (event: GatewayStartEvent): Promise<void> => {
      const config = resolveConfig(event.ctx?.config?.zooPipeline);
      startDaemon(api, config);
    },
    { priority: 50 },
  );
}

function startDaemon(api: PluginAPI, config: ReturnType<typeof resolveConfig>): void {
  // 连续崩溃超过上限，停止自动重启
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

  daemonProcess = spawn("python3", [config.daemonPath], {
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
      // 正常退出，重置计数器
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

  // 健康检查
  const healthUrl = `http://127.0.0.1:${config.httpPort}/health`;
  waitForHealth(healthUrl, HEALTH_TIMEOUT_MS, api).catch(() => {
    // 超时已在函数内记录日志
  });
}

async function waitForHealth(
  url: string,
  timeoutMs: number,
  api: PluginAPI,
): Promise<void> {
  const startTime = Date.now();
  while (Date.now() - startTime < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) {
        api.logger.info(`${LOG_PREFIX} ✅ ZooMesh 守护进程健康就绪: ${url}`);
        // 健康检查通过，重置崩溃计数器
        crashCount = 0;
        return;
      }
    } catch {
      // 还没启动，继续等
    }
    await new Promise((r) => setTimeout(r, HEALTH_POLL_INTERVAL_MS));
  }
  api.logger.warn(
    `${LOG_PREFIX} ⚠️ ZooMesh 健康检查超时 (${timeoutMs}ms): ${url}`,
  );
}
