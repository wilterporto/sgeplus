import os
import json
import threading
import pandas as pd
from datetime import datetime
from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, session, abort, current_app
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired
from app.forms import DietaryRestrictionForm, TenantForm
from werkzeug.utils import secure_filename
from sqlalchemy import func

from app import db
from app.models import ImportJob, DietaryRestriction, Tenant, Student, City
from app.utils.tenancy import filter_by_tenant, get_tenant_id
from app.utils.timezone import get_brasilia_time
from app.audit_utils import log_audit
from app.import_utils import start_import_task, update_import_progress, finish_import_task, fail_import_task

admin_bp = Blueprint('admin', __name__)

# --- WTForms declarations for Admin features ---

# DietaryRestrictionForm importado de app.forms (contém campo 'active')

class ImportDietaryRestrictionForm(FlaskForm):
    file = FileField('Planilha Excel (.xlsx, .xls)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls'], 'Apenas planilhas Excel (.xlsx, .xls) são permitidas!')
    ])
    submit = SubmitField('Importar')

# --- Imports Monitoring / Dashboard ---

@admin_bp.route('/imports')
@login_required
def list_imports():
    if current_user.role != 'admin':
        flash('Acesso restrito a administradores.', 'danger')
        return redirect(url_for('main.index'))
        
    page = request.args.get('page', 1, type=int)
    
    # Filter imports list strictly by active tenant
    query = ImportJob.query
    query = filter_by_tenant(query, ImportJob)
    jobs = query.order_by(ImportJob.created_at.desc()).paginate(page=page, per_page=30)
    
    return render_template('admin/imports.html', jobs=jobs)

@admin_bp.route('/imports/status/<int:id>')
@login_required
def get_import_status(id):
    job = ImportJob.query.get_or_404(id)
    
    # Verify tenant isolation boundaries
    if not current_user.is_system_admin and job.tenant_id != current_user.tenant_id:
        return jsonify({'error': 'Acesso não autorizado'}), 403
        
    return jsonify({
        'id': job.id,
        'status': job.status,
        'processed': job.processed_rows,
        'total': job.total_rows,
        'progress': job.progress_percentage,
        'finished': job.finished_at.strftime('%d/%m/%Y %H:%M') if job.finished_at else None,
        'errors': job.errors # JSON list
    })

@admin_bp.route('/imports/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_import(id):
    if current_user.role != 'admin':
        flash('Acesso restrito a administradores.', 'danger')
        return redirect(url_for('main.index'))
        
    job = ImportJob.query.get_or_404(id)
    
    # Verify tenant isolation boundaries
    if not current_user.is_system_admin and job.tenant_id != current_user.tenant_id:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('admin.list_imports'))
        
    if job.status in ['pending', 'running']:
        job.status = 'failed'
        errors_list = json.loads(job.errors) if job.errors else []
        errors_list.append("Importação cancelada pelo administrador.")
        job.errors = json.dumps(errors_list)
        job.finished_at = get_brasilia_time()
        db.session.commit()
        
        log_audit('UPDATE', 'ImportJob', job.id, f"Importação {job.filename} cancelada manualmente.")
        flash('Importação cancelada com sucesso.', 'success')
    else:
        flash('Esta importação já foi concluída ou falhou.', 'warning')
        
    return redirect(url_for('admin.list_imports'))

# --- Dietary Restrictions Section ---

