from flask import Blueprint
from flask import render_template
rank_bp = Blueprint('rank', __name__)

@rank_bp.route("/rank")
def print_blue():
	return render_template("rank.html")