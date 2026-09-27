from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

bp = Blueprint('main', __name__)

@bp.route('/')
@bp.route('/index')
@login_required
def index():
    return redirect(url_for('dashboard.index'))