@admin_bp.route('/dietary-restrictions', methods=['GET', 'POST'])
@login_required
def list_dietary_restrictions():
    if current_user.role != 'admin':
        flash('Acesso restrito a administradores.', 'danger')
        return redirect(url_for('main.index'))
        
    form = DietaryRestrictionForm()
    import_form = ImportDietaryRestrictionForm()
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    query = DietaryRestriction.query
    query = filter_by_tenant(query, DietaryRestriction)
    
    if search:
        query = query.filter(DietaryRestriction.name.ilike(f'%{search}%'))
        
    restrictions = query.order_by(DietaryRestriction.name).paginate(page=page, per_page=30)
    
    active_job = ImportJob.query.filter_by(
        tenant_id=get_tenant_id(),
        import_type='DietaryRestrictions',
        status='running'
    ).first()
    
    if form.validate_on_submit() and not import_form.submit.data:
        # Check uniqueness inside same tenant scope
        existing = DietaryRestriction.query.filter_by(
            tenant_id=get_tenant_id(),
            name=form.name.data.strip()
        ).first()
        if existing:
            flash('Esta restrição alimentar já está cadastrada.', 'danger')
            return redirect(url_for('admin.list_dietary_restrictions'))
            
        restriction = DietaryRestriction(
            name=form.name.data.strip(),
            active=True,
            tenant_id=get_tenant_id()
        )
        db.session.add(restriction)
        db.session.commit()
        
        log_audit('CREATE', 'DietaryRestriction', restriction.id, f"Criou restrição alimentar {restriction.name}")
        flash('Restrição Alimentar criada com sucesso.', 'success')
        return redirect(url_for('admin.list_dietary_restrictions'))
        
    return render_template(
        'admin/dietary_restrictions.html',
        restrictions=restrictions,
        form=form,
        import_form=import_form,
        search=search,
        active_job=active_job
    )

@admin_bp.route('/dietary-restrictions/<int:id>/edit', methods=['POST'])
@login_required
def edit_dietary_restriction(id):
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))
        
    restriction = DietaryRestriction.query.get_or_404(id)
    
    # Verify tenant isolation boundaries
    if restriction.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('admin.list_dietary_restrictions'))
        
    name = request.form.get('name', '').strip()
    active = request.form.get('active') == 'on'
    
    if name:
        # Check uniqueness inside same tenant scope excluding self
        existing = DietaryRestriction.query.filter(
            DietaryRestriction.tenant_id == get_tenant_id(),
            DietaryRestriction.name == name,
            DietaryRestriction.id != id
        ).first()
        if existing:
            flash('Já existe outra restrição alimentar com este nome.', 'danger')
        else:
            old_name = restriction.name
            restriction.name = name
            restriction.active = active
            db.session.commit()
            log_audit('UPDATE', 'DietaryRestriction', restriction.id, f"Atualizou restrição {old_name} para {name} (Ativo: {active})")
            flash('Restrição Alimentar atualizada com sucesso.', 'success')
    else:
        flash('Erro ao atualizar: Nome é obrigatório.', 'danger')
        
    return redirect(url_for('admin.list_dietary_restrictions'))

@admin_bp.route('/dietary-restrictions/<int:id>/delete', methods=['POST'])
@login_required
def delete_dietary_restriction(id):
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))
        
    restriction = DietaryRestriction.query.get_or_404(id)
    
    # Verify tenant isolation boundaries
    if restriction.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('admin.list_dietary_restrictions'))
        
    name = restriction.name
    
    # Check if there are students linked to this restriction
    if restriction.students:
        flash(f'Erro: Não é possível excluir a restrição "{name}" pois existem alunos vinculados.', 'danger')
        return redirect(url_for('admin.list_dietary_restrictions'))
        
    db.session.delete(restriction)
    db.session.commit()
    
    log_audit('DELETE', 'DietaryRestriction', id, f"Excluiu restrição alimentar {name}")
    flash('Restrição Alimentar excluída com sucesso.', 'success_delete')
    return redirect(url_for('admin.list_dietary_restrictions'))

# --- Dietary Restrictions Excel Background Process ---

