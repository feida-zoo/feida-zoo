/**
 * ZooPipeline Plugin — OpenClaw TypeScript Plugin
 */
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { registerInboundClaim } from "./hooks/inbound-claim.js";
import { registerGatewayStart } from "./hooks/gateway-start.js";

export default definePluginEntry({
  id: "zoo-pipeline",
  name: "Zoo Pipeline",
  description: "飝龘动物园 Pipeline 编排引擎 — 入口守卫 + ZooMesh 守护进程管理",
  register(api) {
    registerInboundClaim(api);
    registerGatewayStart(api);
    api.logger.info("[ZooPipeline] ✅ hooks registered");
  },
});