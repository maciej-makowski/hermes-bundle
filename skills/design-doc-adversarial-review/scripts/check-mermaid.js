#!/usr/bin/env node
// Mermaid fence validator for design docs: renders each .mmd file under the
// current mermaid parser (same generation as GitHub's renderer). Setup, once
// per scratch dir:  npm init -y && npm i mermaid jsdom
// Usage: node check-mermaid.js fence1.mmd fence2.mmd   (exit 1 on any failure)
// Syntax check only: jsdom does no layout, so getBBox is stubbed — a pass says
// nothing about visual dimensions on GitHub.
const fs = require('fs');
const { JSDOM } = require('jsdom');

const dom = new JSDOM('<!DOCTYPE html><html><body><div id="c"></div></body></html>', { pretendToBeVisual: true });
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
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
  let bad = 0;
  for (const f of process.argv.slice(2)) {
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
