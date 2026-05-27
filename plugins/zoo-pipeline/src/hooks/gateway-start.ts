/**
 * gateway_start Hook — 启动 ZooMesh 守护进程
 */
import { spawn, type ChildProcess } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { createRequire } from "node:module";
import { readdirSync } from "node:fs";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";

const _r = createRequire(import.meta.url);
const _gwDistDir = "/opt/homebrew/lib/node_modules/openclaw/dist";
const _rpcFile = readdirSync(_gwDistDir).find(
  (f: string) => f.startsWith("gateway-rpc-") && f.endsWith(".js")
);
const { n: callGatewayFromCli } = _rpcFile
  ? _r(`${_gwDistDir}/${_rpcFile}`)
  : ({} as any);

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

// ── ZooNotify HTTP 服务器 ─────────────────────────────────────────────────

const NOTIFY_PORT = parseInt(process.env.ZOO_NOTIFY_PORT || "18794", 10);

function startNotifyServer(api: OpenClawPluginApi): void {
  const http = require("node:http");
  const server = http.createServer((req: any, res: any) => {
    if (req.method === "POST" && req.url === "/api/zoo-notify") {
      let body = "";
      req.on("data", (chunk: string) => (body += chunk));
      req.on("end", () => {
        try {
          const data = JSON.parse(body);
          const agent = data.agent as string;
          const phase = data.phase || "?";
          const pid = data.pipeline_id || "";
          const msg = `📥 ZooMesh 通知: [${phase}] ${pid}\n${(data.message || "").slice(0, 250)}`;

          api.logger.info(
            `${LOG_PREFIX} 🔔 转发通知到 ${agent}: ${pid}`,
          );

          // Agent QQ openid 映射
          const QQ_OPENID: Record<string, string> = {
            alpha: "639C0438DCC3CCA674064F1AFFBAE57D",
            duci: "9BF8D96BAAB8D6CAF91FA0B6118C42CB",
            panda: "C0B6F9464E1C6191FDE7A35065CEA549",
          };
          const openId = QQ_OPENID[agent];
          if (!openId) {
            api.logger.warn(`${LOG_PREFIX} 未知 agent: ${agent}`);
            res.writeHead(200);
            res.end(JSON.stringify({ status: "ok" }));
            return;
          }
          const { execSync } = require("node:child_process");
          const target = `qqbot:c2c:${openId}`;
          const cmd = `/opt/homebrew/bin/openclaw message send --channel qqbot --target ${target} -m ${JSON.stringify(msg)} 2>/dev/null`;
          try {
            execSync(cmd, { timeout: 5000, stdio: "pipe" });
            api.logger.info(`${LOG_PREFIX} ✅ 通知 ${agent} 发送成功`);
          } catch (e: any) {
            api.logger.warn(
              `${LOG_PREFIX} 通知 ${agent} 发送失败: ${e.stderr?.toString().slice(0, 100) || e.message}`,
            );
          }
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ status: "ok" }));
        } catch (e: any) {
          api.logger.warn(`${LOG_PREFIX} 解析通知失败: ${e.message}`);
          res.writeHead(400);
          res.end(JSON.stringify({ error: "invalid json" }));
        }
      });
    }
    // ── POST /api/sessions-send: daemon 专用，RPC 发送到 agent main session ──
    else if (req.method === "POST" && req.url === "/api/sessions-send") {
      let body = "";
      req.on("data", (chunk: string) => (body += chunk));
      req.on("end", async () => {
        try {
          const data = JSON.parse(body);
          const agent = data.agent as string;
          const message = (data.message || "") as string;
          if (!agent || !message) {
            res.writeHead(400);
            res.end(JSON.stringify({ error: "missing agent or message" }));
            return;
          }
          const yamlPath = resolve(process.env.ZOO_FRAMEWORK_DIR || "/Users/zoo/workspace/code/feida_zoo/framework", "data", "zoo_members.yaml");
          let sessionKey = `agent:${agent}:main`;
          if (existsSync(yamlPath)) {
            try {
              const yaml = require("js-yaml");
              const cfg = yaml.load(readFileSync(yamlPath, "utf-8"));
              sessionKey = (cfg as any)?.members?.[agent]?.session?.key || sessionKey;
            } catch (_) { /* fallback */ }
          }
          api.logger.info(`${LOG_PREFIX} 🔔 sessions-send RPC → ${agent} (${sessionKey})`);
          try {
            await callGatewayFromCli("sessions.send", {}, {
              key: sessionKey,
              message: message.slice(0, 8000),
            });
            api.logger.info(`${LOG_PREFIX} ✅ sessions-send → ${agent} ok`);
          } catch (e: any) {
            api.logger.warn(`${LOG_PREFIX} sessions-send RPC fail: ${e.message}`);
            res.writeHead(502);
            res.end(JSON.stringify({ error: e.message }));
            return;
          }
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ status: "ok" }));
        } catch (e: any) {
          api.logger.warn(`${LOG_PREFIX} sessions-send parse: ${e.message}`);
          res.writeHead(400);
          res.end(JSON.stringify({ error: "invalid json" }));
        }
      });
    } else {
      res.writeHead(404);
      res.end();
    }
  });

  server.listen(NOTIFY_PORT, "127.0.0.1", () => {
    api.logger.info(
      `${LOG_PREFIX} 🎯 ZooNotify HTTP 已启动: http://127.0.0.1:${NOTIFY_PORT}`,
    );
  });
}

