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
from werkzeug.utils import secure_filename

from app import db
from app.models import ReferenceMatrix, Descriptor, SchoolYear, Subject, Theme, ImportJob
from app.utils.tenancy import filter_by_tenant, get_tenant_id
from app.utils.timezone import get_brasilia_time
from app.audit_utils import log_audit
from app.import_utils import start_import_task, update_import_progress, finish_import_task, fail_import_task

matrices_bp = Blueprint('matrices', __name__)

# --- WTForms declarations for Matrices Blueprint ---

class ReferenceMatrixForm(FlaskForm):
    name = StringField('Nome da Matriz', validators=[DataRequired()])
    description = StringField('Descrição (opcional)')
    submit = SubmitField('Salvar')

class ThemeForm(FlaskForm):
    name = StringField('Nome do Tema/Tópico', validators=[DataRequired()])
    matrix_id = SelectField('Matriz de Referência', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Salvar')

class DescriptorForm(FlaskForm):
    type = SelectField('Tipo', choices=[('Descritor', 'Descritor'), ('Habilidade', 'Habilidade')], validators=[DataRequired()])
    code = StringField('Código (Ex: D1)', validators=[DataRequired()])
    description = StringField('Descrição', validators=[DataRequired()])
    matrix_id = SelectField('Matriz de Referência', coerce=int, validators=[DataRequired()])
    theme_id = SelectField('Tema/Tópico (Opcional para Habilidade)', coerce=int, default=0)
    school_year_id = SelectField('Ano Escolar', coerce=int, validators=[DataRequired()])
    subject_id = SelectField('Componente Curricular', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Salvar')

class ImportDescriptorForm(FlaskForm):
    file = FileField('Planilha de Descritores (.xlsx, .xls, .csv)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls', 'csv'], 'Apenas planilhas Excel ou arquivos CSV são permitidos!')
    ])
    submit = SubmitField('Importar')

# --- Reference Matrices CRUD ---

@matrices_bp.route('/', methods=['GET', 'POST'])
@login_required
def list_matrices():
    form = ReferenceMatrixForm()
    
    query = ReferenceMatrix.query
    query = filter_by_tenant(query, ReferenceMatrix)
    matrices = query.order_by(ReferenceMatrix.name).all()
    
    if form.validate_on_submit():
        matrix = ReferenceMatrix(
            name=form.name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            tenant_id=get_tenant_id()
        )
        db.session.add(matrix)
        db.session.commit()
        
        log_audit('CREATE', 'ReferenceMatrix', matrix.id, f"Criou matriz de referência {matrix.name}")
        flash('Matriz criada com sucesso!', 'success')
        return redirect(url_for('matrices.list_matrices'))
        
    return render_template('matrices/list.html', matrices=matrices, form=form)

@matrices_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_matrix(id):
    matrix = ReferenceMatrix.query.get_or_404(id)
    
    # Verify tenant boundary
    if matrix.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('matrices.list_matrices'))
        
    form = ReferenceMatrixForm(obj=matrix)
    if form.validate_on_submit():
        matrix.name = form.name.data.strip()
        matrix.description = form.description.data.strip() if form.description.data else None
        db.session.commit()
        
        log_audit('UPDATE', 'ReferenceMatrix', matrix.id, f"Atualizou matriz de referência {matrix.name}")
        flash('Matriz atualizada.', 'success')
        return redirect(url_for('matrices.list_matrices'))
        
    return render_template('matrices/edit.html', form=form, matrix=matrix)

# --- Themes Section ---

