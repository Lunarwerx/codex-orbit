// Regression: a task-context request made before any pointer interaction (no cached context and no
// hovered row) must still be answered, not throw on a null element.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const bridge = path.join(here, '..', 'stable', 'codex_assets', 'webview', 'assets',
  'window-app-action-helpers-CuuVVkGv-codexpatch.js');

test('task-context request is answered when no row is hovered or cached', () => {
  const posted = [];
  const windowListeners = {};
  globalThis.document = {
    documentElement: {},
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener() {},
  };
  globalThis.window = {
    addEventListener(type, fn) { windowListeners[type] = fn; },
    __codexPostMessage(type, payload) { posted.push([type, payload]); },
  };
  globalThis.MutationObserver = class { observe() {} };

  // The file is an ES module (imports on line 1); the bridge is a self-contained IIFE that uses no imports.
  const src = readFileSync(bridge, 'utf8');
  const iife = src.slice(src.lastIndexOf(';(function(){', src.indexOf('__codexTaskContextBridgeV5')));
  new Function(iife)();
  windowListeners.message({ data: { type: 'codex-request-task-context', requestId: 'r1' } });

  assert.deepEqual(posted, [['codex-task-context-response', { requestId: 'r1' }]]);
});
