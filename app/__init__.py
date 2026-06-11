from flask import Flask
from sqlalchemy import MetaData
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from config import Config
naming_convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

db = SQLAlchemy(metadata=MetaData(naming_convention=naming_convention))
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()

from flask_talisman import Talisman
talisman = Talisman()

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    csrf.init_app(app)
    
    from flask_talisman import Talisman
    # Disable CSP for now to not break existing UI scripts/styles
    talisman.init_app(app, content_security_policy=None, force_https=False)
    
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter.init_app(app)

    
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

    from app.routes import main_bp, questions_bp, exams_bp, reports_bp, auth_bp, admin_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(questions_bp, url_prefix='/questions')
    app.register_blueprint(exams_bp, url_prefix='/exams')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    from app.routes.users import users_bp
    app.register_blueprint(users_bp, url_prefix='/users')
    
    from app.routes.academic import academic_bp
    app.register_blueprint(academic_bp, url_prefix='/academic')

    from app.routes.students import students_bp
    app.register_blueprint(students_bp, url_prefix='/students')

    from app.routes.professors import professors_bp
    app.register_blueprint(professors_bp, url_prefix='/professors')

    from app.routes.matrices import matrices_bp
    app.register_blueprint(matrices_bp, url_prefix='/matrices')
    
    from app.routes.audit import audit_bp
    app.register_blueprint(audit_bp, url_prefix='/audit')

    from app.routes.anthropometry import anthropometry_bp
    app.register_blueprint(anthropometry_bp)

    from app.routes.nutrition import nutrition_bp
    app.register_blueprint(nutrition_bp)
    
    # Context Processor for Version
    @app.context_processor
    def inject_context():
        # Version
        try:
            with open('app/version.txt', 'r') as f:
                version = f.read().strip()
        except FileNotFoundError:
            version = "0.0.0"
            
        # System Config
        from app.models import SystemConfig
        # We need to wrap in try/except to avoid issues during db initialization/migration
        try:
            config = {
                'system_name': SystemConfig.get_value('system_name', 'SGE Plus'),
                'logo_filename': SystemConfig.get_value('logo_filename'),
                'login_bg_filename': SystemConfig.get_value('login_bg_filename')
            }
        except:
            config = {'system_name': 'SGE Plus', 'logo_filename': None, 'login_bg_filename': None}
            
        from app.utils.tenancy import get_tenant_id
        from app.models import Tenant
        tenant_id = get_tenant_id()
        active_tenant = Tenant.query.get(tenant_id) if tenant_id else None
            
        return dict(system_version=version, system_config=config, active_tenant=active_tenant)

    @app.before_request
    def require_login():
        from flask import request, redirect, url_for, session, flash
        from flask_login import current_user
        
        # Whitelist routes that don't require login
        # static: for css/js/images
        # auth.login: to allow logging in
        # auth.forgot_password, auth.reset_password: for recovery
        whitelist_endpoints = ['auth.login', 'auth.forgot_password', 'auth.reset_password', 'static', 'main.get_logo', 'main.get_login_bg', 'main.serve_sw', 'main.serve_manifest', 'main.setup_db_render']
        
        if not current_user.is_authenticated:
            if request.endpoint and \
               request.endpoint not in whitelist_endpoints and \
               not request.endpoint.startswith('static'):
                
                # For AJAX/JSON requests, return 401 JSON instead of 302 redirect
                if request.is_json or \
                   request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
                   'application/json' in request.headers.get('Accept', ''):
                    from flask import jsonify
                    return jsonify({'error': 'Sessão expirada. Por favor, faça login novamente.'}), 401
                    
                return redirect(url_for('auth.login', next=request.url))
        else:
            # Se logado como Super Admin e não tiver cliente ativo na sessão, obriga a selecionar um
            if hasattr(current_user, 'is_system_admin') and current_user.is_system_admin:
                active_tenant_id = session.get('active_tenant_id')
                if not active_tenant_id:
                    allowed_admin_endpoints = [
                        'admin.list_tenants', 
                        'admin.new_tenant', 
                        'admin.edit_tenant', 
                        'admin.delete_tenant',
                        'admin.authenticate_tenant', 
                        'admin.deauthenticate_tenant',
                        'users.profile', 
                        'auth.logout',
                        'students.get_cities_by_uf'
                    ]
                    if request.endpoint and \
                       request.endpoint not in allowed_admin_endpoints and \
                       not request.endpoint.startswith('users.') and \
                       not request.endpoint.startswith('audit.') and \
                       request.endpoint not in whitelist_endpoints and \
                       not request.endpoint.startswith('static'):
                        
                        flash('Por favor, selecione um cliente para acessar o sistema.', 'warning')
                        return redirect(url_for('admin.list_tenants'))

    return app