def _process_dietary_restrictions_import(app, job_id, filepath, task_id=None):
    with app.app_context():
        job = ImportJob.query.get(job_id)
        if not job: return
        
        try:
            job.status = 'running'
            job.started_at = get_brasilia_time()
            db.session.commit()
            
            df = pd.read_excel(filepath)
            total = len(df)
            job.total_rows = total
            db.session.commit()
            
            if task_id:
                start_import_task(total, task_id=task_id)
                
            success_count = 0
            errors = []
            
            # Load existing names inside the active tenant scope for quick lookup
            existing_names = {r.name.strip().lower() for r in DietaryRestriction.query.filter_by(tenant_id=job.tenant_id).all()}
            
            for index, row in df.iterrows():
                col_name = 'Nome' if 'Nome' in df.columns else df.columns[0]
                name_val = str(row.get(col_name, '')).strip()
                
                if not name_val or name_val.lower() == 'nan':
                    errors.append(f"Linha {index+2}: Nome da restrição não informado ou inválido.")
                    job.processed_rows += 1
                    continue
                    
                name_lower = name_val.lower()
                if name_lower in existing_names:
                    errors.append(f"Linha {index+2}: Restrição '{name_val}' já existe.")
                    job.processed_rows += 1
                    continue
                    
                # Create and save within tenant boundaries
                restriction = DietaryRestriction(
                    name=name_val,
                    active=True,
                    tenant_id=job.tenant_id
                )
                db.session.add(restriction)
                existing_names.add(name_lower)
                success_count += 1
                job.processed_rows += 1
                
                if task_id and index % 10 == 0:
                    update_import_progress(task_id, job.processed_rows, message=f"Importando restrição: {name_val}")
                    
                # OTIMIZAÇÃO: Inserção em lote a cada 100 registros
                if success_count % 100 == 0:
                    job.errors = json.dumps(errors)
                    db.session.commit()
                    
            job.status = 'completed'
            job.finished_at = get_brasilia_time()
            job.errors = json.dumps(errors)
            db.session.commit()
            
            if task_id:
                finish_import_task(task_id, message=f"Importação de restrições alimentares concluída. {success_count} registros importados.", log_file=None)
                
        except Exception as e:
            db.session.rollback()
            job.status = 'failed'
            job.errors = json.dumps([f"Erro crítico: {str(e)}"])
            job.finished_at = get_brasilia_time()
            db.session.commit()
            
            if task_id:
                fail_import_task(task_id, f"Erro crítico na importação: {str(e)}")
        finally:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass

