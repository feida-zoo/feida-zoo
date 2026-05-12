// ZooPipeline 插件类型定义

/** 插件配置 */
export interface ZooPipelineConfig {
  daemonPath?: string;
  meshDir?: string;
  frameworkDir?: string;
  httpPort?: string;
}

/** 入站消息上下文 */
export interface InboundContext {
  senderId?: string;
  sessionKey?: string;
}

/** inbound_claim 事件 */
export interface InboundClaimEvent {
  content: string;
  ctx?: InboundContext;
}

/** gateway_start 事件 */
export interface GatewayStartEvent {
  ctx?: {
    config?: {
      zooPipeline?: ZooPipelineConfig;
    };
  };
}

/** claim 结果 */
export interface ClaimResult {
  claim: boolean;
  syntheticReply?: string;
}

/** 日志接口 */
export interface PluginLogger {
  info(message: string, ...args: unknown[]): void;
  warn(message: string, ...args: unknown[]): void;
  error(message: string, ...args: unknown[]): void;
  debug(message: string, ...args: unknown[]): void;
}

/** Hook 优先级选项 */
export interface HookOptions {
  priority?: number;
}

/** 插件 API */
export interface PluginAPI {
  logger: PluginLogger;
  on<T>(
    event: string,
    handler: (event: T) => ClaimResult | Promise<ClaimResult | void> | void,
    options?: HookOptions,
  ): void;
}

/** 任务文件结构 */
export interface TaskFile {
  type: string;
  content: string;
  sender: string;
  sessionKey: string;
  timestamp: string;
  id: string;
}

/** 插件入口定义 */
export interface PluginEntry {
  id: string;
  name: string;
  version: string;
  register(api: PluginAPI): void;
}

export type PluginEntryFn = (entry: PluginEntry) => void;
