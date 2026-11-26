#!/bin/sh
# Build the Vietnamese deck and speaker notes, then render PNG previews.
set -e
cd "$(dirname "$0")"
ROOT="$(cd ../../.. && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
python3 build_vi.py
rm -f deck.pdf notes.pdf
for name in deck notes; do
  if [ "$name" = deck ]; then size=1280,720; else size=794,1123; fi
  "$CHROME" --headless=new --disable-gpu --user-data-dir=/tmp/chrome-deck25-vi-$$ --no-first-run --no-default-browser-check --no-pdf-header-footer --allow-file-access-from-files --window-size=$size \
    --virtual-time-budget=8000 --print-to-pdf="$PWD/$name.pdf" "file://$PWD/$name.html" 2>/dev/null &
  pid=$!; i=0; while kill -0 $pid 2>/dev/null && [ $i -lt 90 ]; do sleep 1; i=$((i+1)); if [ -s "$name.pdf" ] && [ $i -gt 3 ]; then sleep 3; kill $pid 2>/dev/null; break; fi; done
done
cp deck.pdf "$ROOT/slides/thesis-defense-25min-vi.pdf"
cp notes.pdf "$ROOT/slides/thesis-defense-25min-speaker-notes-vi.pdf"
rm -rf preview && mkdir -p preview
pdftoppm -r 50 -png deck.pdf preview/deck
echo "done"
