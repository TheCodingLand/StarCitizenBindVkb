---
name: skeptical-evaluator
description: Manually invoked evaluator agent with an explicitly skeptical personality — use when you want an adversarial review of a design, plan, implementation, or idea before committing to it
---

# Skeptical Evaluator

## Overview

A dedicated adversarial reviewer that assumes things are wrong until proven otherwise. Dispatched as a subagent with a skeptical personality baked into its prompt — not a polite reviewer who finds issues, but a contrarian who actively tries to break your reasoning.

**Core principle:** The value of this agent is that it does NOT want you to succeed. It wants to find why you'll fail.

## When to Use

**Manually invoke when:**
- You have a design or spec and want it stress-tested before committing
- A plan feels too clean — no tradeoffs surfaced, no risks identified
- You're about to make an irreversible decision (architecture, public API, data model)
- You've been working in a silo and want a hostile second opinion
- Something feels "too easy" and you suspect hidden complexity
- You want to pressure-test assumptions before presenting to stakeholders

**Don't use when:**
- You need a standard code review (use requesting-code-review)
- You're debugging a specific failure (use systematic-debugging)
- You need to verify work is complete (use verification-before-completion)

## How to Dispatch

### 1. Choose What to Evaluate

The skeptic can evaluate anything with substance:
- Design documents / specs
- Implementation plans
- Code changes (diff or files)
- Architecture decisions
- API contracts
- Technical proposals
- Your reasoning about a tradeoff

### 2. Establish the Done Criteria Contract

Before dispatching the evaluator, the generator (you) and the evaluator must **agree in writing** on what "done" looks like. This is not the claim — the claim is what you believe. The done criteria are the **testable exit conditions** that both sides accept as proof.

This bridges the gap between high-level specs and verifiable implementation. Without it, the evaluator grades on vibes; with it, the evaluator holds you to your own standard.

**Format:** List concrete, binary-testable criteria. Each must be verifiable by the evaluator through code inspection, running the app, or automated checks.

```markdown
**Done Criteria (agreed by generator and evaluator):**
1. WebSocket connection stays open for 60s of inactivity without dropping
2. Error messages include the failing node ID and a human-readable reason
3. All events emitted during execution appear in the Studio viewer in order
4. `forge-dev` starts and serves the API within 3 seconds on a cold start
5. No Python warnings appear in stderr during normal operation
```

The evaluator checks every criterion. A criterion that passes is marked ✅. A criterion that fails is marked ❌ with evidence. Unverifiable criteria are flagged as a finding (the criterion itself is flawed).

**Rules for done criteria:**
- Must be **binary** — pass or fail, no "partially done"
- Must be **observable** — the evaluator can verify it without asking you
- Must be **specific** — no "works correctly" or "handles errors well"
- Should cover **side effects** — not just the happy path output, but all observable consequences

### 3. Prepare Context

The skeptic needs:
- **The artifact** — the thing being evaluated (file path, inline content, or git range)
- **The claim** — what you believe to be true about the artifact ("this design handles all edge cases", "this plan is complete", "this API is intuitive")
- **Done criteria** — the testable exit conditions from Step 2
- **Constraints** — what the skeptic should take as given vs. what's fair game to challenge
- **Custom rubrics** (optional) — domain-specific criteria with 1/3/5 anchors; aspirational language at the 5-level raises the bar

### 4. Dispatch the Subagent

Use the `runSubagent` tool with the prompt template below. Fill in the placeholders.

```
runSubagent:
  description: "Skeptical evaluation of {ARTIFACT_NAME}"
  prompt: |
    [paste contents of skeptical-evaluator-prompt.md with placeholders filled]
```

### 5. Archive the Evaluation

Every invocation of this skill must persist the final skeptical report to the repo.

**Default location:** `docs/skeptical_analysis/`

**Filename format:** `YYYY-MM-DD-<artifact-slug>.md`

**Rules:**
- Always write the report, even if the verdict is Demolished or Wounded.
- Write the report after the subagent returns and before concluding the task.
- Preserve the evaluator's structure and verdict language; do not rewrite it into a softer summary.
- If the folder does not exist, create it.
- If a file for the same artifact and date already exists, append a short suffix such as `-v2` rather than overwriting silently.

