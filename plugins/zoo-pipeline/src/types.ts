/**
 * SDK type stubs for zoo-pipeline plugin.
 *
 * These replace the openclaw/plugin-sdk imports since that package
 * is not accessible via standard npm resolution in this environment.
 * OpenClaw injects the real API at runtime.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

export interface PluginLogger {
  info(msg: string): void;
  warn(msg: string): void;
  error(msg: string): void;
  debug(msg: string): void;
}

export interface OpenClawPluginApi {
  id: string;
  name: string;
  version?: string;
  description?: string;
  source: string;
  rootDir?: string;
  config: {
    plugins?: Record<string, Record<string, unknown>>;
    [key: string]: unknown;
  };
  logger: PluginLogger;
  pluginConfig?: Record<string, unknown>;
  // SDK uses api.on() not api.registerHook()
  on(
    hook: "inbound_claim",
    handler: (
      event: PluginHookInboundClaimEvent,
      ctx: Record<string, unknown>,
    ) =>
      | Promise<PluginHookInboundClaimResult | void>
      | PluginHookInboundClaimResult
      | void,
    opts?: { priority?: number },
  ): void;
  on(
    hook: "gateway_start",
    handler: (event: PluginHookGatewayStartEvent) => Promise<void> | void,
    opts?: { priority?: number },
  ): void;
}

export interface PluginHookInboundClaimEvent {
  content: string;
  body?: string;
  bodyForAgent?: string;
  transcript?: string;
  timestamp?: number;
  channel: string;
  accountId?: string;
  conversationId?: string;
  parentConversationId?: string;
  senderId?: string;
  [key: string]: unknown;
}

// SDK returns { claim, syntheticReply }
export interface PluginHookInboundClaimResult {
  claim: boolean;
  syntheticReply?: string;
}

export interface PluginHookGatewayStartEvent {
  port: number;
}

export interface DefinePluginEntryOptions {
  id: string;
  name: string;
  description: string;
  register: (api: OpenClawPluginApi) => void;
}

export interface DefinedPluginEntry {
  id: string;
  name: string;
  description: string;
  register: (api: OpenClawPluginApi) => void;
}