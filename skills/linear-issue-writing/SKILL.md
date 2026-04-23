---
name: linear-issue-writing
description: Use this skill when writing, reviewing, or discussing Linear issue descriptions, acceptance criteria, bug reports, exploration/discovery tickets, or task breakdowns. Covers four issue types — Parent Feature, Sub-Issue/Task, Bug Report, and Exploration (discovery-phase tickets that answer open questions before execution is scoped). Triggers when drafting issues, filing bugs, starting a design/feature/tech exploration, defining requirements, or when users ask "how should I write this issue?" or "what should the acceptance criteria be?"
---

# Issue Writing Skill

This skill guides the creation of well-structured, actionable Linear issues that any developer or AI can pick up and execute independently.

## Clarifying Questions Before Drafting

**Before drafting any issue, identify the issue type (Parent Feature, Sub-Issue/Task, Bug Report, or Exploration), then use the `AskUserQuestion` tool _once, upfront_, to resolve the most important unknowns for that type.** Batch 2-4 questions in a single `AskUserQuestion` call rather than asking one at a time.

**While drafting, if new open questions emerge that weren't covered upfront — especially ones the user hasn't thought about — call `AskUserQuestion` again to refine them.** Do not silently guess: surfacing a gap is more valuable than filling it with an assumption.

### Match the template to the phase

Exploration tickets are discovery-phase — their job is to surface and answer open questions, not prescribe execution. **Do NOT convert an exploration ticket into a Parent Feature** (with Solution / High-Level Implementation / Acceptance Criteria) — that flattens open questions into premature decisions. Use the Exploration template when any of the following apply:

- The title contains "Exploration", "Design Exploration", "Feature Exploration", "Spike", or similar framing
- The ticket has more open questions than decided answers
- The user describes the work as "figure out", "explore", "decide between", "spike", or "understand"
- You are enriching an existing ticket whose current body is exploratory — preserve that framing, don't overwrite it with an execution spec

Use Parent Feature / Sub-Issue / Bug Report templates when the work is in the delivery phase — the what-and-why is already decided and the ticket exists to scope or ship it.

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

**Exploration** — ask upfront:

- What triggered this exploration? (customer pain, strategic shift, tech concern, design review outcome, unresolved debate)
- What are the key open questions this exploration must answer?
- Is there a decision-forcing function or deadline? (upcoming launch, town hall, dependent project milestone)
- Who are the stakeholders whose alignment this exploration needs?
- Are there existing mockups, competitor examples, SDDs, research, or prior Linear issues to seed the doc?
- What parallel work is blocked on this exploration's output?

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

## Issue Structure: Exploration Issues

Use this template for any issue whose purpose is to answer open questions _before_ execution is scoped — design exploration, feature exploration, tech spikes, product discovery.

```markdown
## Context

[1–3 sentences: What triggered this exploration? Why is it being done now? What's unclear or contested?]

## Key Questions

[The unresolved questions driving this exploration. The north star of the ticket. Check off as they get answered; move the resolved ones into the Decisions Log with their rationale.]

- [ ] Question 1
- [ ] Question 2

## Hypotheses & Directions Being Considered

[Working theories, alternative approaches, tradeoffs. Do not pick a winner prematurely — this is the place to hold multiple ideas.]

- **Option A:** [description] — pros / cons
- **Option B:** [description] — pros / cons

## References & Prior Art

[Mockups, competitor examples, design system notes, SDDs, research, linked Linear issues, meeting notes.]

## Decisions Log

[Running log of resolved questions. One line per decision.]

- **YYYY-MM-DD** — [decision]. Rationale: […]. Decided by: […].

## Exit Criteria

[Explicit criteria for when the exploration is "Done". An exploration ticket only closes when these are met.]

- [ ] All Key Questions answered or explicitly deferred (with reason)
- [ ] Follow-up execution tickets drafted and linked in Follow-Up Work
- [ ] Stakeholder alignment confirmed (list who)

## Follow-Up Work

[Execution-oriented Parent Feature / sub-issue tickets that come OUT of this exploration. Link them as they're drafted — these are the concrete deliverables the exploration produces.]

- [ ] ENG-XX — [title]
```

**Lifecycle:** An Exploration ticket is only "Done" when Exit Criteria are met _and_ follow-up execution tickets exist. Closing an exploration without follow-up work leaves a zombie ticket — the discovery happened but nothing downstream captures what to ship.

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
6. **Match the template to the phase** - Discovery work uses the Exploration template; delivery work uses Parent Feature / Sub-Issue / Bug Report. Don't use execution-phase structure for discovery-phase work.

### Template decision matrix

| Phase                | Ticket purpose                                          | Template             |
| -------------------- | ------------------------------------------------------- | -------------------- |
| Discovery            | Surface and answer open questions before scope is fixed | **Exploration**      |
| Delivery (scoping)   | Define what will be built and why                       | **Parent Feature**   |
| Delivery (execution) | Ship a specific vertical slice                          | **Sub-Issue / Task** |
| Regression           | Fix behaviour that used to work                         | **Bug Report**       |

If the ticket sits in the discovery phase, use the Exploration template regardless of whether the title uses the word "feature".

## Anti-Patterns to Avoid

- **Vague objectives**: "Improve the dashboard"
- **Missing acceptance criteria**: Assuming it's obvious (for execution-phase tickets)
- **Implementation prescription**: Over-specifying the how
- **Hidden dependencies**: Not mentioning blockers
- **Scope creep**: Adding "nice to haves"
- **Exploration → Parent Feature conversion**: Rewriting a discovery-phase ticket as if it were ready to deliver — flattens open questions into premature decisions. Use the Exploration template and preserve the questions.
- **Acceptance Criteria on Exploration tickets**: Testable-code criteria don't apply to discovery work. Use Exit Criteria instead.
- **Zombie Explorations**: Closing an exploration ticket without drafting follow-up execution tickets. Exit Criteria must include linked follow-up work.

## Mermaid Diagrams

Linear renders Mermaid natively. Include a diagram whenever the issue involves a multi-step flow, state machine, service interaction, or data model — visual clarity saves back-and-forth. Place it in the Parent issue's "High-Level Implementation" section, in sub-issues where flow context is needed, or in bug reports to contrast expected vs actual behaviour.

See `references.md` for syntax and worked examples of flowchart, sequence, state, and ER diagrams.

Remember: **A good issue can be executed by anyone who reads it.**
