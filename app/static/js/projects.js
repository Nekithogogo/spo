// Страница списка проектов: загрузка, фильтр по статусу, поиск, постраничный вывод, создание проекта.
const tableEl = document.getElementById("projects-table");
const stateEl = document.getElementById("projects-state");
const filterEl = document.getElementById("status-filter");
const searchEl = document.getElementById("search");
const pagerEl = document.getElementById("pager");
const form = document.getElementById("project-form");
const errorsEl = document.getElementById("project-errors");
const PAGE_SIZE = 20;
let offset = 0;

fillSelect(filterEl, Object.entries(LABELS.status), true);
fillSelect(form.elements.project_type, Object.entries(LABELS.type));
if (!Session.hasRole("admin", "producer")) document.getElementById("projects-layout").classList.add("single");

async function loadProjects() {
  stateEl.hidden = false;
  stateEl.className = "state";
  stateEl.textContent = "Загрузка…";
  const params = new URLSearchParams({ limit: PAGE_SIZE, offset });
  if (filterEl.value) params.set("status", filterEl.value);
  if (searchEl.value.trim()) params.set("q", searchEl.value.trim());
  try {
    const response = await fetch(`/api/projects?${params}`, { headers: { Authorization: `Bearer ${Session.token}` } });
    if (response.status === 401) return goToLogin();
    const body = await response.json();
    if (!response.ok) throw new ApiError(response.status, body);
    renderProjects(body, Number(response.headers.get("X-Total-Count")));
  } catch (err) {
    tableEl.hidden = true;
    pagerEl.hidden = true;
    stateEl.className = "state error";
    stateEl.textContent = err.message;
  }
}

function renderProjects(projects, total) {
  pagerEl.hidden = total <= PAGE_SIZE;
  document.getElementById("page-info").textContent = `${offset + 1}–${offset + projects.length} из ${total}`;
  document.getElementById("prev").disabled = offset === 0;
  document.getElementById("next").disabled = offset + PAGE_SIZE >= total;
  if (!projects.length) {
    tableEl.hidden = true;
    stateEl.textContent = searchEl.value || filterEl.value ? "Ничего не найдено." : "Проектов пока нет.";
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
      <td><div class="progress"><span data-pct="${pct}"></span></div><span class="muted">${p.tasks_done}/${p.tasks_total}</span></td>
    </tr>`;
  }).join("");
  // ширина задаётся через CSSOM: политика CSP запрещает встроенные атрибуты style
  tableEl.querySelectorAll("[data-pct]").forEach((el) => { el.style.width = `${el.dataset.pct}%`; });
}

async function loadDictionaries() {
  const [clients, producers] = await Promise.all([api("/clients"), api("/users?role=producer")]);
  fillSelect(form.elements.client_id, [["", "— выберите —"], ...clients.map((c) => [c.id, c.name])]);
  fillSelect(form.elements.producer_id, producers.map((u) => [u.id, u.full_name]), true);
  if (Session.hasRole("producer")) form.elements.producer_id.value = Session.user.id;
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

let searchTimer;
searchEl.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { offset = 0; loadProjects(); }, 300);
});
filterEl.addEventListener("change", () => { offset = 0; loadProjects(); });
document.getElementById("prev").addEventListener("click", () => { offset = Math.max(0, offset - PAGE_SIZE); loadProjects(); });
document.getElementById("next").addEventListener("click", () => { offset += PAGE_SIZE; loadProjects(); });

if (Session.token) {
  if (Session.hasRole("admin", "producer")) loadDictionaries().catch((err) => showErrors(form, errorsEl, err));
  loadProjects();
}
