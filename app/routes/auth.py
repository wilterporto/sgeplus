from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from app import db, limiter
from app.models import User, SystemConfig
from app.forms import LoginForm, RequestPasswordResetForm, ResetPasswordForm
import smtplib
from email.mime.text import MIMEText
from werkzeug.security import generate_password_hash
import secrets

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Usuário ou senha inválidos', 'danger')
            return redirect(url_for('auth.login'))
            
        if not user.active:
            flash('Esta conta foi desativada. Contate o administrador.', 'danger')
            return redirect(url_for('auth.login'))
        
        login_user(user, remember=form.remember.data)
        
        # Multi-role logic
        roles = user.get_roles()
        if len(roles) > 1:
            return redirect(url_for('auth.select_role'))
        elif len(roles) == 1:
            session['active_role'] = roles[0]
            if roles[0] == 'unidade':
                schools = user.teaching_units
                if not schools:
                    flash('Este usuário Unidade não possui nenhuma unidade escolar vinculada.', 'danger')
                    logout_user()
                    session.clear()
                    return redirect(url_for('auth.login'))
                elif len(schools) == 1:
                    session['active_school_id'] = schools[0].id
                    session['active_school_name'] = schools[0].name
                else:
                    return redirect(url_for('auth.select_school', next=request.args.get('next')))
        else:
            session['active_role'] = 'student' # Default fallback if no role? Or handle error.
            
        # Access Logging
        try:
            from app.models import AccessLog
            from datetime import datetime
            # import user_agents # Removed missing dependency
            
            ua_string = request.user_agent.string
            platform = request.user_agent.platform
            browser = request.user_agent.browser
            ip = request.remote_addr
            
            # Store Last Access for Display (before updating)
            if user.last_login:
                session['last_access_display'] = user.last_login.strftime('%d/%m/%Y %H:%M')
            else:
                session['last_access_display'] = None

            access_log = AccessLog(
                user_id=user.id,
                ip_address=ip,
                user_agent=ua_string,
                platform=platform,
                browser=browser,
                login_time=datetime.utcnow()
            )
            db.session.add(access_log)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            session['access_log_id'] = access_log.id
        except Exception as e:
            print(f"Error logging access: {e}") 
            
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            if session.get('active_role') in ['admin', 'regional_manager']:
                next_page = url_for('academic.academic_dashboard')
            else:
                next_page = url_for('main.index')
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Login', form=form)

@auth_bp.route('/select_role')
@login_required
def select_role():
    roles = current_user.get_roles()
    if len(roles) <= 1:
         if session.get('active_role') in ['admin', 'regional_manager']:
             return redirect(url_for('academic.academic_dashboard'))
         return redirect(url_for('main.index'))
    return render_template('auth/select_role.html', roles=roles)

@auth_bp.route('/set_role/<role>')
@login_required
def set_role(role):
    if role in current_user.get_roles():
        session['active_role'] = role
        flash(f'Perfil alterado para {role}.', 'success')
        
        if role == 'unidade':
            schools = current_user.teaching_units
            if not schools:
                flash('Este usuário Unidade não possui nenhuma unidade escolar vinculada.', 'danger')
                session['active_school_id'] = None
                session['active_school_name'] = None
            elif len(schools) == 1:
                session['active_school_id'] = schools[0].id
                session['active_school_name'] = schools[0].name
            else:
                return redirect(url_for('auth.select_school'))
        else:
            session.pop('active_school_id', None)
            session.pop('active_school_name', None)
            
        if role in ['admin', 'regional_manager']:
            return redirect(url_for('academic.academic_dashboard'))
    else:
        flash('Perfil inválido.', 'danger')
    return redirect(url_for('main.index'))

