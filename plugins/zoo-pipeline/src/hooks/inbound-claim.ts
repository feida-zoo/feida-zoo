/**
 * inbound_claim Hook — 拦截 /task 命令，写入 ZooMesh 目录
 */
import { randomBytes } from "crypto";
import { mkdir, writeFile, rename } from "fs/promises";
import { join } from "path";
import type {
  OpenClawPluginApi,
  PluginHookInboundClaimEvent,
  PluginHookInboundClaimResult,
} from "../types.js";

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
  content: string,
  meshDir: string,
): Promise<string> {
  const tasksDir = join(meshDir, "inbound", "tasks");
  await mkdir(tasksDir, { recursive: true });

  const fileName = `${taskId}.json`;
  const filePath = join(tasksDir, fileName);
  // Write to SAME directory → avoids cross-filesystem EXDEV
  const tmpPath = join(
    tasksDir,
    `.tmp_${randomBytes(4).toString("hex")}_${taskId}`,
  );

  await writeFile(tmpPath, content, "utf-8");
  await rename(tmpPath, filePath);
  return filePath;
}

// ── Register hook ───────────────────────────────────────────────────────────
export function registerInboundClaim(api: OpenClawPluginApi): void {
  api.registerHook(
    "inbound_claim",
    async (
      event: PluginHookInboundClaimEvent,
    ): Promise<PluginHookInboundClaimResult> => {
      const text = (event.content || "").trim();

      // Word-boundary match: /task but not /taskmaster
      if (!/^\/task\b/.test(text)) {
        return { handled: false };
      }

      const taskContent = text.replace(/^\/task\b/, "").trim();

      // Empty task → guide user
      if (!taskContent) {
        return {
          handled: true,
          reply: {
            content:
              "🐢 指令格式: `/task <你的需求描述>`\n\n例如: `/task 帮我查一下日志`",
          },
        };
      }

      const taskId = generateTaskId();
      const meshDir =
        process.env.ZOO_MESH_DIR ||
        "/Users/zoo/workspace/members/panda/zoo_mesh";

      const task = {
        type: "task_incoming",
        content: taskContent,
        sender: event.senderId || "human",
        sessionKey: "",
        timestamp: new Date().toISOString(),
        id: taskId,
      };

      try {
        const filePath = await writeTaskAtomically(
          taskId,
          JSON.stringify(task, null, 2),
          meshDir,
        );
        api.logger.info(
          `${LOG_PREFIX} 📝 任务已写入: ${taskId} — "${taskContent.slice(0, 50)}"`,
        );
        void filePath;
      } catch (err) {
        api.logger.error(`${LOG_PREFIX} 写入任务文件失败: ${err}`);
        return {
          handled: true,
          reply: {
            content: "🐢 抱歉，写入任务时出现异常，请联系管理员。",
          },
        };
      }

      return {
        handled: true,
        reply: {
          content: `🐢 工单已收到: "${taskContent.slice(0, 60)}${taskContent.length > 60 ? "…" : ""}"\n正在分派中...`,
        },
      };
    },
    { priority: 80 },
  );
}