@matrices_bp.route('/themes', methods=['GET', 'POST'])
@login_required
def list_themes():
    form = ThemeForm()
    
    # Populate matrix choices inside active tenant scope
    form.matrix_id.choices = [(0, 'Selecione um item...')] + [(m.id, m.name) for m in ReferenceMatrix.query.filter_by(tenant_id=get_tenant_id()).order_by(ReferenceMatrix.name).all()]
    
    query = Theme.query
    query = filter_by_tenant(query, Theme)
    themes = query.order_by(Theme.name).all()
    
    if form.validate_on_submit():
        if form.matrix_id.data == 0:
            flash('Selecione uma Matriz válida.', 'danger')
        else:
            theme = Theme(
                name=form.name.data.strip(),
                matrix_id=form.matrix_id.data,
                tenant_id=get_tenant_id()
            )
            db.session.add(theme)
            db.session.commit()
            
            log_audit('CREATE', 'Theme', theme.id, f"Criou tema {theme.name}")
            flash('Tema criado com sucesso.', 'success')
            return redirect(url_for('matrices.list_themes'))
            
    return render_template('matrices/themes.html', themes=themes, form=form)

@matrices_bp.route('/themes/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_theme(id):
    theme = Theme.query.get_or_404(id)
    
    # Verify tenant boundary
    if theme.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('matrices.list_themes'))
        
    form = ThemeForm(obj=theme)
    form.matrix_id.choices = [(m.id, m.name) for m in ReferenceMatrix.query.filter_by(tenant_id=get_tenant_id()).order_by(ReferenceMatrix.name).all()]
    
    if form.validate_on_submit():
        theme.name = form.name.data.strip()
        theme.matrix_id = form.matrix_id.data
        db.session.commit()
        
        log_audit('UPDATE', 'Theme', theme.id, f"Atualizou tema {theme.name}")
        flash('Tema atualizado com sucesso.', 'success')
        return redirect(url_for('matrices.list_themes'))
        
    return render_template('matrices/theme_edit.html', form=form, theme=theme)

@matrices_bp.route('/themes/<int:id>/delete', methods=['POST'])
@login_required
def delete_theme(id):
    theme = Theme.query.get_or_404(id)
    
    # Verify tenant boundary
    if theme.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('matrices.list_themes'))
        
    # Check dependencies in Descriptor
    if Descriptor.query.filter_by(theme_id=id).first():
        flash(f'Erro: Não é possível excluir o tema "{theme.name}" pois existem descritores ou habilidades vinculados a ele.', 'danger')
        return redirect(url_for('matrices.list_themes'))
        
    name = theme.name
    db.session.delete(theme)
    db.session.commit()
    
    log_audit('DELETE', 'Theme', id, f"Excluiu tema {name}")
    flash('Tema excluído com sucesso.', 'success_delete')
    return redirect(url_for('matrices.list_themes'))

@matrices_bp.route('/api/themes/by-matrix/<int:matrix_id>')
@login_required
def api_themes_by_matrix(matrix_id):
    # API loaded via JS strictly isolated by active tenant
    themes = Theme.query.filter_by(tenant_id=get_tenant_id(), matrix_id=matrix_id).order_by(Theme.name).all()
    return jsonify([{'id': t.id, 'name': t.name} for t in themes])

# --- Descriptors & Habilidades CRUD Section ---

