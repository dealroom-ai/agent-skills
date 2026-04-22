---
name: linear-issue-writing
description: Use this skill when writing, reviewing, or discussing issue descriptions, acceptance criteria, bug reports, or task breakdowns. Ensures consistent, high-quality issue structure that any developer or AI can pick up and execute. Triggers when drafting issues, filing bugs, defining requirements, or when users ask "how should I write this issue?" or "what should the acceptance criteria be?"
---

# Issue Writing Skill

This skill guides the creation of well-structured, actionable Linear issues that any developer or AI can pick up and execute independently.

## Clarifying Questions Before Drafting

**Before drafting any issue, identify the issue type (Parent Feature, Sub-Issue/Task, or Bug Report), then use the `AskUserQuestion` tool _once, upfront_, to resolve the most important unknowns for that type.** Batch 2-4 questions in a single `AskUserQuestion` call rather than asking one at a time.

**While drafting, if new open questions emerge that weren't covered upfront — especially ones the user hasn't thought about — call `AskUserQuestion` again to refine them.** Do not silently guess: surfacing a gap is more valuable than filling it with an assumption.

### Question bank by issue type

**Bug Report** — ask upfront:

- Bug description — what's actually happening?
- Expected behaviour — what should happen instead?
- Steps to reproduce?
- Screenshot or recording available? (link or attach)

**Task / Feature** — ask upfront (pick the ones not already answered):

- Where is this needed? (which page, flow, or surface)
- Why is it needed? (user problem or business driver)
- Target audience — who is the primary user?
- What roles use this? (admin, premium, free, …)
- Is it visible to everyone but access-restricted?
- What tracking/analytics events should fire?
- Is there a Solution Design Doc (SDD) to link?
- Are there user flow designs, empty states, or edge-case mocks to reference?

Skip questions you can confidently answer from existing context (codebase, prior messages, linked docs). Only ask what you genuinely need.

**For sub-issues**, only ask clarifying questions where the parent issue doesn't already answer them. Sub-issues inherit context from their parent — re-asking upfront wastes the user's time.

## Issue Structure: Parent Feature Issues

```markdown
## IMPORTANT: Linear Issue Discipline

[Standard discipline rules]

---

## Problem

[1-2 sentences: Why does this feature need to exist?]

## Solution

[1-2 sentences: What are we building to solve this?]

## High-Level Implementation

[Bullet points: key technical decisions and patterns. If a Solution Design Doc exists, link to it here.]

## Codebase Investigation Findings

[What patterns to follow, similar features, code locations]

## Out of Scope / Deferred

[Explicitly list what we're NOT doing]

## Tracking

[Analytics events to fire, metrics to monitor — omit if N/A]

## User Flow & Designs

[Link to designs; describe primary flow, empty states, and edge-case screens — omit if N/A]
```

## Issue Structure: Bug Reports

See `examples.md` for the full Bug Report template and worked examples. Core sections: **Bug Description**, **Expected Behaviour**, **Steps to Reproduce**, **Screenshot / Recording**, **Acceptance Criteria**. Always fill all five — if any are unknown, ask via `AskUserQuestion`.

## Issue Structure: Sub-Issues / Tasks

```markdown
## Objective

[1-2 sentences: What specific thing needs to be done?]

## Acceptance Criteria

- [ ] [Specific, testable criterion 1]
- [ ] [Specific, testable criterion 2]
- [ ] [Specific, testable criterion 3]

## Implementation Notes

- Relevant files: [paths]
- Patterns to follow: [reference]
- Dependencies: [other issues]
```

## Writing Good Acceptance Criteria (SMART)

- **Specific**: Clear about what exactly needs to happen
- **Measurable**: Can objectively verify if it's done
- **Achievable**: Within scope of this single issue
- **Relevant**: Directly related to the objective
- **Testable**: Can be validated by running/checking

## Principles for Issue Writing

1. **Self-Contained Context** - Everything needed to understand and execute
2. **What, Not How** - Describe outcome, not implementation
3. **Appropriate Granularity** - Not too big, not too small
4. **Link to Resources** - Design, API docs, related issues
5. **State Assumptions** - Make implicit expectations explicit

## Anti-Patterns to Avoid

- **Vague objectives**: "Improve the dashboard"
- **Missing acceptance criteria**: Assuming it's obvious
- **Implementation prescription**: Over-specifying the how
- **Hidden dependencies**: Not mentioning blockers
- **Scope creep**: Adding "nice to haves"

## Mermaid Diagrams

Linear renders Mermaid natively. Include a diagram whenever the issue involves a multi-step flow, state machine, service interaction, or data model — visual clarity saves back-and-forth. Place it in the Parent issue's "High-Level Implementation" section, in sub-issues where flow context is needed, or in bug reports to contrast expected vs actual behaviour.

See `references.md` for syntax and worked examples of flowchart, sequence, state, and ER diagrams.

Remember: **A good issue can be executed by anyone who reads it.**
