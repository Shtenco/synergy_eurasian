"""Check local GitHub README links and SVG syntax. No network and no dependencies."""
from pathlib import Path
from urllib.parse import unquote
import re
import sys
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'README.md'
TEXT = DOC.read_text(encoding='utf-8')

md_links = re.findall(r'\]\(([^)]+)\)', TEXT)
img_links = re.findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', TEXT)
all_links = md_links + img_links
bad = []
for href in all_links:
    href = href.split('#', 1)[0].split('?', 1)[0]
    if not href or href.startswith(('http://', 'https://', 'mailto:', '#')):
        continue
    path = (ROOT / unquote(href)).resolve()
    if ROOT not in path.parents and path != ROOT:
        bad.append('Unsafe path: ' + href)
    elif not path.exists():
        bad.append('Missing: ' + href)

for svg in (ROOT / 'assets/readme').glob('*.svg'):
    try:
        doc = ElementTree.parse(svg)
        if not doc.getroot().tag.endswith('svg'):
            bad.append('Not an SVG document: ' + str(svg))
    except Exception as exc:
        bad.append('Invalid SVG: ' + str(svg) + ': ' + str(exc))

if bad:
    print('\n'.join(bad), file=sys.stderr)
    raise SystemExit(1)
print('README links and SVG files OK:', len(all_links), 'links;',
      len(list((ROOT/'assets/readme').glob('*.svg'))), 'illustrations')