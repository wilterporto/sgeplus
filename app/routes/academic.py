import os
import json
import threading
import pandas as pd
import io
from datetime import datetime
from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, session, abort, current_app, send_file
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, SelectField, SelectMultipleField, SubmitField
from wtforms.validators import DataRequired, Optional, Length
from werkzeug.utils import secure_filename
from sqlalchemy import func
from markupsafe import Markup

from app import db
from app.models import TeachingUnit, SchoolYear, Subject, CurriculumStructure, Class, Enrollment, Evaluation, ImportJob, Student, Professor, TeachingAssignment, AbsenceReason, StudentResult, City, QuilombolaCommunity, IndigenousPeople
from app.utils.tenancy import filter_by_tenant, get_tenant_id
from app.utils.timezone import get_brasilia_time
from app.audit_utils import log_audit
from app.import_utils import start_import_task, update_import_progress, finish_import_task, fail_import_task
from app.forms import QuilombolaCommunityForm, IndigenousPeopleForm, ImportDefinitionForm

academic_bp = Blueprint('academic', __name__)

# --- WTForms declarations for Academic Blueprint ---

class TeachingUnitForm(FlaskForm):
    name = StringField('Nome da Unidade', validators=[DataRequired()])
    type = SelectField('Tipo', choices=[('Regional', 'Regional'), ('Escola', 'Escola')], validators=[DataRequired()])
    parent_id = SelectField('Regional Superior (Opcional)', coerce=int, default=0)
    inep_code = StringField('Código INEP', validators=[Optional(), Length(max=20)])
    uf = SelectField('UF', choices=[('', 'Selecione a UF')], validators=[Optional()])
    municipio = SelectField('Município', choices=[('', 'Selecione o Município')], validators=[Optional()])
    residential_zone = SelectField('Localização', choices=[
        ('', 'Selecione...'),
        ('Urbana', 'Urbana'),
        ('Rural', 'Rural')
    ], validators=[Optional()])
    differentiated_location = SelectField('Localização Diferenciada', choices=[
        ('Não está em área de localização diferenciada', 'Não está em área de localização diferenciada'),
        ('Área de assentamento', 'Área de assentamento'),
        ('Terra indígena', 'Terra indígena'),
        ('Comunidade quilombola', 'Comunidade quilombola'),
        ('Área onde se localizam povos e comunidades tradicionais', 'Área onde se localizam povos e comunidades tradicionais')
    ], default='Não está em área de localização diferenciada', validators=[Optional()])
    latitude = StringField('Latitude', validators=[Optional(), Length(max=50)])
    longitude = StringField('Longitude', validators=[Optional(), Length(max=50)])
    submit = SubmitField('Salvar')

class ImportUnitForm(FlaskForm):
    file = FileField('Planilha de Unidades (.xlsx, .xls)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls'], 'Apenas planilhas Excel são permitidas!')
    ])
    submit = SubmitField('Importar')

class SchoolYearForm(FlaskForm):
    name = StringField('Ano de Escolaridade (Ex: 9º Ano)', validators=[DataRequired()])
    submit = SubmitField('Salvar')

class SubjectForm(FlaskForm):
    name = StringField('Nome do Componente Curricular', validators=[DataRequired()])
    submit = SubmitField('Salvar')

class CurriculumForm(FlaskForm):
    name = StringField('Nome da Estrutura Curricular', validators=[DataRequired()])
    school_year_id = SelectField('Ano Escolar', coerce=int, validators=[DataRequired()])
    subjects = SelectMultipleField('Componentes Curriculares', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Salvar')

class ClassForm(FlaskForm):
    name = StringField('Nome da Turma', validators=[DataRequired()])
    shift = SelectField('Turno', choices=[('Matutino', 'Matutino'), ('Vespertino', 'Vespertino'), ('Noturno', 'Noturno'), ('Integral', 'Integral')], validators=[DataRequired()])
    school_year_id = SelectField('Ano Escolar', coerce=int, validators=[DataRequired()])
    structure_id = SelectField('Estrutura Curricular', coerce=int, validators=[DataRequired()])
    teaching_unit_id = SelectField('Unidade Escolar', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Salvar')

class ImportClassForm(FlaskForm):
    file = FileField('Planilha de Turmas (.xlsx, .xls)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls'], 'Apenas planilhas Excel são permitidas!')
    ])
    submit = SubmitField('Importar')

class EvaluationForm(FlaskForm):
    name = StringField('Nome da Avaliação', validators=[DataRequired()])
    type = SelectField('Tipo', choices=[('Diagnóstica', 'Diagnóstica'), ('Formativa', 'Formativa'), ('Somativa', 'Somativa')], validators=[DataRequired()])
    logo = FileField('Logomarca (opcional)', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'svg'], 'Apenas imagens são permitidas!')])
    multiple_components = SelectField('Múltiplos Componentes', choices=[('0', 'Não'), ('1', 'Sim')], default='0')
    submit = SubmitField('Salvar')

class AbsenceReasonForm(FlaskForm):
    name = StringField(Markup('Nome <span class="text-danger">*</span>'), validators=[DataRequired(message="O campo Nome é obrigatório.")])
    submit = SubmitField('Salvar')

# --- Teaching Units Section ---

@academic_bp.route('/units', methods=['GET', 'POST'])
@login_required
def list_units():
    form = TeachingUnitForm()
    import_form = ImportUnitForm()
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    # Exclude parent_id self choice during save inside form populating
    reg_choices = [(0, 'Nenhuma')]
    regionals = TeachingUnit.query.filter_by(type='Regional')
    regionals = filter_by_tenant(regionals, TeachingUnit).order_by(TeachingUnit.name).all()
    reg_choices.extend([(r.id, r.name) for r in regionals])
    form.parent_id.choices = reg_choices
    
    ufs = db.session.query(City.uf).distinct().order_by(City.uf).all()
    form.uf.choices = [('', 'Selecione a UF')] + [(u[0], u[0]) for u in ufs]
    if form.uf.data:
        cities = City.query.filter_by(uf=form.uf.data).order_by(City.name).all()
        form.municipio.choices = [('', 'Selecione o Município')] + [(c.name, c.name) for c in cities]
    
    query = TeachingUnit.query
    query = filter_by_tenant(query, TeachingUnit)
    
    if search:
        query = query.filter(TeachingUnit.name.ilike(f'%{search}%'))
        
    units = query.order_by(TeachingUnit.name).paginate(page=page, per_page=30)
    
    active_job = ImportJob.query.filter_by(
        tenant_id=get_tenant_id(),
        import_type='Units',
        status='running'
    ).first()
    
    if form.validate_on_submit() and not import_form.submit.data:
        unit = TeachingUnit(
            name=form.name.data.strip(),
            type=form.type.data,
            tenant_id=get_tenant_id(),
            inep_code=form.inep_code.data.strip() if form.inep_code.data else None,
            uf=form.uf.data if form.uf.data else None,
            municipio=form.municipio.data if form.municipio.data else None,
            residential_zone=form.residential_zone.data if form.residential_zone.data else None,
            differentiated_location=form.differentiated_location.data if form.differentiated_location.data else None,
            latitude=form.latitude.data.strip() if form.latitude.data else None,
            longitude=form.longitude.data.strip() if form.longitude.data else None
        )
        if form.parent_id.data != 0:
            unit.parent_id = form.parent_id.data
            
        db.session.add(unit)
        db.session.commit()
        
        log_audit('CREATE', 'TeachingUnit', unit.id, f"Criou unidade de ensino {unit.name}")
        flash('Unidade de ensino cadastrada com sucesso.', 'success')
        return redirect(url_for('academic.list_units'))
        
    return render_template('academic/units.html', units=units, form=form, import_form=import_form, search=search, active_job=active_job)

