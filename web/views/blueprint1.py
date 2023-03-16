from flask import Blueprint, render_template

bp = Blueprint("blueprint1", __name__)

@bp.route('/')
def index():
    return render_template("dyagramForm.html")