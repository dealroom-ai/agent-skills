import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { skillsSourceDir } from "./util.js";

export async function list() {
  const dir = skillsSourceDir();
  const entries = await readdir(dir, { withFileTypes: true });
  const skills = entries
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();

  if (skills.length === 0) {
    console.log("No skills found.");
    return;
  }

  console.log("Available skills:\n");
  const width = Math.max(...skills.map((s) => s.length));
  for (const name of skills) {
    const desc = await readDescription(join(dir, name, "SKILL.md"));
    console.log(`  ${name.padEnd(width + 2)}${desc}`);
  }
  console.log(
    "\nInstall with: npx github:dealroom-ai/agent-skills install <name>",
  );
}

async function readDescription(file) {
  try {
    const content = await readFile(file, "utf8");
    const frontmatter = content.match(/^---\n([\s\S]*?)\n---/);
    if (!frontmatter) return "";
    const match = frontmatter[1].match(
      /^description:\s*(.+?)(?:\n[a-z_]+:|$)/ms,
    );
    if (!match) return "";
    const text = match[1].replace(/^>\s*/, "").replace(/\s+/g, " ").trim();
    return text.length > 90 ? text.slice(0, 87) + "..." : text;
  } catch {
    return "";
  }
}
