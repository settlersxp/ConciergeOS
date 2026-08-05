# Reusable Prompt: Generate Slidev Presentation from Git Branch Analysis

Copy and adapt this prompt to generate Slidev presentations that walk through the development journey of a feature branch, including problems encountered, solutions applied, tests performed, and lessons learned.

---

## Prompt Template

```
Create a Slidev-compatible markdown presentation based on the following analysis of a git branch.

### Input
- Git branch: [BRANCH_NAME]
- Relevant commits: [LIST_COMMITS or "analyze the branch history"]
- Topic: [TOPIC_DESCRIPTION]

### Requirements

#### 1. Frontmatter
Use this Slidev configuration:
- theme: default
- class: text-center
- highlighter: shiki
- lineNumbers: true
- transitions: slide-up
- Enable PlantUML with: plantuml.open = https://www.plantuml.com/plantuml/svg/
- Enable KaTeX if math formulas are needed: katex: true
- Set customFields with title

#### 2. Slide Structure (follow this flow)

**Slide 1 — Title**
- Main title describing the topic
- Subtitle with a hook (what went wrong / what was learned)
- One-liner description
- Show branch name and key commit hash

**Slide 2 — Architecture Overview (layout: two-cols)**
- Left column: PlantUML diagram showing the system architecture (request flow, services, ports)
- Right column: Bullet list of services with short descriptions
- Use `::right::` separator

**Slide 3 — Goal**
- State what the feature/fix was supposed to achieve
- Use a Markdown table if comparing users, roles, or configurations
- Keep it concise

**Slide 4+ — Step-by-step walk-through (layout: default)**
- Each slide = one step in the development journey
- Title format: "Step N — [Short description]"
- If there was a problem encountered, use this pattern:
  - `<h3 class="text-red-500 font-bold">PROBLEM: [description]</h3>`
  - `<h3 class="text-green-200 font-bold">Fix in `[FILE]`:</h3>`
  - Show code diff or relevant code block
- If it was a setup/initialization step:
  - Show configuration files with code blocks
  - Label each config file

**Mid-point slide — Interim Results (layout: two-cols)**
- Show what worked at this point
- Left: status description
- Right: Markdown table with test results or state comparison
- Use `::right::` separator

**Later slides — Test Results (layout: two-cols)**
- Left: test result tables with ✅ / ❌ indicators
- Right: PlantUML diagram showing final architecture flow

**Comparison slide — BEFORE/AFTER**
- Show BEFORE state with PlantUML diagram
- Show AFTER state with PlantUML diagram
- Highlight what changed

**Analysis slide — Why It Failed / Lessons**
- Use `<h3 class="text-yellow-500 font-bold">[heading]:</h3>` for callouts
- Bullet points or numbered lists
- Keep it scannable

**Lessons Learned**
- Use a Markdown table with columns: # | Lesson
- Number each lesson
- Bold the key takeaway, then elaborate

**Conceptual comparison (layout: two-cols)**
- Use `::left::` and `::right::` to compare two concepts (e.g., Groups vs Permissions)
- Use bullet lists under each side

**Correct Approach (layout: default)**
- Step-by-step recommendation
- Show code snippets
- Use `<h3 class="text-green-500 font-bold">N. [step title]:</h3>` for numbered steps

**Summary slide**
- Blockquote with the main takeaway message
- Keep it to 2-3 sentences max

**Q&A slide (layout: full, class: text-center)**
- "# Q&A" + "## Questions?"

#### 3. PlantUML Diagram Rules
- Always wrap in `@startuml` / `@enduml`
- Use `skinparam rectangle { BackgroundColor White, BorderColor Black }` for styling
- Use `rectangle "Name" as alias` for components
- Use `note "label" as n` + `n -right-> component` for route labels
- Use `-right->` for arrows between components
- Do NOT use `participant` (sequence-only, causes errors)
- Do NOT use color syntax inline with rectangle labels (causes parser confusion)
- Keep diagrams simple: 3-4 components max per diagram

#### 4. Styling Rules
- Use Tailwind CSS utility classes for colored headings:
  - Problems: `<h3 class="text-red-500 font-bold">`
  - Fixes: `<h3 class="text-green-200 font-bold">`
  - Warnings: `<h3 class="text-yellow-500 font-bold">`
  - Recommendations: `<h3 class="text-green-500 font-bold">`
- Do NOT mix code blocks and regular text as subtitles on the same column (use bullet lists instead)
- Keep code blocks focused (only show relevant lines)
- Use Markdown tables for structured data comparisons
- The conclussion slide should always be vertically centered

#### 5. Layouts Available
- `default` — single column
- `two-cols` — left + right with `::right::` separator
- `image-left` — image on left, content on right (requires `image:` frontmatter)
- `full` — full width, no title bar

#### 6. Code Block Rules
- Always specify language for syntax highlighting (python, yaml, json, toml, shell)
- Show BEFORE/AFTER diffs inline with comments when applicable
- Keep snippets under 15 lines when possible
- Add file path labels above each block

#### 7. What NOT to do
- Do NOT use LaTeX/KaTeX for diagrams or tables (plain Markdown is preferred)
- Do NOT use unsupported layouts (e.g., `three-cols`, `aside`)
- Do NOT use `participant` in PlantUML (only `rectangle`)
- Do NOT use inline colors in PlantUML rectangle labels
- Do NOT create overly granular checklists or verbose slides
```

---

## Quick Start: How to Use

1. **Analyze a git branch** — identify commits, files changed, problems, solutions
2. **Fill in** `[BRANCH_NAME]`, `[LIST_COMMITS]`, `[TOPIC_DESCRIPTION]`
3. **Paste the prompt** into your AI assistant
4. **Review** the generated `.md` file for:
   - PlantUML syntax correctness
   - Slidev layout validity
   - Consistent styling
5. **Run** with `npx slidev your_file.md --open`