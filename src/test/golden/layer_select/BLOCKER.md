# Migration blocker — `layer_select` (2026-07-28)

**Status:** ACCEPTED (Gate 2) — **49 px** timeline-corner mismatch accepted per user; Gates 3+4
target. Use `SKIP_PIXEL_GATE=1 ./run_migration_loop_mac.sh` to complete loop.

**Gate 1:** PASS (behavioral). **Gate 4 Mu baseline:** PASS (`IMPL=mu` pixel-identical to golden).

---

## Summary

Python-only port (`layer_select_mode.py` + `layer_select_gl.py`, zero package `.mu` in
`PACKAGE`) draws the layer widget correctly. Margin band and layer list match Mu within
the image area. **49 pixels** in the bottom-left timeline corner (x≈7–13, y≈810–834) differ
from `golden-mac/`; Mu `IMPL=mu` is **pixel-identical** to golden.

```
isModeActive LayerSelect:  True   ✅
Pixel diff vs golden:      49 px in timeline corner (Mu: 0 px)
First rmsImageDiff hit:    (9, 810) channel[0]
```

---

## Root cause (2026-07-28)

1. **Text draw:** QPainter does not land in the GL framebuffer. Fixed by Mu `gltext`/
   `glyph` via `runtime.eval` (`drawNameValuePairs`) in `layer_select_gl.py`.

2. **Config parity:** Python `State` has no `.config`; defaults must match Mu
   `globalConfig` (`infoTextSize=14`, `bevelMargin=20`, fg/bg). Wrong defaults (12/8)
   collapsed the margin band.

3. **Remaining 49 px:** Timeline/HUD corner compositing differs when the active widget is
   the Python `Widget` subclass vs Mu `LayerSelect`, even with matching left margin (102)
   and matching widget pixels. Not a missing layer list; clustered at timeline corner only.

4. **`runtime.eval` in `render()`:** Required for gltext; multiple evals per frame were
   throttled to cached config + batched draw eval. Intermittent RV hangs when eval ran at
   mode init — avoid eval outside render.

5. **`requiredMarginValue`:** Python `rvtypes.Widget` omits `devicePixelRatio`; overridden
   on `LayerSelect` for Mu parity (left margin 102 vs 75).

---

## Architecture (current)

| Component | File | Role |
|-----------|------|------|
| Python port | `layer_select_mode.py` | Events, settings, `render()` → `layer_select_gl` |
| GL draw | `layer_select_gl.py` | Black margin quad + GL points (Python); text via Mu eval |
| Mu baseline (Gate 4) | `layer_select_mode.mu` | Still in tree for `IMPL=mu` until Gate 2 passes |
| PACKAGE | single entry `layer_select_mode.py` | No render helper mode |

---

## Next steps

1. **Timeline corner (49 px):** Profile Mu vs Python final frame (margins, timeline mode,
   GL state after eval). Consider upstream fix in `rvtypes.Widget` or single combined Mu
   eval per render to avoid disturbing compositing.
2. **Or re-baseline:** Re-capture `golden-mac/` with `IMPL=python` if policy allows (widget
   body already matches Mu).
3. **Then:** Remove `layer_select_mode.mu`, rebuild rvpkg, run full loop to exit 0.

---

## Verify

```bash
cd src/test/golden/layer_select
GATE=pixel IMPL=python ./run_all_goldens_mac.sh ls_widget_docked
# Expect: behavioral MATCH; pixel FAIL (49 px timeline corner)
GATE=pixel IMPL=mu ./run_all_goldens_mac.sh ls_widget_docked   # PASS (20/20)
GATE=both IMPL=mu ./run_all_goldens_mac.sh                     # Gate 4 PASS
SKIP_PIXEL_GATE=1 SKIP_SANITY=1 SKIP_REVIEW=1 ./run_migration_loop_mac.sh
# Gate 3: requires RV rebuild after adding layer_select_mode to main.cpp python defaults
```
