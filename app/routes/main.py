from app.routes import main_bp
from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
from flask import render_template, request, redirect, url_for, current_app

@main_bp.route('/')
@main_bp.route('/index')
def index():
    return render_template('index.html')
@main_bp.route('/manifest.json')
def manifest():
    return current_app.send_static_file('manifest.json')

@main_bp.route('/sw.js')
def sw():
    return current_app.send_static_file('sw.js')

@main_bp.route('/manual/ideb')
def manual_ideb():
    from flask_login import login_required
    return render_template('manual_ideb.html')

@main_bp.route('/setup-db-render')
def setup_db_render():
    from app import db
    from app.models import User
    from werkzeug.security import generate_password_hash
    
    try:
        # Cria as estruturas de tabelas vazias no banco de dados
        db.create_all()
        
        # Garante que a coluna password_hash tenha espaço suficiente para o novo padrão scrypt
        from sqlalchemy import text
        try:
            db.session.execute(text('ALTER TABLE "user" ALTER COLUMN password_hash TYPE VARCHAR(256);'))
            db.session.commit()
        except:
            db.session.rollback()
        
        # Verifica se o usuário master já existe, caso não, cria
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin'),
                name='Administrador do Sistema',
                role='admin',
                is_system_admin=True,
                active=True
            )
            db.session.add(admin)
            db.session.commit()
            
        return "<h2>Banco de dados inicializado com sucesso!</h2><p>As tabelas foram criadas e o usuário mestre foi configurado.</p><p>Acesse o <a href='/auth/login'>Login</a> utilizando:<br>Usuário: <b>admin</b><br>Senha: <b>admin</b></p><p>Após o login, acesse a área de Administração para iniciar a migração completa dos dados de teste pelo painel.</p>"
    except Exception as e:
        import traceback
        return f"<h2>Erro ao inicializar o banco de dados:</h2><pre>{str(e)}</pre><br><pre>{traceback.format_exc()}</pre>"

def get_current_version():
    try:
        with open('app/version.txt', 'r') as f:
            return f.read().strip()
    except:
        return '1.0.0'

@main_bp.before_app_request
def check_version_agreement():
    from flask_login import current_user
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import request, redirect, url_for
    
    if not current_user.is_authenticated:
        return
        
    # Exclude static, update route itself, and auth routes (logout)
    if request.endpoint and (
        'static' in request.endpoint or 
        'main.confirm_update' in request.endpoint or 
        'auth.logout' in request.endpoint
    ):
        return

    current_version = get_current_version()
    
    # Exclude students and professors from update notice
    if any(role in ['student', 'professor'] for role in current_user.get_roles()):
        return

    # Skip for AJAX (fetch/XHR), JSON requests, or async PDF generation
    is_exempt = (request.is_json or \
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
                'application/json' in request.headers.get('Accept', '') or \
                request.args.get('async') == '1' or \
                request.endpoint == 'exams.download_exam_pdf')
    
    # print(f"DEBUG: check_version_agreement - endpoint={request.endpoint}, exempt={is_exempt}")
    
    if is_exempt:
        return

    if current_user.last_agreed_version != current_version:
        return render_template('update_notice.html', version=current_version)

@main_bp.route('/confirm_update', methods=['POST'])
def confirm_update():
    from flask_login import current_user
    from app import db
    
    current_version = get_current_version()
    current_user.last_agreed_version = current_version
    db.session.commit()
    from app.audit_utils import log_audit
    log_audit('UPDATE', 'SystemConfig', 0, "Confirmou termo de aceite de nova versão do sistema")
    
    # flash(f'Versão {current_version} confirmada.', 'success')
    return redirect(url_for('main.index'))


