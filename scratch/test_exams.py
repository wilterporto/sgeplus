import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import User, Exam, Tenant
from app.utils.analytics import get_exam_stats
from flask import session

app = create_app()
with app.app_context():
    from flask_login import login_user
    with app.test_request_context():
        user = User.query.filter_by(email='admin@sgeplus.com').first()
        login_user(user)
        
        tenant = Tenant.query.filter(Tenant.name.ilike('%Goiânia%')).first()
        session['active_tenant_id'] = tenant.id
        print("Tenant:", tenant.name, tenant.id)
        
        exams = Exam.query.filter_by(tenant_id=tenant.id).all()
        print(f"Found {len(exams)} exams.")
        for exam in exams:
            stats = get_exam_stats(exam.id)
            print(f"Exam {exam.id} ({exam.title}): {stats}")
