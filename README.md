# Fournil — handoff package for Claude Code

## How to use it

1. Create an empty GitHub repository (e.g. `fournil`) and clone it.
2. Copy everything from this folder into the repo root and commit.
3. Open Claude Code in the repo. It reads `CLAUDE.md` automatically.
4. Start with this prompt:

> Read CLAUDE.md, docs/SPEC.md, docs/DATA.md, docs/PLAN.md and design/README.md.
> Then do milestone M0 only. Before writing code, list anything in the docs that is unclear
> or contradictory and ask me. When M0 is done, show me how to check it and stop.

5. Then one milestone per session: "Do M1", "Do M2"… Review and test each one before moving on.

## What's inside

| Path | Content |
|---|---|
| `CLAUDE.md` | Rules Claude Code follows on every task: stack, conventions, privacy, definition of done |
| `docs/SPEC.md` | Product spec: users, screens, scoring, delivery mode, commune page, open questions |
| `docs/DATA.md` | Data sources, join keys, pipeline layout, output files, quality checks |
| `docs/PLAN.md` | Milestones M0–M7 with acceptance criteria, plus the "later" list |
| `design/` | The three mockups, design tokens and the reference algorithms |

## Decisions already made
National absolute score · range sliders follow the visible area · commune boundaries, not bubbles ·
département view counts Go communes · delivery mode with Distance or Contiguous communes ·
details in a pinned card + a full commune page · paid features later · leads only with opt-in.

## Still open (see SPEC §7)
Product name · onboarding questions or not · takeover/new-opening presets vs separate scores ·
reference city on the commune page · crime criterion on by default.

## Run it locally

```
uv sync                              # Python 3.12 + dev tools (first time only)
uv run python scripts/serve.py       # http://localhost:8000/
```

The site is plain HTML/CSS/JS (no build step). `scripts/build_site.sh` assembles `public/` + `src/`
into `_site/`, which the GitHub Action deploys to https://yoanngrange.github.io/fournil/ on every push to `main`.
