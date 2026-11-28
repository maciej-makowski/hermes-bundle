#!/usr/bin/env node
// Render-check mermaid sources with the CURRENT mermaid (npm) under jsdom.
// Setup (once, in this script's directory): npm init -y && npm install mermaid jsdom
// Usage: node mermaid-render-check.js <file1.mmd> [<file2.mmd> ...]
// Extract the fences from a markdown doc first, e.g.:
//   awk '/```mermaid/{n++; f="/tmp/d" n ".mmd"; next} /^```$/{f=""; next} f{print > f}' doc.md
// Why not a hosted render proxy (kroki.io etc.): its mermaid build can lag the
// current parser and reject valid modern syntax (quoted subgraph titles, a bare
// % inside a quoted label); a proxy 400 is not evidence the fence is invalid.
// The getBBox stub below only fakes SVG geometry (jsdom does no layout); a
// successful render still proves the syntax parses and renders.

const fs = require('fs');
const { JSDOM } = require('jsdom');

const dom = new JSDOM('<!DOCTYPE html><html><body><div id="c"></div></body></html>', { pretendToBeVisual: true });
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
global.DOMPurify = undefined;
global.CSSStyleSheet = dom.window.CSSStyleSheet;
global.CSSRule = dom.window.CSSRule;
global.CSSStyleDeclaration = dom.window.CSSStyleDeclaration;
global.getComputedStyle = dom.window.getComputedStyle.bind(dom.window);
dom.window.SVGElement.prototype.getBBox = function () { return { x: 0, y: 0, width: 100, height: 20 }; };
dom.window.HTMLElement.prototype.getBBox = dom.window.SVGElement.prototype.getBBox;

(async () => {
  const m = require('mermaid');
  const mermaid = m.default ?? m;
  if (typeof mermaid.initialize !== 'function') {
    console.error('API SHAPE:', Object.keys(m).slice(0, 15).join(','));
    process.exit(2);
  }
  mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' });
  const files = process.argv.slice(2);
  let bad = 0;
  for (const f of files) {
    const code = fs.readFileSync(f, 'utf8');
    try {
      await mermaid.parse(code);
      const { svg } = await mermaid.render('r' + Math.random().toString(36).slice(2), code, dom.window.document.getElementById('c'));
      console.log(`OK   ${f} (${svg.length} bytes svg)`);
    } catch (e) {
      bad++;
      console.log(`FAIL ${f}: ${String(e.message || e).split('\n').slice(0, 3).join(' | ')}`);
    }
  }
  process.exit(bad ? 1 : 0);
})().catch(e => { console.error('HARNESS ERROR:', String(e).split('\n').slice(0, 4).join(' | ')); process.exit(2); });
