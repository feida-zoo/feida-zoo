/**
 * ZooPipeline Plugin — OpenClaw TypeScript Plugin
 *
 * Entry point using definePluginEntry.
 * At runtime OpenClaw provides the real implementation of definePluginEntry.
 */
import type {
  DefinePluginEntryOptions,
  DefinedPluginEntry,
  OpenClawPluginApi,
} from "./types.js";
import { registerInboundClaim } from "./hooks/inbound-claim.js";
import { registerGatewayStart } from "./hooks/gateway-start.js";

// Real definePluginEntry injected by OpenClaw at runtime
declare const definePluginEntry: (
  opts: DefinePluginEntryOptions,
) => DefinedPluginEntry;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _definePluginEntry = (definePluginEntry as any);

export default _definePluginEntry({
  id: "zoo-pipeline",
  name: "Zoo Pipeline",
  description: "飝龘动物园 Pipeline 编排引擎 — 入口守卫 + ZooMesh 守护进程管理",
  register(api: OpenClawPluginApi) {
    registerInboundClaim(api);
    registerGatewayStart(api);
    api.logger.info("[ZooPipeline] ✅ hooks registered");
  },
});