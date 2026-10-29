// Страница входа: получение токена и переход на запрошенную страницу.
const form = document.getElementById("login-form");
const errorsEl = document.getElementById("login-errors");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const button = form.querySelector("button");
  button.disabled = true;
  try {
    const result = await api("/auth/login", { method: "POST", body: formData(form) });
    Session.save(result.token, result.user);
    const next = new URLSearchParams(location.search).get("next") || "/";
    location.replace(next.startsWith("/") && !next.startsWith("//") ? next : "/");  // только свои адреса
  } catch (err) {
    showErrors(form, errorsEl, err);
  } finally {
    button.disabled = false;
  }
});