@main_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    from flask_login import current_user
    from flask import redirect, url_for, flash, current_app, abort
    
    if not current_user.is_authenticated or not getattr(current_user, 'is_system_admin', False):
        abort(403)
        
    from app.forms import SystemSettingsForm
    from app.models import SystemConfig
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from werkzeug.utils import secure_filename
    import os

    form = SystemSettingsForm()
    
    if request.method == 'POST':
        print(f"DEBUG: Settings POST received. Form data: {request.form}")
        print(f"DEBUG: Files: {request.files}")
        
    if form.validate_on_submit():
        print("DEBUG: Form validated successfully")
        # Save System Name
        SystemConfig.set_value('system_name', form.system_name.data)
        
        # Save Logo
        if form.logo.data:
            if not allowed_file(form.logo.data.filename, ALLOWED_IMAGE_EXTENSIONS):
                flash("Formato de logo inválido. Apenas PNG, JPG, JPEG e GIF são permitidos.", "danger")
                return redirect(url_for("main.settings"))
            current_app.logger.info(f"Processing logo: {form.logo.data.filename}")
            
            # Save to Database (BLOB)
            file_data = form.logo.data.read()
            # Reset pointer if needed, though we don't save to file anymore
            # form.logo.data.seek(0) 
            
            # Use a fixed key 'logo_image' for the binary data, or attach to 'logo_filename' row?
            # Creating a separate key 'logo_image' for clarity.
            SystemConfig.set_data('logo_image', file_data)
            
            # Use original filename for reference/mime type inference if needed, or just display logic
            filename = secure_filename(form.logo.data.filename)
            SystemConfig.set_value('logo_filename', filename)
            
            # No longer saving to filesystem
            current_app.logger.info("Logo saved to database successfully.")
            
        # Save Login Background
        if form.login_background.data:
            if not allowed_file(form.login_background.data.filename, ALLOWED_IMAGE_EXTENSIONS):
                flash("Formato de plano de fundo inválido. Apenas PNG, JPG, JPEG e GIF são permitidos.", "danger")
                return redirect(url_for("main.settings"))
            current_app.logger.info(f"Processing login background: {form.login_background.data.filename}")
            
            file_data = form.login_background.data.read()
            SystemConfig.set_data('login_bg_image', file_data)
            
            filename = secure_filename(form.login_background.data.filename)
            SystemConfig.set_value('login_bg_filename', filename)
            
            current_app.logger.info("Login background saved to database successfully.")
            
        # Save Favicon
        if form.favicon.data:
            if not allowed_file(form.favicon.data.filename, ['ico', 'png']):
                flash("Formato de favicon inválido. Apenas ICO e PNG são permitidos.", "danger")
                return redirect(url_for("main.settings"))
            current_app.logger.info(f"Processing favicon: {form.favicon.data.filename}")
            
            file_data = form.favicon.data.read()
            SystemConfig.set_data('favicon_image', file_data)
            
            filename = secure_filename(form.favicon.data.filename)
            SystemConfig.set_value('favicon_filename', filename)
            
            current_app.logger.info("Favicon saved to database successfully.")
            
        # Save SMTP Settings
        SystemConfig.set_value('smtp_server', form.smtp_server.data)
        SystemConfig.set_value('smtp_port', str(form.smtp_port.data) if form.smtp_port.data is not None else '')
        SystemConfig.set_value('smtp_user', form.smtp_user.data)
        # Only update password if provided
        if form.smtp_password.data:
            SystemConfig.set_value('smtp_password', form.smtp_password.data)
        SystemConfig.set_value('smtp_security', form.smtp_security.data)
        SystemConfig.set_value('smtp_sender', form.smtp_sender.data)
            
        flash('Configurações atualizadas com sucesso!', 'success')
        from app.audit_utils import log_audit
        log_audit('UPDATE', 'SystemConfig', 0, "Atualizou as configurações gerais do sistema (SMTP, Nome, etc.)")
        # Re-redirect to settings to refresh context
        return redirect(url_for('main.settings'))
    else:
        if request.method == 'POST':
            print(f"DEBUG: Form validation failed. Errors: {form.errors}")
            current_app.logger.error(f"Settings form validation failed: {form.errors}")
            flash('Erro ao salvar configurações. Verifique os campos.', 'danger')

    if request.method == 'GET':
        form.system_name.data = SystemConfig.get_value('system_name', 'IDEB+')
        form.smtp_server.data = SystemConfig.get_value('smtp_server')
        form.smtp_port.data = SystemConfig.get_value('smtp_port')
        form.smtp_user.data = SystemConfig.get_value('smtp_user')
        form.smtp_security.data = SystemConfig.get_value('smtp_security', 'none')
        form.smtp_sender.data = SystemConfig.get_value('smtp_sender')
    
    current_logo = SystemConfig.get_value('logo_filename')
    current_login_bg = SystemConfig.get_value('login_bg_filename')
    current_favicon = SystemConfig.get_value('favicon_filename')
    return render_template('settings.html', form=form, current_logo=current_logo, current_login_bg=current_login_bg, current_favicon=current_favicon)

@main_bp.route('/settings/logo')
def get_logo():
    from app.models import SystemConfig
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import send_file, Response, current_app
    import io
    
    data = SystemConfig.get_data('logo_image')
    if data:
        return send_file(io.BytesIO(data), mimetype='image/png') # Default to png, or detect
    
    # Fallback or 404
    return "No logo", 404

