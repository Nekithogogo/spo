"""HTML-страницы. Данные страницы получают из REST API через fetch."""
from flask import Blueprint, render_template

pages = Blueprint("pages", __name__)


@pages.get("/")
def projects_page():
    return render_template("projects.html")


@pages.get("/projects/<int:project_id>")
def project_page(project_id):
    return render_template("project.html", project_id=project_id)
