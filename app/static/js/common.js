// Общие функции клиента: запросы к API и справочники подписей.
const LABELS = {
  status: {
    new: "Новый", preproduction: "Препродакшн", shooting: "Съёмка",
    postproduction: "Постпродакшн", review: "Согласование", done: "Сдан", cancelled: "Отменён",
  },
  type: {
    commercial: "Реклама", music_video: "Клип", corporate: "Корпоративное видео",
    event: "Мероприятие", documentary: "Документальный", other: "Другое",
  },
  stage: { preproduction: "Препродакшн", shooting: "Съёмка", postproduction: "Постпродакшн", review: "Согласование" },
  taskStatus: { todo: "К выполнению", in_progress: "В работе", done: "Готово" },
};

class ApiError extends Error {
  constructor(status, body) {
    super(body && body.error ? body.error : `Ошибка ${status}`);
    this.status = status;
    this.details = body && body.details ? body.details : {};
  }
}

async function api(path, options = {}) {
  const init = { headers: { Accept: "application/json" }, ...options };
  if (options.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(options.body);
  }
  let response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch (e) {
    throw new ApiError(0, { error: "Сервер недоступен. Проверьте подключение." });
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, body);
  return body;
}

function fillSelect(select, entries, keepFirst = false) {
  if (!keepFirst) select.innerHTML = "";
  for (const [value, text] of entries) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = text;
    select.append(opt);
  }
}

function formData(form) {
  const data = {};
  for (const [k, v] of new FormData(form).entries()) data[k] = typeof v === "string" ? v.trim() : v;
  return data;
}

function showErrors(form, box, err) {
  form.querySelectorAll(".invalid").forEach((el) => el.classList.remove("invalid"));
  box.innerHTML = "";
  if (!err) return;
  const items = Object.entries(err.details || {});
  for (const [field] of items) {
    const input = form.elements[field];
    if (input) input.classList.add("invalid");
  }
  const lines = items.length ? items.map(([, msg]) => msg) : [err.message];
  box.innerHTML = lines.map((m) => `<div>${escapeHtml(m)}</div>`).join("");
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function fmtDate(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

function fmtMoney(n) {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(n) + " ₽";
}