@academic_bp.route('/units/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_unit(id):
    unit = TeachingUnit.query.get_or_404(id)
    
    # Verify tenant boundary
    if unit.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_units'))
        
    form = TeachingUnitForm(obj=unit)
    
    reg_choices = [(0, 'Nenhuma')]
    regionals = TeachingUnit.query.filter_by(type='Regional')
    regionals = filter_by_tenant(regionals, TeachingUnit).order_by(TeachingUnit.name).all()
    # Exclude self regional
    if unit.type == 'Regional':
        regionals = [r for r in regionals if r.id != unit.id]
    reg_choices.extend([(r.id, r.name) for r in regionals])
    form.parent_id.choices = reg_choices
    
    ufs = db.session.query(City.uf).distinct().order_by(City.uf).all()
    form.uf.choices = [('', 'Selecione a UF')] + [(u[0], u[0]) for u in ufs]
    
    # Preenche as cidades com base no UF submetido ou no banco
    current_uf = form.uf.data if form.is_submitted() else unit.uf
    if current_uf:
        cities = City.query.filter_by(uf=current_uf).order_by(City.name).all()
        form.municipio.choices = [('', 'Selecione o Município')] + [(c.name, c.name) for c in cities]
    
    if form.validate_on_submit():
        unit.name = form.name.data.strip()
        unit.type = form.type.data
        if form.parent_id.data != 0:
            unit.parent_id = form.parent_id.data
        else:
            unit.parent_id = None
            
        unit.inep_code = form.inep_code.data.strip() if form.inep_code.data else None
        unit.uf = form.uf.data if form.uf.data else None
        unit.municipio = form.municipio.data if form.municipio.data else None
        unit.residential_zone = form.residential_zone.data if form.residential_zone.data else None
        unit.differentiated_location = form.differentiated_location.data if form.differentiated_location.data else None
        unit.latitude = form.latitude.data.strip() if form.latitude.data else None
        unit.longitude = form.longitude.data.strip() if form.longitude.data else None
        
        db.session.commit()
        log_audit('UPDATE', 'TeachingUnit', unit.id, f"Atualizou unidade de ensino {unit.name}")
        flash('Unidade de ensino atualizada com sucesso.', 'success')
        return redirect(url_for('academic.list_units'))
        
    if request.method == 'GET':
        form.parent_id.data = unit.parent_id if unit.parent_id else 0
        
    return render_template('academic/unit_edit.html', form=form, unit=unit)

@academic_bp.route('/units/<int:id>/delete', methods=['POST'])
@login_required
def delete_unit(id):
    unit = TeachingUnit.query.get_or_404(id)
    
    # Verify tenant boundary
    if unit.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_units'))
        
    # Check associations
    if unit.classes.count() > 0:
        flash(f'Erro: Não é possível excluir a unidade "{unit.name}" pois existem turmas vinculadas a ela.', 'danger')
        return redirect(url_for('academic.list_units'))
        
    name = unit.name
    db.session.delete(unit)
    db.session.commit()
    
    log_audit('DELETE', 'TeachingUnit', id, f"Excluiu unidade de ensino {name}")
    flash('Unidade de ensino excluída com sucesso.', 'success_delete')
    return redirect(url_for('academic.list_units'))

# --- Units Import Background Thread ---

def _process_units_import(app, job_id, filepath, task_id=None):
    with app.app_context():
        job = ImportJob.query.get(job_id)
        if not job: return
        
        try:
            job.status = 'running'
            job.started_at = get_brasilia_time()
            db.session.commit()
            
            df = pd.read_excel(filepath)
            df.columns = df.columns.str.lower().str.strip()
            
            # Garantir que Regionais sejam importadas primeiro
            if 'tipo' in df.columns:
                df['is_regional'] = df['tipo'].astype(str).str.strip().str.lower() == 'regional'
                df = df.sort_values(by='is_regional', ascending=False)
            
            total = len(df)
            job.total_rows = total
            db.session.commit()
            
            if task_id:
                start_import_task(total, task_id=task_id)
                
            success_count = 0
            errors = []
            
            existing_units_by_inep = {}
            existing_units_by_name = {}
            regionals_by_name = {}
            
            for u in TeachingUnit.query.filter_by(tenant_id=job.tenant_id).all():
                if u.inep_code:
                    existing_units_by_inep[u.inep_code] = u
                existing_units_by_name[u.name.strip().lower()] = u
                if u.type == 'Regional':
                    regionals_by_name[u.name.strip().lower()] = u
            
            for index, row in df.iterrows():
                name = str(row.get('nome', '')).strip()
                utype = str(row.get('tipo', '')).strip()
                parent_name = str(row.get('regional superior', '')).strip()
                
                if not name or name.lower() == 'nan':
                    errors.append(f"Linha {index+2}: Nome da unidade não informado.")
                    job.processed_rows += 1
                    continue
                    
                if utype not in ['Regional', 'Escola']:
                    errors.append(f"Linha {index+2}: Tipo inválido '{utype}'. Deve ser 'Regional' ou 'Escola'.")
                    job.processed_rows += 1
                    continue
                    
                inep_code = str(row.get('código inep', '')).strip()
                if inep_code.lower() == 'nan' or not inep_code:
                    inep_code = None
                
                name_lower = name.lower()
                
                unit = None
                if inep_code and inep_code in existing_units_by_inep:
                    unit = existing_units_by_inep[inep_code]
                elif name_lower in existing_units_by_name:
                    unit = existing_units_by_name[name_lower]
                
                uf = str(row.get('uf', '')).strip()
                if uf.lower() == 'nan' or not uf: uf = None
                
                municipio = str(row.get('município', '')).strip()
                if municipio.lower() == 'nan' or not municipio: municipio = None
                
                residential_zone = str(row.get('localização', '')).strip()
                if residential_zone.lower() == 'nan' or not residential_zone: residential_zone = None
                
                differentiated_location = str(row.get('localização diferenciada', '')).strip()
                if differentiated_location.lower() == 'nan' or not differentiated_location: differentiated_location = None
                
                latitude = str(row.get('latitude', '')).strip()
                if latitude.lower() == 'nan' or not latitude: latitude = None
                
                longitude = str(row.get('longitude', '')).strip()
                if longitude.lower() == 'nan' or not longitude: longitude = None

                is_new = False
                if not unit:
                    unit = TeachingUnit(tenant_id=job.tenant_id)
                    is_new = True
                
                unit.name = name
                unit.type = utype
                unit.inep_code = inep_code
                unit.uf = uf
                unit.municipio = municipio
                unit.residential_zone = residential_zone
                unit.differentiated_location = differentiated_location
                unit.latitude = latitude
                unit.longitude = longitude
                
                if parent_name and parent_name.lower() != 'nan':
                    parent_lower = parent_name.lower()
                    if parent_lower in regionals_by_name:
                        unit.parent_id = regionals_by_name[parent_lower].id
                    else:
                        errors.append(f"Linha {index+2}: Regional Superior '{parent_name}' não encontrada.")
                        if is_new:
                            job.processed_rows += 1
                            continue
                
                if is_new:
                    db.session.add(unit)
                
                # Atualizar os caches em memória para referências subsequentes (ex: uma escola aponta para a regional recém criada na mesma planilha)
                if inep_code: existing_units_by_inep[inep_code] = unit
                existing_units_by_name[name_lower] = unit
                if utype == 'Regional':
                    regionals_by_name[name_lower] = unit
                    
                success_count += 1
                job.processed_rows += 1
                
                if task_id and index % 10 == 0:
                    update_import_progress(task_id, job.processed_rows, message=f"Processando unidade: {name}")
                    
                if success_count % 100 == 0:
                    job.errors = json.dumps(errors)
                    db.session.commit()
                    
            job.status = 'completed'
            job.finished_at = get_brasilia_time()
            job.errors = json.dumps(errors)
            db.session.commit()
            
            if task_id:
                finish_import_task(task_id, message=f"Importação de unidades concluída. {success_count} registros importados.", log_file=None)
                
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

@academic_bp.route('/units/import', methods=['POST'])
@login_required
def import_units():
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))
        
    if ImportJob.is_any_running():
        flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
        return redirect(url_for('academic.list_units'))
        
    form = ImportUnitForm()
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
            import_type='Units',
            filename=filename,
            status='pending',
            tenant_id=get_tenant_id()
        )
        db.session.add(job)
        db.session.commit()
        
        thread = threading.Thread(
            target=_process_units_import,
            args=(current_app._get_current_object(), job.id, filepath, task_id)
        )
        thread.start()
        
        flash('A importação de unidades de ensino foi iniciada em segundo plano.', 'info')
    else:
        for field, errors in form.errors.items():
            flash(f"Erro em {getattr(form, field).label.text}: {', '.join(errors)}", 'danger')
            
    return redirect(url_for('academic.list_units'))

