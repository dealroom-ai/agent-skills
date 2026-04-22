import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

export function skillsSourceDir() {
  const here = dirname(fileURLToPath(import.meta.url));
  return resolve(here, "..", "skills");
}

export function parseArgs(argv) {
  const positional = [];
  const flags = {};
  for (const arg of argv) {
    if (arg.startsWith("--")) {
      const [k, v] = arg.slice(2).split("=");
      flags[k] = v === undefined ? true : v;
    } else {
      positional.push(arg);
    }
  }
  return { positional, flags };
}
