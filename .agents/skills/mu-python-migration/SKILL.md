---
name: mu-python-migration
description: >-
  Orchestrate migrating an RV plugin package from Mu to Python via golden tests.
  Use when the user asks to port, migrate, or convert a Mu package to Python,
  build coverage, capture baselines, or run the migration loop.
---

# Mu → Python migration

**Read first:** [`src/test/golden/VERIFICATION.md`](../../src/test/golden/VERIFICATION.md)
(migration loop, gates, harness, definition of done). Package inventory:
`src/test/golden/<package>/COVERAGE.md`.

One **migration loop** per package — port the **whole package**. You may work through
areas in any order inside the loop, but Mu sources stay until everything in
`COVERAGE.md` passes.

Follow these phases in order. Do not skip user checkpoints.

## 1. Confirm package

Ask the user which package to migrate (`src/plugins/rv-packages/<name>/`).

## 2. File inventory

Identify:

- Mu sources (`.mu`, `.mu.in`, generated outputs)
- Existing Python in the package
- Assets to keep unchanged (`.ui`, icons, `PACKAGE`, images)
- Files to create (Python port, scenarios under `src/test/golden/<package>/scenarios/`)
- **External callers** — other packages or scripts that depend on this package

Present the list to the user. After they approve, record it in the package's `COVERAGE.md`
(create `src/test/golden/<package>/COVERAGE.md` if it does not exist yet).

## 3. Behavior coverage

Find every observable behavior in the package. Be extremely thorough — launch parallel
agents for large packages if needed.

**Discovery checklist:**

- Event bindings and handlers (what fires on graph/UI changes)
- Menus, buttons, shortcuts, dialogs
- Property reads/writes and cross-node effects
- Qt subclass overrides (especially drag/drop and custom widgets)
- Toggle combinations — exercise on/off pairs that change visual or behavioral outcomes
- **Trigger vs outcome** — command-API scenarios pin outcomes; note real UI triggers still
  needed as separate scenarios when closing 🟡 gaps

**Real media:** if a behavior needs loading files (thumbnails, codecs, paths), ask the user
how to supply fixtures — do not hardcode machine-specific paths in the repo.

**Scenarios:** one file = one linear scripted run. A scenario may chain many steps and write
multiple PNG artifacts; `compare.py` diffs all of them. Behaviors with no deterministic
outcome belong in COVERAGE.md's **Dropped** section, not as eternal ⬜ items.

Map each behavior to gate(s) **B** / **P**, status (✅/🟡/⬜), and scenario id in
`COVERAGE.md`.

## 4. Baselines

Ask the user for permission before capturing or committing goldens.

Use the capture workflow in `VERIFICATION.md` — never hand-edit files under `golden/` or
`golden-mac/`.

## 5. Migration loop

Ask the user whether `COVERAGE.md` is complete, Mu baselines are committed, and you may
start the loop. Follow [`VERIFICATION.md`](../../src/test/golden/VERIFICATION.md#migration-loop-4-mandatory-gates--conditional-sanity--review).

If they approve:

1. Implement the Python port for the **entire package** (tackle areas in any order).
2. **Run the migration loop** until it passes (max 15 failed runs) — method in
   [`VERIFICATION.md`](../../src/test/golden/VERIFICATION.md#migration-loop-4-mandatory-gates--conditional-sanity--review):
   ```bash
   cd src/test/golden/<package>
   ./run_migration_loop_mac.sh   # or run_migration_loop.sh on Linux
   ```
3. **Loop algorithm:** fix port → run orchestrator → if non-zero, diagnose and repeat.
   Package-specific harness notes and failure hints: `COVERAGE.md` for that package.
4. Do not remove Mu sources until the user approves, after the full package passes.
5. Update `COVERAGE.md` statuses as behaviors go green.
