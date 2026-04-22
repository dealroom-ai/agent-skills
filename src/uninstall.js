import { rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { parseArgs } from "./util.js";

export async function uninstall(argv) {
  const { positional, flags } = parseArgs(argv);
  const name = positional[0];
  if (!name) {
    throw new Error("Usage: uninstall <name> [--project]");
  }

  const base = flags.project
    ? join(process.cwd(), ".claude", "skills")
    : join(homedir(), ".claude", "skills");
  const dest = join(base, name);

  if (!existsSync(dest)) {
    console.log(`${dest} does not exist — nothing to remove.`);
    return;
  }

  await rm(dest, { recursive: true, force: true });
  console.log(`Removed ${dest}`);
}
