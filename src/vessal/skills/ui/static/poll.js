/**
 * poll.js — HTTP polling + event dispatch.
 * Polls GET /render every 300ms, calls window.onRenderSpec(spec) when updated.
 * sendEvent(event) POSTs to /events.
 */
(function() {
  let currentVersion = -1;

  async function poll() {
    try {
      // use current page path as base (/skills/ui/)
      const base = location.pathname.replace(/\/$/, '');
      const res = await fetch(`${base}/render?after_version=${currentVersion}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.unchanged === true) return;
      if (data.version > currentVersion) {
        currentVersion = data.version;
        if (window.onRenderSpec) {
          window.onRenderSpec(data);
        }
      }
    } catch (e) {
      // Ignore network errors, retry next poll
    }
  }

  window.sendEvent = async function(event) {
    try {
      const base = location.pathname.replace(/\/$/, '');
      const res = await fetch(`${base}/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(event),
      });
      if (!res.ok) console.warn('sendEvent failed:', res.status);
    } catch (e) {
      console.error('sendEvent failed:', e);
    }
  };

  setInterval(poll, 300);
  poll();  // Initial poll
})();
