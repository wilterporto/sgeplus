from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import AuditLog, AccessLog, User
from functools import wraps

audit_bp = Blueprint('audit', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acesso negado. Apenas administradores podem acessar a auditoria.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@audit_bp.route('/')
@login_required
@admin_required
def index():
    # Dashboard or Redirect to Logs
    return redirect(url_for('audit.list_logs'))

@audit_bp.route('/logs')
@login_required
@admin_required
def list_logs():
    from app.models import Tenant
    page = request.args.get('page', 1, type=int)
    tenant_id = request.args.get('tenant_id', type=int)
    
    query = AuditLog.query.join(User)
    tenants = None
    
    if current_user.is_system_admin:
        tenants = Tenant.query.order_by(Tenant.name).all()
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
    else:
        query = query.filter(User.tenant_id == current_user.tenant_id)
        
    logs = query.order_by(AuditLog.timestamp.desc()).paginate(page=page, per_page=30)
    return render_template('audit/logs.html', logs=logs, tenants=tenants, selected_tenant_id=tenant_id)

@audit_bp.route('/access')
@login_required
@admin_required
def list_access():
    from app.models import Tenant
    page = request.args.get('page', 1, type=int)
    tenant_id = request.args.get('tenant_id', type=int)
    
    query = AccessLog.query.join(User)
    tenants = None
    
    if current_user.is_system_admin:
        tenants = Tenant.query.order_by(Tenant.name).all()
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
    else:
        query = query.filter(User.tenant_id == current_user.tenant_id)
        
    access_logs = query.order_by(AccessLog.login_time.desc()).paginate(page=page, per_page=30)
    return render_template('audit/access.html', access_logs=access_logs, tenants=tenants, selected_tenant_id=tenant_id)

@audit_bp.route('/reports/no_access')
@login_required
@admin_required
def no_access_report():
    # Users who have NEVER logged in (no AccessLog or last_login is None)
    # Using last_login is simpler/faster
    from app.utils.tenancy import filter_by_tenant
    query = User.query.filter(User.last_login == None)
    query = filter_by_tenant(query, User)
    users = query.all()
    return render_template('audit/no_access_report.html', users=users)
