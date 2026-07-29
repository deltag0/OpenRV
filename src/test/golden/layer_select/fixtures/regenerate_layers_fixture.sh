#!/usr/bin/env bash
# Generate a tiny multi-layer EXR for layer_select golden tests.
#
# Output: test_layers.exr in this directory (committed fixture input).
# Then either:
#   export LAYER_EXR_FIXTURE="$PWD/test_layers.exr"
# or add to fixtures/layers.env (optional, gitignored).
#
# Requires: oiiotool (OpenImageIO). Install examples:
#   macOS:  brew install openimageio
#   Rocky:  dnf install OpenImageIO-utils   (name may vary)
#
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/test_layers.exr"

OIIOTOOL="${OIIOTOOL:-oiiotool}"
if ! command -v "$OIIOTOOL" >/dev/null 2>&1; then
    echo "ERROR: oiiotool not found." >&2
    echo "Install OpenImageIO (e.g. brew install openimageio) or set OIIOTOOL=/path/to/oiiotool" >&2
    exit 1
fi

# Three small parts (64x64 RGB half) — names become Layer Selector entries via RV's EXR reader.
"$OIIOTOOL" \
    --pattern "constant:color=0.85,0.15,0.15" 64x64 3 -d half -attrib oiio:subimagename beauty \
    --pattern "constant:color=0.15,0.75,0.20" 64x64 3 -d half -attrib oiio:subimagename diffuse \
    --pattern "constant:color=0.20,0.35,0.90" 64x64 3 -d half -attrib oiio:subimagename specular \
    --siappendall -o "$OUT"

echo "Wrote $OUT"
echo ""
echo "Verify in RV: load the file, press '/', you should see beauty / diffuse / specular + Default."
echo ""
echo "For golden tests:"
echo "  export LAYER_EXR_FIXTURE=$OUT"
echo "  # or: echo 'LAYER_EXR_FIXTURE=$OUT' >> layers.env"
