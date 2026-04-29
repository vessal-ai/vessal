const root = document.getElementById("app");

async function load() {
  root.textContent = "Loading...";
  try {
    const r = await fetch("/skills/list");
    if (!r.ok) { root.textContent = `Error: ${r.status}`; return; }
    const body = await r.json();
    render(body.skills || []);
  } catch (e) {
    root.textContent = `Error: ${e}`;
  }
}

function render(skills) {
  root.innerHTML = "";
  const list = document.createElement("ul");
  list.className = "skill-list";
  for (const s of skills) {
    const li = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = s.name;
    const summary = document.createElement("span");
    summary.className = "summary";
    summary.textContent = s.summary || "(no summary)";
    const flag = document.createElement("span");
    flag.className = "flag";
    flag.textContent = s.has_ui ? "UI" : "";
    const reload = document.createElement("button");
    reload.textContent = "reload";
    reload.addEventListener("click", () => reloadSkill(s.name));
    li.append(name, summary, flag, reload);
    list.appendChild(li);
  }
  root.appendChild(list);
}

async function reloadSkill(name) {
  try {
    const r = await fetch("/reload/skill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!r.ok) alert(`reload failed: ${r.status}`);
    await load();
  } catch (e) {
    alert(`reload error: ${e}`);
  }
}

load();
