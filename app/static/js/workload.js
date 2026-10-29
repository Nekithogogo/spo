// Отчёт о загрузке сотрудников (FR-12).
const tableEl = document.getElementById("workload-table");
const stateEl = document.getElementById("workload-state");

api("/reports/workload").then((rows) => {
  stateEl.hidden = true;
  tableEl.hidden = false;
  tableEl.tBodies[0].innerHTML = rows.map((r) => `<tr>
      <td>${escapeHtml(r.full_name)}</td>
      <td>${LABELS.role[r.role]}</td>
      <td><b>${r.open_tasks}</b></td>
      <td>${r.in_progress}</td>
      <td class="${r.overdue ? "warn" : ""}">${r.overdue}</td>
      <td>${r.projects}</td>
    </tr>`).join("");
}).catch((err) => {
  stateEl.className = "state error";
  stateEl.textContent = err.status === 403 ? "Отчёт доступен продюсерам и администратору." : err.message;
});