@matrices_bp.route('/descriptors', methods=['GET', 'POST'])
@login_required
def list_descriptors():
    matrix_id = request.args.get('matrix_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    school_year_id = request.args.get('school_year_id', type=int)
    
    query = Descriptor.query
    query = filter_by_tenant(query, Descriptor)
    
    if matrix_id:
        query = query.filter_by(matrix_id=matrix_id)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if school_year_id:
        query = query.filter_by(school_year_id=school_year_id)
        
    page = request.args.get('page', 1, type=int)
    pagination = query.order_by(Descriptor.code).paginate(page=page, per_page=30)
    descriptors = pagination.items
    
    form = DescriptorForm()
    # Populate dropdown choices inside tenant boundary
    form.matrix_id.choices = [(0, 'Selecione um item...')] + [(m.id, m.name) for m in ReferenceMatrix.query.filter_by(tenant_id=get_tenant_id()).order_by(ReferenceMatrix.name).all()]
    form.school_year_id.choices = [(0, 'Selecione um item...')] + [(y.id, y.name) for y in SchoolYear.query.filter_by(tenant_id=get_tenant_id()).order_by(SchoolYear.name).all()]
    form.subject_id.choices = [(0, 'Selecione um item...')] + [(s.id, s.name) for s in Subject.query.filter_by(tenant_id=get_tenant_id()).order_by(Subject.name).all()]
    form.theme_id.choices = [(0, 'Selecione um item...')]
    
    import_form = ImportDescriptorForm()
    
    if matrix_id:
        form.matrix_id.data = matrix_id
        
    active_job = ImportJob.query.filter_by(
        tenant_id=get_tenant_id(),
        import_type='Descriptors',
        status='running'
    ).first()
    
    matrices = ReferenceMatrix.query.filter_by(tenant_id=get_tenant_id()).order_by(ReferenceMatrix.name).all()
    
    if form.validate_on_submit() and not import_form.submit.data:
        # Theme conditional validation
        if form.type.data == 'Descritor' and (not form.theme_id.data or form.theme_id.data == 0):
            flash('O campo Tema é obrigatório para Descritores.', 'danger')
            return redirect(url_for('matrices.list_descriptors', matrix_id=matrix_id))
            
        descriptor = Descriptor(
            type=form.type.data,
            code=form.code.data.strip(),
            description=form.description.data.strip(),
            matrix_id=form.matrix_id.data,
            school_year_id=form.school_year_id.data,
            subject_id=form.subject_id.data,
            theme_id=form.theme_id.data if (form.type.data == 'Descritor' and form.theme_id.data != 0) else None,
            tenant_id=get_tenant_id(),
            is_active=True
        )
        db.session.add(descriptor)
        db.session.commit()
        
        log_audit('CREATE', 'Descriptor', descriptor.id, f"Criou descritor/habilidade {descriptor.code}")
        flash('Item criado com sucesso.', 'success')
        return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
        
    subjects = filter_by_tenant(Subject.query, Subject).order_by(Subject.name).all()
    years = filter_by_tenant(SchoolYear.query, SchoolYear).order_by(SchoolYear.name).all()
    
    return render_template(
        'matrices/descriptors.html',
        descriptors=descriptors,
        pagination=pagination,
        matrices=matrices,
        current_matrix_id=matrix_id,
        form=form,
        import_form=import_form,
        active_job=active_job,
        subjects=subjects,
        years=years,
        current_subject_id=subject_id,
        current_year_id=school_year_id
    )

@matrices_bp.route('/descriptors/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_descriptor(id):
    descriptor = Descriptor.query.get_or_404(id)
    
    if descriptor.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('matrices.list_descriptors'))
        
    form = DescriptorForm(obj=descriptor)
    form.matrix_id.choices = [(m.id, m.name) for m in ReferenceMatrix.query.filter_by(tenant_id=get_tenant_id()).order_by(ReferenceMatrix.name).all()]
    form.school_year_id.choices = [(y.id, y.name) for y in SchoolYear.query.filter_by(tenant_id=get_tenant_id()).order_by(SchoolYear.name).all()]
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.filter_by(tenant_id=get_tenant_id()).order_by(Subject.name).all()]
    
    # Populate theme choices for matrix scope
    if descriptor.matrix_id:
        form.theme_id.choices = [(t.id, t.name) for t in Theme.query.filter_by(tenant_id=get_tenant_id(), matrix_id=descriptor.matrix_id).order_by(Theme.name).all()]
    else:
        form.theme_id.choices = [(0, 'Selecione um item...')]
        
    if form.validate_on_submit():
        if form.type.data == 'Descritor' and (not form.theme_id.data or form.theme_id.data == 0):
            flash('O campo Tema é obrigatório para Descritores.', 'danger')
        else:
            descriptor.type = form.type.data
            descriptor.code = form.code.data.strip()
            descriptor.description = form.description.data.strip()
            descriptor.school_year_id = form.school_year_id.data
            descriptor.subject_id = form.subject_id.data
            descriptor.matrix_id = form.matrix_id.data
            descriptor.theme_id = form.theme_id.data if (form.type.data == 'Descritor' and form.theme_id.data != 0) else None
            
            db.session.commit()
            log_audit('UPDATE', 'Descriptor', descriptor.id, f"Atualizou descritor/habilidade {descriptor.code}")
            flash('Item atualizado.', 'success')
            return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))
            
    if request.method == 'GET':
        form.theme_id.data = descriptor.theme_id if descriptor.theme_id else 0
        
    return render_template('matrices/descriptor_edit.html', form=form, descriptor=descriptor)