@admin_bp.route('/dietary-restrictions/import', methods=['POST'])
@login_required
def import_dietary_restrictions():
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))
        
    if ImportJob.is_any_running():
        flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
        return redirect(url_for('admin.list_dietary_restrictions'))
        
    form = ImportDietaryRestrictionForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        task_id = request.form.get('X-Progress-ID')
        
        uploads_dir = os.path.join(current_app.root_path, '..', 'instance', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        filepath = os.path.join(uploads_dir, filename)
        file.save(filepath)
        
        # Instantiate ImportJob strictly bound to active tenant
        job = ImportJob(
            user_id=current_user.id,
            import_type='DietaryRestrictions',
            filename=filename,
            status='pending',
            tenant_id=get_tenant_id()
        )
        db.session.add(job)
        db.session.commit()
        
        thread = threading.Thread(
            target=_process_dietary_restrictions_import,
            args=(current_app._get_current_object(), job.id, filepath, task_id)
        )
        thread.start()
        
        flash('A importação de restrições alimentares foi iniciada em segundo plano.', 'info')
    else:
        for field, errors in form.errors.items():
            flash(f"Erro em {getattr(form, field).label.text}: {', '.join(errors)}", 'danger')
            
    return redirect(url_for('admin.list_dietary_restrictions'))

# --- Multi-Tenancy System Clients Management (Super Admins Only) ---

@admin_bp.route('/tenants')
@login_required
def list_tenants():
    if not current_user.is_system_admin:
        flash('Acesso restrito a administradores do sistema.', 'danger')
        return redirect(url_for('main.index'))
        
    page = request.args.get('page', 1, type=int)
    tenants = Tenant.query.order_by(Tenant.name).paginate(page=page, per_page=30)
    return render_template('admin/tenants.html', tenants=tenants)

@admin_bp.route('/tenants/create', methods=['GET', 'POST'])
@login_required
def new_tenant():
    if not current_user.is_system_admin:
        flash('Acesso restrito a administradores do sistema.', 'danger')
        return redirect(url_for('main.index'))
        
    form = TenantForm()
    
    ufs = db.session.query(City.uf).distinct().order_by(City.uf).all()
    form.uf.choices = [('', 'Selecione a UF')] + [(u[0], u[0]) for u in ufs]
    
    selected_uf = request.form.get('uf')
    if selected_uf:
        cities = City.query.filter_by(uf=selected_uf).order_by(City.name).all()
        form.municipio.choices = [('', 'Selecione o Município')] + [(c.name, c.name) for c in cities]
    
    if form.validate_on_submit():
        # Check uniqueness globally
        existing = Tenant.query.filter_by(name=form.name.data.strip()).first()
        if existing:
            flash('Já existe um cliente cadastrado com este nome.', 'danger')
            return render_template('admin/tenant_form.html', form=form, title="Novo Cliente")
            
        tenant = Tenant(
            name=form.name.data.strip(),
            type=form.type.data,
            uf=form.uf.data if form.uf.data else None,
            municipio=form.municipio.data if form.municipio.data else None,
            map_url=form.map_url.data.strip() if form.map_url.data else None
        )
        db.session.add(tenant)
        db.session.commit()
        
        log_audit('CREATE', 'Tenant', tenant.id, f"Cliente {tenant.name} criado do tipo {tenant.type}")
        flash('Cliente criado com sucesso.', 'success')
        return redirect(url_for('admin.list_tenants'))
        
    return render_template('admin/tenant_form.html', form=form, title="Novo Cliente")

@admin_bp.route('/tenants/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_tenant(id):
    if not current_user.is_system_admin:
        flash('Acesso restrito a administradores do sistema.', 'danger')
        return redirect(url_for('main.index'))
        
    tenant = Tenant.query.get_or_404(id)
    form = TenantForm(obj=tenant)
    
    ufs = db.session.query(City.uf).distinct().order_by(City.uf).all()
    form.uf.choices = [('', 'Selecione a UF')] + [(u[0], u[0]) for u in ufs]
    
    selected_uf = request.form.get('uf') or tenant.uf
    if selected_uf:
        cities = City.query.filter_by(uf=selected_uf).order_by(City.name).all()
        form.municipio.choices = [('', 'Selecione o Município')] + [(c.name, c.name) for c in cities]
    
    if form.validate_on_submit():
        existing = Tenant.query.filter(Tenant.name == form.name.data.strip(), Tenant.id != id).first()
        if existing:
            flash('Já existe outro cliente com este nome.', 'danger')
            return render_template('admin/tenant_form.html', form=form, title="Editar Cliente", tenant=tenant)
            
        old_name = tenant.name
        tenant.name = form.name.data.strip()
        tenant.type = form.type.data
        tenant.uf = form.uf.data if form.uf.data else None
        tenant.municipio = form.municipio.data if form.municipio.data else None
        tenant.map_url = form.map_url.data.strip() if form.map_url.data else None
        db.session.commit()
        
        log_audit('UPDATE', 'Tenant', tenant.id, f"Cliente {old_name} atualizado para {tenant.name} (Tipo: {tenant.type})")
        flash('Cliente atualizado com sucesso.', 'success')
        return redirect(url_for('admin.list_tenants'))
        
    return render_template('admin/tenant_form.html', form=form, title="Editar Cliente", tenant=tenant)

@admin_bp.route('/tenants/<int:id>/delete', methods=['POST'])
@login_required
def delete_tenant(id):
    if not current_user.is_system_admin:
        flash('Acesso restrito a administradores do sistema.', 'danger')
        return redirect(url_for('main.index'))
        
    tenant = Tenant.query.get_or_404(id)
    
    # Importação local para evitar importações circulares e realizar checagem rigorosa
    from app.models import (
        User, ReferenceMatrix, SchoolYear, Subject, Theme, Descriptor,
        Question, Evaluation, Exam, AbsenceReason, TeachingUnit,
        CurriculumStructure, Class, Professor, Student, ImportJob
    )
    
    dependencies = []
    
    if User.query.filter_by(tenant_id=id).first():
        dependencies.append("Usuários")
    if ReferenceMatrix.query.filter_by(tenant_id=id).first():
        dependencies.append("Matrizes de Referência")
    if SchoolYear.query.filter_by(tenant_id=id).first():
        dependencies.append("Anos Letivos")
    if Subject.query.filter_by(tenant_id=id).first():
        dependencies.append("Disciplinas")
    if Theme.query.filter_by(tenant_id=id).first():
        dependencies.append("Temas")
    if Descriptor.query.filter_by(tenant_id=id).first():
        dependencies.append("Descritores/Habilidades")
    if Question.query.filter_by(tenant_id=id).first():
        dependencies.append("Questões")
    if Evaluation.query.filter_by(tenant_id=id).first():
        dependencies.append("Avaliações")
    if Exam.query.filter_by(tenant_id=id).first():
        dependencies.append("Exames")
    if AbsenceReason.query.filter_by(tenant_id=id).first():
        dependencies.append("Motivos de Ausência")
    if TeachingUnit.query.filter_by(tenant_id=id).first():
        dependencies.append("Unidades de Ensino/Escolas")
    if CurriculumStructure.query.filter_by(tenant_id=id).first():
        dependencies.append("Estruturas Curriculares")
    if Class.query.filter_by(tenant_id=id).first():
        dependencies.append("Turmas")
    if Professor.query.filter_by(tenant_id=id).first():
        dependencies.append("Professores")
    if DietaryRestriction.query.filter_by(tenant_id=id).first():
        dependencies.append("Restrições Alimentares")
    if Student.query.filter_by(tenant_id=id).first():
        dependencies.append("Estudantes")
    if ImportJob.query.filter_by(tenant_id=id).first():
        dependencies.append("Monitoramentos de Importação")
        
    if dependencies:
        dep_str = ", ".join(dependencies)
        flash(f'Erro: Não é possível excluir o cliente "{tenant.name}" pois ele possui registros dependentes em: {dep_str}.', 'danger')
        return redirect(url_for('admin.list_tenants'))
        
    tenant_name = tenant.name
    db.session.delete(tenant)
    db.session.commit()
    
    log_audit('DELETE', 'Tenant', id, f"Excluiu cliente {tenant_name}")
    flash('Cliente excluído com sucesso.', 'success_delete')
    return redirect(url_for('admin.list_tenants'))

@admin_bp.route('/tenants/<int:id>/authenticate', methods=['GET'])
@login_required
def authenticate_tenant(id):
    if not current_user.is_system_admin:
        abort(403)
        
    tenant = Tenant.query.get_or_404(id)
    session['active_tenant_id'] = tenant.id
    session['active_tenant_name'] = tenant.name
    
    flash(f'Autenticado com sucesso no cliente: {tenant.name}', 'success')
    return redirect(url_for('academic.academic_dashboard'))

@admin_bp.route('/tenants/deauthenticate', methods=['GET'])
@login_required
def deauthenticate_tenant():
    if not current_user.is_system_admin:
        abort(403)
        
    tenant_name = session.pop('active_tenant_name', 'Cliente')
    session.pop('active_tenant_id', None)
    
    flash(f'Conexão encerrada com: {tenant_name}', 'info')
    return redirect(url_for('admin.list_tenants'))

@admin_bp.route('/migrate-test-data', methods=['POST'])
@login_required
def migrate_test_data():
    if not current_user.is_system_admin:
        abort(403)
        
    def run_migration_job(app):
        from scripts.migrate_to_postgres import run_migration
        try:
            # Re-initialize within app context to allow DB ops
            run_migration()
        except Exception as e:
            app.logger.error(f"Erro na migração de teste: {e}")

    # Fire and forget thread
    thread = threading.Thread(
        target=run_migration_job,
        args=(current_app._get_current_object(),)
    )
    thread.start()
    
    flash('Migração de dados para o Neon PostgreSQL iniciada em segundo plano. Verifique os logs do servidor para acompanhar o progresso.', 'info')
    return redirect(url_for('admin.list_tenants'))

@admin_bp.route('/migrate-status')
@login_required
def migrate_status():
    if not current_user.is_system_admin:
        abort(403)
        
    from app.models import SystemConfig
    status = SystemConfig.get_value('migration_status', 'idle')
    percent = SystemConfig.get_value('migration_percent', '0')
    message = SystemConfig.get_value('migration_message', '')
    
    return jsonify({
        'status': status,
        'percent': int(percent) if percent.isdigit() else 0,
        'message': message
    })
