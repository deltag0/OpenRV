#!/usr/bin/env bash
# Regenerates the real-media fixtures used by the sm_media_*/sm_button_* golden
# scenarios. These are INPUTS to the scenarios, not goldens themselves -- they
# don't need to be bit-reproducible across regenerations (only the captured
# session.rv/panel.png in golden/<id>/ need that). Re-run only if a fixture
# needs to change in size/format/content, and commit the resulting bytes.
#
# Uses this repo's own rvio (no external tool dependency) to render tiny real
# media files from a procedural movieproc source.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

RVIO="${RVIO:-../../../../../_build/stage/app/RV.app/Contents/MacOS/rvio}"  # macOS
if [ ! -x "$RVIO" ]; then
    RVIO="../../../../../_build/stage/app/bin/rvio"  # Linux
fi

"$RVIO" "smptebars,start=1,end=1,fps=24.movieproc" -resize 64 48 -o bars_frame.jpg
"$RVIO" "smptebars,start=1,end=8,fps=8.movieproc" -resize 64 48 -o bars_clip.mov