@matrices_bp.route('/descriptors/<int:id>/delete', methods=['POST'])
@login_required
def delete_descriptor(id):
    descriptor = Descriptor.query.get_or_404(id)
    
    if descriptor.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('matrices.list_descriptors'))
        
    matrix_id = descriptor.matrix_id
    code = descriptor.code
    db.session.delete(descriptor)
    db.session.commit()
    
    log_audit('DELETE', 'Descriptor', id, f"Excluiu descritor/habilidade {code}")
    flash('Excluído com sucesso.', 'success_delete')
    return redirect(url_for('matrices.list_descriptors', matrix_id=matrix_id))

@matrices_bp.route('/descriptors/<int:id>/toggle-active', methods=['POST'])
@login_required
def toggle_descriptor_active(id):
    descriptor = Descriptor.query.get_or_404(id)
    
    if descriptor.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('matrices.list_descriptors'))
        
    descriptor.is_active = not descriptor.is_active
    db.session.commit()
    
    status = "ativado" if descriptor.is_active else "desativado"
    log_audit('UPDATE', 'Descriptor', descriptor.id, f"Alterou status do descritor {descriptor.code} para {'Ativo' if descriptor.is_active else 'Inativo'}")
    flash(f"Descritor {descriptor.code} {status} com sucesso.", "success")
    return redirect(url_for('matrices.list_descriptors', matrix_id=descriptor.matrix_id))

# --- Descriptors Excel Import Background Thread ---

