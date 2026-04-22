#!/usr/bin/env node
import { install } from "../src/install.js";
import { uninstall } from "../src/uninstall.js";
import { list } from "../src/list.js";

const [command, ...rest] = process.argv.slice(2);

const commands = { install, uninstall, list, ls: list };

if (
  !command ||
  command === "help" ||
  command === "--help" ||
  command === "-h"
) {
  printHelp();
  process.exit(0);
}

const fn = commands[command];
if (!fn) {
  console.error(`Unknown command: ${command}\n`);
  printHelp();
  process.exit(1);
}

try {
  await fn(rest);
} catch (err) {
  console.error(err.message);
  process.exit(1);
}

function printHelp() {
  console.log(
    `agent-skills — install Claude Code skills from Dealroom AI

Usage:
  npx github:dealroom-ai/agent-skills list
  npx github:dealroom-ai/agent-skills install <name> [--project] [--force]
  npx github:dealroom-ai/agent-skills uninstall <name> [--project]

Flags:
  --project   install into ./.claude/skills (default is ~/.claude/skills)
  --force     overwrite an existing skill of the same name

Repo: https://github.com/dealroom-ai/agent-skills`,
  );
}
