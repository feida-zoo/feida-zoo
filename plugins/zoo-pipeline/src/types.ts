/**
 * 仅项目内部使用的类型定义
 * SDK 类型直接从 openclaw/plugin-sdk/plugin-entry 导入
 */

/** 从 SDK 重新导出供测试使用 */
import type {
  PluginHookInboundClaimEvent,
  PluginHookInboundClaimResult,
} from "openclaw/plugin-sdk/plugin-entry";

export type {
  PluginHookInboundClaimEvent,
  PluginHookInboundClaimResult,
};
