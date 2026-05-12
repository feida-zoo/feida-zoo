import type { PluginAPI, InboundClaimEvent, ClaimResult } from "../types.js";
import { writeTaskFile } from "./task-writer.js";
import { LOG_PREFIX } from "../config.js";

export function registerInboundClaim(api: PluginAPI): void {
  api.on(
    "inbound_claim",
    async (event: InboundClaimEvent): Promise<ClaimResult | void> => {
      const text = (event.content || "").trim();

      // 只拦截 /task 前缀的命令
      if (!text.startsWith("/task")) {
        return; // 放行
      }

      const taskContent = text.replace("/task", "").trim();
      if (!taskContent) {
        return {
          claim: true,
          syntheticReply: "🐢 指令格式: `/task <你的需求>`",
        };
      }

      const taskId = `task_${Date.now()}_${Math.random()
        .toString(36)
        .slice(2, 8)}`;
      const task = {
        type: "task_incoming",
        content: taskContent,
        sender: event.ctx?.senderId || "human",
        sessionKey: event.ctx?.sessionKey || "",
        timestamp: new Date().toISOString(),
        id: taskId,
      };

      await writeTaskFile(task);

      api.logger.info(
        `${LOG_PREFIX} 📝 任务已写入 ZooMesh: ${taskId} (${taskContent.slice(0, 40)})`,
      );

      return {
        claim: true,
        syntheticReply: `🐢 工单已收到，正在评估: "${taskContent.slice(0, 60)}..."`,
      };
    },
    { priority: 80 },
  );
}
