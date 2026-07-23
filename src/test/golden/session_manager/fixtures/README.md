# Real-media fixtures

`bars_frame.jpg` (single-frame JPEG) and `bars_clip.mp4` (8-frame, 8fps,
64x48 movie) are tiny **real files** used by the `sm_media_*`/`sm_button_*`
scenarios that need to exercise the real-file loading and thumbnail/filmstrip
pipeline -- the `movieproc` procedural sources most other scenarios use never
touch that code path.

These are inputs, not goldens: they don't need to be bit-reproducible across
regenerations, only the `session.rv`/`panel.png` captured *from* them do.
Regenerate with `./regenerate_fixtures.sh` (uses this repo's own `rvio`, no
external tool dependency) only if a fixture needs to change, and commit the
resulting bytes.

## Environment variables (all file paths)

No paths are hardcoded in the repo. Set these via the shell or `mp4.env`:

| Variable | Required | Purpose |
|---|---|---|
| `SM_TEST_MP4_DIR` | for `sm_mp4_all.py` | Directory of `*.mp4` clips to load |
| `SM_TEST_MP4_FIXTURE` | optional | Single MP4 for `sm_mp4_load.py` |
| `SM_TEST_MP4_QUIESCE` | optional | `1` = wait for thumbnail+filmstrip on every clip (slow) |
| `SM_TEST_IMAGE_FIXTURE` | optional | Still image (default: `bars_frame.jpg` here) |
| `SM_TEST_MOVIE_FIXTURE` | optional | Single movie (default: `bars_clip.mp4` here) |

Local setup:

```bash
cp mp4.env.example mp4.env
# edit mp4.env — it is gitignored
./run_mp4_integration.sh
```

Or export directly:

```bash
export SM_TEST_MP4_DIR=/path/to/mp4/clips
python3 src/test/golden/harness/run_scenario.py \
  --scenario src/test/golden/session_manager/scenarios/sm_mp4_all.py \
  --out /tmp/mp4_all --impl python --timeout 7200
```

Scenarios:

- `sm_mp4_load.py` — one MP4 + preview quiesce (golden-capable)
- `sm_mp4_all.py` — every `*.mp4` in `SM_TEST_MP4_DIR` (integration only)
