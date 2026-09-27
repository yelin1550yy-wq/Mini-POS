from flask import Blueprint, jsonify
from flask_login import login_required

bp = Blueprint('api', __name__)

@bp.route('/health')
def health():
    return jsonify({'status': 'ok'})