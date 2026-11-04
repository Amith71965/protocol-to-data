# Diagrams

Each diagram is authored as Archify JSON under `.archify/` (gitignored working
directories) and rendered to a standalone, explorable HTML page here. The HTML
is the source of truth; the SVG and PNG are exports of it.

| File | Use |
|---|---|
| `*.html` | Interactive page — pan, zoom, route tracing, light/dark |
| `*.svg` | Theme-adaptive export, embedded in the README (renders correctly on GitHub in both light and dark) |
| `*-light.svg` | Light-only export, for light-background write-ups |
| `*.png` | High-resolution raster, for the blog |

## Regenerating

Render the HTML:

```bash
node ~/.claude/skills/archify/bin/archify.mjs finalize architecture \
  .archify/<folder>/candidate.json docs/diagrams/<name>.html --quality showcase --json
```

Archify's CLI emits HTML only — PNG and dual-theme SVG are export actions inside
the rendered page. To capture them without a manual download, serve the pages
with a save endpoint:

```bash
python scripts/serve_diagrams.py
```

Open `http://127.0.0.1:8766/<name>.html` and run this in the page console. It
intercepts the Blob the exporter hands to its download anchor and POSTs it back:

```js
async function exportTo(format, filename) {
  const captured = [];
  const realCreate = URL.createObjectURL;
  const realClick = HTMLAnchorElement.prototype.click;
  URL.createObjectURL = (obj) => { captured.push(obj); return realCreate.call(URL, obj); };
  HTMLAnchorElement.prototype.click = function () {};
  try {
    await Archify.exportMenu.run(format);
    for (let i = 0; i < 80 && !captured.length; i++) await new Promise(r => setTimeout(r, 100));
  } finally {
    URL.createObjectURL = realCreate;
    HTMLAnchorElement.prototype.click = realClick;
  }
  const blob = captured.at(-1);
  const res = await fetch('/save', { method: 'POST', headers: { 'X-Filename': filename }, body: blob });
  return { bytes: blob.size, saved: await res.text() };
}

await exportTo('svg', '<name>.svg');        // theme-adaptive
await exportTo('svg-light', '<name>-light.svg');
await exportTo('png', '<name>.png');
```
