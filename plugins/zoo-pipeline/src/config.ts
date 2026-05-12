import type { ZooPipelineConfig } from "./types.js";

/** 默认配置常量 — 可被环境变量或插件配置覆盖 */
export const DEFAULTS = {
  /** ZooMesh daemon 脚本默认路径 */
  DAEMON_PATH:
    process.env.ZOO_MESH_DAEMON ||
    "/Users/zoo/workspace/code/feida_zoo/framework/core/mesh/zoo_mesh_daemon.py",

  /** ZooMesh 数据目录默认路径 */
  MESH_DIR:
    process.env.ZOO_MESH_DIR ||
    "/Users/zoo/workspace/members/panda/zoo_mesh",

  /** feida_zoo framework 目录默认路径 */
  FRAMEWORK_DIR:
    process.env.ZOO_FRAMEWORK_DIR ||
    "/Users/zoo/workspace/code/feida_zoo/framework",

  /** ZooMesh HTTP API 默认端口 */
  HTTP_PORT: process.env.ZOO_MESH_HTTP_PORT || "18793",
};

/** 日志前缀 */
export const LOG_PREFIX = "[ZooPipeline]";

/** 崩溃重启上限 */
export const MAX_CRASH_COUNT = 5;

/** 崩溃后重启延迟（毫秒） */
export const CRASH_RESTART_DELAY_MS = 5000;

/** 健康检查轮询间隔（毫秒） */
export const HEALTH_POLL_INTERVAL_MS = 2000;

/** 健康检查超时（毫秒） */
export const HEALTH_TIMEOUT_MS = 30000;

/** 消息长度上限 */
export const MAX_MESSAGE_LENGTH = 2000;

/**
 * 解析插件配置，环境变量 > 插件配置 > 默认值
 */
export function resolveConfig(
  pluginConfig?: ZooPipelineConfig,
): Required<ZooPipelineConfig> {
  return {
    daemonPath: pluginConfig?.daemonPath || DEFAULTS.DAEMON_PATH,
    meshDir: pluginConfig?.meshDir || DEFAULTS.MESH_DIR,
    frameworkDir: pluginConfig?.frameworkDir || DEFAULTS.FRAMEWORK_DIR,
    httpPort: pluginConfig?.httpPort || DEFAULTS.HTTP_PORT,
  };
}
