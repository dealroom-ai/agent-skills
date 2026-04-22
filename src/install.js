import { cp, mkdir, rm } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
import { parseArgs, skillsSourceDir } from "./util.js";

export async function install(argv) {
  const { positional, flags } = parseArgs(argv);
  const name = positional[0];
  if (!name) {
    throw new Error("Usage: install <name> [--project] [--force]");
  }

  const src = join(skillsSourceDir(), name);
  if (!existsSync(src)) {
    throw new Error(
      `Skill "${name}" not found. Run \`list\` to see available skills.`,
    );
  }

  const base = flags.project
    ? join(process.cwd(), ".claude", "skills")
    : join(homedir(), ".claude", "skills");
  const dest = join(base, name);

  if (existsSync(dest)) {
    if (!flags.force) {
      throw new Error(
        `${dest} already exists. Re-run with --force to overwrite.`,
      );
    }
    await rm(dest, { recursive: true, force: true });
  }

  await mkdir(base, { recursive: true });
  await cp(src, dest, { recursive: true });
  console.log(`Installed ${name} → ${dest}`);
}
