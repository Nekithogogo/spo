// Карточка проекта: данные проекта, задачи по этапам, добавление задачи и смена статуса.
const root = document.getElementById("project");
const projectId = root.dataset.id;
const stateEl = document.getElementById("project-state");
const board = document.getElementById("tasks-board");
const form = document.getElementById("task-form");
const errorsEl = document.getElementById("task-errors");

fillSelect(form.elements.stage, Object.entries(LABELS.stage));

function setText(id, text) {
  document.getElementById(id).textContent = text;
}

function renderProject(p) {
  document.title = `${p.title} · Видеостудия`;
  setText("p-title", p.title);
  const badge = document.getElementById("p-status");
  badge.textContent = LABELS.status[p.status];
  badge.className = `badge s-${p.status}`;
  setText("p-client", p.client_name);
  setText("p-producer", p.producer_name || "—");
  setText("p-type", LABELS.type[p.project_type]);
  setText("p-budget", fmtMoney(p.budget));
  setText("p-dates", `${fmtDate(p.start_date)} — ${fmtDate(p.deadline)}`);
  setText("p-members", p.members.map((m) => `${m.full_name} (${m.role_in_project})`).join(", ") || "—");
  setText("p-description", p.description || "");
  renderTasks(p.tasks);
}

function renderTasks(tasks) {
  board.innerHTML = Object.entries(LABELS.stage).map(([stage, label]) => {
    const items = tasks.filter((t) => t.stage === stage);
    const cards = items.map((t) => `
      <li class="task ${t.status}">
        <div>${escapeHtml(t.title)}</div>
        <div class="muted">${escapeHtml(t.assignee_name || "без исполнителя")} · до ${fmtDate(t.due_date)}</div>
        <select data-task="${t.id}" aria-label="Статус задачи">
          ${Object.entries(LABELS.taskStatus).map(([v, l]) => `<option value="${v}" ${v === t.status ? "selected" : ""}>${l}</option>`).join("")}
        </select>
      </li>`).join("");
    return `<div class="column"><h3>${label} <span class="muted">${items.length}</span></h3>
      <ul>${cards || '<li class="empty">Нет задач</li>'}</ul></div>`;
  }).join("");
}

async function loadProject() {
  try {
    const p = await api(`/projects/${projectId}`);
    stateEl.hidden = true;
    root.hidden = false;
    renderProject(p);
  } catch (err) {
    stateEl.className = "state error";
    stateEl.textContent = err.status === 404 ? "Проект не найден." : err.message;
  }
}

board.addEventListener("change", async (e) => {
  const select = e.target.closest("select[data-task]");
  if (!select) return;
  select.disabled = true;
  try {
    await api(`/tasks/${select.dataset.task}`, { method: "PATCH", body: { status: select.value } });
    await loadProject();
  } catch (err) {
    alert(err.message);
    await loadProject();
  }
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = form.querySelector("button");
  button.disabled = true;
  try {
    await api(`/projects/${projectId}/tasks`, { method: "POST", body: formData(form) });
    showErrors(form, errorsEl, null);
    form.reset();
    await loadProject();
  } catch (err) {
    showErrors(form, errorsEl, err);
  } finally {
    button.disabled = false;
  }
});

api("/users").then((users) => fillSelect(form.elements.assignee_id, users.map((u) => [u.id, u.full_name]), true));
loadProject();
