from flask import Blueprint

main_bp = Blueprint('main', __name__)
questions_bp = Blueprint('questions', __name__)
exams_bp = Blueprint('exams', __name__)
reports_bp = Blueprint('reports', __name__)

from .auth import auth_bp
from .main import main_bp
from .questions import questions_bp
from .exams import exams_bp
from .reports import reports_bp
from .admin import admin_bp
