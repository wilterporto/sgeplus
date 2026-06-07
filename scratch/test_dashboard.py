import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import User, Exam

app = create_app()
with app.app_context():
    user = User.query.filter_by(email='admin@sgeplus.com').first()
    if not user:
        user = User.query.first()
    
    with app.test_client(user=user) as client:
        pass
