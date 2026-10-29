// Карточка проекта: этапы и история, задачи, съёмочная группа, бронирование оборудования.
const root = document.getElementById("project");
const projectId = root.dataset.id;
const stateEl = document.getElementById("project-state");
const board = document.getElementById("tasks-board");
const taskForm = document.getElementById("task-form");
const statusForm = document.getElementById("status-form");
const memberForm = document.getElementById("member-form");
const bookingForm = document.getElementById("booking-form");
let project = null;

fillSelect(taskForm.elements.stage, Object.entries(LABELS.stage));

function setText(id, text) {
  document.getElementById(id).textContent = text;
}

function canEditTask(t) {
  return project.can_manage || t.assignee_id === Session.user.id;
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
  setText("p-description", p.description || "");

  root.querySelectorAll("[data-manage]").forEach((el) => { el.hidden = !p.can_manage; });
  statusForm.hidden = !p.can_manage || !p.allowed_transitions.length;
  fillSelect(statusForm.elements.status, p.allowed_transitions.map((s) => [s, LABELS.status[s]]));
  const closed = ["done", "cancelled"].includes(p.status);
  document.getElementById("task-create").hidden = closed || !Session.hasRole("admin", "producer", "director");
  bookingForm.hidden = bookingForm.hidden || closed;

  renderTasks(p.tasks);
  renderMembers(p.members);
}

function renderTasks(tasks) {
  board.innerHTML = Object.entries(LABELS.stage).map(([stage, label]) => {
    const items = tasks.filter((t) => t.stage === stage);
    const cards = items.map((t) => `
      <li class="task ${t.status}">
        <div>${escapeHtml(t.title)}</div>
        <div class="muted">${escapeHtml(t.assignee_name || "без исполнителя")} · до ${fmtDate(t.due_date)}</div>
        <div class="task-actions">
          <select data-task="${t.id}" aria-label="Статус задачи" ${canEditTask(t) ? "" : "disabled"}>
            ${Object.entries(LABELS.taskStatus).map(([v, l]) => `<option value="${v}" ${v === t.status ? "selected" : ""}>${l}</option>`).join("")}
          </select>
          ${project.can_manage ? `<button type="button" class="icon" data-delete-task="${t.id}" title="Удалить задачу">✕</button>` : ""}
        </div>
      </li>`).join("");
    return `<div class="column"><h3>${label} <span class="muted">${items.length}</span></h3>
      <ul>${cards || '<li class="empty">Нет задач</li>'}</ul></div>`;
  }).join("");
}

function renderMembers(members) {
  document.getElementById("members").innerHTML = members.map((m) => `
    <li><span><b>${escapeHtml(m.full_name)}</b> <span class="muted">${escapeHtml(m.role_in_project)}</span></span>
      ${project.can_manage ? `<button type="button" class="icon" data-delete-member="${m.id}" title="Исключить">✕</button>` : ""}</li>`
  ).join("") || '<li class="empty">Группа не набрана</li>';
}

function renderBookings(bookings) {
  document.getElementById("bookings").innerHTML = bookings.map((b) => `
    <li><span><b>${escapeHtml(b.equipment_name)}</b> <span class="muted">${escapeHtml(b.inventory_number)}</span><br>
      <span class="muted">${fmtDateTime(b.starts_at)} — ${fmtDateTime(b.ends_at)}</span></span>
      ${project.can_manage ? `<button type="button" class="icon" data-delete-booking="${b.id}" title="Отменить бронь">✕</button>` : ""}</li>`
  ).join("") || '<li class="empty">Оборудование не забронировано</li>';
}

function renderHistory(entries) {
  document.getElementById("history").innerHTML = entries.map((h) => `
    <li><span>${h.old_status ? `${LABELS.status[h.old_status]} → ` : ""}<b>${LABELS.status[h.new_status]}</b>
      ${h.comment ? `<span class="muted">«${escapeHtml(h.comment)}»</span>` : ""}</span>
      <span class="muted">${fmtDateTime(h.changed_at)} · ${escapeHtml(h.changed_by_name || "—")}</span></li>`
  ).join("") || '<li class="empty">Нет записей</li>';
}

async function loadProject() {
  try {
    project = await api(`/projects/${projectId}`);
    stateEl.hidden = true;
    root.hidden = false;
    renderProject(project);
    const [bookings, history] = await Promise.all([api(`/projects/${projectId}/bookings`), api(`/projects/${projectId}/history`)]);
    renderBookings(bookings);
    renderHistory(history);
  } catch (err) {
    stateEl.hidden = false;
    root.hidden = true;
    stateEl.className = "state error";
    stateEl.textContent = err.status === 404 ? "Проект не найден." : err.message;
  }
}

async function submitForm(form, errorsBox, request) {
  const button = form.querySelector("button");
  button.disabled = true;
  try {
    await request(formData(form));
    showErrors(form, errorsBox, null);
    form.reset();
    await loadProject();
  } catch (err) {
    showErrors(form, errorsBox, err);
  } finally {
    button.disabled = false;
  }
}

board.addEventListener("change", async (e) => {
  const select = e.target.closest("select[data-task]");
  if (!select) return;
  select.disabled = true;
  try {
    await api(`/tasks/${select.dataset.task}`, { method: "PATCH", body: { status: select.value } });
  } catch (err) {
    alert(err.message);
  }
  await loadProject();
});

root.addEventListener("click", async (e) => {
  const btn = e.target.closest("button.icon");
  if (!btn) return;
  const { deleteTask, deleteMember, deleteBooking } = btn.dataset;
  const [path, question] = deleteTask ? [`/tasks/${deleteTask}`, "Удалить задачу?"]
    : deleteMember ? [`/projects/${projectId}/members/${deleteMember}`, "Исключить сотрудника из группы?"]
      : [`/bookings/${deleteBooking}`, "Отменить бронь?"];
  if (!confirm(question)) return;
  try {
    await api(path, { method: "DELETE" });
  } catch (err) {
    alert(err.message);
  }
  await loadProject();
});

statusForm.addEventListener("submit", (e) => {
  e.preventDefault();
  submitForm(statusForm, document.getElementById("status-errors"), (data) =>
    api(`/projects/${projectId}`, { method: "PATCH", body: data }));
});

taskForm.addEventListener("submit", (e) => {
  e.preventDefault();
  submitForm(taskForm, document.getElementById("task-errors"), (data) =>
    api(`/projects/${projectId}/tasks`, { method: "POST", body: data }));
});

memberForm.addEventListener("submit", (e) => {
  e.preventDefault();
  submitForm(memberForm, document.getElementById("member-errors"), ({ user_id, role_in_project }) =>
    api(`/projects/${projectId}/members/${user_id}`, { method: "PUT", body: { role_in_project } }));
});

bookingForm.addEventListener("submit", (e) => {
  e.preventDefault();
  submitForm(bookingForm, document.getElementById("booking-errors"), (data) =>
    api(`/projects/${projectId}/bookings`, { method: "POST", body: data }));
});

if (Session.token) {
  api("/users").then((users) => {
    fillSelect(taskForm.elements.assignee_id, users.map((u) => [u.id, u.full_name]), true);
    fillSelect(memberForm.elements.user_id, users.map((u) => [u.id, `${u.full_name} (${LABELS.role[u.role]})`]));
  });
  api("/equipment").then((items) => fillSelect(bookingForm.elements.equipment_id,
    items.filter((i) => i.is_available).map((i) => [i.id, `${i.inventory_number} · ${i.name}`])));
  loadProject();
}