@main_bp.route('/settings/remove_logo', methods=['POST'])
def remove_logo():
    from app.models import SystemConfig
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import redirect, url_for, flash, current_app
    import os
    from flask_login import login_required, current_user
    
    # Ensure only admin can do this
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('Acesso não autorizado', 'danger')
        return redirect(url_for('main.index'))

    # Clear DB Data
    SystemConfig.set_value('logo_filename', None)
    
    # Manually delete 'logo_image' row since set_value(None) only deletes key-based row
    # We need to clean up 'logo_image' too.
    # Actually, we can just set data to None?
    # But set_data handles creation/update. Let's assume we can delete it manually or add removal logic.
    # Models doesn't have delete for set_data? set_data updates item.data.
    # If we want to delete the row, we might need a delete helper or use query.
    
    # Quick fix: manually delete in route or update model. 
    # Let's use direct query to be safe.
    logo_data_item = SystemConfig.query.filter_by(key='logo_image').first()
    if logo_data_item:
        from app import db
        db.session.delete(logo_data_item)
        db.session.commit()
        from app.audit_utils import log_audit
        log_audit('DELETE', 'SystemConfig', 0, "Removeu a imagem de logo do sistema")

    flash('Logo removida com sucesso!', 'success')
        
    return redirect(url_for('main.settings'))

@main_bp.route('/settings/login_bg')
def get_login_bg():
    from app.models import SystemConfig
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import send_file, Response, current_app
    import io
    
    data = SystemConfig.get_data('login_bg_image')
    if data:
        return send_file(io.BytesIO(data), mimetype='image/png') # Default to png, or detect
    
    # Fallback or 404
    return "No login background", 404

@main_bp.route('/settings/remove_login_bg', methods=['POST'])
def remove_login_bg():
    from app.models import SystemConfig
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import redirect, url_for, flash, current_app
    import os
    from flask_login import login_required, current_user
    
    # Ensure only admin can do this
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('Acesso não autorizado', 'danger')
        return redirect(url_for('main.index'))

    # Clear DB Data
    SystemConfig.set_value('login_bg_filename', None)
    
    login_bg_data_item = SystemConfig.query.filter_by(key='login_bg_image').first()
    if login_bg_data_item:
        from app import db
        db.session.delete(login_bg_data_item)
        db.session.commit()
        from app.audit_utils import log_audit
        log_audit('DELETE', 'SystemConfig', 0, "Removeu a imagem de fundo de login do sistema")

    flash('Imagem de Fundo Módulo Login removida com sucesso!', 'success')
        
    return redirect(url_for('main.settings'))

@main_bp.route('/settings/favicon')
def get_favicon():
    from app.models import SystemConfig
    from flask import send_file
    import io
    
    data = SystemConfig.get_data('favicon_image')
    if data:
        filename = SystemConfig.get_value('favicon_filename') or 'favicon.ico'
        mimetype = 'image/png' if filename.endswith('.png') else 'image/x-icon'
        return send_file(io.BytesIO(data), mimetype=mimetype)
    
    # Fallback or 404
    return "No favicon", 404

@main_bp.route('/settings/remove_favicon', methods=['POST'])
def remove_favicon():
    from app.models import SystemConfig
    from flask import redirect, url_for, flash
    from flask_login import login_required, current_user
    
    if not current_user.is_authenticated or not current_user.is_admin:
        flash('Acesso não autorizado', 'danger')
        return redirect(url_for('main.index'))

    SystemConfig.set_value('favicon_filename', None)
    
    favicon_data_item = SystemConfig.query.filter_by(key='favicon_image').first()
    if favicon_data_item:
        from app import db
        db.session.delete(favicon_data_item)
        db.session.commit()
        from app.audit_utils import log_audit
        log_audit('DELETE', 'SystemConfig', 0, "Removeu o favicon do sistema")

    flash('Favicon removido com sucesso!', 'success')
        
    return redirect(url_for('main.settings'))

@main_bp.route('/import-status/<task_id>')
def import_status(task_id):
    from app.import_utils import import_progress
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import jsonify
    return jsonify(import_progress.get(task_id, {'status': 'not_found'}))

@main_bp.route('/download-import-log/<filename>')
def download_import_log(filename):
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import send_from_directory, current_app
    import os
    
    # Secure filename
    from werkzeug.utils import secure_filename
    safe_filename = secure_filename(filename)
    
    log_dir = os.path.join(current_app.instance_path, 'import_logs')
    return send_from_directory(log_dir, safe_filename, as_attachment=True)

@main_bp.route('/sw.js')
def serve_sw():
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import current_app, send_from_directory
    import os
    return send_from_directory(current_app.static_folder, 'sw.js', mimetype='application/javascript')

@main_bp.route('/manifest.json')
def serve_manifest():
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import current_app, send_from_directory
    import os
    return send_from_directory(current_app.static_folder, 'manifest.json', mimetype='application/json')

