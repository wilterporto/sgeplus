from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User
from app.forms import UserForm
from functools import wraps

users_bp = Blueprint('users', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Você não tem permissão para acessar esta página.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@users_bp.route('/', methods=['GET'])
@login_required
@admin_required
def list_users():
    page = request.args.get('page', 1, type=int)
    query = User.query
    
    # Injeção de isolamento por Tenant
    from app.utils.tenancy import filter_by_tenant
    query = filter_by_tenant(query, User)
    
    users_pagination = query.order_by(User.name.asc()).paginate(page=page, per_page=30)
    return render_template('users/list.html', users=users_pagination)

@users_bp.route('/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    form = UserForm()
    from app.models import TeachingUnit, Tenant
    from app.utils.tenancy import filter_by_tenant
    
    # Configurar escolhas de escolas filtradas por tenant
    tu_query = TeachingUnit.query.filter_by(type='Escola')
    tu_query = filter_by_tenant(tu_query, TeachingUnit)
    form.teaching_unit_ids.choices = [(tu.id, tu.name) for tu in tu_query.order_by(TeachingUnit.name).all()]
    
    # Configurar escolhas de clientes
    if current_user.is_system_admin:
        form.tenant_id.choices = [(0, 'Nenhum / Administrador de Sistema')] + [(t.id, t.name) for t in Tenant.query.order_by(Tenant.name).all()]
    else:
        form.tenant_id.choices = [(current_user.tenant_id or 1, current_user.tenant.name if current_user.tenant else 'SME Goiânia')]
    
    if form.validate_on_submit():
        # Handle multiple roles
        primary_role = form.roles.data[0] if form.roles.data else 'student'
        roles_str = ','.join(form.roles.data)

        # Enforce Email for non-students
        if 'student' not in form.roles.data:
            if not form.email.data:
                flash('O campo E-mail é obrigatório para este perfil.', 'danger')
                return render_template('users/form.html', form=form, title='Novo Usuário')
                
        # Custom validation: if role is 'unidade', teaching_unit_ids must not be empty
        if 'unidade' in form.roles.data and not form.teaching_unit_ids.data:
            form.teaching_unit_ids.errors.append('Selecione pelo menos uma unidade escolar para o perfil Unidade.')
            return render_template('users/form.html', form=form, title='Novo Usuário')
        
        # Atribuir tenant_id
        from flask import session
        is_system_admin = False
        if current_user.is_system_admin and not session.get('active_tenant_id'):
            # Administração global: pega do form
            tenant_id = form.tenant_id.data if form.tenant_id.data > 0 else None
            if 'admin' in form.roles.data and not tenant_id:
                is_system_admin = True
        else:
            # Visão do cliente: assume automaticamente o tenant ativo
            from app.utils.tenancy import get_tenant_id
            tenant_id = get_tenant_id()
            # Usuários criados na visão do cliente nunca são administradores globais do sistema
            is_system_admin = False
        
        user = User(username=form.username.data, email=form.email.data, name=form.name.data,
                    role=primary_role, roles=roles_str, regional=form.regional.data,
                    active=form.active.data, tenant_id=tenant_id, is_system_admin=is_system_admin)
        user.set_password(form.password.data)
        
        # Save relationships
        if 'unidade' in form.roles.data and form.teaching_unit_ids.data:
            schools = TeachingUnit.query.filter(TeachingUnit.id.in_(form.teaching_unit_ids.data)).all()
            user.teaching_units = schools
            
        db.session.add(user)
        db.session.commit()
        
        from app.audit_utils import log_audit
        log_audit('CREATE', 'User', user.id, f"Created user {user.username} with roles {roles_str}")
        
        flash('Usuário criado com sucesso!', 'success')
        return redirect(url_for('users.list_users'))
    return render_template('users/form.html', form=form, title='Novo Usuário')

@users_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    user = User.query.get_or_404(id)
    
    # Validar isolamento por tenant
    if not current_user.is_system_admin and user.tenant_id != current_user.tenant_id:
        flash('Acesso não autorizado a este usuário.', 'danger')
        return redirect(url_for('users.list_users'))
        
    form = UserForm(obj=user)
    from app.models import TeachingUnit, Tenant
    from app.utils.tenancy import filter_by_tenant
    
    # Configurar escolhas de escolas filtradas por tenant
    tu_query = TeachingUnit.query.filter_by(type='Escola')
    tu_query = filter_by_tenant(tu_query, TeachingUnit)
    form.teaching_unit_ids.choices = [(tu.id, tu.name) for tu in tu_query.order_by(TeachingUnit.name).all()]
    
    # Configurar escolhas de clientes
    if current_user.is_system_admin:
        form.tenant_id.choices = [(0, 'Nenhum / Administrador de Sistema')] + [(t.id, t.name) for t in Tenant.query.order_by(Tenant.name).all()]
    else:
        form.tenant_id.choices = [(current_user.tenant_id or 1, current_user.tenant.name if current_user.tenant else 'SME Goiânia')]
    
    # Pre-populate roles for GET
    if request.method == 'GET':
        form.roles.data = user.get_roles()
        form.teaching_unit_ids.data = [tu.id for tu in user.teaching_units]
        form.tenant_id.data = user.tenant_id or 0
    
    # Password validation override for edit
    if request.method == 'POST':
        # If password field is empty, remove it from validation to keep old password
        if not form.password.data:
            form.password.validators = []
            
    if form.validate_on_submit():
        # Enforce Email for non-students
        if 'student' not in form.roles.data:
            if not form.email.data:
                flash('O campo E-mail é obrigatório para este perfil.', 'danger')
                return render_template('users/form.html', form=form, title='Editar Usuário', user_id=id)

        # Custom validation: if role is 'unidade', teaching_unit_ids must not be empty
        if 'unidade' in form.roles.data and not form.teaching_unit_ids.data:
            form.teaching_unit_ids.errors.append('Selecione pelo menos uma unidade escolar para o perfil Unidade.')
            return render_template('users/form.html', form=form, title='Editar Usuário', user_id=id)

        user.username = form.username.data
        user.name = form.name.data
        user.email = form.email.data
        user.active = form.active.data
        
        # Atualizar tenant_id se for Super Admin
        from flask import session
        if current_user.is_system_admin:
            if not session.get('active_tenant_id'):
                # Administração global: atualiza do form
                user.tenant_id = form.tenant_id.data if form.tenant_id.data > 0 else None
                if 'admin' in form.roles.data and not user.tenant_id:
                    user.is_system_admin = True
                else:
                    user.is_system_admin = False
            else:
                # Visão do cliente: não altera tenant_id e garante que is_system_admin seja False
                user.is_system_admin = False
        
        # Update roles
        user.roles = ','.join(form.roles.data)
        user.role = form.roles.data[0] if form.roles.data else 'student'
        
        user.regional = form.regional.data
        if form.password.data:
            user.set_password(form.password.data)
            
        # Update school relationships
        if 'unidade' in form.roles.data and form.teaching_unit_ids.data:
            schools = TeachingUnit.query.filter(TeachingUnit.id.in_(form.teaching_unit_ids.data)).all()
            user.teaching_units = schools
        else:
            user.teaching_units = []
        
        db.session.commit()
        
        from app.audit_utils import log_audit
        log_audit('UPDATE', 'User', user.id, f"Updated user {user.username}")
        
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('users.list_users'))
        
    return render_template('users/form.html', form=form, title='Editar Usuário', user_id=id)

@users_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_user(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Você não pode excluir a si mesmo!', 'danger')
        return redirect(url_for('users.list_users'))
        
    user_id = user.id
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    from app.audit_utils import log_audit
    log_audit('DELETE', 'User', user_id, f"Deleted user {username}")
    
    flash('Excluído com sucesso', 'success_delete')
    return redirect(url_for('users.list_users'))

@users_bp.route('/toggle_active/<int:id>', methods=['POST'])
@login_required
@admin_required
def toggle_active(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
         flash('Você não pode desativar a si mesmo!', 'danger')
         return redirect(url_for('users.list_users'))
         
    user.active = not user.active
    db.session.commit()
    
    from app.audit_utils import log_audit
    status = 'Ativado' if user.active else 'Desativado'
    log_audit('UPDATE', 'User', user.id, f"User {user.username} {status}")
    
    flash(f'Usuário {status} com sucesso.', 'success')
    return redirect(url_for('users.list_users'))

@users_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = UserForm(obj=current_user)
    
    # Disable fields not editable by user, EXCEPT email
    del form.active
    del form.roles
    del form.regional
    # Read-only attributes logic handled in template usually, or just don't render them as inputs.
    # We DO want to allow email editing.
    
    if request.method == 'POST':
        # Need to re-validate form with limited fields or custom logic
        # UserForm expects username/roles/etc which might be missing or readonly
        # Simple approach: Verify specific fields we care about
        
        new_email = request.form.get('email')
        new_password = request.form.get('password')
        
        messages = []
        
        # 1. Update Email
        if new_email and new_email != current_user.email:
            # Check uniqueness
            existing = User.query.filter_by(email=new_email).first()
            if existing and existing.id != current_user.id:
                flash('Este e-mail já está em uso por outro usuário.', 'danger')
            else:
                current_user.email = new_email
                from app.models import Student, Professor
                
                # Sync logic (Student/Professor)
                # Ideally this should be a signal or service method, but inline for now based on previous patterns
                if current_user.role == 'student':
                    student = Student.query.filter_by(user_id=current_user.id).first()
                    if student:
                        student.email = new_email
                elif current_user.role == 'professor':
                    professor = Professor.query.filter_by(user_id=current_user.id).first()
                    if professor:
                         professor.email = new_email
                
                messages.append('E-mail atualizado.')

        # 2. Update Password
        if new_password:
             current_user.set_password(new_password)
             messages.append('Senha alterada.')
        
        if messages:
            db.session.commit()
            flash(' '.join(messages), 'success')
            return redirect(url_for('users.profile'))
        elif request.method == 'POST' and not new_password and (new_email == current_user.email or not new_email):
             flash('Nenhuma alteração detectada.', 'info')
             
    # For GET or invalid form, we prepare display
    # We might want a separate ChangePasswordForm, but re-using UserForm password field is quick hack
    
    return render_template('users/profile.html', user=current_user, form=form)
