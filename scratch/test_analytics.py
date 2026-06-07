import sys
import os
import traceback

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import User, Exam
from app.utils.analytics import get_dashboard_data, get_exam_stats
from flask import session

app = create_app()
with app.app_context():
    # Hack to mock current_user and session for tenant
    from flask_login import login_user
    with app.test_request_context():
        user = User.query.filter_by(email='admin@sgeplus.com').first()
        if not user:
            user = User.query.first()
            
        login_user(user)
        session['active_tenant_id'] = 2 # SME Goiânia is typically 2, let's assume it or we can check
        
        from app.models import Tenant
        tenant = Tenant.query.filter(Tenant.name.ilike('%Goiânia%')).first()
        if tenant:
            session['active_tenant_id'] = tenant.id
            print("Using tenant:", tenant.name, tenant.id)
            
        exam = Exam.query.filter_by(tenant_id=tenant.id).first()
        if not exam:
            exam = Exam.query.first()
            
        print(f"Testing Dashboard for Exam: {exam.id} - {exam.title}")
        
        try:
            data = get_dashboard_data(exam_id=exam.id)
            if data is None:
                print("get_dashboard_data returned None!")
            else:
                print("Dashboard data returned kpis:", data.get('kpis'))
        except Exception as e:
            print("Error in get_dashboard_data!")
            traceback.print_exc()

        print("\n--- Testing get_exam_stats ---")
        try:
            stats = get_exam_stats(exam_id=exam.id)
            print("Stats:", stats)
        except Exception as e:
            print("Error in get_exam_stats!")
            traceback.print_exc()
