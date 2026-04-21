const SKILL_API = window.location.origin + '/skills/chat';
const SYSTEM_API = window.location.origin;

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

loadHistory().then(() => setInterval(pollOutbox, 2000));
pollStatus();
setInterval(pollStatus, 2000);