@academic_bp.route('/units/template/download')
@login_required
def download_units_template():
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))
        
    columns = [
        "Nome", "Tipo", "Regional Superior", "Código INEP", "UF", 
        "Município", "Localização", "Localização Diferenciada", 
        "Latitude", "Longitude"
    ]
    df = pd.DataFrame(columns=columns)
    
    # Adicionar uma linha de exemplo
    df.loc[0] = [
        "Escola Estadual Exemplo", "Escola", "Regional de Ensino X", 
        "12345678", "TO", "Palmas", "Urbana", 
        "Não está em área de localização diferenciada", "-10.1833", "-48.3333"
    ]
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Unidades')
            
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='layout_unidades.xlsx'
    )

# --- Definitions Section (School Years & Subjects Curriculum Components) ---

@academic_bp.route('/definitions', methods=['GET', 'POST'])
@login_required
def definitions():
    year_form = SchoolYearForm(prefix='year')
    subject_form = SubjectForm(prefix='subject')
    quilombola_form = QuilombolaCommunityForm(prefix='quilombola')
    indigenous_form = IndigenousPeopleForm(prefix='indigenous')
    
    if year_form.validate_on_submit() and year_form.submit.data:
        existing = SchoolYear.query.filter_by(name=year_form.name.data.strip(), tenant_id=get_tenant_id()).first()
        if existing:
            flash('Este ano escolar já está cadastrado.', 'danger')
        else:
            sy = SchoolYear(name=year_form.name.data.strip(), tenant_id=get_tenant_id())
            db.session.add(sy)
            db.session.commit()
            log_audit('CREATE', 'SchoolYear', sy.id, f"Criou ano escolar {sy.name}")
            flash('Ano escolar adicionado com sucesso.', 'success')
        return redirect(url_for('academic.definitions'))
        
    if subject_form.validate_on_submit() and subject_form.submit.data:
        existing = Subject.query.filter_by(name=subject_form.name.data.strip(), tenant_id=get_tenant_id()).first()
        if existing:
            flash('Este componente curricular já está cadastrado.', 'danger')
        else:
            sb = Subject(name=subject_form.name.data.strip(), tenant_id=get_tenant_id())
            db.session.add(sb)
            db.session.commit()
            log_audit('CREATE', 'Subject', sb.id, f"Criou componente curricular {sb.name}")
            flash('Componente curricular adicionado com sucesso.', 'success')
        return redirect(url_for('academic.definitions'))
        
    if quilombola_form.validate_on_submit() and quilombola_form.submit.data:
        existing = QuilombolaCommunity.query.filter_by(name=quilombola_form.name.data.strip(), tenant_id=get_tenant_id()).first()
        if existing:
            flash('Esta comunidade quilombola já está cadastrada.', 'danger')
        else:
            qc = QuilombolaCommunity(name=quilombola_form.name.data.strip(), tenant_id=get_tenant_id())
            db.session.add(qc)
            db.session.commit()
            log_audit('CREATE', 'QuilombolaCommunity', qc.id, f"Criou comunidade quilombola {qc.name}")
            flash('Comunidade quilombola adicionada com sucesso.', 'success')
        return redirect(url_for('academic.definitions'))
        
    if indigenous_form.validate_on_submit() and indigenous_form.submit.data:
        existing = IndigenousPeople.query.filter_by(name=indigenous_form.name.data.strip(), tenant_id=get_tenant_id()).first()
        if existing:
            flash('Este povo indígena já está cadastrado.', 'danger')
        else:
            ip = IndigenousPeople(name=indigenous_form.name.data.strip(), tenant_id=get_tenant_id())
            db.session.add(ip)
            db.session.commit()
            log_audit('CREATE', 'IndigenousPeople', ip.id, f"Criou povo indígena {ip.name}")
            flash('Povo indígena adicionado com sucesso.', 'success')
        return redirect(url_for('academic.definitions'))
        
    years = filter_by_tenant(SchoolYear.query, SchoolYear).order_by(SchoolYear.name).all()
    subjects = filter_by_tenant(Subject.query, Subject).order_by(Subject.name).all()
    quilombola_communities = filter_by_tenant(QuilombolaCommunity.query, QuilombolaCommunity).order_by(QuilombolaCommunity.name).all()
    indigenous_peoples = filter_by_tenant(IndigenousPeople.query, IndigenousPeople).order_by(IndigenousPeople.name).all()
    
    import_quilombola_form = ImportDefinitionForm()
    import_indigenous_form = ImportDefinitionForm()
    
    active_quilombola_job = ImportJob.query.filter_by(
        tenant_id=get_tenant_id(),
        import_type='Quilombola',
        status='running'
    ).first()
    
    active_indigenous_job = ImportJob.query.filter_by(
        tenant_id=get_tenant_id(),
        import_type='Indigenous',
        status='running'
    ).first()
    
    return render_template('academic/definitions.html', 
        years=years, 
        subjects=subjects, 
        quilombola_communities=quilombola_communities,
        indigenous_peoples=indigenous_peoples,
        year_form=year_form, 
        subject_form=subject_form,
        quilombola_form=quilombola_form,
        indigenous_form=indigenous_form,
        import_quilombola_form=import_quilombola_form,
        import_indigenous_form=import_indigenous_form,
        active_quilombola_job=active_quilombola_job,
        active_indigenous_job=active_indigenous_job
    )

@academic_bp.route('/quilombola/<int:id>/delete', methods=['POST'])
@login_required
def delete_quilombola(id):
    qc = QuilombolaCommunity.query.get_or_404(id)
    if qc.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.definitions'))
        
    # Check for constraints
    students = Student.query.filter_by(quilombola_community_id=qc.id).first()
    if students:
        flash('Não é possível excluir a comunidade quilombola, pois existem alunos vinculados a ela.', 'danger')
        return redirect(url_for('academic.definitions'))
        
    db.session.delete(qc)
    db.session.commit()
    log_audit('DELETE', 'QuilombolaCommunity', id, f"Deletou comunidade quilombola {qc.name}")
    flash('Comunidade quilombola excluída com sucesso.', 'success')
    return redirect(url_for('academic.definitions'))

@academic_bp.route('/indigenous/<int:id>/delete', methods=['POST'])
@login_required
def delete_indigenous(id):
    ip = IndigenousPeople.query.get_or_404(id)
    if ip.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.definitions'))
        
    # Check for constraints
    students = Student.query.filter_by(indigenous_people_id=ip.id).first()
    if students:
        flash('Não é possível excluir o povo indígena, pois existem alunos vinculados a ele.', 'danger')
        return redirect(url_for('academic.definitions'))
        
    db.session.delete(ip)
    db.session.commit()
    log_audit('DELETE', 'IndigenousPeople', id, f"Deletou povo indígena {ip.name}")
    flash('Povo indígena excluído com sucesso.', 'success')
    return redirect(url_for('academic.definitions'))

def _process_definition_import(app, job_id, filepath, task_id, def_type):
    with app.app_context():
        from app.services.import_service import ImportService
        
        job = ImportJob.query.get(job_id)
        if not job: return
        job.status = 'running'
        db.session.commit()
        
        try:
            with open(filepath, 'rb') as f:
                result = ImportService.process_file(f, type=def_type, task_id=task_id)
            
            if not result['success']:
                if task_id:
                    fail_import_task(task_id, result.get('error', 'Erro desconhecido.'))
                job.status = 'failed'
                job.error_message = result.get('error')
                db.session.commit()
                return
                
            data = result['data']
            total = len(data)
            
            # Extract unique names
            names_in_file = {str(row.get('name', row.get('Nome', ''))).strip() for row in data if row.get('name') or row.get('Nome')}
            
            if def_type == 'quilombola':
                existing_records = QuilombolaCommunity.query.filter(
                    QuilombolaCommunity.name.in_(names_in_file),
                    QuilombolaCommunity.tenant_id == job.tenant_id
                ).all()
            elif def_type == 'indigenous':
                existing_records = IndigenousPeople.query.filter(
                    IndigenousPeople.name.in_(names_in_file),
                    IndigenousPeople.tenant_id == job.tenant_id
                ).all()
            else:
                existing_records = []
                
            existing_names = {rec.name for rec in existing_records}
            
            new_records = []
            
            for i, name in enumerate(names_in_file):
                if name not in existing_names:
                    if def_type == 'quilombola':
                        new_records.append(QuilombolaCommunity(name=name, tenant_id=job.tenant_id))
                    elif def_type == 'indigenous':
                        new_records.append(IndigenousPeople(name=name, tenant_id=job.tenant_id))
                        
                if task_id and i % 50 == 0:
                    update_import_progress(task_id, i + 1, message=f"Inserindo registros ({i + 1}/{total})...")
            
            if new_records:
                db.session.bulk_save_objects(new_records)
                db.session.commit()
                
            if task_id:
                update_import_progress(task_id, total, message="Concluído")        
            job.status = 'completed'
            job.processed_rows = total
            job.total_rows = total
            job.completed_at = get_brasilia_time()
            db.session.commit()
            
            if task_id:
                finish_import_task(task_id)
            
        except Exception as e:
            if task_id:
                fail_import_task(task_id, str(e))
            job.status = 'failed'
            job.error_message = str(e)
            db.session.commit()