### 6. Process the Verdict

The skeptic returns a structured evaluation. Handle it:

| Verdict | Action |
|---------|--------|
| **Demolished** (any rubric = 1, or aggregate ≤ 2.0) | Serious structural problems found. Do NOT proceed. Rethink fundamentals. |
| **Wounded** (any rubric = 2, or aggregate ≤ 3.0) | Real issues that need addressing. Fix before proceeding. |
| **Scratched** (all ≥ 3, aggregate ≤ 4.0) | Minor concerns. Address or consciously accept the risk. |
| **Survived** (all ≥ 3, aggregate > 4.0) | The skeptic couldn't break it. High confidence to proceed. |

**If you disagree with a finding:**
- Re-read it assuming the skeptic is right. Can you prove them wrong with evidence?
- If yes, document your counter-reasoning and proceed.
- If no, the skeptic found something real.

## End-to-End Interaction

The evaluator does not just read code and screenshots. It **interacts with the running application** through its full protocol stack, exercising the actual system end-to-end.

### Principle: Verify Through the Wire

Reading code proves intent. Running code proves behavior. The skeptical evaluator must do both, but **privileges runtime evidence over source analysis** when they conflict.

The evaluator should use every available tool to exercise the system:
- **Playwright** for browser interactions — clicking, typing, navigating, waiting for elements
- **Fetch/HTTP** for API calls — sending requests, checking responses, verifying headers
- **WebSocket clients** for real-time protocols — connecting, sending messages, observing events
- **Terminal commands** for CLI tools — running processes, checking output, measuring timing
- **Browser DevTools** via Playwright — inspecting network traffic, console output, storage state

### Full-Chain Verification

The evaluator traces data through the **entire protocol chain**, not just one hop. If a feature claims "audio is processed through the backend," the evaluator should verify:

1. **Generate input** — e.g., synthesize audio via TTS, construct test payloads
2. **Initiate protocol** — e.g., request microphone permission, open WebSocket connection
3. **Transmit through the system** — e.g., stream audio through the browser to the backend via WebSocket
4. **Verify backend processing** — e.g., confirm the backend received, processed, and responded to the data
5. **Check output fidelity** — e.g., confirm STT returns matching text after the audio round-tripped through the full protocol
6. **Verify all side effects** — every observable consequence of the operation must be checked:
   - Events fired (and in correct order)
   - State mutations (database, in-memory, UI)
   - Logs emitted
   - Error handlers NOT triggered (negative assertions)
   - Cleanup completed (connections closed, temp files removed)

The chain must be tested **as a whole**, not in isolated units. The point is to find the gaps between components — the places where unit tests pass but integration fails.

### Side Effect Coherence

Every action in a system produces side effects beyond its return value. The evaluator must verify **all observable side effects are coherent**:

- If an event is emitted, does the UI reflect it?
- If a WebSocket message is sent, does the recipient's state update?
- If an error occurs mid-chain, are partial results cleaned up?
- If a process completes, are all "in progress" indicators cleared?
- Do timing-sensitive operations handle slow backends without breaking?

### When E2E is Not Possible

If the system can't be run (e.g., evaluating a design doc before implementation), the evaluator should:
1. Identify which done criteria **would require** E2E verification
2. Flag them as "unverifiable at this stage" in findings
3. Specify exact E2E tests to run once implementation exists
4. Score the artifact on what CAN be verified, noting the gap

## What the Skeptic Does NOT Do

- **Does not rewrite your work.** It finds problems, not solutions.
- **Does not soften findings.** If something is broken, it says so directly.
- **Does not praise.** Strengths are acknowledged only to establish that the skeptic actually read the artifact. The focus is on what's wrong.
- **Does not respect sunk cost.** "You already built it" is not a defense against a valid criticism.

## Customizing the Evaluation Focus

### Rubric-Based Scoring

The evaluator scores against explicit rubrics, not vibes. Every artifact is scored on 5 universal rubrics (coherence, completeness, correctness, robustness, assumption hygiene) plus domain-specific rubrics selected by artifact type.

The verdict is **derived from rubric scores**, not chosen independently:
- Any score of 1 → Demolished
- Any score of 2 → Wounded  
- All ≥ 3 but aggregate ≤ 4.0 → Scratched
- All ≥ 3 and aggregate > 4.0 → Survived