@auth_bp.route('/select_school', methods=['GET', 'POST'])
@login_required
def select_school():
    if session.get('active_role') != 'unidade':
        flash('Esta operação é permitida apenas para usuários com perfil Unidade.', 'danger')
        return redirect(url_for('main.index'))
        
    schools = current_user.teaching_units
    if not schools:
        flash('Nenhuma unidade escolar vinculada a esta conta.', 'danger')
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        school_id = request.form.get('school_id', type=int)
        school = next((s for s in schools if s.id == school_id), None)
        if school:
            session['active_school_id'] = school.id
            session['active_school_name'] = school.name
            flash(f'Escola ativa definida para: {school.name}', 'success')
            
            next_page = request.args.get('next')
            if not next_page or not next_page.startswith('/'):
                next_page = url_for('main.index')
            return redirect(next_page)
        else:
            flash('Escola selecionada inválida.', 'danger')
            
    return render_template('auth/select_school.html', schools=schools)

@auth_bp.route('/change_school/<int:school_id>')
@login_required
def change_school(school_id):
    if session.get('active_role') != 'unidade':
        flash('Esta operação é permitida apenas para usuários com perfil Unidade.', 'danger')
        return redirect(url_for('main.index'))
        
    schools = current_user.teaching_units
    school = next((s for s in schools if s.id == school_id), None)
    if school:
        session['active_school_id'] = school.id
        session['active_school_name'] = school.name
        flash(f'Escola alterada para: {school.name}', 'success')
    else:
        flash('Escola inválida ou sem acesso.', 'danger')
    return redirect(request.referrer or url_for('main.index'))

@auth_bp.route('/change_role')
@login_required
def change_role():
    return redirect(url_for('auth.select_role'))

@auth_bp.route('/logout')
def logout():
    # Update Access Log
    access_log_id = session.get('access_log_id')
    if access_log_id:
        from app.models import AccessLog
        from datetime import datetime
        try:
            log = AccessLog.query.get(access_log_id)
            if log:
                log.logout_time = datetime.utcnow()
                log.logout_type = 'MANUAL'
                db.session.commit()
        except Exception as e:
            print(f"Error updating logout log: {e}")

    session.pop('active_role', None)
    session.pop('access_log_id', None)
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    form = RequestPasswordResetForm()
    if form.validate_on_submit():
        identifier = form.identifier.data
        user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()
        
        if user:
            if not user.email:
                if user.role in ['student', 'professor']:
                    flash('Você não possui e-mail cadastrado no sistema. Procure sua escola ou secretaria de educação para atualizar seu cadastro.', 'warning')
                else:
                    flash('Você não possui e-mail cadastrado. Contate o administrador.', 'warning')
                return redirect(url_for('auth.login'))
            
            send_password_reset_email(user)
        
        # Generic message for security (or specific if we want to confirm success)
        # Given the requirements, we likely want to communicate success/failure clearly but safely.
        # "Verifique seu e-mail" is standard. The error above handles the specific "No Email" case.
        flash('Verifique seu e-mail para as instruções de recuperação.', 'info')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/forgot_password.html', title='Recuperar Senha', form=form)

def send_password_reset_email(user):
    token = user.get_reset_password_token()
    send_email('Recuperação de Senha',
               sender=SystemConfig.get_value('smtp_sender'),
               recipients=[user.email],
               text_body=render_template('auth/email/reset_password.txt', user=user, token=token),
               html_body=render_template('auth/email/reset_password.html', user=user, token=token))

def send_email(subject, sender, recipients, text_body, html_body):
    # Retrieve SMTP settings
    smtp_server = SystemConfig.get_value('smtp_server')
    smtp_port = SystemConfig.get_value('smtp_port')
    smtp_user = SystemConfig.get_value('smtp_user')
    smtp_password = SystemConfig.get_value('smtp_password')
    smtp_security = SystemConfig.get_value('smtp_security')

    if not smtp_server:
        print("SMTP not configured. Email suppressed.")
        return

    msg = MIMEText(html_body, 'html')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ", ".join(recipients)

    try:
        server = smtplib.SMTP(smtp_server, int(smtp_port) if smtp_port else 25)
        if smtp_security == 'tls':
            server.starttls()
        elif smtp_security == 'ssl':
            server = smtplib.SMTP_SSL(smtp_server, int(smtp_port) if smtp_port else 465)
        
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
            
        server.sendmail(sender, recipients, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('main.index'))
        
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Sua senha foi redefinida.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', form=form)
