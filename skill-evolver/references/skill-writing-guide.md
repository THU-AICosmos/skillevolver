# Skill Writing Guide

This guide applies across domains. The target format should work for:

- kernel and systems tasks
- algorithmic and data-processing tasks
- office / document / spreadsheet tasks
- other benchmark families that need reusable agent experience

## Core Philosophy: Knowledge + Reusable Tools, Not End-to-End Pipelines

A good skill has two components: **knowledge the model lacks** and **reusable tools that save repeated work**. The mistake to avoid is bundling the entire task into one script — but the opposite mistake (pure markdown with zero tooling) is just as bad, because every trial wastes turns re-implementing the same helper code.

**What good skills provide:**
- **Knowledge**: Niche APIs, gotchas, silent failure modes, correct tool selection — things the model can't derive from pretraining
- **Single-purpose scripts**: Reusable tools that do ONE thing the agent would otherwise re-write every time (e.g., `recalc.py` that recalculates Excel formulas via LibreOffice — 177 lines, one command: `python recalc.py output.xlsx`)
- **Code examples**: Small, copy-paste-ready snippets showing the right API calls

**What good skills do NOT do:**
- Bundle the entire task workflow into one script (agent becomes a script runner, loses reasoning ability)
- Teach things the LLM already knows (pandas groupby, basic regex, standard file I/O)
- Provide ONLY markdown documentation with no tooling (agent re-implements the same boilerplate every run, wasting tokens and turns)

**The litmus test**: After reading the skill, the agent should still reason about the task — but it should NOT have to re-write common helper code that every trial needs.

**Real examples:**

Bad (over-automated — agent stops thinking):
```
# LaTeX Formula Extraction Skill
## Quick Start
Run the bundled script: `python scripts/extract_formulas.py input.pdf output.md`
The script handles PDF parsing, formula extraction, cleaning, and syntax fixing.
```
→ Agent runs script in 4 turns, script misses cross-type bracket mismatch because programmatic logic can't detect it. LLM reasoning *would* have caught it.

Bad (pure markdown — agent re-invents the wheel every run):
```
# Excel Formula Recalculation Skill
## Key Insight
openpyxl doesn't compute formula values. Use LibreOffice headless to recalculate.
Run: `libreoffice --headless --convert-to xlsx output.xlsx`
```
→ Agent reads the tip, but still spends 5+ turns writing subprocess calls, handling temp dirs, moving files, and verifying. Every trial repeats this boilerplate.

Good (knowledge + reusable tool):
```
# Excel Formula Recalculation Skill
## Key Insight
openpyxl reads/writes formula strings but NOT cached computed values.
After saving with openpyxl, formula cells will contain None when read back.
## Recalculation Tool
Run the bundled script to force-recalculate all formulas:
`python scripts/recalc.py output.xlsx`
The script invokes LibreOffice headless, handles temp files, and verifies
that no formula errors (#REF!, #DIV/0!, etc.) remain.
## Gotchas
- Headers/footers have separate paragraph collections — process them explicitly
- Nested tables: `doc.tables` only returns top-level; recurse via `cell.tables`
```
→ Agent reasons about the task, uses `recalc.py` for the mechanical step, and focuses its turns on the actual problem. 5 turns, correct result.

## Anatomy of a Skill

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter (name, description required)
│   └── Markdown instructions (knowledge + tool usage guide)
└── Bundled Resources (expected for most skills)
    ├── scripts/    - Reusable single-purpose tools
    ├── references/ - API docs, gotcha lists, format specs
    └── assets/     - Files used in output (templates, icons, fonts)
```

## Required Sections

The preferred `SKILL.md` structure is:

```markdown
# <Skill Title>

