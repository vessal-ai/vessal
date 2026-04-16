/**
 * avatar.js — hermit crab avatar animation system.
 * Receives body spec, plays animations in sequence via action queue.
 * Click avatar → dispatches avatar_tap event.
 */
(function() {
  let avatarEl = null;
  let speechEl = null;
  let speechTimer = null;
  let actionQueue = [];
  let processing = false;
  let _pendingState = null;

  function createAvatar() {
    // Prevent duplicate avatars (e.g. hot reload, double script load)
    if (document.querySelector('.avatar')) return;

    avatarEl = document.createElement('div');
    avatarEl.className = 'avatar emotion-idle';
    avatarEl.innerHTML = `
      <div class="avatar-speech" id="avatar-speech"></div>
      <div class="avatar-shell"></div>
      <div class="avatar-body">
        <div class="avatar-eyes">
          <div class="avatar-eye"></div>
          <div class="avatar-eye"></div>
        </div>
      </div>
      <div class="avatar-claw avatar-claw-left"></div>
      <div class="avatar-claw avatar-claw-right"></div>
    `;

    speechEl = avatarEl.querySelector('#avatar-speech');

    // click avatar = wake/interrupt
    avatarEl.addEventListener('click', () => {
      if (typeof window.sendEvent === 'function') {
        window.sendEvent({ event: 'avatar_tap', ts: Date.now() / 1000 });
      }
    });

    document.body.appendChild(avatarEl);
  }

  function setEmotion(emotion) {
    if (!avatarEl) return;
    // Remove all emotion classes
    avatarEl.className = avatarEl.className.replace(/\s*emotion-\w+/g, '').trim();
    avatarEl.classList.add(`emotion-${emotion || 'idle'}`);
  }

  function showSpeech(text, duration) {
    if (!speechEl) return;
    if (speechTimer) clearTimeout(speechTimer);
    speechEl.textContent = text;
    speechEl.classList.add('visible');
    if (duration > 0) {
      speechTimer = setTimeout(() => {
        speechEl.classList.remove('visible');
        speechTimer = null;
      }, duration * 1000);
    } else {
      speechTimer = null;
    }
  }

  function hideSpeech() {
    if (speechEl) speechEl.classList.remove('visible');
    if (speechTimer) { clearTimeout(speechTimer); speechTimer = null; }
  }

  function moveTo(target) {
    if (!avatarEl) return;
    if (typeof target === 'string') {
      // Move near an element
      const el = document.getElementById(target) || document.querySelector(`[data-id="${target}"]`);
      if (el) {
        const rect = el.getBoundingClientRect();
        avatarEl.style.left = `${rect.left - 70}px`;
        avatarEl.style.bottom = `${window.innerHeight - rect.top - rect.height / 2}px`;
      }
    } else if (Array.isArray(target) || (target && typeof target === 'object')) {
      const [x, y] = Array.isArray(target) ? target : [target.x || 0, target.y || 0];
      avatarEl.style.left = `${x}px`;
      avatarEl.style.bottom = `${window.innerHeight - y}px`;
    }
  }

  // ── Action queue ──

  async function processQueue() {
    if (processing) return;
    processing = true;

    while (actionQueue.length > 0) {
      const action = actionQueue.shift();

      switch (action.type) {
        case 'move':
          moveTo(action.target);
          await delay(600);  // Wait for CSS transition
          break;
        case 'speak':
          showSpeech(action.text, action.duration || 3);
          await delay(300);  // Fade in time
          break;
        case 'emote':
          setEmotion(action.emotion);
          await delay(200);
          break;
        case 'point':
          // Future: visual indicator pointing at element
          await delay(200);
          break;
      }

      // Small pause between actions
      await delay(200);
    }

    // Apply final state after queue drains
    if (_pendingState) {
      const s = _pendingState;
      _pendingState = null;
      if (s.emotion) setEmotion(s.emotion);
      if (s.speech) showSpeech(s.speech, 3);
      if (s.position) moveTo(s.position);
    }

    processing = false;
  }

  function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // ── Body spec handler ──

  window.onBodySpec = function(bodySpec) {
    if (!bodySpec) return;

    if (bodySpec.actions && bodySpec.actions.length > 0) {
      // Save final state to apply after queue drains
      _pendingState = bodySpec.state || null;
      actionQueue.push(...bodySpec.actions);
      processQueue();
    } else if (bodySpec.state) {
      // No actions: apply state directly
      if (bodySpec.state.emotion) setEmotion(bodySpec.state.emotion);
      if (bodySpec.state.speech) showSpeech(bodySpec.state.speech, 3);
      if (bodySpec.state.position) moveTo(bodySpec.state.position);
    }
  };

  // Initialize
  createAvatar();
})();
