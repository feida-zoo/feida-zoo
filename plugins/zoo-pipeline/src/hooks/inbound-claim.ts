/**
 * inbound_claim Hook — 拦截 /task 命令，写入 ZooMesh 目录
 */
import { randomBytes } from "node:crypto";
import { mkdir, writeFile, rename } from "node:fs/promises";
import { join } from "node:path";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk/plugin-entry";
import type {
  PluginHookInboundClaimEvent,
  PluginHookInboundClaimResult,
} from "openclaw/plugin-sdk/plugin-entry";

const LOG_PREFIX = "[ZooPipeline:inbound-claim]";

// ── Task ID ─────────────────────────────────────────────────────────────────
function generateTaskId(): string {
  const ts = Date.now();
  const rnd = randomBytes(4).toString("hex");
  return `task_${ts}_${rnd}`;
}

// ── Atomic task file write (same-directory to avoid EXDEV on macOS) ────────
async function writeTaskAtomically(
  taskId: string,
  taskContent: string,
  sender: string,
  meshDir: string,
): Promise<string> {
  const tasksDir = join(meshDir, "inbound", "tasks");
  await mkdir(tasksDir, { recursive: true });

  const task = {
    type: "task_incoming",
    content: taskContent,
    sender,
    sessionKey: "",
    timestamp: new Date().toISOString(),
    id: taskId,
  };

  const fileName = `${taskId}.json`;
  const filePath = join(tasksDir, fileName);
  const tmpPath = join(
    tasksDir,
    `.tmp_${randomBytes(4).toString("hex")}_${taskId}`,
  );

  await writeFile(tmpPath, JSON.stringify(task, null, 2), "utf-8");
  await rename(tmpPath, filePath);
  return filePath;
}

// ── Register hook ───────────────────────────────────────────────────────────
export function registerInboundClaim(api: OpenClawPluginApi): void {
  api.on(
    "inbound_claim",
    async (
      event: PluginHookInboundClaimEvent,
    ): Promise<PluginHookInboundClaimResult | void> => {
      const text = (event.content || "").trim();

      // Word-boundary match: /task but not /taskmaster
      if (!/^\/task\b/.test(text)) {
        return; // 放行
      }

      const taskContent = text.replace(/^\/task\b/, "").trim();

      // Empty task → guide user
      if (!taskContent) {
        return {
          handled: true,
          reply: {
            text: "🐢 指令格式: `/task <你的需求描述>`\n\n例如: `/task 帮我查一下日志`",
          },
        };
      }

      const taskId = generateTaskId();
      const meshDir =
        process.env.ZOO_MESH_DIR ||
        `${process.env.FEIDA_ZOO_HOME || "/home/afei/workspace/code/feida_zoo"}/../panda/zoo_mesh`;
      const sender = event.senderId || "human";

      try {
        const filePath = await writeTaskAtomically(
          taskId,
          taskContent,
          sender,
          meshDir,
        );
        api.logger.info(
          `${LOG_PREFIX} 📝 任务已写入: ${taskId} — "${taskContent.slice(0, 50)}" (${filePath})`,
        );
      } catch (err) {
        api.logger.error(`${LOG_PREFIX} 写入任务文件失败: ${err}`);
        return {
          handled: true,
          reply: {
            text: "🐢 抱歉，写入任务时出现异常，请联系管理员。",
          },
        };
      }

      return {
        handled: true,
        reply: {
          text: `🐢 工单已收到: "${taskContent.slice(0, 60)}${taskContent.length > 60 ? "…" : ""}"\n正在分派中...`,
        },
      };
    },
    { priority: 80 },
  );
}
