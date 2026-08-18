# Rebrand: label-tool → fyndnot

## Goal
Rename the project from "Labeling Tool" / "label-tool" to **fyndnot** across the entire codebase, and replace the favicon/logo with a new "rocks & gems" SVG mark.

## Name
**fyndnot** — "fynd" (Swedish for find/discovery) + "not" (short for notation).
An annotation tool for discovering and marking data.

## Logo
Rocks & gems concept:
- Pile of 3-4 warm orange/brown angular stones
- Background stone (slightly darker, semi-transparent) for depth
- Faceted crystals on top in sunset coral (#f97316), violet (#a855f7), and amber (#fbbf24)
- Small sparkle above
- Color palette consistent with existing frontend (sunset/coral/violet gradient)

## Files to update

### Frontend
| File | Change |
|------|--------|
| `frontend/index.html` | `<title>` from `frontend` to `fyndnot` |
| `frontend/package.json` | `"name"` from `frontend` to `fyndnot` |
| `frontend/public/favicon.svg` | Replace with rocks & gems SVG |
| `frontend/src/views/LoginView.tsx` | "Label Tool" heading → "fyndnot" |

### Backend
| File | Change |
|------|--------|
| `backend/main.py` | `FastAPI(title="Labeling Tool")` → `FastAPI(title="fyndnot")` |

### Documentation
| File | Change |
|------|--------|
| `README.md` | Title + description updated |
| `AGENTS.md` | Heading updated |
| `features/plans/2026-08-13-labeling-tool-implementation.md` | Title updated |
| `features/architecture-decision.md` | Title updated |

## Logo SVG (final)
```svg
<svg xmlns="http://www.w3.org/2000/svg" width="140" height="140" viewBox="0 0 140 140" fill="none">
  <!-- Shadow base -->
  <ellipse cx="70" cy="116" rx="44" ry="8" fill="#fbbf24" opacity="0.12"/>
  <!-- Background stone -->
  <polygon points="80,95 110,85 115,65 95,58 72,68 70,88" fill="#ea580c" stroke="#c2410c" stroke-width="2" opacity="0.25"/>
  <polygon points="95,58 104,64 92,68" fill="#fdba74" opacity="0.15"/>
  <!-- Rock 1 (bottom left) -->
  <polygon points="35,100 25,80 40,65 65,72 60,100" fill="#fed7aa" stroke="#fdba74" stroke-width="2"/>
  <polygon points="40,65 50,68 42,78" fill="#ffedd5" opacity="0.5"/>
  <!-- Rock 2 (bottom right) -->
  <polygon points="75,105 100,100 110,78 95,68 72,78" fill="#fed7aa" stroke="#fdba74" stroke-width="2"/>
  <polygon points="95,68 102,75 90,77" fill="#ffedd5" opacity="0.5"/>
  <!-- Rock 3 (center) -->
  <polygon points="50,82 65,70 85,72 88,90 55,95" fill="#fef3c7" stroke="#fde68a" stroke-width="2"/>
  <polygon points="65,70 72,72 68,82" fill="#fffbeb" opacity="0.5"/>
  <!-- Crystal 1 (orange) -->
  <polygon points="55,55 62,38 72,42 68,60" fill="#f97316" stroke="#ea580c" stroke-width="1.5"/>
  <polygon points="55,55 68,60 63,52" fill="#fdba74" opacity="0.5"/>
  <polygon points="62,38 66,40 64,50" fill="#fdba74" opacity="0.4"/>
  <!-- Crystal 2 (violet) -->
  <polygon points="75,50 82,35 90,45 85,58" fill="#a855f7" stroke="#9333ea" stroke-width="1.5"/>
  <polygon points="75,50 85,58 80,51" fill="#d8b4fe" opacity="0.5"/>
  <polygon points="82,35 86,38 83,48" fill="#d8b4fe" opacity="0.4"/>
  <!-- Crystal 3 (amber) -->
  <polygon points="45,62 50,52 55,62 50,68" fill="#fbbf24" stroke="#f59e0b" stroke-width="1.5"/>
  <polygon points="45,62 50,68 48,63" fill="#fde68a" opacity="0.5"/>
  <!-- Sparkle -->
  <path d="M92 28l1.5 4 4 1.5-4 1.5-1.5 4-1.5-4-4-1.5 4-1.5 1.5-4z" fill="#fbbf24"/>
</svg>
```
