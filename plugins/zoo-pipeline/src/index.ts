import type { PluginAPI } from "./types.js";
import { registerInboundClaim } from "./hooks/inbound-claim.js";
import { registerGatewayStart } from "./hooks/gateway-start.js";

/**
 * ZooPipeline 插件入口
 *
 * 功能：
 * 1. inbound_claim hook — 拦截 /task 命令，写入 ZooMesh 目录
 * 2. gateway_start hook — 启动 ZooMesh 守护进程，崩溃自动重启
 */
export function definePluginEntry(api: PluginAPI): void {
  registerInboundClaim(api);
  registerGatewayStart(api);
}
