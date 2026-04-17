// app.js — Alpine component + SSE subscription + chat POST
import { renderFrame } from "./frame-renderer.js";

const VIEWS = [
  { id: "chat",   icon: "💬", label: "Chat" },
  { id: "frames", icon: "🎞️", label: "Frames" },
  { id: "state",  icon: "🔧", label: "State" },
  { id: "logs",   icon: "📜", label: "Logs" },
  { id: "market", icon: "🛒", label: "Skill Market" },
];

window.consoleApp = function consoleApp() {
  return {
    views: VIEWS,
    current: "chat",
    project: "",
    state: { sleeping: true, frame: 0 },
    banner: null,
    pinnedFrame: null,
    rightCollapsed: localStorage.getItem("right-collapsed") === "1",
    messages: [],
    input: "",
    frames: [],
    selectedFrame: null,

    async init() {
      this.pollStatus();
      setInterval(() => this.pollStatus(), 2000);
      this.openSse();
      await this.loadMessages();
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
        this.pinnedFrame = ev.payload;
        this.frames.push(ev.payload);
        const pane = document.getElementById("frame-pinned");
        if (pane) renderFrame(pane, ev.payload);
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

    async loadMessages() {
      try {
        const r = await fetch("/skills/chat/outbox");
        if (r.ok) {
          const body = await r.json();
          this.messages = body.messages || [];
        }
      } catch {}
    },

    async send() {
      const text = this.input.trim();
      if (!text) return;
      this.messages.push({ role: "user", content: text });
      this.input = "";
      try {
        await fetch("/skills/chat/inbox", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: text }),
        });
      } catch (e) {
        this.banner = { level: "red", text: `Send failed: ${e}` };
      }
      setTimeout(() => this.loadMessages(), 500);
    },

    async loadFrames() {
      try {
        const r = await fetch("/frames");
        if (r.ok) {
          const body = await r.json();
          this.frames = body.frames || [];
          if (this.frames.length > 0) this.selectFrame(this.frames[this.frames.length - 1]);
        }
      } catch {}
    },

    selectFrame(f) {
      this.selectedFrame = f.number;
      const pane = document.getElementById("frame-detail-pane");
      if (pane) {
        import("./frame-renderer.js").then(m => m.renderFrame(pane, f));
      }
    },

    toggleRight() {
      this.rightCollapsed = !this.rightCollapsed;
      localStorage.setItem("right-collapsed", this.rightCollapsed ? "1" : "0");
    },
  };
};
