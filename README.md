# agent-skills

Installable [Claude Code](https://docs.claude.com/en/docs/claude-code) skills curated by the Dealroom AI team.

A **skill** is a folder with a `SKILL.md` (+ optional reference files) that Claude Code loads and uses when its trigger conditions match. Dropping a skill under `~/.claude/skills/<name>/` makes it available across every project.

## Install a skill

```bash
# list everything available
npx github:dealroom-ai/agent-skills list

# install into ~/.claude/skills/<name>
npx github:dealroom-ai/agent-skills install linear-issue-writing

# install into ./.claude/skills/<name> in the current repo instead
npx github:dealroom-ai/agent-skills install linear-issue-writing --project

# overwrite an existing install
npx github:dealroom-ai/agent-skills install linear-issue-writing --force

# remove
npx github:dealroom-ai/agent-skills uninstall linear-issue-writing
```

Requires Node 18+. After install, restart Claude Code (or start a new session) to pick the skill up.

## Available skills

| Skill                    | What it does                                                                                            |
| ------------------------ | ------------------------------------------------------------------------------------------------------- |
| `linear-issue-writing`   | Structure Linear issues (parent features, sub-tasks, bug reports) with clear acceptance criteria.       |
| `next-gen-api-hackathon` | Onboard hackathon participants to the Dealroom next-gen API — OAuth2 setup, token refresh, doc routing. |

## Contributing a skill

1. Create `skills/<your-skill-name>/SKILL.md` with YAML frontmatter:

   ```markdown
   ---
   name: your-skill-name
   description: One sentence describing when Claude should invoke this skill.
   ---

   # Skill body

   Instructions, examples, templates, etc.
   ```

2. Add supporting files (`examples.md`, `references.md`, etc.) alongside `SKILL.md` if the skill gets long.
3. Add a row to the table above.
4. Open a PR.

Keep skills portable: no hard-coded paths, no repo-specific assumptions. If something is dealroom-next-gen-specific, it belongs in that repo's `.claude/skills/` instead.

## License

MIT
