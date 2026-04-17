// frame-renderer.js — renders a single Vessal frame into a given container.
// Logic extracted from src/vessal/ark/util/logging/viewer.html. Keep in sync
// when viewer.html changes until S4.3 deletes the independent viewer route.

export function renderFrame(container, frame) {
  container.innerHTML = "";
  if (!frame) {
    container.textContent = "(no current frame)";
    return;
  }

  const h = document.createElement("div");
  h.className = "frame-header";
  h.textContent = `Frame #${frame.number ?? "?"}${frame.wake ? "  ·  " + frame.wake : ""}`;
  container.appendChild(h);

  if (frame.pong) {
    const pong = frame.pong;
    if (pong.think) {
      const t = document.createElement("pre");
      t.className = "frame-section think";
      t.textContent = pong.think;
      container.appendChild(labeled("think", t));
    }
    if (pong.action) {
      const op = typeof pong.action === "string"
        ? pong.action
        : pong.action.operation || JSON.stringify(pong.action, null, 2);
      const a = document.createElement("pre");
      a.className = "frame-section action";
      a.textContent = op;
      container.appendChild(labeled("action", a));
      if (pong.action.expect) {
        const e = document.createElement("pre");
        e.className = "frame-section expect";
        e.textContent = pong.action.expect;
        container.appendChild(labeled("expect", e));
      }
    }
  }

  if (frame.observation) {
    const obs = frame.observation;
    if (obs.stdout) {
      const o = document.createElement("pre");
      o.className = "frame-section observation";
      o.textContent = obs.stdout;
      container.appendChild(labeled("stdout", o));
    }
    if (obs.error) {
      const e = document.createElement("pre");
      e.className = "frame-section error";
      e.textContent = obs.error;
      container.appendChild(labeled("error", e));
    }
  }
}

function labeled(label, el) {
  const wrap = document.createElement("div");
  const lab = document.createElement("div");
  lab.className = "frame-label";
  lab.textContent = label;
  wrap.appendChild(lab);
  wrap.appendChild(el);
  return wrap;
}