@academic_bp.route('/quilombola/import', methods=['POST'])
@login_required
def import_quilombola():
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))
        
    if ImportJob.is_any_running():
        flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
        return redirect(url_for('academic.definitions'))
        
    form = ImportDefinitionForm()
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
            import_type='Quilombola',
            filename=filename,
            status='pending',
            tenant_id=get_tenant_id()
        )
        db.session.add(job)
        db.session.commit()
        
        thread = threading.Thread(
            target=_process_definition_import,
            args=(current_app._get_current_object(), job.id, filepath, task_id, 'quilombola')
        )
        thread.start()
        
        flash('Importação de comunidades quilombolas iniciada em segundo plano. Aguarde a conclusão.', 'info')
    else:
         flash('Erro no arquivo enviado.', 'danger')
         
    return redirect(url_for('academic.definitions'))

@academic_bp.route('/indigenous/import', methods=['POST'])
@login_required
def import_indigenous():
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))
        
    if ImportJob.is_any_running():
        flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
        return redirect(url_for('academic.definitions'))
        
    form = ImportDefinitionForm()
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
            import_type='Indigenous',
            filename=filename,
            status='pending',
            tenant_id=get_tenant_id()
        )
        db.session.add(job)
        db.session.commit()
        
        thread = threading.Thread(
            target=_process_definition_import,
            args=(current_app._get_current_object(), job.id, filepath, task_id, 'indigenous')
        )
        thread.start()
        
        flash('Importação de povos indígenas iniciada em segundo plano. Aguarde a conclusão.', 'info')
    else:
         flash('Erro no arquivo enviado.', 'danger')
         
    return redirect(url_for('academic.definitions'))

