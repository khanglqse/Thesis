#!/bin/sh
# English slides with Vietnamese speaker notes.
set -e
cd "$(dirname "$0")"
ROOT="$(cd ../../.. && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
python3 build_notes.py
rm -f notes.pdf
"$CHROME" --headless=new --disable-gpu --user-data-dir=/tmp/chrome-deck-en-vi-$$ --no-first-run --no-default-browser-check --no-pdf-header-footer --allow-file-access-from-files --window-size=794,1123 \
  --virtual-time-budget=8000 --print-to-pdf="$PWD/notes.pdf" "file://$PWD/notes.html" 2>/dev/null &
pid=$!; i=0; while kill -0 $pid 2>/dev/null && [ $i -lt 90 ]; do sleep 1; i=$((i+1)); if [ -s notes.pdf ] && [ $i -gt 3 ]; then sleep 3; kill $pid 2>/dev/null; break; fi; done
cp notes.pdf "$ROOT/slides/thesis-defense-40min-en-speaker-vi.pdf"
rm -rf preview && mkdir -p preview
pdftoppm -r 40 -png -f 1 -l 4 notes.pdf preview/notes
echo "done"