This prevents the evaluator from summarizing with "looks good" when scores say otherwise.

### Criteria Language Shapes Output

The phrasing of rubric anchors steers the evaluator before feedback even starts. Compare:

| Weak anchor | Strong anchor | Effect |
|-------------|--------------|--------|
| "Good enough" | "Museum-quality" | Raises aspiration ceiling |
| "Handles errors" | "Every failure mode produces a clear, actionable signal" | Forces specificity |
| "Has tests" | "A developer guesses the right call without reading docs" | Shifts from checkbox to empathy |

When writing custom rubrics, use aspirational language at the 5-level. The evaluator calibrates its scrutiny to match the bar you set.

### Custom Rubrics

Add domain-specific rubrics via the `{ADDITIONAL_RUBRICS_OR_NONE}` placeholder:

```markdown
| X1 | **API Ergonomics** — Can a new developer use this correctly on first try? | Requires reading source code to use correctly | Docs sufficient but verbose | A developer guesses the right call without reading docs |
| X2 | **Naming Precision** — Do names eliminate ambiguity? | Names are misleading or generic | Names are accurate but unremarkable | Every name is the only name that could work |
```

### Focus and Exclusion Directives

Add focus directives to steer skepticism toward specific concerns:

```markdown
**Focus areas (attack these hardest):**
- Concurrency and race conditions
- Error handling under partial failure
- Backward compatibility with existing clients
- Performance at 10x current scale
```

Or exclude areas the skeptic shouldn't waste time on:

```markdown
**Out of scope (don't challenge these):**
- Choice of programming language (decided, non-negotiable)
- Use of SQLite for storage (constraint, not a choice)
```

## Integration with Other Skills

**After brainstorming → before writing-plans:**
Dispatch the skeptic on the spec before creating an implementation plan. Catch design flaws before they become code.

**After writing-plans → before execution:**
Dispatch the skeptic on the plan. Are tasks ordered correctly? Are dependencies identified? Are estimates realistic?

**After implementation → before merge:**
Dispatch the skeptic on the diff. Different from code review — the skeptic isn't checking style or conventions, it's trying to find how the code will fail in production.

**After every skeptical run:**
Archive the full report in `docs/skeptical_analysis/` before you present your final summary.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Dispatching without a clear claim | The skeptic needs something to attack. "Review this" is too vague. State what you believe. |
| Asking vague questions like "Is this good?" | Never. The evaluator scores against rubrics. Frame claims as testable assertions, not quality questions. |
| Treating all findings as blockers | Read the verdict. Scratched ≠ Demolished. |
| Arguing with findings without evidence | Either prove the skeptic wrong with code/data, or accept the finding. |
| Using the skeptic as a rubber stamp | If you dismiss every finding, stop using this tool. |
| Dispatching too early | Half-formed ideas get demolished trivially. Have something concrete first. |
| Dispatching too late | After you've shipped is too late. Use before irreversible decisions. |
| Reviewing code without running it | If the system can be started, the evaluator must interact with it. Code review alone misses integration failures. |
| Skipping side effect verification | Checking only return values is insufficient. Verify events, state mutations, logs, and cleanup. |
| No done criteria contract | Always establish testable exit conditions before dispatching. Without them, the evaluator grades on vibes. |

## Example

```
You've written a spec for a new event bus. You think it's solid.

1. Read the spec
2. State your claim: "This event bus design handles backpressure,
   ordering guarantees, and error propagation correctly."
3. Dispatch the skeptic with the spec file path and your claim
4. Skeptic returns: Wounded
   - "Ordering guarantee claims are contradicted by the fan-out
     design in Section 3. Fan-out is inherently unordered unless
     you add sequencing — which you haven't."
   - "Backpressure strategy assumes consumers are faster than
     producers on average. What happens during sustained bursts
     longer than the buffer?"
   - "Error propagation says 'errors are forwarded to subscribers'
     but doesn't define what happens when the error handler itself
     throws."
5. You fix the spec, re-dispatch. Skeptic returns: Scratched.
6. Proceed to planning.
```

See prompt template at: `skeptical-evaluator/skeptical-evaluator-prompt.md`
