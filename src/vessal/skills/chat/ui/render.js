/**
 * render.js — Pure function collection for rendering frame sections.
 *
 * Each render* function: takes a frame data sub-structure → returns an HTML string.
 * No side effects, no DOM manipulation, no state.
 *
 * Data path reference (FrameRecord schema v6):
 *   ping.system_prompt         → renderSystemPrompt
 *   ping.state.frame_stream    → renderFrameStream
 *   ping.state.signals         → renderSignals
 *   pong.think                 → renderThink
 *   pong.action.operation      → renderOperation
 *   pong.action.expect         → renderExpect
 *   observation.stdout         → renderStdout
 *   observation.diff           → renderDiff
 *   observation.error          → renderError
 *   observation.verdict        → renderVerdict
 */

// ── Utility functions ──

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * HTML wrapper for a single section. Supports <details> partial collapsing.
 * @param {string} key - Section identifier (used for CSS class and toggle matching)
 * @param {string} label - Display title
 * @param {string} bodyHtml - Content HTML
 * @param {boolean} collapsed - Collapsed by default
 * @param {string} [extraClass] - Extra CSS class
 * @param {boolean} raw - When true, bodyHtml is output directly (not wrapped in <pre>), for structured content like verdict
 */
function section(key, label, bodyHtml, collapsed = false, extraClass = '', raw = false) {
  const cls = `frame-section ${extraClass}`.trim();
  const inner = raw ? `<div class="section-body">${bodyHtml}</div>`
                     : `<div class="section-body"><pre class="code-block">${bodyHtml}</pre></div>`;
  if (collapsed) {
    return `<details class="${cls}" data-section="${key}">
      <summary class="section-label">${label}</summary>
      ${inner}
    </details>`;
  }
  return `<div class="${cls}" data-section="${key}">
    <div class="section-label">${label}</div>
    ${inner}
  </div>`;
}

// ── 10 section render functions ──

// Ping layer
function renderSystemPrompt(ping) {
  const text = (ping && ping.system_prompt) || '';
  if (!text.trim()) return '';
  return section('system_prompt', 'System Prompt', escHtml(text), true);
}

function renderFrameStream(ping) {
  const state = (ping && ping.state) || {};
  const text = state.frame_stream || '';
  if (!text.trim()) return '';
  return section('frame_stream', 'Frame Stream', escHtml(text), false);
}

function renderSignals(ping) {
  const state = (ping && ping.state) || {};
  const text = state.signals || '';
  if (!text.trim()) return '';
  return section('signals', 'Signals', escHtml(text), true);
}

// Pong layer
function renderThink(pong) {
  const text = (pong && pong.think) || '';
  if (!text.trim()) return '';
  return section('think', 'Think', escHtml(text), true, 'think');
}

function renderOperation(pong) {
  const action = (pong && pong.action) || {};
  const text = action.operation || '';
  if (!text.trim()) return '';
  return section('operation', 'Operation', escHtml(text));
}

function renderExpect(pong) {
  const action = (pong && pong.action) || {};
  const text = action.expect || '';
  if (!text.trim()) return '';
  return section('expect', 'Expect', escHtml(text));
}

// Observation layer
function renderStdout(obs) {
  const text = (obs && obs.stdout) || '';
  if (!text.trim()) return '';
  return section('stdout', 'Stdout', escHtml(text));
}

function renderDiff(obs) {
  const items = (obs && obs.diff) || [];
  if (!Array.isArray(items) || items.length === 0) return '';
  const rows = items.map(d => {
    const op = d.op || '?';
    const name = escHtml(d.name || '');
    const type = escHtml(d.type || '');
    const cls = op === '+' ? 'diff-add' : (op === '-' ? 'diff-del' : 'diff-other');
    return `<div class="${cls}">${escHtml(op)} ${name}: ${type}</div>`;
  });
  return section('diff', 'Diff', rows.join(''));
}

function renderError(obs) {
  const text = (obs && obs.error) || null;
  if (!text) return '';
  return section('error', 'Error', escHtml(text), false, 'error');
}

function renderVerdict(obs) {
  const v = obs && obs.verdict;
  if (!v) return '';
  const isPass = v.passed === v.total;
  let html = `<div class="verdict-bar ${isPass ? 'pass' : 'fail'}">
    ${isPass ? '✓' : '✗'} ${v.passed}/${v.total} assertions passed
  </div>`;
  if (v.failures && v.failures.length > 0) {
    html += '<div class="verdict-failures">';
    for (const f of v.failures) {
      html += `<div class="verdict-failure-item">
        <div class="assertion">${escHtml(f.assertion || '')}</div>
        <div class="message">${escHtml(f.message || '')}</div>
      </div>`;
    }
    html += '</div>';
  }
  return section('verdict', 'Verdict', html, false, '', true);
}

// ── Frame-level rendering ──

/**
 * Render all sections of a single frame.
 * @param {object} frame - FrameRecord schema v6
 * @param {Set<string>} visible - Set of visible section keys
 * @returns {string} HTML
 */
function renderFrame(frame, visible) {
  const ping = frame.ping || {};
  const pong = frame.pong || {};
  const obs = frame.observation || {};
  const hasError = obs.error != null;
  const num = frame.number || '?';

  const renderers = [
    ['system_prompt', () => renderSystemPrompt(ping)],
    ['frame_stream', () => renderFrameStream(ping)],
    ['signals',      () => renderSignals(ping)],
    ['think',        () => renderThink(pong)],
    ['operation',    () => renderOperation(pong)],
    ['expect',       () => renderExpect(pong)],
    ['stdout',       () => renderStdout(obs)],
    ['diff',         () => renderDiff(obs)],
    ['error',        () => renderError(obs)],
    ['verdict',      () => renderVerdict(obs)],
  ];

  let body = '';
  for (const [key, fn] of renderers) {
    if (visible.has(key)) body += fn();
  }

  return `<div class="frame-card${hasError ? ' has-error' : ''}">
    <div class="frame-card-header">
      <span>Frame #${num}</span>
    </div>
    <div class="frame-card-body">${body || '<span class="empty">(empty frame)</span>'}</div>
  </div>`;
}
