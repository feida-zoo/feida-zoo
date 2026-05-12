import { mkdir, writeFile, rename } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomBytes } from "node:crypto";
import type { TaskFile } from "../types.js";
import { LOG_PREFIX } from "../config.js";

/** 原子写入 ZooMesh 目录 */
export async function writeTaskFile(
  task: TaskFile,
  meshDir?: string,
): Promise<string> {
  const dir = meshDir || process.env.ZOO_MESH_DIR;
  if (!dir) {
    throw new Error(
      `${LOG_PREFIX} ZOO_MESH_DIR 未设置，且未提供 meshDir 参数`,
    );
  }

  const tasksDir = join(dir, "inbound", "tasks");
  await mkdir(tasksDir, { recursive: true });

  const filePath = join(tasksDir, `${task.id}.json`);

  // 原子写入：先写临时文件，再 rename
  const tmpName = `.tmp_${randomBytes(4).toString("hex")}_${Date.now()}`;
  const tmpPath = join(tmpdir(), tmpName);

  await writeFile(tmpPath, JSON.stringify(task, null, 2), "utf-8");
  await rename(tmpPath, filePath);

  return filePath;
}