@academic_bp.route('/quilombola/download-layout')
@login_required
def download_quilombola_layout():
    data = {
        'Nome': ['Comunidade Exemplo 1', 'Comunidade Exemplo 2']
    }
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Layout')
        worksheet = writer.sheets['Layout']
        worksheet.column_dimensions['A'].width = 30
    output.seek(0)
    return send_file(output, download_name='layout_quilombolas.xlsx', as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@academic_bp.route('/indigenous/download-layout')
@login_required
def download_indigenous_layout():
    data = {
        'Nome': ['Povo Exemplo 1', 'Povo Exemplo 2']
    }
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Layout')
        worksheet = writer.sheets['Layout']
        worksheet.column_dimensions['A'].width = 30
    output.seek(0)
    return send_file(output, download_name='layout_povos_indigenas.xlsx', as_attachment=True, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@academic_bp.route('/year/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_year(id):
    year = SchoolYear.query.get_or_404(id)
    
    if year.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.definitions'))
        
    form = SchoolYearForm(obj=year)
    if form.validate_on_submit():
        existing = SchoolYear.query.filter(SchoolYear.tenant_id == get_tenant_id(), SchoolYear.name == form.name.data.strip(), SchoolYear.id != id).first()
        if existing:
            flash('Já existe outro ano escolar com este nome.', 'danger')
        else:
            old_name = year.name
            year.name = form.name.data.strip()
            db.session.commit()
            log_audit('UPDATE', 'SchoolYear', year.id, f"Atualizou ano escolar {old_name} para {year.name}")
            flash('Ano escolar atualizado com sucesso.', 'success')
            return redirect(url_for('academic.definitions'))
            
    return render_template('academic/year_edit.html', form=form, year=year)

@academic_bp.route('/year/<int:id>/delete', methods=['POST'])
@login_required
def delete_year(id):
    year = SchoolYear.query.get_or_404(id)
    
    if year.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.definitions'))
        
    # Check associations
    if year.classes.count() > 0 or year.curriculums.count() > 0:
        flash(f'Erro: Não é possível excluir o ano escolar "{year.name}" pois está em uso.', 'danger')
        return redirect(url_for('academic.definitions'))
        
    name = year.name
    db.session.delete(year)
    db.session.commit()
    
    log_audit('DELETE', 'SchoolYear', id, f"Excluiu ano escolar {name}")
    flash('Ano escolar excluído com sucesso.', 'success_delete')
    return redirect(url_for('academic.definitions'))

@academic_bp.route('/subject/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_subject(id):
    subject = Subject.query.get_or_404(id)
    
    if subject.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.definitions'))
        
    form = SubjectForm(obj=subject)
    if form.validate_on_submit():
        existing = Subject.query.filter(Subject.tenant_id == get_tenant_id(), Subject.name == form.name.data.strip(), Subject.id != id).first()
        if existing:
            flash('Já existe outro componente curricular com este nome.', 'danger')
        else:
            old_name = subject.name
            subject.name = form.name.data.strip()
            db.session.commit()
            log_audit('UPDATE', 'Subject', subject.id, f"Atualizou componente {old_name} para {subject.name}")
            flash('Componente curricular atualizado com sucesso.', 'success')
            return redirect(url_for('academic.definitions'))
            
    return render_template('academic/subject_edit.html', form=form, subject=subject)

@academic_bp.route('/subject/<int:id>/delete', methods=['POST'])
@login_required
def delete_subject(id):
    subject = Subject.query.get_or_404(id)
    
    if subject.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.definitions'))
        
    # Check CurriculumStructure association
    from app.models import curriculum_subjects
    assoc_curriculums = db.session.query(curriculum_subjects).filter_by(subject_id=id).count()
    if assoc_curriculums > 0:
        flash('Erro: Este componente está vinculado a estruturas curriculares.', 'danger')
        return redirect(url_for('academic.definitions'))
        
    if TeachingAssignment.query.filter_by(subject_id=id).count() > 0:
        flash('Erro: Este componente está vinculado a atribuições de professores.', 'danger')
        return redirect(url_for('academic.definitions'))
        
    name = subject.name
    db.session.delete(subject)
    db.session.commit()
    
    log_audit('DELETE', 'Subject', id, f"Excluiu componente curricular {name}")
    flash('Componente curricular excluído com sucesso.', 'success_delete')
    return redirect(url_for('academic.definitions'))

# --- Curriculum Structures Section ---

@academic_bp.route('/curriculums', methods=['GET', 'POST'])
@login_required
def list_curriculums():
    form = CurriculumForm()
    
    # Populate choices inside current tenant scope
    form.school_year_id.choices = [(y.id, y.name) for y in filter_by_tenant(SchoolYear.query, SchoolYear).order_by(SchoolYear.name).all()]
    form.subjects.choices = [(s.id, s.name) for s in filter_by_tenant(Subject.query, Subject).order_by(Subject.name).all()]
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    query = CurriculumStructure.query
    query = filter_by_tenant(query, CurriculumStructure)
    
    if search:
        query = query.filter(CurriculumStructure.name.ilike(f'%{search}%'))
        
    curriculums = query.order_by(CurriculumStructure.name).paginate(page=page, per_page=30)
    
    if form.validate_on_submit():
        structure = CurriculumStructure(
            name=form.name.data.strip(),
            school_year_id=form.school_year_id.data,
            tenant_id=get_tenant_id()
        )
        selected_subjects = Subject.query.filter(Subject.id.in_(form.subjects.data), Subject.tenant_id == get_tenant_id()).all()
        structure.subjects.extend(selected_subjects)
        
        db.session.add(structure)
        db.session.commit()
        
        log_audit('CREATE', 'CurriculumStructure', structure.id, f"Criou estrutura curricular {structure.name}")
        flash('Estrutura Curricular criada com sucesso.', 'success')
        return redirect(url_for('academic.list_curriculums'))
        
    return render_template('academic/curriculums.html', curriculums=curriculums, form=form)

@academic_bp.route('/curriculums/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_curriculum(id):
    structure = CurriculumStructure.query.get_or_404(id)
    
    if structure.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_curriculums'))
        
    form = CurriculumForm(obj=structure)
    form.school_year_id.choices = [(y.id, y.name) for y in filter_by_tenant(SchoolYear.query, SchoolYear).order_by(SchoolYear.name).all()]
    form.subjects.choices = [(s.id, s.name) for s in filter_by_tenant(Subject.query, Subject).order_by(Subject.name).all()]
    
    if form.validate_on_submit():
        structure.name = form.name.data.strip()
        structure.school_year_id = form.school_year_id.data
        
        selected_subjects = Subject.query.filter(Subject.id.in_(form.subjects.data), Subject.tenant_id == get_tenant_id()).all()
        structure.subjects = selected_subjects
        
        db.session.commit()
        log_audit('UPDATE', 'CurriculumStructure', structure.id, f"Atualizou estrutura curricular {structure.name}")
        flash('Estrutura Curricular atualizada com sucesso.', 'success')
        return redirect(url_for('academic.list_curriculums'))
        
    if request.method == 'GET':
        form.subjects.data = [s.id for s in structure.subjects]
        form.school_year_id.data = structure.school_year_id
        
    return render_template('academic/curriculum_edit.html', form=form, structure=structure)

@academic_bp.route('/curriculums/<int:id>/delete', methods=['POST'])
@login_required
def delete_curriculum(id):
    structure = CurriculumStructure.query.get_or_404(id)
    
    if structure.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_curriculums'))
        
    if structure.classes.count() > 0:
        flash('Erro: Não é possível excluir uma estrutura curricular vinculada a turmas.', 'danger')
        return redirect(url_for('academic.list_curriculums'))
        
    name = structure.name
    db.session.delete(structure)
    db.session.commit()
    
    log_audit('DELETE', 'CurriculumStructure', id, f"Excluiu estrutura curricular {name}")
    flash('Estrutura Curricular excluída com sucesso.', 'success_delete')
    return redirect(url_for('academic.list_curriculums'))

# --- Classes Section ---

@academic_bp.route('/classes', methods=['GET', 'POST'])
@login_required
def list_classes():
    form = ClassForm()
    import_form = ImportClassForm()
    
    form.school_year_id.choices = [(y.id, y.name) for y in filter_by_tenant(SchoolYear.query, SchoolYear).order_by(SchoolYear.name).all()]
    form.structure_id.choices = [(s.id, s.name) for s in filter_by_tenant(CurriculumStructure.query, CurriculumStructure).order_by(CurriculumStructure.name).all()]
    form.teaching_unit_id.choices = [(u.id, u.name) for u in filter_by_tenant(TeachingUnit.query, TeachingUnit).filter_by(type='Escola').order_by(TeachingUnit.name).all()]
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    regional_id = request.args.get('regional_id', type=int)
    unit_id = request.args.get('unit_id', type=int)
    
    # Active role checking
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')
    
    query = Class.query
    query = filter_by_tenant(query, Class)
    
    if active_role == 'unidade' and active_school_id:
        query = query.filter(Class.teaching_unit_id == active_school_id)
        unit_id = active_school_id
    elif unit_id:
        query = query.filter(Class.teaching_unit_id == unit_id)
    elif regional_id:
        query = query.join(TeachingUnit).filter(TeachingUnit.parent_id == regional_id)
        
    if search:
        query = query.join(SchoolYear).filter(
            (Class.name.ilike(f'%{search}%')) |
            (SchoolYear.name.ilike(f'%{search}%'))
        )
        
    classes = query.order_by(Class.name).paginate(page=page, per_page=30)
    
    active_job = ImportJob.query.filter_by(
        tenant_id=get_tenant_id(),
        import_type='Classes',
        status='running'
    ).first()
    
    regionals = TeachingUnit.query.filter_by(type='Regional').order_by(TeachingUnit.name).all()
    schools = TeachingUnit.query.filter_by(type='Escola').order_by(TeachingUnit.name).all()
    
    if form.validate_on_submit() and not import_form.submit.data:
        # Check structure matches year
        struct = CurriculumStructure.query.get(form.structure_id.data)
        if struct.school_year_id != form.school_year_id.data:
            flash('Erro: A Estrutura Curricular não corresponde ao Ano Escolar selecionado.', 'danger')
        else:
            new_class = Class(
                name=form.name.data.strip(),
                shift=form.shift.data,
                school_year_id=form.school_year_id.data,
                structure_id=form.structure_id.data,
                teaching_unit_id=form.teaching_unit_id.data,
                tenant_id=get_tenant_id()
            )
            db.session.add(new_class)
            db.session.commit()
            
            log_audit('CREATE', 'Class', new_class.id, f"Criou turma {new_class.name}")
            flash('Turma cadastrada com sucesso.', 'success')
            return redirect(url_for('academic.list_classes'))
            
    return render_template(
        'academic/classes.html',
        classes=classes,
        form=form,
        import_form=import_form,
        regionals=regionals,
        schools=schools,
        regional_id=regional_id,
        unit_id=unit_id,
        search=search,
        active_job=active_job
    )

@academic_bp.route('/classes/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_class(id):
    klass = Class.query.get_or_404(id)
    
    if klass.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_classes'))
        
    form = ClassForm(obj=klass)
    form.school_year_id.choices = [(y.id, y.name) for y in filter_by_tenant(SchoolYear.query, SchoolYear).order_by(SchoolYear.name).all()]
    form.structure_id.choices = [(s.id, s.name) for s in filter_by_tenant(CurriculumStructure.query, CurriculumStructure).order_by(CurriculumStructure.name).all()]
    form.teaching_unit_id.choices = [(u.id, u.name) for u in filter_by_tenant(TeachingUnit.query, TeachingUnit).filter_by(type='Escola').order_by(TeachingUnit.name).all()]
    
    if form.validate_on_submit():
        struct = CurriculumStructure.query.get(form.structure_id.data)
        if struct.school_year_id != form.school_year_id.data:
            flash('Erro: A Estrutura Curricular não corresponde ao Ano Escolar selecionado.', 'danger')
        else:
            klass.name = form.name.data.strip()
            klass.shift = form.shift.data
            klass.school_year_id = form.school_year_id.data
            klass.structure_id = form.structure_id.data
            klass.teaching_unit_id = form.teaching_unit_id.data
            
            db.session.commit()
            log_audit('UPDATE', 'Class', klass.id, f"Atualizou turma {klass.name}")
            flash('Turma atualizada com sucesso.', 'success')
            return redirect(url_for('academic.list_classes'))
            
    return render_template('academic/class_edit.html', form=form, klass=klass)

@academic_bp.route('/classes/<int:id>/delete', methods=['POST'])
@login_required
def delete_class(id):
    klass = Class.query.get_or_404(id)
    
    if klass.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_classes'))
        
    if klass.enrollments.count() > 0:
        flash(f'Erro: Não é possível excluir a turma "{klass.name}" pois existem alunos matriculados.', 'danger')
        return redirect(url_for('academic.list_classes'))
        
    name = klass.name
    db.session.delete(klass)
    db.session.commit()
    
    log_audit('DELETE', 'Class', id, f"Excluiu turma {name}")
    flash('Turma excluída com sucesso.', 'success_delete')
    return redirect(url_for('academic.list_classes'))

@academic_bp.route('/classes/<int:id>/students')
@login_required
def list_class_students(id):
    klass = Class.query.get_or_404(id)
    
    if klass.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_classes'))
        
    page = request.args.get('page', 1, type=int)
    enrollments = klass.enrollments.paginate(page=page, per_page=30)
    
    return render_template('academic/class_students.html', klass=klass, enrollments=enrollments)

@academic_bp.route('/classes/<int:id>/enroll', methods=['POST'])
@login_required
def enroll_student(id):
    klass = Class.query.get_or_404(id)
    
    if klass.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_classes'))
        
    student_id = request.form.get('student_id')
    if not student_id:
        flash('Erro: Aluno não selecionado.', 'danger')
        return redirect(url_for('academic.list_class_students', id=id))
        
    student = Student.query.get_or_404(student_id)
    
    if student.tenant_id != get_tenant_id():
        flash('Erro de segurança: Aluno pertence a outra rede de ensino.', 'danger')
        return redirect(url_for('academic.list_class_students', id=id))
        
    # Check duplicate
    existing = Enrollment.query.filter_by(student_id=student.id, class_id=klass.id).first()
    if existing:
        flash(f'O aluno {student.name} já está matriculado nesta turma.', 'warning')
        return redirect(url_for('academic.list_class_students', id=id))
        
    enrollment = Enrollment(student_id=student.id, class_id=klass.id)
    db.session.add(enrollment)
    db.session.commit()
    
    log_audit('CREATE', 'Enrollment', enrollment.id, f"Matriculou {student.name} na turma {klass.name}")
    flash(f'Aluno {student.name} matriculado com sucesso.', 'success')
    return redirect(url_for('academic.list_class_students', id=id))

@academic_bp.route('/classes/<int:id>/unenroll/<int:student_id>', methods=['POST'])
@login_required
def unenroll_student(id, student_id):
    klass = Class.query.get_or_404(id)
    
    if klass.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_classes'))
        
    enrollment = Enrollment.query.filter_by(class_id=id, student_id=student_id).first_or_404()
    
    student_name = enrollment.student.name
    db.session.delete(enrollment)
    db.session.commit()
    
    log_audit('DELETE', 'Enrollment', enrollment.id, f"Desvinculou {student_name} da turma {klass.name}")
    flash('Vínculo do aluno desfeito com sucesso.', 'success_delete')
    return redirect(url_for('academic.list_class_students', id=id))

# --- Classes Import Background Thread ---

def _process_classes_import(app, job_id, filepath, task_id=None):
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
            
            # Lookups
            schools_by_name = {s.name.strip().lower(): s for s in TeachingUnit.query.filter_by(tenant_id=job.tenant_id, type='Escola').all()}
            schools_by_inep = {s.inep_code.strip(): s for s in TeachingUnit.query.filter_by(tenant_id=job.tenant_id, type='Escola').all() if s.inep_code}
            years = {y.name.strip().lower(): y for y in SchoolYear.query.filter_by(tenant_id=job.tenant_id).all()}
            structures = {s.name.strip().lower(): s for s in CurriculumStructure.query.filter_by(tenant_id=job.tenant_id).all()}
            existing_classes = {(c.name.strip().lower(), c.teaching_unit_id) for c in Class.query.filter_by(tenant_id=job.tenant_id).all()}
            
            for index, row in df.iterrows():
                name = str(row.get('Nome da Turma', row.get('Nome', ''))).strip()
                shift = str(row.get('Turno', '')).strip()
                year_name = str(row.get('Ano Escolar', '')).strip()
                structure_name = str(row.get('Estrutura Curricular', '')).strip()
                school_name = str(row.get('Unidade de Ensino', row.get('Unidade Escolar', ''))).strip()
                inep = str(row.get('INEP da Escola', row.get('INEP', ''))).strip()
                
                if not name or name.lower() == 'nan':
                    errors.append(f"Linha {index+2}: Nome da turma não informado.")
                    job.processed_rows += 1
                    continue
                    
                if shift not in ['Matutino', 'Vespertino', 'Noturno', 'Integral']:
                    errors.append(f"Linha {index+2}: Turno inválido '{shift}'. Deve ser Matutino, Vespertino, Noturno ou Integral.")
                    job.processed_rows += 1
                    continue
                    
                name_l = name.lower()
                
                school_obj = None
                if inep and inep != 'nan':
                    # Sometimes pandas reads INEP as float like 12345678.0
                    if inep.endswith('.0'):
                        inep = inep[:-2]
                    school_obj = schools_by_inep.get(inep)
                    
                if not school_obj:
                    school_lower = school_name.lower()
                    school_obj = schools_by_name.get(school_lower)
                    
                if not school_obj:
                    errors.append(f"Linha {index+2}: Unidade Escolar não encontrada (INEP: '{inep}', Nome: '{school_name}').")
                    job.processed_rows += 1
                    continue

                if (name_l, school_obj.id) in existing_classes:
                    errors.append(f"Linha {index+2}: Turma '{name}' já existe nesta escola.")
                    job.processed_rows += 1
                    continue
                    
                year_lower = year_name.lower()
                if year_lower not in years:
                    errors.append(f"Linha {index+2}: Ano Escolar '{year_name}' não encontrado.")
                    job.processed_rows += 1
                    continue
                    
                struct_lower = structure_name.lower()
                if struct_lower not in structures:
                    errors.append(f"Linha {index+2}: Estrutura Curricular '{structure_name}' não encontrada.")
                    job.processed_rows += 1
                    continue
                    
                struct_obj = structures[struct_lower]
                year_obj = years[year_lower]
                
                if struct_obj.school_year_id != year_obj.id:
                    errors.append(f"Linha {index+2}: Estrutura Curricular não corresponde ao Ano Escolar.")
                    job.processed_rows += 1
                    continue
                    
                klass = Class(
                    name=name,
                    shift=shift,
                    school_year_id=year_obj.id,
                    structure_id=struct_obj.id,
                    teaching_unit_id=school_obj.id,
                    tenant_id=job.tenant_id
                )
                
                db.session.add(klass)
                existing_classes.add((name_l, school_obj.id))
                success_count += 1
                job.processed_rows += 1
                
                if task_id and index % 10 == 0:
                    update_import_progress(task_id, job.processed_rows, message=f"Importando turma: {name}")
                    
                # OTIMIZAÇÃO: Inserção em lote a cada 100 registros
                if success_count % 100 == 0:
                    job.errors = json.dumps(errors)
                    db.session.commit()
                    
            job.status = 'completed'
            job.finished_at = get_brasilia_time()
            job.errors = json.dumps(errors)
            db.session.commit()
            
            if task_id:
                finish_import_task(task_id, message=f"Importação de turmas concluída. {success_count} registros importados.", log_file=None)
                
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

@academic_bp.route('/classes/download-layout')
@login_required
def download_class_layout():
    import pandas as pd
    from io import BytesIO
    from flask import send_file
    
    data = {
        'INEP da Escola': ['12345678', ''],
        'Unidade de Ensino': ['Escola Exemplo 1', 'Escola Exemplo 1'],
        'Nome da Turma': ['101', '102'],
        'Ano Escolar': ['1º Ano', '1º Ano'],
        'Turno': ['Matutino', 'Vespertino'],
        'Estrutura Curricular': ['Ensino Fundamental - Anos Iniciais', 'Ensino Fundamental - Anos Iniciais']
    }
    
    df = pd.DataFrame(data)
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Layout Turmas')
        # Adjust column widths
        worksheet = writer.sheets['Layout Turmas']
        for idx, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = max_len
            
    output.seek(0)
    
    return send_file(
        output,
        download_name='layout_importacao_turmas.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@academic_bp.route('/classes/import', methods=['POST'])
@login_required
def import_classes():
    if current_user.role != 'admin':
        return redirect(url_for('main.index'))
        
    if ImportJob.is_any_running():
        flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
        return redirect(url_for('academic.list_classes'))
        
    form = ImportClassForm()
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
            import_type='Classes',
            filename=filename,
            status='pending',
            tenant_id=get_tenant_id()
        )
        db.session.add(job)
        db.session.commit()
        
        thread = threading.Thread(
            target=_process_classes_import,
            args=(current_app._get_current_object(), job.id, filepath, task_id)
        )
        thread.start()
        
        flash('A importação de turmas foi iniciada em segundo plano.', 'info')
    else:
        for field, errors in form.errors.items():
            flash(f"Erro em {getattr(form, field).label.text}: {', '.join(errors)}", 'danger')
            
    return redirect(url_for('academic.list_classes'))

# --- Academic Tenant Search API ---

@academic_bp.route('/api/students/search')
@login_required
def search_students_api():
    query = request.args.get('q', '').strip()
    if not query:
        return {'results': []}
        
    import re
    clean_query = re.sub(r'[^0-9]', '', query)
    
    # Strictly isolated by tenant
    students_query = Student.query
    
    students_query = students_query.filter(
        (Student.name.ilike(f'%{query}%')) |
        (Student.cpf.ilike(f'%{clean_query}%')) |
        (Student.registration_number.ilike(f'%{query}%'))
    )
    
    students = students_query.limit(20).all()
    
    return {'results': [{
        'id': s.id,
        'name': s.name,
        'cpf': s.cpf,
        'registration': s.registration_number
    } for s in students]}

# --- Evaluations Section ---

@academic_bp.route('/evaluations', methods=['GET', 'POST'])
@login_required
def list_evaluations():
    form = EvaluationForm()
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    query = Evaluation.query
    query = filter_by_tenant(query, Evaluation)
    
    if search:
        query = query.filter(Evaluation.name.ilike(f'%{search}%'))
        
    evaluations = query.order_by(Evaluation.name).paginate(page=page, per_page=30)
    
    if form.validate_on_submit():
        logo_path = None
        if form.logo.data:
            if not allowed_file(form.logo.data.filename, ALLOWED_IMAGE_EXTENSIONS):
                flash("Formato de logo inválido.", "danger")
                return redirect(request.url)
            filename = secure_filename(form.logo.data.filename)
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
            os.makedirs(upload_folder, exist_ok=True)
            logo_path = f'uploads/logos/{filename}'
            form.logo.data.save(os.path.join(upload_folder, filename))
            
        evaluation = Evaluation(
            name=form.name.data.strip(),
            type=form.type.data,
            quantity=form.quantity.data,
            logo_path=logo_path,
            scoring_type='none',
            question_values=None,
            multiple_components=(form.multiple_components.data == '1'),
            tenant_id=get_tenant_id()
        )
        db.session.add(evaluation)
        db.session.commit()
        
        log_audit('CREATE', 'Evaluation', evaluation.id, f"Criou avaliação {evaluation.name}")
        flash('Avaliação cadastrada com sucesso!', 'success')
        return redirect(url_for('academic.list_evaluations'))
        
    return render_template('academic/evaluations.html', evaluations=evaluations, form=form)

@academic_bp.route('/evaluations/<int:id>/edit', methods=['POST'])
@login_required
def edit_evaluation(id):
    evaluation = Evaluation.query.get_or_404(id)
    
    if evaluation.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_evaluations'))
        
    form = EvaluationForm()
    
    # Modal trick: process WTForm data manually since files might be multipart
    name = request.form.get('name', '').strip()
    type_val = request.form.get('type')
    quantity = request.form.get('quantity', type=int)
    multiple_components = request.form.get('multiple_components') == '1'
    
    if name and type_val and quantity:
        evaluation.name = name
        evaluation.type = type_val
        evaluation.quantity = quantity
        evaluation.multiple_components = multiple_components
        
        # Handle optional logo
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename != '':
            filename = secure_filename(logo_file.filename)
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
            os.makedirs(upload_folder, exist_ok=True)
            evaluation.logo_path = f'uploads/logos/{filename}'
            logo_file.save(os.path.join(upload_folder, filename))
            
        db.session.commit()
        log_audit('UPDATE', 'Evaluation', evaluation.id, f"Atualizou avaliação {evaluation.name}")
        flash('Avaliação atualizada com sucesso!', 'success')
    else:
        flash('Erro ao editar avaliação: Preencha todos os campos obrigatórios.', 'danger')
        
    return redirect(url_for('academic.list_evaluations'))

@academic_bp.route('/evaluations/<int:id>/delete', methods=['POST'])
@login_required
def delete_evaluation(id):
    evaluation = Evaluation.query.get_or_404(id)
    
    if evaluation.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_evaluations'))
        
    # Check associated exams
    if evaluation.exams.count() > 0:
        flash(f'Erro: Não é possível excluir a avaliação "{evaluation.name}" pois existem provas vinculadas.', 'danger')
        return redirect(url_for('academic.list_evaluations'))
        
    name = evaluation.name
    db.session.delete(evaluation)
    db.session.commit()
    
    log_audit('DELETE', 'Evaluation', id, f"Excluiu avaliação {name}")
    flash('Avaliação excluída com sucesso!', 'success')
    return redirect(url_for('academic.list_evaluations'))

# --- Consolidated Academic Dashboard (Strictly Tenant Isolated) ---

@academic_bp.route('/indicators')
@login_required

def academic_dashboard():
    # Helper context summaries
    total_schools = filter_by_tenant(TeachingUnit.query.filter_by(type='Escola'), TeachingUnit).count()
    total_classes = filter_by_tenant(Class.query, Class).count()
    total_students = filter_by_tenant(Student.query, Student).count()
    
    prof_q = filter_by_tenant(Professor.query, Professor)
    total_professors = prof_q.count()
    
    avg_students = total_students / total_classes if total_classes > 0 else 0
    
    # Active unmodulated items
    professors_unmodulated = filter_by_tenant(Professor.query, Professor).filter(
        ~Professor.id.in_(db.session.query(TeachingAssignment.professor_id))
    ).count()
    
    classes_unmodulated = filter_by_tenant(Class.query, Class).filter(
        ~Class.id.in_(db.session.query(TeachingAssignment.class_id))
    ).count()
    
    # Regionals consolidated breakdown (Fast SQL aggregation)
    school_alias = db.aliased(TeachingUnit)
    regional_alias = db.aliased(TeachingUnit)
    
    reg_q = db.session.query(
        regional_alias.name,
        func.count(func.distinct(school_alias.id)),
        func.count(func.distinct(Class.id)),
        func.count(Enrollment.id)
    ).select_from(regional_alias)     .outerjoin(school_alias, (school_alias.parent_id == regional_alias.id) & (school_alias.type == 'Escola'))     .outerjoin(Class, Class.teaching_unit_id == school_alias.id)     .outerjoin(Enrollment, (Enrollment.class_id == Class.id))     .filter(regional_alias.type == 'Regional')
    reg_q = filter_by_tenant(reg_q, regional_alias)
     
    regionals_data_raw = reg_q.group_by(regional_alias.id, regional_alias.name)                              .order_by(regional_alias.name).all()
                              
    total_schools_all = total_schools or 1
    total_classes_all = total_classes or 1
    total_students_all = total_students or 1
    
    regionals_data = []
    for row in regionals_data_raw:
        regionals_data.append({
            'name': row[0],
            'schools': row[1],
            'schools_perc': round(row[1] / total_schools_all * 100, 2),
            'classes': row[2],
            'classes_perc': round(row[2] / total_classes_all * 100, 2),
            'students': row[3],
            'students_perc': round(row[3] / total_students_all * 100, 2)
        })
        
    # School Years Distribution
    years_q = db.session.query(
        SchoolYear.name,
        func.count(func.distinct(Class.id)),
        func.count(Enrollment.id)
    ).select_from(SchoolYear)     .outerjoin(Class, Class.school_year_id == SchoolYear.id)     .outerjoin(Enrollment, Enrollment.class_id == Class.id)
    years_q = filter_by_tenant(years_q, SchoolYear)
     
    years_data_raw = years_q.group_by(SchoolYear.name).order_by(SchoolYear.name).all()
    years_data = [{'name': row[0], 'classes': row[1], 'students': row[2]} for row in years_data_raw]
    
    # Shifts breakdown
    shifts_q = db.session.query(
        Class.shift,
        func.count(func.distinct(Class.id)),
        func.count(Enrollment.id)
    ).select_from(Class)     .outerjoin(Enrollment, Enrollment.class_id == Class.id)
    shifts_q = filter_by_tenant(shifts_q, Class)
     
    shifts_data_raw = shifts_q.group_by(Class.shift).all()
    shifts_data = [{'shift': row[0] or 'Não informado', 'classes': row[1], 'students': row[2]} for row in shifts_data_raw]
    
    # Student Demographics
    student_sex_q = filter_by_tenant(db.session.query(Student.sex, func.count(Student.id)), Student).group_by(Student.sex)
    student_sex_raw = student_sex_q.all()
    student_sex_stats = []
    for sex, count in student_sex_raw:
        perc = round(count / total_students * 100, 2) if total_students > 0 else 0
        student_sex_stats.append({'name': sex or 'Não informado', 'count': count, 'perc': perc})
        
    student_race_q = filter_by_tenant(db.session.query(Student.race, func.count(Student.id)), Student).group_by(Student.race)
    student_race_raw = student_race_q.all()
    student_race_stats = []
    for race, count in student_race_raw:
        student_race_stats.append((race or 'Não informado', count))
        
    # Student Nationalities (Clean aggregation)
    nationality_q = filter_by_tenant(db.session.query(Student.nationality, func.count(Student.id)), Student).group_by(Student.nationality)
    nationality_raw = nationality_q.all()
        
    br_count = 0
    foreign_count = 0
    for nat, count in nationality_raw:
        if not nat or 'Brasileiro' in nat or nat.strip().lower() == 'nan':
            br_count += count
        else:
            foreign_count += count
            
    student_nationality_stats = {
        'br_count': br_count,
        'br_perc': round(br_count / total_students * 100, 2) if total_students > 0 else 0,
        'foreign_count': foreign_count,
        'foreign_perc': round(foreign_count / total_students * 100, 2) if total_students > 0 else 0
    }
    
    student_country_q = filter_by_tenant(db.session.query(Student.birth_country, func.count(Student.id).label('total')), Student)        .filter(Student.nationality.notilike('%Brasileiro%'), Student.birth_country != None)        .group_by(Student.birth_country)        .order_by(func.count(Student.id).desc())        .limit(5)
    student_country_stats = student_country_q.all()
        
    student_zone_q = filter_by_tenant(db.session.query(Student.residential_zone, func.count(Student.id)), Student).group_by(Student.residential_zone)
    student_zone_raw = student_zone_q.all()
    student_zone_stats = []
    for zone, count in student_zone_raw:
        perc = round(count / total_students * 100, 2) if total_students > 0 else 0
        student_zone_stats.append({'name': zone or 'Não informado', 'count': count, 'perc': perc})
        
    student_location_q = filter_by_tenant(db.session.query(Student.differentiated_location, func.count(Student.id)), Student).group_by(Student.differentiated_location)
    student_location_raw = student_location_q.all()
    student_location_stats = []
    for loc, count in student_location_raw:
        perc = round(count / total_students * 100, 2) if total_students > 0 else 0
        student_location_stats.append({'name': loc or 'Não informado', 'count': count, 'perc': perc})
        
    # Social Benefits and Special Needs
    bolsa_count = filter_by_tenant(Student.query.filter_by(bolsa_familia=True), Student).count()
    bolsa_perc = round(bolsa_count / total_students * 100, 2) if total_students > 0 else 0
    
    special_needs_count = filter_by_tenant(Student.query.filter_by(special_needs=True), Student).count()
    special_needs_perc = round(special_needs_count / total_students * 100, 2) if total_students > 0 else 0
    
    student_social_stats = {
        'bolsa_count': bolsa_count,
        'bolsa_perc': bolsa_perc,
        'special_needs_count': special_needs_count,
        'special_needs_perc': special_needs_perc
    }
    
    # Professor Demographics
    prof_sex_q = filter_by_tenant(db.session.query(Professor.sex, func.count(Professor.id)), Professor).group_by(Professor.sex)
    prof_sex_raw = prof_sex_q.all()
    professor_sex_stats = []
    for sex, count in prof_sex_raw:
        perc = round(count / total_professors * 100, 2) if total_professors > 0 else 0
        professor_sex_stats.append({'name': sex or 'Não informado', 'count': count, 'perc': perc})
        
    prof_race_q = filter_by_tenant(db.session.query(Professor.race, func.count(Professor.id)), Professor).group_by(Professor.race)
    prof_race_raw = prof_race_q.all()
    professor_race_stats = []
    for race, count in prof_race_raw:
        professor_race_stats.append((race or 'Não informado', count))
        
    return render_template(
        'academic/dashboard.html',
        summary={
            'total_schools': total_schools,
            'total_classes': total_classes,
            'total_students': total_students,
            'total_professors': total_professors,
            'avg_students': avg_students,
            'professors_unmodulated': professors_unmodulated,
            'classes_unmodulated': classes_unmodulated
        },
        regionals=regionals_data,
        years=years_data,
        shifts=shifts_data,
        student_demographics={
            'sex': student_sex_stats,
            'race': student_race_stats,
            'nationality': student_nationality_stats,
            'countries': [{'name': c[0] or 'Não informado', 'count': c[1]} for c in student_country_stats],
            'zone': student_zone_stats,
            'location': student_location_stats,
            'social': student_social_stats
        },
        professor_demographics={
            'sex': professor_sex_stats,
            'race': professor_race_stats
        }
    )
@academic_bp.route('/absence-reasons', methods=['GET', 'POST'])
@login_required
def list_absence_reasons():
    form = AbsenceReasonForm()
    
    # Process form submission (creation)
    if form.validate_on_submit():
        # Check uniqueness inside the active tenant scope
        existing = AbsenceReason.query.filter_by(
            tenant_id=get_tenant_id(),
            name=form.name.data.strip()
        ).first()
        if existing:
            flash('Este motivo de ausência já está cadastrado.', 'danger')
            return redirect(url_for('academic.list_absence_reasons'))
            
        reason = AbsenceReason(
            name=form.name.data.strip(),
            tenant_id=get_tenant_id()
        )
        db.session.add(reason)
        db.session.commit()
        
        log_audit('CREATE', 'AbsenceReason', reason.id, f"Criou motivo de ausência {reason.name}")
        flash('Motivo de Ausência criado com sucesso.', 'success')
        return redirect(url_for('academic.list_absence_reasons'))
        
    page = request.args.get('page', 1, type=int)
    query = AbsenceReason.query
    query = filter_by_tenant(query, AbsenceReason)
    
    # Paginação estrita de 30 registros por página
    reasons_pagination = query.order_by(AbsenceReason.name).paginate(page=page, per_page=30)
    
    return render_template(
        'academic/absence_reasons.html',
        reasons=reasons_pagination.items,
        reasons_pagination=reasons_pagination,
        form=form
    )

@academic_bp.route('/absence-reasons/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_absence_reason(id):
    reason = AbsenceReason.query.get_or_404(id)
    
    # Verify tenant isolation boundaries
    if reason.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_absence_reasons'))
        
    form = AbsenceReasonForm(obj=reason)
    if form.validate_on_submit():
        # Check uniqueness inside the same tenant scope excluding self
        existing = AbsenceReason.query.filter(
            AbsenceReason.tenant_id == get_tenant_id(),
            AbsenceReason.name == form.name.data.strip(),
            AbsenceReason.id != id
        ).first()
        if existing:
            flash('Já existe outro motivo de ausência com este nome.', 'danger')
            return render_template('academic/absence_reason_edit.html', form=form, reason=reason)
            
        old_name = reason.name
        reason.name = form.name.data.strip()
        db.session.commit()
        
        log_audit('UPDATE', 'AbsenceReason', reason.id, f"Atualizou motivo de ausência {old_name} para {reason.name}")
        flash('Motivo de Ausência atualizado com sucesso.', 'success')
        return redirect(url_for('academic.list_absence_reasons'))
        
    return render_template('academic/absence_reason_edit.html', form=form, reason=reason)

@academic_bp.route('/absence-reasons/<int:id>/delete', methods=['POST'])
@login_required
def delete_absence_reason(id):
    reason = AbsenceReason.query.get_or_404(id)
    
    # Verify tenant isolation boundaries
    if reason.tenant_id != get_tenant_id():
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('academic.list_absence_reasons'))
        
    # Check dependencies in StudentResult
    if StudentResult.query.filter_by(absence_reason_id=id).first():
        flash(f'Erro: Não é possível excluir o motivo "{reason.name}" pois ele possui registros de notas/resultados de alunos vinculados.', 'danger')
        return redirect(url_for('academic.list_absence_reasons'))
        
    name = reason.name
    db.session.delete(reason)
    db.session.commit()
    
    log_audit('DELETE', 'AbsenceReason', id, f"Excluiu motivo de ausência {name}")
    flash('Motivo de Ausência excluído com sucesso.', 'success_delete')
    return redirect(url_for('academic.list_absence_reasons'))