def _process_descriptors_import(app, job_id, filepath, task_id=None):
    with app.app_context():
        job = ImportJob.query.get(job_id)
        if not job: return
        
        try:
            job.status = 'running'
            job.started_at = get_brasilia_time()
            db.session.commit()
            
            # Auto-detect file format
            if filepath.endswith('.csv'):
                df = pd.read_csv(filepath, sep=';', encoding='utf-8', dtype=str)
            else:
                df = pd.read_excel(filepath, dtype=str)
                
            total = len(df)
            job.total_rows = total
            db.session.commit()
            
            if task_id:
                start_import_task(total, task_id=task_id)
                
            success_count = 0
            errors = []
            
            # Pre-load lookups inside active tenant boundaries (Name -> ID)
            matrices = {m.name.strip().lower(): m.id for m in ReferenceMatrix.query.filter_by(tenant_id=job.tenant_id).all()}
            themes = {(t.name.strip().lower(), t.matrix_id): t.id for t in Theme.query.filter_by(tenant_id=job.tenant_id).all()}
            years = {y.name.strip().lower(): y.id for y in SchoolYear.query.filter_by(tenant_id=job.tenant_id).all()}
            subjects = {s.name.strip().lower(): s.id for s in Subject.query.filter_by(tenant_id=job.tenant_id).all()}
            existing_codes = {d.code.strip().lower() for d in Descriptor.query.filter_by(tenant_id=job.tenant_id).all()}
            
            for index, row in df.iterrows():
                mat_name = str(row.get('Matriz de Referência', '')).strip()
                theme_name = str(row.get('Tema', '')).strip()
                year_name = str(row.get('Ano Escolar', '')).strip()
                subject_name = str(row.get('Disciplina', '')).strip()
                # Fallback to 'Componente' if 'Disciplina' is missing
                if not subject_name or subject_name.lower() == 'nan':
                    subject_name = str(row.get('Componente', '')).strip()
                    
                code = str(row.get('Código', '')).strip()
                desc_text = str(row.get('Descrição', '')).strip()
                dtype = str(row.get('Tipo', 'Descritor')).strip()
                
                if not code or code.lower() == 'nan':
                    errors.append(f"Linha {index+2}: Código do item não informado.")
                    job.processed_rows += 1
                    continue
                    
                if not desc_text or desc_text.lower() == 'nan':
                    errors.append(f"Linha {index+2}: Descrição não informada.")
                    job.processed_rows += 1
                    continue
                    
                code_lower = code.lower()
                if code_lower in existing_codes:
                    errors.append(f"Linha {index+2}: Código '{code}' já existe.")
                    job.processed_rows += 1
                    continue
                    
                mat_lower = mat_name.lower()
                if mat_lower not in matrices:
                    errors.append(f"Linha {index+2}: Matriz '{mat_name}' não encontrada.")
                    job.processed_rows += 1
                    continue
                matrix_id = matrices[mat_lower]
                
                year_lower = year_name.lower()
                if year_lower not in years:
                    errors.append(f"Linha {index+2}: Ano Escolar '{year_name}' não encontrado.")
                    job.processed_rows += 1
                    continue
                year_id = years[year_lower]
                
                sub_lower = subject_name.lower()
                if sub_lower not in subjects:
                    errors.append(f"Linha {index+2}: Componente Curricular '{subject_name}' não encontrado.")
                    job.processed_rows += 1
                    continue
                subject_id = subjects[sub_lower]
                
                theme_id = None
                if dtype == 'Descritor':
                    if not theme_name or theme_name.lower() == 'nan':
                        errors.append(f"Linha {index+2}: Tema é obrigatório para Descritor.")
                        job.processed_rows += 1
                        continue
                    theme_lower = theme_name.lower()
                    if (theme_lower, matrix_id) in themes:
                        theme_id = themes[(theme_lower, matrix_id)]
                    else:
                        # Auto-create Theme under tenant boundary
                        new_theme = Theme(
                            name=theme_name,
                            matrix_id=matrix_id,
                            tenant_id=job.tenant_id
                        )
                        db.session.add(new_theme)
                        db.session.flush()
                        themes[(theme_lower, matrix_id)] = new_theme.id
                        theme_id = new_theme.id
                        
                descriptor = Descriptor(
                    type=dtype,
                    code=code,
                    description=desc_text,
                    matrix_id=matrix_id,
                    theme_id=theme_id,
                    school_year_id=year_id,
                    subject_id=subject_id,
                    tenant_id=job.tenant_id,
                    is_active=True
                )
                
                db.session.add(descriptor)
                existing_codes.add(code_lower)
                success_count += 1
                job.processed_rows += 1
                
                if task_id and index % 10 == 0:
                    update_import_progress(task_id, job.processed_rows, message=f"Importando descritor: {code}")
                    
                # OTIMIZAÇÃO: Inserção em lote a cada 100 registros
                if success_count % 100 == 0:
                    job.errors = json.dumps(errors)
                    db.session.commit()
                    
            job.status = 'completed'
            job.finished_at = get_brasilia_time()
            job.errors = json.dumps(errors)
            db.session.commit()
            
            if task_id:
                finish_import_task(task_id, message=f"Importação de descritores concluída. {success_count} registros importados.", log_file=None)
                
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

@matrices_bp.route('/descriptors/import', methods=['POST'])
@login_required
def import_descriptors():
    if ImportJob.is_any_running():
        flash('Não é possível realizar importações enquanto houver outra em andamento. Por favor, aguarde a conclusão.', 'warning')
        return redirect(url_for('matrices.list_descriptors'))
        
    form = ImportDescriptorForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        task_id = request.form.get('X-Progress-ID')
        
        uploads_dir = os.path.join(current_app.root_path, '..', 'instance', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        filepath = os.path.join(uploads_dir, filename)
        file.save(filepath)
        
        job = ImportJob(
            user_id=current_user.id,
            import_type='Descriptors',
            filename=filename,
            status='pending',
            tenant_id=get_tenant_id()
        )
        db.session.add(job)
        db.session.commit()
        
        thread = threading.Thread(
            target=_process_descriptors_import,
            args=(current_app._get_current_object(), job.id, filepath, task_id)
        )
        thread.start()
        
        flash('A importação de descritores foi iniciada em segundo plano.', 'info')
    else:
        for field, errors in form.errors.items():
            flash(f"Erro no campo {field}: {', '.join(errors)}", 'danger')
            
    return redirect(url_for('matrices.list_descriptors'))
