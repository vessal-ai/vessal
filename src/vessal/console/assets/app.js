// app.js — Alpine component + SSE subscription

const VIEWS = [
  { id: "frames", icon: "🎞️", label: "Frames" },
];

function consoleApp() {
  return {
    views: VIEWS,
    current: "frames",
    project: "",
    state: { sleeping: true, frame: 0 },
    banner: null,
    frames: [],
    selectedFrame: null,
    get currentFrame() {
      if (this.selectedFrame == null) return null;
      return this.frames.find(f => f.n === this.selectedFrame) || null;
    },

    async init() {
      this.pollStatus();
      setInterval(() => this.pollStatus(), 2000);
      this.openSse();
      await this.loadSkillUis();
    },

    async pollStatus() {
      try {
        const r = await fetch("/status");
        if (r.ok) this.state = await r.json();
      } catch {}
    },

    openSse() {
      const es = new EventSource("/events");
      es.onmessage = (ev) => {
        const data = JSON.parse(ev.data);
        this.handleEvent(data);
      };
      es.onerror = () => {
        this.banner = { level: "gray", text: "SSE connection lost, retrying..." };
      };
    },

    handleEvent(ev) {
      if (ev.type === "frame") {
        const f = ev.payload;
        const idx = this.frames.findIndex(x => x.n === f.n);
        if (idx >= 0) this.frames.splice(idx, 1, f);
        else this.frames.push(f);
        if (this.selectedFrame == null) this.selectedFrame = f.n;
      } else if (ev.type === "agent_crash") {
        this.banner = {
          level: "red",
          text: `Agent crashed: ${ev.payload.reason || "exit " + ev.payload.exit_code}`,
        };
      } else if (ev.type === "gate_reject") {
        this.banner = { level: "yellow", text: `Action rejected by gate: ${ev.payload.rule}` };
      } else if (ev.type === "llm_timeout") {
        this.banner = { level: "gray", text: "LLM timeout, retrying..." };
      } else if (ev.type === "restart_required") {
        this.banner = { level: "yellow", text: `${ev.payload.file} changed — restart required` };
      }
    },

    async loadFrames() {
      const last = this.frames.length ? this.frames[this.frames.length - 1].n : 0;
      try {
        const r = await fetch(`/frames?after=${last}`);
        if (r.ok) {
          const body = await r.json();
          const incoming = body.frames || [];
          for (const f of incoming) {
            const idx = this.frames.findIndex(x => x.n === f.n);
            if (idx >= 0) this.frames.splice(idx, 1, f);
            else this.frames.push(f);
          }
          if (this.frames.length > 0 && this.selectedFrame == null) {
            this.selectedFrame = this.frames[this.frames.length - 1].n;
          }
        }
      } catch {}
    },

    selectFrame(f) { this.selectedFrame = f.n; },

    frameExcerpt(f) {
      return (f.pong_think || f.pong_operation || f.obs_stdout || '').toString().slice(0, 80);
    },

    async loadSkillUis() {
      try {
        const r = await fetch("/skills/ui");
        if (!r.ok) return;
        const body = await r.json();
        for (const s of body.skills || []) {
          this.views.push({ id: `skill:${s.name}`, icon: "🧩", label: s.name, url: s.url });
        }
      } catch {}
    },
  };
}

document.addEventListener("alpine:init", () => {
  window.Alpine.data("consoleApp", consoleApp);
});
