// Страница списка проектов: загрузка, фильтр по статусу, создание проекта.
const tableEl = document.getElementById("projects-table");
const stateEl = document.getElementById("projects-state");
const filterEl = document.getElementById("status-filter");
const form = document.getElementById("project-form");
const errorsEl = document.getElementById("project-errors");

fillSelect(filterEl, Object.entries(LABELS.status), true);
fillSelect(form.elements.project_type, Object.entries(LABELS.type));

async function loadProjects() {
  stateEl.hidden = false;
  stateEl.className = "state";
  stateEl.textContent = "Загрузка…";
  try {
    const status = filterEl.value;
    const projects = await api(`/projects${status ? `?status=${encodeURIComponent(status)}` : ""}`);
    renderProjects(projects);
  } catch (err) {
    tableEl.hidden = true;
    stateEl.className = "state error";
    stateEl.textContent = err.message;
  }
}

function renderProjects(projects) {
  if (!projects.length) {
    tableEl.hidden = true;
    stateEl.textContent = "Проектов пока нет.";
    return;
  }
  stateEl.hidden = true;
  tableEl.hidden = false;
  tableEl.tBodies[0].innerHTML = projects.map((p) => {
    const pct = p.tasks_total ? Math.round((100 * p.tasks_done) / p.tasks_total) : 0;
    return `<tr>
      <td><a href="/projects/${p.id}">${escapeHtml(p.title)}</a><div class="muted">${LABELS.type[p.project_type]}</div></td>
      <td>${escapeHtml(p.client_name)}</td>
      <td>${escapeHtml(p.producer_name || "—")}</td>
      <td><span class="badge s-${p.status}">${LABELS.status[p.status]}</span></td>
      <td>${fmtDate(p.deadline)}</td>
      <td><div class="progress"><span style="width:${pct}%"></span></div><span class="muted">${p.tasks_done}/${p.tasks_total}</span></td>
    </tr>`;
  }).join("");
}

async function loadDictionaries() {
  const [clients, producers] = await Promise.all([api("/clients"), api("/users?role=producer")]);
  fillSelect(form.elements.client_id, [["", "— выберите —"], ...clients.map((c) => [c.id, c.name])]);
  fillSelect(form.elements.producer_id, producers.map((u) => [u.id, u.full_name]), true);
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = form.querySelector("button");
  button.disabled = true;
  try {
    const project = await api("/projects", { method: "POST", body: formData(form) });
    showErrors(form, errorsEl, null);
    form.reset();
    window.location.href = `/projects/${project.id}`;
  } catch (err) {
    showErrors(form, errorsEl, err);
  } finally {
    button.disabled = false;
  }
});

filterEl.addEventListener("change", loadProjects);
loadDictionaries().catch((err) => showErrors(form, errorsEl, err));
loadProjects();
