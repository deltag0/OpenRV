# Real-media fixtures

`bars_frame.jpg` (single-frame JPEG) and `bars_clip.mov` (8-frame, 8fps,
64x48 movie) are tiny **real files** used by the `sm_media_*`/`sm_button_*`
scenarios that need to exercise the real-file loading and thumbnail/filmstrip
pipeline -- the `movieproc` procedural sources most other scenarios use never
touch that code path.

These are inputs, not goldens: they don't need to be bit-reproducible across
regenerations, only the `session.rv`/`panel.png` captured *from* them do.
Regenerate with `./regenerate_fixtures.sh` (uses this repo's own `rvio`, no
external tool dependency) only if a fixture needs to change, and commit the
resulting bytes.

Scenarios resolve these via `_sm_common.IMAGE_FIXTURE` / `MOVIE_FIXTURE`,
which default to this directory but can be overridden with
`SM_TEST_IMAGE_FIXTURE` / `SM_TEST_MOVIE_FIXTURE` for ad hoc testing against
different media without editing scenario code.