## What This Skill Is For
## Atomic Operations
## Failure Lessons
## Success Patterns
## Decision Rules
## Anti-Patterns / Do Not Overfit
## References
```

### Section intent

- `What This Skill Is For`
  - Explain the class of problems, not one benchmark item

- `Atomic Operations`
  - Small scripts or snippets that do one reusable thing
  - Each operation should remain useful across multiple tasks in the same family
  - Place executable operations under `scripts/`

- `Failure Lessons`
  - Trace-backed mistakes
  - Include symptom + root cause
  - Put extended lessons and evidence under `references/`

- `Success Patterns`
  - Trace-backed contrasts to the failure lessons
  - Explain why the successful path worked
  - Put extended contrasts and examples under `references/`

- `Decision Rules`
  - Conditional advice in the form:
    - "When you need X and constraints Y hold, do Z"
  - These should be the most reusable part of the skill

- `Anti-Patterns / Do Not Overfit`
  - Explicitly list what must not be copied from the current task

- `References`
  - Point to bundled scripts, docs, APIs, and constraints

## Directory Convention

Within a skill directory:

- `SKILL.md`
  - compact summary
  - decision rules
  - routing layer to other files

- `scripts/`
  - atomic reusable tools
  - should be directly invocable

- `references/`
  - historical lessons
  - success/failure contrasts
  - supporting evidence
  - API and format notes

This split matters. If everything is stuffed into `SKILL.md`, the skill becomes bloated and task-specific. If everything is stuffed into scripts, the agent loses the reasoning layer. Keep the routing and decision layer in `SKILL.md`, the tools in `scripts/`, and the accumulated experience in `references/`.

## What Not To Put In A Skill

Do not turn a skill into:

- a full solution for one task
- a list of shell steps tied to one benchmark file layout
- a document that only makes sense for one domain term set
- a collection of rigid prohibitions without context
- a long implementation pasted from the current winning trial

If you need to preserve a concrete implementation pattern, convert it into:

- an atomic operation script, or
- a decision rule, or
- a failure/success contrast

## Script Decision Checklist

Before finalizing any skill, walk through this checklist. A SKILL.md-only skill is the exception, not the norm — most tasks have at least one mechanical operation worth bundling.

**Step 1: Scan traces for repeated code.** Look for code blocks that appear (with minor variation) across 2+ traces. Common patterns:
- Subprocess calls (LibreOffice, ffmpeg, gnumeric, ImageMagick, pandoc)
- File parsing boilerplate (STL binary parsing, PDF table extraction, OOXML unzipping)
- Data structure construction (matrix building, graph adjacency lists from raw data)
- Output validation (checking file format, verifying computed values, diffing against expected structure)

**Step 2: For each repeated pattern, ask — does this require LLM reasoning?**
- If YES (e.g., interpreting results, choosing parameters, handling ambiguous cases) → keep as code examples in SKILL.md
- If NO (e.g., mechanical parsing, subprocess orchestration, matrix construction from a known formula) → bundle as a script

**Step 3: Write the script.** Each script should:
- Do ONE thing (single "→" in its description)
- Be runnable as a standalone command: `python scripts/tool.py <args>`
- Include a docstring explaining what it does and how to call it
- Handle errors with clear messages (not silent failures)

**If you cannot identify ANY scriptable operation, explain why in your trace analysis.** Pure-markdown skills are valid for tasks where every step genuinely requires LLM judgment (e.g., creative writing, code review), but these are rare. Most domain tasks have at least one mechanical step.

## When to Bundle Scripts

**Bundle a script whenever you see the same operation repeated across traces.** If 3 out of 4 trials all wrote similar subprocess code to recalculate Excel formulas, or all implemented the same CSV parsing boilerplate — that's a strong signal to bundle it as a reusable tool.

**Good candidates for bundled scripts:**
- Operations that require tricky subprocess orchestration (LibreOffice headless, ffmpeg, etc.)
- File format conversions that need precise temp-file handling
- Data parsing that requires binary format knowledge or domain-specific structure (STL meshes, PCAP packets, seismic data)
- Matrix/graph construction from raw input files (susceptance matrices, adjacency lists)
- Validation/verification steps that check output correctness
- Any boilerplate that every trial re-implements from scratch

**What good bundled scripts look like in practice:**
- A binary file parser (50-100 lines) that handles struct unpacking and returns clean Python objects — saves the agent from re-writing format-specific parsing every trial
- A subprocess wrapper (30-80 lines) that orchestrates an external tool (LibreOffice, ffmpeg, gnumeric), handles temp files, and verifies success — eliminates a class of bugs around wrong flags, missing cleanup, and silent failures
- A matrix/graph builder (30-60 lines) that constructs domain-specific data structures from raw input files — prevents re-deriving formulas and index mappings each run

Each of these patterns saves 5-10 turns per trial and eliminates recurring bugs (off-by-one in parsing, wrong subprocess flags, missing temp-file cleanup).

| Good (single-purpose tool) | Bad (end-to-end pipeline) |
|---|---|
| `recalc.py` (80 lines) — recalculates spreadsheet formulas via external engine | `extract_formulas.py` (313 lines) — PDF→extract→clean→fix→output |
| `parse_binary.py` (90 lines) — parses a domain-specific binary format into objects | `build_pivot_report.py` (283 lines) — PDF→extract→merge→pivot→write |
| `build_matrix.py` (45 lines) — constructs a numeric matrix from structured input | `update_embedded_excel.py` (248 lines) — extract→parse→modify→save |
| `validate_output.py` (50 lines) — checks output file for common errors | `solve_and_report.py` (200 lines) — parse→solve→format→write |

**The rule**: If a script has more than one "→" in its description, it's doing too much. Split it into single-purpose tools and let the agent orchestrate. But DO write the single-purpose tools — a pure-markdown skill that teaches knowledge without providing any tooling forces every trial to waste turns on the same boilerplate.

## Decision Rule Style

Prefer this:

- "When strict structural compatibility matters, preserve module names and state_dict keys exactly."
- "When runtime discovery is needed, derive filenames from the instruction and directory contents instead of hardcoding them."
- "When a performance shortcut repeatedly fails verifier constraints, demote it behind a guarded check rather than banning it globally."

Avoid this:

- "Always use X"
- "Never use Y"
- "Run these exact five commands"

Absolute language is allowed only when repeated trace evidence and task constraints justify it.

## Failure/Success Contrast Pattern

Write lessons as pairs whenever possible:

- Failure:
  - "Adding a buffer introduced extra state_dict keys and caused strict weight loading to fail."
- Success:
  - "Keeping module structure unchanged preserved strict load_state_dict compatibility while still allowing channels_last and autotuning."

This paired format is much more reusable than isolated warnings.

## Generalization Test

Before finalizing a skill, ask:

1. Would this still make sense if all filenames changed?
2. Would this still make sense if the next task was a related architecture but not the same model?
3. Would this still make sense if the same failure mode appeared in a different domain?
4. Is the skill teaching a rule, or merely preserving a local fix?

If the answer to most of these is "no", the skill is still too task-specific.

## Progressive Disclosure

Skills use a three-level loading system:
1. **Metadata** (name + description) - Always in context (~100 words)
2. **SKILL.md body** - In context whenever skill triggers (<500 lines ideal)
3. **Bundled resources** - As needed (unlimited, scripts can execute without loading)

**Key patterns:**
- Keep SKILL.md under 500 lines; if you're approaching this limit, add an additional layer of hierarchy along with clear pointers about where the model using the skill should go next to follow up.
- Reference files clearly from SKILL.md with guidance on when to read them
- For large reference files (>300 lines), include a table of contents

**Domain organization**: When a skill supports multiple domains/frameworks, organize by variant:
```
cloud-deploy/
├── SKILL.md (workflow + selection)
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```
Claude reads only the relevant reference file.

## Writing Style

- Prefer imperative form in instructions
- Explain **why** things are important instead of heavy-handed MUSTs
- Use theory of mind — make the skill general, not super-narrow to specific examples
- Start by writing a draft, then look at it with fresh eyes and improve it
- Skills must not contain malware, exploit code, or any content that could compromise system security
