# Fyndnot Rebrand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename all "label-tool" / "Labeling Tool" references to "fyndnot" and replace the favicon with the new rocks & gems logo.

**Architecture:** Simple find-and-replace across 9 files. The favicon SVG is replaced entirely. No logic changes, no new dependencies.

**Tech Stack:** Vanilla file edits.

---

### Task 1: Frontend Favicon — Rocks & Gems SVG

**Files:**
- Modify: `frontend/public/favicon.svg` (full replace)
- Modify: `frontend/public/icons.svg` (no change needed — only favicon)

- [ ] **Step 1: Read existing favicon to confirm path**

- [ ] **Step 2: Replace favicon.svg with rocks & gems logo**

Content to write:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="140" height="140" viewBox="0 0 140 140" fill="none">
  <ellipse cx="70" cy="116" rx="44" ry="8" fill="#fbbf24" opacity="0.12"/>
  <polygon points="80,95 110,85 115,65 95,58 72,68 70,88" fill="#ea580c" stroke="#c2410c" stroke-width="2" opacity="0.25"/>
  <polygon points="95,58 104,64 92,68" fill="#fdba74" opacity="0.15"/>
  <polygon points="35,100 25,80 40,65 65,72 60,100" fill="#fed7aa" stroke="#fdba74" stroke-width="2"/>
  <polygon points="40,65 50,68 42,78" fill="#ffedd5" opacity="0.5"/>
  <polygon points="75,105 100,100 110,78 95,68 72,78" fill="#fed7aa" stroke="#fdba74" stroke-width="2"/>
  <polygon points="95,68 102,75 90,77" fill="#ffedd5" opacity="0.5"/>
  <polygon points="50,82 65,70 85,72 88,90 55,95" fill="#fef3c7" stroke="#fde68a" stroke-width="2"/>
  <polygon points="65,70 72,72 68,82" fill="#fffbeb" opacity="0.5"/>
  <polygon points="55,55 62,38 72,42 68,60" fill="#f97316" stroke="#ea580c" stroke-width="1.5"/>
  <polygon points="55,55 68,60 63,52" fill="#fdba74" opacity="0.5"/>
  <polygon points="62,38 66,40 64,50" fill="#fdba74" opacity="0.4"/>
  <polygon points="75,50 82,35 90,45 85,58" fill="#a855f7" stroke="#9333ea" stroke-width="1.5"/>
  <polygon points="75,50 85,58 80,51" fill="#d8b4fe" opacity="0.5"/>
  <polygon points="82,35 86,38 83,48" fill="#d8b4fe" opacity="0.4"/>
  <polygon points="45,62 50,52 55,62 50,68" fill="#fbbf24" stroke="#f59e0b" stroke-width="1.5"/>
  <polygon points="45,62 50,68 48,63" fill="#fde68a" opacity="0.5"/>
  <path d="M92 28l1.5 4 4 1.5-4 1.5-1.5 4-1.5-4-4-1.5 4-1.5 1.5-4z" fill="#fbbf24"/>
</svg>
```

- [ ] **Step 3: Commit favicon change**

```bash
git add frontend/public/favicon.svg
git commit -m "feat: replace favicon with fyndnot rocks & gems logo"
```

---

### Task 2: Frontend Title and Name

**Files:**
- Modify: `frontend/index.html` — `<title>frontend</title>` → `<title>fyndnot</title>`
- Modify: `frontend/package.json` — `"name": "frontend"` → `"name": "fyndnot"`

- [ ] **Step 1: Update index.html title**

In `frontend/index.html:7`, change `<title>frontend</title>` to `<title>fyndnot</title>`.

- [ ] **Step 2: Update package.json name**

In `frontend/package.json:2`, change `"name": "frontend"` to `"name": "fyndnot"`.

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html frontend/package.json
git commit -m "feat: rename frontend title and package name to fyndnot"
```

---

### Task 3: LoginView Heading

**Files:**
- Modify: `frontend/src/views/LoginView.tsx:35` — "Label Tool" heading

- [ ] **Step 1: Update heading text**

In `frontend/src/views/LoginView.tsx:35`, change:
```tsx
<h1 className="text-xl font-bold text-[var(--color-text-heading)]">
  Label Tool
</h1>
```
to:
```tsx
<h1 className="text-xl font-bold text-[var(--color-text-heading)]">
  fyndnot
</h1>
```

Also update the subtitle at line 37-39:
```tsx
<p className="text-sm text-[var(--color-text-muted)] mt-1">
  Sign in to start labeling
</p>
```
→
```tsx
<p className="text-sm text-[var(--color-text-muted)] mt-1">
  Discover. Annotate. Export.
</p>
```

And update the icon letter at line 31-33:
```tsx
<div className="w-12 h-12 rounded-xl bg-gradient-to-br from-sunset-500 to-coral-500 flex items-center justify-center text-white text-lg font-bold mb-3 shadow-sm">
  L
</div>
```
→
```tsx
<div className="w-12 h-12 rounded-xl bg-gradient-to-br from-sunset-500 to-coral-500 flex items-center justify-center text-white text-lg font-bold mb-3 shadow-sm">
  f
</div>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/LoginView.tsx
git commit -m "feat: update LoginView branding to fyndnot"
```

---

### Task 4: Backend FastAPI Title

**Files:**
- Modify: `backend/main.py:6` — FastAPI title

- [ ] **Step 1: Update FastAPI title**

In `backend/main.py:6`, change:
```python
app = FastAPI(title="Labeling Tool")
```
to:
```python
app = FastAPI(title="fyndnot")
```

- [ ] **Step 2: Commit**

```bash
git add backend/main.py
git commit -m "feat: rename FastAPI title to fyndnot"
```

---

### Task 5: Documentation Updates

**Files:**
- Modify: `README.md` — title and description
- Modify: `AGENTS.md` — heading
- Modify: `features/plans/2026-08-13-labeling-tool-implementation.md` — title (first line)
- Modify: `features/architecture-decision.md` — title (first line)

- [ ] **Step 1: Update README.md**

In `README.md:1`, change `# Labeling Tool` to `# fyndnot`.
In `README.md:3`, change description to mention "fyndnot".

- [ ] **Step 2: Update AGENTS.md heading**

In `AGENTS.md:7`, change `# Anchored Summary — Labeling Tool (complete)` to `# Anchored Summary — fyndnot (complete)`.

- [ ] **Step 3: Update implementation plan doc**

In `features/plans/2026-08-13-labeling-tool-implementation.md:1`, change `# Labeling Tool Implementation Plan` to `# fyndnot Implementation Plan`.

- [ ] **Step 4: Update architecture decision doc**

In `features/architecture-decision.md:1`, change `# Architecture Decision Record — Labeling Tool` to `# Architecture Decision Record — fyndnot`.

- [ ] **Step 5: Commit**

```bash
git add README.md AGENTS.md features/plans/2026-08-13-labeling-tool-implementation.md features/architecture-decision.md
git commit -m "docs: rename documentation references to fyndnot"
```

---

### Task 6: Verify No Remaining References

- [ ] **Step 1: Search for remaining references**

```bash
rg -i "label.?tool|labeling" --include="*.{md,py,tsx,ts,json,html,svg}" --no-ignore
```

Expected: Only hits in `.git/` or irrelevant matches. If any remain, update them.

- [ ] **Step 2: Verify frontend builds**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: Build succeeds with no errors.

- [ ] **Step 3: Commit any final fixes**

```bash
git add -A
git commit -m "chore: finalize fyndnot rebrand"
```
