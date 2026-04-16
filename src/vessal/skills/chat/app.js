/**
 * app.js — Application logic: polling, toggle state, chat send/receive.
 *
 * Depends on: render.js (renderFrame function)
 * Data sources: /frames (frame data), /status (agent status), /skills/chat/* (chat)
 */

const SKILL_API = window.location.origin + '/skills/chat';
const SYSTEM_API = window.location.origin;

// ── Section definitions ──

const SECTIONS = [
  { key: 'system_prompt', label: 'System Prompt', defaultOn: false },
  { key: 'frame_stream',  label: 'Frame Stream',  defaultOn: true },
  { key: 'signals',       label: 'Signals',       defaultOn: false },
  { key: 'think',         label: 'Think',      defaultOn: true },
  { key: 'operation',     label: 'Operation',  defaultOn: true },
  { key: 'expect',        label: 'Expect',     defaultOn: true },
  { key: 'stdout',        label: 'Stdout',     defaultOn: true },
  { key: 'diff',          label: 'Diff',       defaultOn: true },
  { key: 'error',         label: 'Error',      defaultOn: true },
  { key: 'verdict',       label: 'Verdict',    defaultOn: true },
];

const STORAGE_KEY = 'vessal_visible_sections';

// ── Toggle state management ──

function loadVisibleSections() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return new Set(JSON.parse(stored));
  } catch {}
  return new Set(SECTIONS.filter(s => s.defaultOn).map(s => s.key));
}

function saveVisibleSections(visible) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...visible]));
}

let visibleSections = loadVisibleSections();

function initToggleBar() {
  const bar = document.getElementById('toggleBar');
  for (const s of SECTIONS) {
    const label = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = visibleSections.has(s.key);
    cb.addEventListener('change', () => {
      if (cb.checked) visibleSections.add(s.key);
      else visibleSections.delete(s.key);
      saveVisibleSections(visibleSections);
      rerenderAllFrames();
    });
    label.appendChild(cb);
    label.appendChild(document.createTextNode(s.label));
    bar.appendChild(label);
  }
}

// ── Frame polling + rendering ──

let frames = [];
let lastFrameNumber = 0;
let isTailing = true;
const frameList = document.getElementById('frameList');

async function pollFrames() {
  try {
    const resp = await fetch(`${SYSTEM_API}/frames?after=${lastFrameNumber}`);
    const data = await resp.json();
    const newFrames = data.frames || [];
    for (const f of newFrames) {
      frames.push(f);
      if ((f.number || 0) > lastFrameNumber) lastFrameNumber = f.number;
      appendFrameCard(f);
    }
    if (newFrames.length > 0 && isTailing) {
      frameList.scrollTop = frameList.scrollHeight;
    }
    document.getElementById('frameStats').textContent = `${frames.length} frames`;
  } catch {}
}

function appendFrameCard(frame) {
  const div = document.createElement('div');
  div.innerHTML = renderFrame(frame, visibleSections);
  const card = div.firstElementChild;
  if (card) frameList.appendChild(card);
}

function rerenderAllFrames() {
  frameList.innerHTML = '';
  for (const f of frames) appendFrameCard(f);
  if (isTailing) frameList.scrollTop = frameList.scrollHeight;
}

// Detect manual scroll — disable tailing when more than 100px from the bottom
frameList.addEventListener('scroll', () => {
  const atBottom = frameList.scrollHeight - frameList.scrollTop - frameList.clientHeight < 100;
  isTailing = atBottom;
});

// ── Agent status polling ──

const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');

async function pollStatus() {
  try {
    const resp = await fetch(`${SYSTEM_API}/status`);
    const data = await resp.json();
    if (data.sleeping) {
      statusDot.style.background = '#ffc107';
      statusText.textContent = 'Sleeping';
    } else {
      statusDot.style.background = '#4caf50';
      statusText.textContent = `Working (frame ${data.frame || 0})`;
    }
  } catch {
    statusDot.style.background = '#f44336';
    statusText.textContent = 'Offline';
  }
}

// ── Chat ──

const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
let lastOutboxTs = 0;

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendMessage(); });

function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = '';
  appendChat('user', text);
  fetch(`${SKILL_API}/inbox`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: text }),
  }).catch(err => appendChat('agent', `[Send failed: ${err.message}]`));
}

function appendChat(role, content) {
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.textContent = content;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function loadHistory() {
  try {
    const resp = await fetch(`${SKILL_API}/history`);
    const data = await resp.json();
    for (const msg of (data.messages || [])) {
      appendChat(msg.role || 'agent', msg.content || '');
      if ((msg.ts || 0) > lastOutboxTs) lastOutboxTs = msg.ts;
    }
  } catch {}
}

async function pollOutbox() {
  try {
    const resp = await fetch(`${SKILL_API}/outbox?after=${lastOutboxTs}`);
    const data = await resp.json();
    for (const msg of (data.messages || [])) {
      appendChat('agent', msg.content || '');
      if (msg.ts > lastOutboxTs) lastOutboxTs = msg.ts;
    }
  } catch {}
}

// ── Initialization ──

initToggleBar();
loadHistory().then(() => setInterval(pollOutbox, 2000));
pollFrames();
setInterval(pollFrames, 1500);
pollStatus();
setInterval(pollStatus, 2000);
