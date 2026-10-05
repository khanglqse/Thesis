#!/bin/sh
# Build HTML, print both English PDFs with headless Chrome, and render PNG previews.
set -e
cd "$(dirname "$0")"
ROOT="$(cd ../../.. && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
python3 build_en.py
rm -f deck.pdf notes.pdf
for name in deck notes; do
  if [ "$name" = deck ]; then size=1280,720; else size=794,1123; fi
  "$CHROME" --headless=new --disable-gpu --user-data-dir=/tmp/chrome-deck-en-$$ --no-first-run --no-default-browser-check --no-pdf-header-footer --allow-file-access-from-files --window-size=$size \
    --virtual-time-budget=8000 --print-to-pdf="$PWD/$name.pdf" "file://$PWD/$name.html" 2>/dev/null &
  pid=$!; i=0; while kill -0 $pid 2>/dev/null && [ $i -lt 90 ]; do sleep 1; i=$((i+1)); if [ -s "$name.pdf" ] && [ $i -gt 3 ]; then sleep 3; kill $pid 2>/dev/null; break; fi; done
done
cp deck.pdf "$ROOT/slides/thesis-defense-40min-en.pdf"
cp notes.pdf "$ROOT/slides/thesis-defense-40min-speaker-notes-en.pdf"
rm -rf preview && mkdir -p preview
pdftoppm -r 60 -png deck.pdf preview/deck
pdftoppm -r 50 -png -f 1 -l 6 notes.pdf preview/notes
echo "done"