// ── Dashboard 进程管理 ─────────────────────────────────────────────────

const DASHBOARD_PATH =
  process.env.ZOO_DASHBOARD_SCRIPT ||
  "/Users/zoo/workspace/code/feida_zoo/dashboard/app_enhanced.py";
const DASHBOARD_PYTHON =
  process.env.ZOO_DASHBOARD_PYTHON ||
  "/Users/zoo/workspace/code/feida_zoo/venv/bin/python";
const DASHBOARD_PORT = parseInt(process.env.ZOO_DASHBOARD_PORT || "18792", 10);

let dashboardProcess: ChildProcess | null = null;
let dashboardCrashCount = 0;
const DASHBOARD_MAX_CRASH = 5;
const DASHBOARD_HEALTH_TIMEOUT = 15000;

function startDashboard(api: OpenClawPluginApi): void {
  if (dashboardCrashCount >= DASHBOARD_MAX_CRASH) {
    api.logger.error(
      `${LOG_PREFIX} 🚨 Dashboard 连续崩溃 ${dashboardCrashCount} 次，停止自动重启`,
    );
    return;
  }

  api.logger.info(
    `${LOG_PREFIX} 启动 Dashboard: ${DASHBOARD_PATH} (端口 ${DASHBOARD_PORT})`,
  );

  dashboardProcess = spawn(DASHBOARD_PYTHON, [DASHBOARD_PATH], {
    env: { ...process.env },
    stdio: ["ignore", "pipe", "pipe"],
  });

  dashboardProcess.stdout?.on("data", (data: Buffer) => {
    for (const line of data.toString().split("\n")) {
      if (line.trim()) {
        api.logger.info(`${LOG_PREFIX} [Dashboard] ${line.trim()}`);
      }
    }
  });

  dashboardProcess.stderr?.on("data", (data: Buffer) => {
    for (const line of data.toString().split("\n")) {
      if (line.trim()) {
        api.logger.warn(`${LOG_PREFIX} [Dashboard:err] ${line.trim()}`);
      }
    }
  });

  dashboardProcess.on("exit", (code: number | null) => {
    if (code !== 0 && code !== null) {
      dashboardCrashCount++;
      api.logger.warn(
        `${LOG_PREFIX} ⚠️ Dashboard 异常退出 (code=${code})，${CRASH_RESTART_DELAY_MS}ms 后重启`,
      );
      setTimeout(() => startDashboard(api), CRASH_RESTART_DELAY_MS);
    } else {
      dashboardCrashCount = 0;
    }
  });

  dashboardProcess.on("error", (err: Error) => {
    dashboardCrashCount++;
    api.logger.error(
      `${LOG_PREFIX} 🚨 Dashboard 启动失败: ${err.message}`,
    );
    if (dashboardCrashCount < DASHBOARD_MAX_CRASH) {
      setTimeout(() => startDashboard(api), CRASH_RESTART_DELAY_MS);
    }
  });

  const healthUrl = `http://127.0.0.1:${DASHBOARD_PORT}/api/task-stats`;
  waitForHealth(healthUrl, DASHBOARD_HEALTH_TIMEOUT, api).catch(() => {});
}

export function registerGatewayStart(api: OpenClawPluginApi): void {
  api.on(
    "gateway_start",
    async (): Promise<void> => {
      startNotifyServer(api);
      startDashboard(api);
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
