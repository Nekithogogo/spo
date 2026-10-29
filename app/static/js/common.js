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
  role: { admin: "Администратор", producer: "Продюсер", director: "Режиссёр", operator: "Оператор", editor: "Монтажёр" },
};

// Сеанс: токен хранится в sessionStorage вкладки и удаляется при закрытии браузера.
const Session = {
  get token() { return sessionStorage.getItem("studio.token"); },
  get user() {
    try { return JSON.parse(sessionStorage.getItem("studio.user")); } catch { return null; }
  },
  save(token, user) {
    sessionStorage.setItem("studio.token", token);
    sessionStorage.setItem("studio.user", JSON.stringify(user));
  },
  clear() {
    sessionStorage.removeItem("studio.token");
    sessionStorage.removeItem("studio.user");
  },
  hasRole(...roles) { return Boolean(this.user) && roles.includes(this.user.role); },
};

function goToLogin() {
  Session.clear();
  const next = encodeURIComponent(location.pathname + location.search);
  location.replace(`/login?next=${next}`);
}

class ApiError extends Error {
  constructor(status, body) {
    super(body && body.error ? body.error : `Ошибка ${status}`);
    this.status = status;
    this.details = body && body.details ? body.details : {};
  }
}

async function api(path, options = {}) {
  const init = { headers: { Accept: "application/json" }, ...options };
  if (Session.token) init.headers.Authorization = `Bearer ${Session.token}`;
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
  if (response.status === 401 && path !== "/auth/login") {
    goToLogin();
    throw new ApiError(401, { error: "Требуется вход в систему" });
  }
  if (response.status === 204) return null;
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

// Время показывается в часовом поясе студии, как и вводится в поля datetime-local.
const STUDIO_TZ = "Europe/Moscow";

function fmtDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("ru-RU", {
    timeZone: STUDIO_TZ, day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

// Элементы с data-roles="admin producer" видны только этим ролям (на сервере права проверяются отдельно).
function applyRoles(root = document) {
  root.querySelectorAll("[data-roles]").forEach((el) => {
    el.hidden = !Session.hasRole(...el.dataset.roles.split(" "));
  });
}

(function initLayout() {
  if (document.body.classList.contains("public")) return;
  if (!Session.token) {
    goToLogin();
    return;
  }
  const nav = document.getElementById("nav");
  const user = Session.user;
  document.getElementById("nav-user").textContent = `${user.full_name} · ${LABELS.role[user.role]}`;
  applyRoles();
  nav.hidden = false;
  document.getElementById("logout").addEventListener("click", async () => {
    try { await api("/auth/logout", { method: "POST" }); } finally { goToLogin(); }
  });
})();
