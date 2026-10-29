// Swagger UI для /api/docs. Если пользователь уже вошёл в веб-интерфейс, его токен подставляется в Authorize.
const ui = SwaggerUIBundle({
  url: "/api/openapi.json",
  dom_id: "#swagger",
  deepLinking: true,
  onComplete() {
    const token = sessionStorage.getItem("studio.token");
    if (!token) return;
    ui.authActions.authorize({
      bearerAuth: { name: "bearerAuth", schema: { type: "http", scheme: "bearer" }, value: token },
    });
  },
});
