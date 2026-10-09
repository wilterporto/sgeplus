import os
import io
import pandas as pd
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify, send_file
import io
from xhtml2pdf import pisa
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import Evaluation, PartnerInstitution, ExternalEvaluationStudent, ExternalEvaluationResult, ExternalEvaluationDescriptor, ImportJob
from app.utils.tenancy import filter_by_tenant, get_tenant_id
from app.utils.timezone import get_brasilia_time
from app.audit_utils import log_audit
from app.import_utils import start_import_task, update_import_progress, finish_import_task, fail_import_task
from app.forms import PartnerInstitutionForm
from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS

# We will need the EvaluationForm from academic or recreate it.
from app.routes.academic import EvaluationForm

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SubmitField

class ImportExternalStudentForm(FlaskForm):
    file = FileField('Planilha de Alunos (.xlsx, .xls, .csv)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls', 'csv'], 'Apenas arquivos Excel ou CSV são permitidos!')
    ])
    submit = SubmitField('Importar')

class ImportExternalResultForm(FlaskForm):
    file = FileField('Planilha de Resultados (.xlsx, .xls, .csv)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls', 'csv'], 'Apenas arquivos Excel ou CSV são permitidos!')
    ])
    submit = SubmitField('Importar')

class ImportDescriptorForm(FlaskForm):
    file = FileField('Planilha de Descritores (.xlsx, .xls, .csv)', validators=[
        FileRequired(),
        FileAllowed(['xlsx', 'xls', 'csv'], 'Apenas arquivos Excel ou CSV são permitidos!')
    ])
    submit = SubmitField('Importar')


external_evaluations_bp = Blueprint('external_evaluations', __name__)

@external_evaluations_bp.route('/partner_institutions', methods=['GET', 'POST'])
@login_required
def list_partner_institutions():
    tenant_id = get_tenant_id()
    form = PartnerInstitutionForm()
    
    if form.validate_on_submit():
        if form.school_year.data is None or form.school_year.data == '':
            flash("O Ano Letivo é obrigatório para Avaliações Externas.", "danger")
            return redirect(request.url)
        if form.cycle.data is None or form.cycle.data == '':
            flash("O Ciclo é obrigatório para Avaliações Externas.", "danger")
            return redirect(request.url)
        institution = PartnerInstitution(
            tenant_id=tenant_id,
            name=form.name.data,
            active=form.active.data
        )
        db.session.add(institution)
        db.session.commit()
        log_audit('create_partner_institution', 'partner_institution', institution.id, f'Criou instituição: {institution.name}')
        flash('Instituição parceira salva com sucesso!', 'success')
        return redirect(url_for('external_evaluations.list_partner_institutions'))
        
    page = request.args.get('page', 1, type=int)
    query = filter_by_tenant(PartnerInstitution.query, PartnerInstitution).filter_by(active=True)
    institutions = query.order_by(PartnerInstitution.name).paginate(page=page, per_page=30, error_out=False)
    
    return render_template('external_evaluations/partner_institutions.html', institutions=institutions, form=form)

@external_evaluations_bp.route('/partner_institutions/<int:id>/edit', methods=['POST'])
@login_required
def edit_partner_institution(id):
    institution = filter_by_tenant(PartnerInstitution.query, PartnerInstitution).filter_by(id=id).first_or_404()
    
    form = PartnerInstitutionForm()
    if form.validate_on_submit():
        if form.school_year.data is None or form.school_year.data == '':
            flash("O Ano Letivo é obrigatório para Avaliações Externas.", "danger")
            return redirect(request.url)
        if form.cycle.data is None or form.cycle.data == '':
            flash("O Ciclo é obrigatório para Avaliações Externas.", "danger")
            return redirect(request.url)
        institution.name = form.name.data
        institution.active = form.active.data
        db.session.commit()
        log_audit('edit_partner_institution', 'partner_institution', institution.id, f'Editou instituição: {institution.name}')
        flash('Instituição parceira atualizada com sucesso!', 'success')
        
    return redirect(url_for('external_evaluations.list_partner_institutions'))

@external_evaluations_bp.route('/partner_institutions/<int:id>/delete', methods=['POST'])
@login_required
def delete_partner_institution(id):
    institution = filter_by_tenant(PartnerInstitution.query, PartnerInstitution).filter_by(id=id).first_or_404()
    
    # Exclusão lógica
    institution.active = False
    db.session.commit()
    log_audit('delete_partner_institution', 'partner_institution', institution.id, f'Excluiu logicamente instituição: {institution.name}')
    flash('Instituição parceira excluída com sucesso!', 'success')
    return redirect(url_for('external_evaluations.list_partner_institutions'))

@external_evaluations_bp.route('/evaluations', methods=['GET', 'POST'])
@login_required
def list_evaluations():
    form = EvaluationForm()
    form.type.choices = [('Formativa', 'Formativa'), ('Diagnóstica', 'Diagnóstica')]
    partners = filter_by_tenant(PartnerInstitution.query, PartnerInstitution).filter_by(active=True).all()
    form.partner_institution_id.choices = [(0, 'Selecione...')] + [(p.id, p.name) for p in partners]
    
    # Forçar origem como Externa
    if request.method == 'GET':
        form.origin.data = 'Externa'
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    query = filter_by_tenant(Evaluation.query, Evaluation).filter_by(origin='Externa')
    
    if search:
        query = query.filter(Evaluation.name.ilike(f'%{search}%'))
        
    evaluations = query.order_by(Evaluation.name).paginate(page=page, per_page=30)
    
    if form.validate_on_submit():
        if form.school_year.data is None or form.school_year.data == '':
            flash("O Ano Letivo é obrigatório para Avaliações Externas.", "danger")
            return redirect(request.url)
        if form.cycle.data is None or form.cycle.data == '':
            flash("O Ciclo é obrigatório para Avaliações Externas.", "danger")
            return redirect(request.url)
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
            origin='Externa',
            partner_institution_id=form.partner_institution_id.data if form.partner_institution_id.data else None,
            quantity=form.quantity.data if hasattr(form, 'quantity') and form.quantity.data else 10,
            logo_path=logo_path,
            scoring_type='none',
            question_values=None,
            multiple_components=(form.multiple_components.data == '1'),
            school_year=form.school_year.data,
            cycle=int(form.cycle.data) if form.cycle.data is not None and form.cycle.data != '' else None,
            tenant_id=get_tenant_id()
        )
        
        db.session.add(evaluation)
        db.session.commit()
        
        log_audit('create_evaluation', 'evaluation', evaluation.id, f"Criou avaliação externa {evaluation.name}")
        flash('Avaliação externa cadastrada com sucesso!', 'success')
        return redirect(url_for('external_evaluations.list_evaluations'))
        
    return render_template('external_evaluations/evaluations.html', evaluations=evaluations, form=form)

@external_evaluations_bp.route('/evaluations/<int:id>/edit', methods=['POST'])
@login_required
def edit_evaluation(id):
    evaluation = filter_by_tenant(Evaluation.query, Evaluation).filter_by(id=id, origin='Externa').first_or_404()
    
    form = EvaluationForm()
    
    type_val = request.form.get('type')
    origin_val = 'Externa'
    multiple_components = request.form.get('multiple_components') == '1'
    partner_institution_id = request.form.get('partner_institution_id', type=int)
    school_year = request.form.get('school_year', type=int)
    cycle = request.form.get('cycle', type=int)
    
    if type_val and school_year and cycle is not None:
        partner = filter_by_tenant(PartnerInstitution.query, PartnerInstitution).filter_by(id=partner_institution_id).first() if partner_institution_id else None
        partner_name = partner.name if partner else "Sem Instituição"
        eval_name = f"{type_val} - {partner_name} - {school_year} - Ciclo {cycle}"
        
        existing = filter_by_tenant(Evaluation.query, Evaluation).filter(
            Evaluation.id != id,
            Evaluation.origin == 'Externa',
            Evaluation.type == type_val,
            Evaluation.partner_institution_id == (partner_institution_id if partner_institution_id else None),
            Evaluation.school_year == school_year,
            Evaluation.cycle == cycle
        ).first()
        
        if existing:
            flash("Já existe uma avaliação externa cadastrada com este Tipo, Instituição Parceira, Ano Letivo e Ciclo.", "danger")
            return redirect(url_for('external_evaluations.list_evaluations'))
            
        evaluation.name = eval_name
        evaluation.type = type_val
        evaluation.origin = origin_val
        evaluation.multiple_components = multiple_components
        evaluation.school_year = school_year
        evaluation.cycle = cycle
        
        if partner_institution_id:
            evaluation.partner_institution_id = partner_institution_id
        else:
            evaluation.partner_institution_id = None
        
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename != '':
            filename = secure_filename(logo_file.filename)
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'logos')
            os.makedirs(upload_folder, exist_ok=True)
            evaluation.logo_path = f'uploads/logos/{filename}'
            logo_file.save(os.path.join(upload_folder, filename))
            
        db.session.commit()
        log_audit('update_evaluation', 'evaluation', evaluation.id, f"Atualizou avaliação externa {evaluation.name}")
        flash('Avaliação externa atualizada com sucesso!', 'success')
    else:
        flash('Erro ao editar avaliação: Preencha todos os campos obrigatórios.', 'danger')
        
    return redirect(url_for('external_evaluations.list_evaluations'))

@external_evaluations_bp.route('/evaluations/<int:id>/delete', methods=['POST'])
@login_required
def delete_evaluation(id):
    evaluation = filter_by_tenant(Evaluation.query, Evaluation).filter_by(id=id, origin='Externa').first_or_404()
    
    if evaluation.exams.count() > 0:
        flash('Não é possível excluir esta avaliação pois existem provas vinculadas a ela.', 'danger')
        return redirect(url_for('external_evaluations.list_evaluations'))
        
    db.session.delete(evaluation)
    db.session.commit()
    log_audit('delete_evaluation', 'evaluation', id, f"Excluiu avaliação externa {evaluation.name}")
    flash('Avaliação externa excluída com sucesso!', 'success')
    return redirect(url_for('external_evaluations.list_evaluations'))

@external_evaluations_bp.route('/evaluations/<int:id>/students', methods=['GET', 'POST'])
@login_required
def list_students(id):
    evaluation = filter_by_tenant(Evaluation.query, Evaluation).filter_by(id=id, origin='Externa').first_or_404()
    form = ImportExternalStudentForm()
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    query = filter_by_tenant(ExternalEvaluationStudent.query, ExternalEvaluationStudent).filter_by(evaluation_id=id)
    
    if search:
        query = query.filter(ExternalEvaluationStudent.alu_nome.ilike(f'%{search}%'))
        
    students = query.order_by(ExternalEvaluationStudent.alu_nome).paginate(page=page, per_page=30)
    
    return render_template('external_evaluations/students.html', evaluation=evaluation, students=students, form=form)

@external_evaluations_bp.route('/evaluations/<int:id>/import_students', methods=['POST'])
@login_required
def import_students(id):
    evaluation = filter_by_tenant(Evaluation.query, Evaluation).filter_by(id=id, origin='Externa').first_or_404()
    form = ImportExternalStudentForm()
    
    if form.validate_on_submit():
        if form.school_year.data is None or form.school_year.data == '':
            flash("O Ano Letivo é obrigatório para Avaliações Externas.", "danger")
            return redirect(request.url)
        if form.cycle.data is None or form.cycle.data == '':
            flash("O Ciclo é obrigatório para Avaliações Externas.", "danger")
            return redirect(request.url)
        file = form.file.data
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        
        content = file.read()
        
        task_id = start_import_task(0)
        
        import threading
        thread = threading.Thread(target=process_student_import, args=(task_id, content, ext, id, get_tenant_id()))
        thread.start()
        
    
        
    return jsonify({'success': True, 'task_id': task_id, 'message': 'Importação iniciada com sucesso. Acompanhe o progresso.'})
        
    return jsonify({'success': False, 'message': 'Arquivo inválido.'}), 400

def process_student_import(task_id, file_content, ext, evaluation_id, tenant_id):
    from app import create_app
    app = create_app()
    with app.app_context():
        try:
            if ext == 'csv':
                # Use str as dtype for all to prevent pandas from mangling numbers
                df = pd.read_csv(io.BytesIO(file_content), sep=';', dtype=str)
            else:
                df = pd.read_excel(io.BytesIO(file_content), dtype=str)
                
            total_records = len(df)
            if total_records == 0:
                finish_import_task(task_id, 0)
                return
                
            from app.import_utils import import_progress
            if task_id in import_progress:
                import_progress[task_id]['total'] = total_records
                
            update_import_progress(task_id, 0, 'Processando planilha...')
            
            existing_students = ExternalEvaluationStudent.query.filter_by(
                tenant_id=tenant_id, 
                evaluation_id=evaluation_id
            ).all()
            
            existing_map = {s.alu_id: s for s in existing_students if s.alu_id}
            
            students_to_insert = []
            processed = 0
            
            for index, row in df.iterrows():
                # Get fields safely, defaulting to empty string if missing/NaN
                def get_val(col):
                    val = row.get(col)
                    return str(val) if pd.notna(val) else None
                
                alu_id = get_val('ALU_ID')
                
                if alu_id and alu_id in existing_map:
                    # Update existing
                    student = existing_map[alu_id]
                    student.mun_id = get_val('MUN_ID')
                    student.mun_nome = get_val('MUN_NOME')
                    student.esc_id = get_val('ESC_ID')
                    student.esc_nome = get_val('ESC_NOME')
                    student.esc_inep = get_val('ESC_INEP')
                    student.ser_number = get_val('SER_NUMBER')
                    student.ser_nome = get_val('SER_NOME')
                    student.tur_id = get_val('TUR_ID')
                    student.tur_nome = get_val('TUR_NOME')
                    student.tur_periodo = get_val('TUR_PERIODO')
                    student.alu_inep = get_val('ALU_INEP')
                    student.alu_nome = get_val('ALU_NOME')
                    student.alu_nome_mae = get_val('ALU_NOME_MAE')
                    student.alu_nome_pai = get_val('ALU_NOME_PAI')
                    student.alu_nome_resp = get_val('ALU_NOME_RESP')
                    student.alu_dt_nasc = get_val('ALU_DT_NASC')
                    student.alu_tel1 = get_val('ALU_TEL1')
                    student.alu_tel2 = get_val('ALU_TEL2')
                    student.alu_email = get_val('ALU_EMAIL')
                    student.alu_uf = get_val('ALU_UF')
                    student.alu_endereco = get_val('ALU_ENDERECO')
                    student.alu_cidade = get_val('ALU_CIDADE')
                    student.alu_numero = get_val('ALU_NUMERO')
                    student.alu_complemento = get_val('ALU_COMPLEMENTO')
                    student.alu_bairro = get_val('ALU_BAIRRO')
                    student.alu_cep = get_val('ALU_CEP')
                    student.alu_ativo = get_val('ALU_ATIVO')
                    student.alu_status = get_val('ALU_STATUS')
                    student.alu_cpf = get_val('ALU_CPF')
                    student.pel_nome = get_val('PEL_NOME')
                    student.gen_nome = get_val('GEN_NOME')
                else:
                    # Insert new
                    student = ExternalEvaluationStudent(
                        tenant_id=tenant_id,
                        evaluation_id=evaluation_id,
                        mun_id=get_val('MUN_ID'),
                        mun_nome=get_val('MUN_NOME'),
                        esc_id=get_val('ESC_ID'),
                        esc_nome=get_val('ESC_NOME'),
                        esc_inep=get_val('ESC_INEP'),
                        ser_number=get_val('SER_NUMBER'),
                        ser_nome=get_val('SER_NOME'),
                        tur_id=get_val('TUR_ID'),
                        tur_nome=get_val('TUR_NOME'),
                        tur_periodo=get_val('TUR_PERIODO'),
                        alu_id=alu_id,
                        alu_inep=get_val('ALU_INEP'),
                        alu_nome=get_val('ALU_NOME'),
                        alu_nome_mae=get_val('ALU_NOME_MAE'),
                        alu_nome_pai=get_val('ALU_NOME_PAI'),
                        alu_nome_resp=get_val('ALU_NOME_RESP'),
                        alu_dt_nasc=get_val('ALU_DT_NASC'),
                        alu_tel1=get_val('ALU_TEL1'),
                        alu_tel2=get_val('ALU_TEL2'),
                        alu_email=get_val('ALU_EMAIL'),
                        alu_uf=get_val('ALU_UF'),
                        alu_endereco=get_val('ALU_ENDERECO'),
                        alu_cidade=get_val('ALU_CIDADE'),
                        alu_numero=get_val('ALU_NUMERO'),
                        alu_complemento=get_val('ALU_COMPLEMENTO'),
                        alu_bairro=get_val('ALU_BAIRRO'),
                        alu_cep=get_val('ALU_CEP'),
                        alu_ativo=get_val('ALU_ATIVO'),
                        alu_status=get_val('ALU_STATUS'),
                        alu_cpf=get_val('ALU_CPF'),
                        pel_nome=get_val('PEL_NOME'),
                        gen_nome=get_val('GEN_NOME')
                    )
                    students_to_insert.append(student)
                
                processed += 1
                
                # Commit updates and bulk insert new records periodically
                if processed % 500 == 0:
                    if students_to_insert:
                        db.session.bulk_save_objects(students_to_insert)
                        students_to_insert = []
                    db.session.commit()
                    update_import_progress(task_id, processed, 'Processando alunos...')
                    
            if students_to_insert:
                db.session.bulk_save_objects(students_to_insert)
            db.session.commit()
                
            finish_import_task(task_id, processed)
            
        except Exception as e:
            fail_import_task(task_id, str(e))

@external_evaluations_bp.route('/evaluations/<int:id>/results', methods=['GET', 'POST'])
@login_required
def list_results(id):
    evaluation = filter_by_tenant(Evaluation.query, Evaluation).filter_by(id=id, origin='Externa').first_or_404()
    form = ImportExternalResultForm()
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    
    query = filter_by_tenant(ExternalEvaluationResult.query, ExternalEvaluationResult).filter_by(evaluation_id=id)
    
    if search:
        query = query.outerjoin(ExternalEvaluationResult.student).filter(
            db.or_(
                ExternalEvaluationResult.alu_id.ilike(f'%{search}%'),
                ExternalEvaluationStudent.alu_nome.ilike(f'%{search}%')
            )
        )
        
    results = query.outerjoin(ExternalEvaluationResult.student).order_by(ExternalEvaluationStudent.alu_nome, ExternalEvaluationResult.alu_id).paginate(page=page, per_page=30)
    
    return render_template('external_evaluations/results.html', evaluation=evaluation, results=results, form=form)

@external_evaluations_bp.route('/evaluations/<int:id>/import_results', methods=['POST'])
@login_required
def import_results(id):
    evaluation = filter_by_tenant(Evaluation.query, Evaluation).filter_by(id=id, origin='Externa').first_or_404()
    form = ImportExternalResultForm()
    
    if form.validate_on_submit():
        if form.school_year.data is None or form.school_year.data == '':
            flash("O Ano Letivo é obrigatório para Avaliações Externas.", "danger")
            return redirect(request.url)
        if form.cycle.data is None or form.cycle.data == '':
            flash("O Ciclo é obrigatório para Avaliações Externas.", "danger")
            return redirect(request.url)
        file = form.file.data
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower()
        
        content = file.read()
        
        from app.import_utils import start_import_task
        task_id = start_import_task(0)
        
        import threading
        thread = threading.Thread(target=process_result_import, args=(task_id, content, ext, id, get_tenant_id()))
        thread.start()
        
        from flask import jsonify
        return jsonify({'success': True, 'task_id': task_id, 'message': 'Importação iniciada com sucesso. Acompanhe o progresso.'})
        
    from flask import jsonify
    return jsonify({'success': False, 'message': 'Arquivo inválido.'}), 400

def process_result_import(task_id, file_content, ext, evaluation_id, tenant_id):
    from app import create_app
    app = create_app()
    with app.app_context():
        from app.import_utils import finish_import_task, fail_import_task, update_import_progress, import_progress
        try:
            if ext == 'csv':
                df = pd.read_csv(io.BytesIO(file_content), sep=';', dtype=str)
            else:
                df = pd.read_excel(io.BytesIO(file_content), dtype=str)
                
            total_records = len(df)
            if total_records == 0:
                finish_import_task(task_id, 0)
                return
                
            if task_id in import_progress:
                import_progress[task_id]['total'] = total_records
                
            update_import_progress(task_id, 0, 'Processando planilha...')
            
            existing_students = ExternalEvaluationStudent.query.filter_by(
                tenant_id=tenant_id,
                evaluation_id=evaluation_id
            ).all()
            student_map = {s.alu_id: s.id for s in existing_students if s.alu_id}
            
            # Para os resultados, sendo por alternativa, é melhor apagar todos e reinserir da planilha atualizada.
            db.session.execute(db.delete(ExternalEvaluationResult).where(
                db.and_(
                    ExternalEvaluationResult.tenant_id == tenant_id,
                    ExternalEvaluationResult.evaluation_id == evaluation_id
                )
            ))
            db.session.commit()
            
            results_to_insert = []
            processed = 0
            
            for index, row in df.iterrows():
                def get_val(col):
                    val = row.get(col)
                    return str(val) if pd.notna(val) else None
                    
                alu_id = get_val('ALU_ID')
                student_id = student_map.get(alu_id)
                
                result = ExternalEvaluationResult(
                    tenant_id=tenant_id,
                    evaluation_id=evaluation_id,
                    external_evaluation_student_id=student_id,
                    alu_id=alu_id,
                    mun_uf=get_val('MUN_UF'),
                    mun_ibge=get_val('MUN_IBGE'),
                    esc_inep=get_val('ESC_INEP'),
                    ser_number=get_val('SER_NUMBER'),
                    ser_nome=get_val('SER_NOME'),
                    tur_periodo=get_val('TUR_PERIODO'),
                    tur_nome=get_val('TUR_NOME'),
                    ava_nome=get_val('AVA_NOME'),
                    ava_ano=get_val('AVA_ANO'),
                    tes_id=get_val('TES_ID'),
                    dis_nome=get_val('DIS_NOME'),
                    alt_finalizado=get_val('ALT_FINALIZADO'),
                    alt_justificativa=get_val('ALT_JUSTIFICATIVA'),
                    nr_questao=get_val('NR_QUESTAO'),
                    teg_ordem=get_val('TEG_ORDEM'),
                    atr_resposta=get_val('ATR_RESPOSTA'),
                    atr_certo=get_val('ATR_CERTO'),
                    mti_codigo=get_val('MTI_CODIGO')
                )
                results_to_insert.append(result)
                processed += 1
                
                if len(results_to_insert) >= 500:
                    db.session.bulk_save_objects(results_to_insert)
                    db.session.commit()
                    update_import_progress(task_id, processed, 'Processando resultados...')
                    results_to_insert = []
                    
            if results_to_insert:
                db.session.bulk_save_objects(results_to_insert)
                db.session.commit()
                
            finish_import_task(task_id, processed)
            
        except Exception as e:
            fail_import_task(task_id, str(e))

from sqlalchemy import func
from app.models import TeachingUnit

@external_evaluations_bp.route('/dashboard')
@login_required
def dashboard():
    evaluations = filter_by_tenant(Evaluation.query, Evaluation).filter_by(origin='Externa').order_by(Evaluation.name).all()
    selected_id = request.args.get('evaluation_id', type=int)
    
    evaluation = None
    available_years = []
    
    if selected_id:
        evaluation = filter_by_tenant(Evaluation.query, Evaluation).filter_by(id=selected_id, origin='Externa').first()
        if evaluation:
            available_years = [r[0] for r in db.session.query(ExternalEvaluationStudent.ser_nome).filter_by(evaluation_id=selected_id).distinct().all() if r[0]]
                
    return render_template('external_evaluations/dashboard.html', evaluations=evaluations, evaluation=evaluation, available_years=available_years, active_page='external_evaluations')

@external_evaluations_bp.route('/evaluations/<int:id>/dashboard_filters_api')
@login_required
def dashboard_filters_api(id):
    year = request.args.get('year')
    if not year:
        return jsonify({'disciplines': [], 'shifts': []})
        
    q_base = db.session.query(ExternalEvaluationStudent).filter(
        ExternalEvaluationStudent.evaluation_id == id, ExternalEvaluationStudent.ser_nome == year
    )
    
    available_shifts = [r[0] for r in q_base.with_entities(ExternalEvaluationStudent.tur_periodo).distinct().all() if r[0]]
    
    q_res = db.session.query(ExternalEvaluationResult).join(
        ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).filter(
        ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationStudent.ser_nome == year
    )
    
    available_disciplines = [r[0] for r in q_res.with_entities(ExternalEvaluationResult.dis_nome).distinct().all() if r[0]]
    
    return jsonify({
        'disciplines': available_disciplines,
        'shifts': available_shifts
    })

@external_evaluations_bp.route('/school_results')
@login_required
def school_results():
    tenant_id = get_tenant_id()
    
    evaluations = filter_by_tenant(Evaluation.query, Evaluation).filter_by(origin='Externa').all()
    
    evaluation_id = request.args.get('evaluation_id', type=int)
    year = request.args.get('year')
    
    q_years = db.session.query(ExternalEvaluationStudent.ser_nome).distinct()
    if evaluation_id:
        q_years = q_years.filter_by(evaluation_id=evaluation_id)
    years = [y[0] for y in q_years.all() if y[0]]
    
    results_data = {}
    disciplines = []
    
    if evaluation_id and year:
        # Optimization: group by first in DB if possible, but calculating proficiencies per student
        # is easier in Python since we need to categorize students by level (Abaixo do basico, etc.)
        
        q = db.session.query(
            ExternalEvaluationResult.esc_inep,
            ExternalEvaluationResult.dis_nome,
            ExternalEvaluationStudent.tur_nome,
            ExternalEvaluationStudent.id.label('student_id'),
            db.func.sum(db.cast(ExternalEvaluationResult.atr_certo == '1', db.Integer)).label('correct_q'),
            db.func.count(ExternalEvaluationResult.id).label('total_q')
        ).join(
            ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
        ).filter(
            ExternalEvaluationResult.evaluation_id == evaluation_id,
            ExternalEvaluationStudent.ser_nome == year,
            ExternalEvaluationResult.alt_finalizado == '1',
            ExternalEvaluationResult.nr_questao.isnot(None),
            ExternalEvaluationResult.nr_questao != ''
        ).group_by(
            ExternalEvaluationResult.esc_inep,
            ExternalEvaluationResult.dis_nome,
            ExternalEvaluationStudent.tur_nome,
            ExternalEvaluationStudent.id
        )
        
        student_results = q.all()
        
        from app.models import TeachingUnit
        schools = TeachingUnit.query.filter_by(tenant_id=tenant_id, type='Escola').all()
        school_names = {s.inep_code: s.name for s in schools if s.inep_code}
        
        for esc_inep, dis_nome, tur_nome, std_id, correct_q, total_q in student_results:
            if not esc_inep: continue
            if not dis_nome: continue
            if not tur_nome: tur_nome = 'Turma Desconhecida'
            
            if dis_nome not in disciplines:
                disciplines.append(dis_nome)
                
            if esc_inep not in results_data:
                results_data[esc_inep] = {
                    'inep': esc_inep,
                    'name': school_names.get(esc_inep, 'Escola Desconhecida'),
                    'disciplines': {}
                }
                
            if dis_nome not in results_data[esc_inep]['disciplines']:
                results_data[esc_inep]['disciplines'][dis_nome] = {
                    'total_correct': 0,
                    'total_questions': 0,
                    'students': [],
                    'turmas': {}
                }
                
            stats = results_data[esc_inep]['disciplines'][dis_nome]
            stats['total_correct'] += int(correct_q or 0)
            stats['total_questions'] += int(total_q or 0)
            student_dict = {'correct': int(correct_q or 0), 'total': int(total_q or 0)}
            stats['students'].append(student_dict)
            
            if tur_nome not in stats['turmas']:
                stats['turmas'][tur_nome] = {
                    'name': tur_nome,
                    'total_correct': 0,
                    'total_questions': 0,
                    'students': []
                }
            t_stats = stats['turmas'][tur_nome]
            t_stats['total_correct'] += int(correct_q or 0)
            t_stats['total_questions'] += int(total_q or 0)
            t_stats['students'].append(student_dict)
            
        def process_stats(stats):
            if stats['total_questions'] > 0:
                avg_prof = (stats['total_correct'] / stats['total_questions']) * 100
            else:
                avg_prof = 0
                
            levels = {'Abaixo do básico': 0, 'Básico': 0, 'Proficiente': 0, 'Avançado': 0}
            total_students = len(stats['students'])
            
            for sinfo in stats['students']:
                if sinfo['total'] > 0:
                    pct = (sinfo['correct'] / sinfo['total']) * 100
                    if pct < 25: levels['Abaixo do básico'] += 1
                    elif pct < 50: levels['Básico'] += 1
                    elif pct < 75: levels['Proficiente'] += 1
                    else: levels['Avançado'] += 1
                    
            level_pcts = {k: (v / total_students * 100) if total_students > 0 else 0 for k, v in levels.items()}
            
            stats['avg_prof'] = avg_prof
            stats['levels'] = levels
            stats['level_pcts'] = level_pcts
            stats['total_students'] = total_students
            
            if 'students' in stats:
                del stats['students']
            
        for inep, sdata in results_data.items():
            for dis, stats in sdata['disciplines'].items():
                process_stats(stats)
                for t_name, t_stats in stats['turmas'].items():
                    process_stats(t_stats)
    
    return render_template('external_evaluations/school_results.html', 
                           evaluations=evaluations, 
                           years=years,
                           evaluation_id=evaluation_id,
                           year=year,
                           results_data=results_data,
                           disciplines=disciplines)

@external_evaluations_bp.route('/turma_students_api')
@login_required
def turma_students_api():
    evaluation_id = request.args.get('evaluation_id')
    esc_inep = request.args.get('esc_inep')
    dis_nome = request.args.get('dis_nome')
    tur_nome = request.args.get('tur_nome')
    
    if not all([evaluation_id, esc_inep, dis_nome, tur_nome]):
        return jsonify({'error': 'Missing parameters'}), 400
        
    q = db.session.query(
        ExternalEvaluationStudent.alu_nome,
        db.func.sum(db.cast(ExternalEvaluationResult.atr_certo == '1', db.Integer)).label('correct_q'),
        db.func.count(ExternalEvaluationResult.id).label('total_q')
    ).join(
        ExternalEvaluationResult, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).filter(
        ExternalEvaluationResult.evaluation_id == evaluation_id,
        ExternalEvaluationResult.esc_inep == esc_inep,
        ExternalEvaluationResult.dis_nome == dis_nome,
        ExternalEvaluationStudent.tur_nome == tur_nome,
        ExternalEvaluationResult.alt_finalizado == '1',
        ExternalEvaluationResult.nr_questao.isnot(None),
        ExternalEvaluationResult.nr_questao != ''
    ).group_by(
        ExternalEvaluationStudent.id,
        ExternalEvaluationStudent.alu_nome
    ).order_by(
        ExternalEvaluationStudent.alu_nome
    )
    
    students = []
    for alu_nome, correct_q, total_q in q.all():
        total = int(total_q or 0)
        correct = int(correct_q or 0)
        pct = (correct / total * 100) if total > 0 else 0
        
        level = 'Abaixo do básico'
        if pct >= 75:
            level = 'Avançado'
        elif pct >= 50:
            level = 'Proficiente'
        elif pct >= 25:
            level = 'Básico'
            
        students.append({
            'name': alu_nome or 'Aluno Desconhecido',
            'correct': correct,
            'total': total,
            'prof': round(pct, 1),
            'level': level
        })
        
    return jsonify({'students': students})

@external_evaluations_bp.route('/print_school_report')
@login_required
def print_school_report():
    evaluation_id = request.args.get('evaluation_id')
    year = request.args.get('year')
    esc_inep = request.args.get('esc_inep')
    
    if not all([evaluation_id, year, esc_inep]):
        return "Parâmetros inválidos", 400
        
    evaluation = Evaluation.query.get(evaluation_id)
    school_name = db.session.query(ExternalEvaluationStudent.esc_nome).filter(
        ExternalEvaluationStudent.esc_inep == esc_inep
    ).first()
    school_name = school_name[0] if school_name else 'Escola Desconhecida'
    
    q = db.session.query(
        ExternalEvaluationResult.dis_nome,
        ExternalEvaluationStudent.tur_nome,
        db.func.sum(db.cast(ExternalEvaluationResult.atr_certo == '1', db.Integer)).label('correct_q'),
        db.func.count(ExternalEvaluationResult.id).label('total_q'),
        ExternalEvaluationStudent.id.label('student_id')
    ).join(
        ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).filter(
        ExternalEvaluationResult.evaluation_id == evaluation_id,
        ExternalEvaluationStudent.ser_nome == year,
        ExternalEvaluationResult.esc_inep == esc_inep,
        ExternalEvaluationResult.alt_finalizado == '1',
        ExternalEvaluationResult.nr_questao.isnot(None),
        ExternalEvaluationResult.nr_questao != ''
    ).group_by(
        ExternalEvaluationResult.dis_nome,
        ExternalEvaluationStudent.tur_nome,
        ExternalEvaluationStudent.id
    )
    
    student_results = q.all()
    
    disciplines_data = {}
    
    for dis_nome, tur_nome, correct_q, total_q, std_id in student_results:
        if not dis_nome: continue
        if not tur_nome: tur_nome = 'Turma Desconhecida'
        
        if dis_nome not in disciplines_data:
            disciplines_data[dis_nome] = {
                'total_correct': 0, 'total_questions': 0, 'students': [], 'turmas': {}
            }
            
        stats = disciplines_data[dis_nome]
        stats['total_correct'] += int(correct_q or 0)
        stats['total_questions'] += int(total_q or 0)
        student_dict = {'correct': int(correct_q or 0), 'total': int(total_q or 0)}
        stats['students'].append(student_dict)
        
        if tur_nome not in stats['turmas']:
            stats['turmas'][tur_nome] = {
                'name': tur_nome, 'total_correct': 0, 'total_questions': 0, 'students': []
            }
        t_stats = stats['turmas'][tur_nome]
        t_stats['total_correct'] += int(correct_q or 0)
        t_stats['total_questions'] += int(total_q or 0)
        t_stats['students'].append(student_dict)
        
    def process_stats(stats):
        if stats['total_questions'] > 0:
            avg_prof = (stats['total_correct'] / stats['total_questions']) * 100
        else:
            avg_prof = 0
            
        levels = {'Abaixo do básico': 0, 'Básico': 0, 'Proficiente': 0, 'Avançado': 0}
        total_students = len(stats['students'])
        
        for sinfo in stats['students']:
            if sinfo['total'] > 0:
                pct = (sinfo['correct'] / sinfo['total']) * 100
                if pct < 25: levels['Abaixo do básico'] += 1
                elif pct < 50: levels['Básico'] += 1
                elif pct < 75: levels['Proficiente'] += 1
                else: levels['Avançado'] += 1
                
        level_pcts = {k: (v / total_students * 100) if total_students > 0 else 0 for k, v in levels.items()}
        
        stats['avg_prof'] = avg_prof
        stats['levels'] = levels
        stats['level_pcts'] = level_pcts
        stats['total_students'] = total_students
        if 'students' in stats: del stats['students']
        
    for dis, stats in disciplines_data.items():
        process_stats(stats)
        for t_name, t_stats in stats['turmas'].items():
            process_stats(t_stats)
            
    html = render_template('external_evaluations/pdf_school_report.html',
                           school_name=school_name,
                           evaluation_name=evaluation.name if evaluation else '',
                           year=year,
                           disciplines_data=disciplines_data)
                           
    dest = io.BytesIO()
    pisa.CreatePDF(html, dest=dest)
    dest.seek(0)
    
    return send_file(dest, download_name=f"relatorio_escola_{esc_inep}.pdf", as_attachment=True, mimetype='application/pdf')

@external_evaluations_bp.route('/print_turma_students_report')
@login_required
def print_turma_students_report():
    evaluation_id = request.args.get('evaluation_id')
    esc_inep = request.args.get('esc_inep')
    dis_nome = request.args.get('dis_nome')
    tur_nome = request.args.get('tur_nome')
    
    if not all([evaluation_id, esc_inep, dis_nome, tur_nome]):
        return "Parâmetros inválidos", 400
        
    evaluation = Evaluation.query.get(evaluation_id)
    school_name = db.session.query(ExternalEvaluationStudent.esc_nome).filter(
        ExternalEvaluationStudent.esc_inep == esc_inep
    ).first()
    school_name = school_name[0] if school_name else 'Escola Desconhecida'
        
    q = db.session.query(
        ExternalEvaluationStudent.alu_nome,
        db.func.sum(db.cast(ExternalEvaluationResult.atr_certo == '1', db.Integer)).label('correct_q'),
        db.func.count(ExternalEvaluationResult.id).label('total_q')
    ).join(
        ExternalEvaluationResult, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).filter(
        ExternalEvaluationResult.evaluation_id == evaluation_id,
        ExternalEvaluationResult.esc_inep == esc_inep,
        ExternalEvaluationResult.dis_nome == dis_nome,
        ExternalEvaluationStudent.tur_nome == tur_nome,
        ExternalEvaluationResult.alt_finalizado == '1',
        ExternalEvaluationResult.nr_questao.isnot(None),
        ExternalEvaluationResult.nr_questao != ''
    ).group_by(
        ExternalEvaluationStudent.id,
        ExternalEvaluationStudent.alu_nome
    ).order_by(
        ExternalEvaluationStudent.alu_nome
    )
    
    students = []
    for alu_nome, correct_q, total_q in q.all():
        total = int(total_q or 0)
        correct = int(correct_q or 0)
        pct = (correct / total * 100) if total > 0 else 0
        
        level = 'Abaixo do básico'
        if pct >= 75:
            level = 'Avançado'
        elif pct >= 50:
            level = 'Proficiente'
        elif pct >= 25:
            level = 'Básico'
            
        students.append({
            'name': alu_nome or 'Aluno Desconhecido',
            'correct': correct,
            'total': total,
            'prof': round(pct, 1),
            'level': level
        })
        
    html = render_template('external_evaluations/pdf_turma_students.html',
                           school_name=school_name,
                           evaluation_name=evaluation.name if evaluation else '',
                           dis_nome=dis_nome,
                           tur_nome=tur_nome,
                           students=students)
                           
    dest = io.BytesIO()
    pisa.CreatePDF(html, dest=dest)
    dest.seek(0)
    
    return send_file(dest, download_name=f"relatorio_alunos_{tur_nome}.pdf".replace(' ', '_'), as_attachment=True, mimetype='application/pdf')

@external_evaluations_bp.route('/evaluations/<int:id>/dashboard_api')
@login_required
def dashboard_api(id):
    year = request.args.get('year')
    if not year:
        return jsonify({'drilldown': [], 'race': [], 'gender': [], 'radar': [], 'justifications': [], 'summary': {}, 'donut': []})
    level = request.args.get('level', 'rede')
    
    filter_dis_nome = request.args.get('filter_dis_nome')
    filter_shift = request.args.get('filter_shift')
    
    regional_id = request.args.get('regional_id')
    school_inep = request.args.get('school_inep')
    ser_nome = request.args.get('ser_nome')
    tur_nome = request.args.get('tur_nome')
    
    tenant_id = get_tenant_id()
    
    # Base query for results
    q = db.session.query(ExternalEvaluationResult, ExternalEvaluationStudent).join(
        ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationStudent.ser_nome == year)
    
    if filter_dis_nome:
        q = q.filter(ExternalEvaluationResult.dis_nome == filter_dis_nome)
    if filter_shift:
        q = q.filter(ExternalEvaluationStudent.tur_periodo == filter_shift)
        
    # We also need to join TeachingUnit to know Regional
    # external_evaluation_result.esc_inep -> TeachingUnit.inep_code
    SchoolAlias = db.aliased(TeachingUnit)
    RegionalAlias = db.aliased(TeachingUnit)
    
    q = q.outerjoin(SchoolAlias, db.and_(SchoolAlias.inep_code == ExternalEvaluationResult.esc_inep, SchoolAlias.tenant_id == tenant_id, SchoolAlias.type == 'Escola'))
    q = q.outerjoin(RegionalAlias, RegionalAlias.id == SchoolAlias.parent_id)
    
    # Apply drill-down filters
    if regional_id:
        q = q.filter(RegionalAlias.id == regional_id)
    if school_inep:
        q = q.filter(ExternalEvaluationResult.esc_inep == school_inep)
    if ser_nome:
        q = q.filter(ExternalEvaluationStudent.ser_nome == ser_nome)
    if tur_nome:
        q = q.filter(ExternalEvaluationStudent.tur_nome == tur_nome)

    def calculate_percent(query, group_by_col, id_col=None):
        # We need to count total questions and correct questions grouped by group_by_col
        # Correct questions: atr_certo in ('1', 'true', 'certo', 'True', 'CERTO')
        results = query.all()
        
        groups = {}
        for r, s in results:
            # Determine group label
            if isinstance(group_by_col, str):
                if hasattr(s, group_by_col):
                    label = getattr(s, group_by_col)
                elif hasattr(r, group_by_col):
                    label = getattr(r, group_by_col)
                else:
                    label = 'Desconhecido'
            else:
                # If we passed a callable (like for regional)
                label = group_by_col(r, s)
                
            if not label:
                label = 'Não Informado'
                
            group_id = label
            if id_col:
                group_id = id_col(r, s) or label
                
            if group_id not in groups:
                groups[group_id] = {'label': label, 'total': 0, 'correct': 0}
                
            groups[group_id]['total'] += 1
            if str(r.atr_certo).lower() in ('1', 'true', 'certo'):
                groups[group_id]['correct'] += 1
                
        out = []
        for gid, data in groups.items():
            pct = (data['correct'] / data['total'] * 100) if data['total'] > 0 else 0
            out.append({
                'id': gid,
                'label': data['label'],
                'value': round(pct, 2)
            })
            
        out.sort(key=lambda x: x['label'])
        return out

    # Drilldown Chart
    drilldown_data = []
    
    # Load all to memory since we need it for everything (SQLite handles a few thousand rows fine in memory, 
    # but we can optimize if needed. For now memory is fast).
    if level == 'rede':
        # Group by regional
        # Here we have to fetch the regional name from RegionalAlias
        def get_regional_label(r, s):
            # We can't easily get it without executing, let's just do an aggregated query using SQLAlchemy
            pass
            
    # For better performance, let's use SQLAlchemy aggregates
    # Subquery or group_by
    from sqlalchemy import case, cast, Float
    correct_condition = ExternalEvaluationResult.atr_certo.in_(['1', 'true', 'certo', 'True', 'CERTO'])
    correct_cases = case((correct_condition, 1), else_=0)
    absent_cases = case((ExternalEvaluationResult.alt_finalizado == '0', 1), else_=0)
    
    # Setup group columns for drilldown
    if level == 'rede':
        group_col = db.literal('Consolidado da Rede')
        id_col = db.literal('rede_total')
    elif level == 'regionals':
        group_col = RegionalAlias.name
        id_col = RegionalAlias.id
    elif level == 'school':
        group_col = SchoolAlias.name
        id_col = ExternalEvaluationResult.esc_inep
    elif level == 'year':
        group_col = ExternalEvaluationStudent.ser_nome
        id_col = ExternalEvaluationStudent.ser_nome
    elif level == 'class':
        group_col = ExternalEvaluationStudent.tur_nome
        id_col = ExternalEvaluationStudent.tur_nome
    elif level == 'student':
        group_col = ExternalEvaluationStudent.alu_nome
        id_col = ExternalEvaluationStudent.alu_id
    else:
        group_col = ExternalEvaluationStudent.alu_nome
        id_col = ExternalEvaluationStudent.alu_id
        
    # Build single student query
    q_student = db.session.query(
        ExternalEvaluationResult.external_evaluation_student_id,
        func.count(ExternalEvaluationResult.id).label('total_q'),
        func.sum(correct_cases).label('correct_q'),
        func.sum(absent_cases).label('absent_q'),
        func.max(ExternalEvaluationResult.alt_finalizado).label('finalizado'),
        func.max(ExternalEvaluationStudent.tur_nome).label('tur_nome'),
        func.max(ExternalEvaluationResult.esc_inep).label('esc_inep'),
        func.max(ExternalEvaluationStudent.alu_frequencia).label('alu_frequencia'),
        func.max(ExternalEvaluationStudent.pel_nome).label('pel_nome'),
        func.max(ExternalEvaluationStudent.gen_nome).label('gen_nome'),
        func.max(group_col).label('group_col_label'),
        func.max(id_col).label('group_col_id')
    ).join(
        ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationResult.ser_nome == year)
    
    if filter_dis_nome: q_student = q_student.filter(ExternalEvaluationResult.dis_nome == filter_dis_nome)
    if filter_shift: q_student = q_student.filter(ExternalEvaluationResult.tur_periodo == filter_shift)
    if school_inep: q_student = q_student.filter(ExternalEvaluationResult.esc_inep == school_inep)
    if ser_nome: q_student = q_student.filter(ExternalEvaluationResult.ser_nome == ser_nome)
    if tur_nome: q_student = q_student.filter(ExternalEvaluationResult.tur_nome == tur_nome)

    needs_regional_alias = level in ('regionals',) or regional_id
    needs_school_alias = level in ('school',) or needs_regional_alias
    
    if needs_school_alias:
        q_student = q_student.outerjoin(SchoolAlias, db.and_(SchoolAlias.inep_code == ExternalEvaluationResult.esc_inep, SchoolAlias.tenant_id == tenant_id, SchoolAlias.type == 'Escola'))
    if needs_regional_alias:
        q_student = q_student.outerjoin(RegionalAlias, RegionalAlias.id == SchoolAlias.parent_id)
        
    if regional_id:
        q_student = q_student.filter(RegionalAlias.id == regional_id)
            
    student_results = q_student.group_by(ExternalEvaluationResult.external_evaluation_student_id).all()
    
    # Compute race, gender, and drilldown in Python
    race_stats = {}
    gender_stats = {}
    drill_stats = {}
    
    for r in student_results:
        total_q = r.total_q or 0
        correct_q = r.correct_q or 0
        absent_q = r.absent_q or 0
        
        race = r.pel_nome or 'Não Informado'
        if race not in race_stats: race_stats[race] = {'total': 0, 'correct': 0, 'absent': 0}
        race_stats[race]['total'] += total_q
        race_stats[race]['correct'] += correct_q
        race_stats[race]['absent'] += absent_q
        
        gender = r.gen_nome or 'Não Informado'
        if gender not in gender_stats: gender_stats[gender] = {'total': 0, 'correct': 0, 'absent': 0}
        gender_stats[gender]['total'] += total_q
        gender_stats[gender]['correct'] += correct_q
        gender_stats[gender]['absent'] += absent_q
        
        drill_id = r.group_col_id or 'unknown'
        drill_label = r.group_col_label or 'Não Informado'
        if drill_id not in drill_stats:
            drill_stats[drill_id] = {'label': drill_label, 'total': 0, 'correct': 0, 'absent': 0, 'freq_sum': 0, 'freq_count': 0}
        drill_stats[drill_id]['total'] += total_q
        drill_stats[drill_id]['correct'] += correct_q
        drill_stats[drill_id]['absent'] += absent_q
        if r.alu_frequencia is not None:
            drill_stats[drill_id]['freq_sum'] += r.alu_frequencia
            drill_stats[drill_id]['freq_count'] += 1

    def stats_to_chart(stats_dict):
        out = []
        for label, data in stats_dict.items():
            pct = (data['correct'] / data['total'] * 100) if data['total'] > 0 else 0
            pct_abs = (data['absent'] / data['total'] * 100) if data['total'] > 0 else 0
            out.append({'label': label, 'value': round(pct, 2), 'absent': round(pct_abs, 2)})
        out.sort(key=lambda x: str(x['label']))
        return out
        
    race_data = stats_to_chart(race_stats)
    gender_data = stats_to_chart(gender_stats)
    
    drilldown_data = []
    freq_performance_data = []
    
    for drill_id, data in drill_stats.items():
        pct = (data['correct'] / data['total'] * 100) if data['total'] > 0 else 0
        pct_abs = (data['absent'] / data['total'] * 100) if data['total'] > 0 else 0
        drilldown_data.append({
            'id': drill_id,
            'label': data['label'],
            'value': round(pct, 2),
            'absent': round(pct_abs, 2)
        })
        
        if data['freq_count'] > 0:
            avg_freq = data['freq_sum'] / data['freq_count']
            freq_performance_data.append({
                'x': round(avg_freq, 1),
                'y': round(pct, 1),
                'label': data['label']
            })
            
    drilldown_data.sort(key=lambda x: str(x['label']))
    
    # Helper to calculate secondary charts using the SAME base filters (only used for radar_data now)
    def get_chart_data(group_col):
        q = db.session.query(
            group_col.label('label'),
            func.count(ExternalEvaluationResult.id).label('total'),
            func.sum(correct_cases).label('correct'),
            func.sum(absent_cases).label('absent')
        ).select_from(ExternalEvaluationResult).join(
            ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
        ).filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationResult.ser_nome == year)

        if needs_school_alias:
            q = q.outerjoin(SchoolAlias, db.and_(SchoolAlias.inep_code == ExternalEvaluationResult.esc_inep, SchoolAlias.tenant_id == tenant_id, SchoolAlias.type == 'Escola'))
        if needs_regional_alias:
            q = q.outerjoin(RegionalAlias, RegionalAlias.id == SchoolAlias.parent_id)
         
        if filter_dis_nome: q = q.filter(ExternalEvaluationResult.dis_nome == filter_dis_nome)
        if filter_shift: q = q.filter(ExternalEvaluationResult.tur_periodo == filter_shift)
        if regional_id: q = q.filter(RegionalAlias.id == regional_id)
        if school_inep: q = q.filter(ExternalEvaluationResult.esc_inep == school_inep)
        if ser_nome: q = q.filter(ExternalEvaluationResult.ser_nome == ser_nome)
        if tur_nome: q = q.filter(ExternalEvaluationResult.tur_nome == tur_nome)
        
        res = q.group_by(group_col).all()
        data = []
        for row in res:
            pct = (row.correct / row.total * 100) if row.total and row.total > 0 else 0
            pct_absent = (row.absent / row.total * 100) if row.total and row.total > 0 else 0
            data.append({'label': row.label or 'Não Informado', 'value': round(pct, 2), 'absent': round(pct_absent, 2)})
        return data

    radar_data = get_chart_data(ExternalEvaluationResult.mti_codigo)
    
    # Justifications for absence
    q_just = db.session.query(
        ExternalEvaluationResult.alt_justificativa.label('label'),
        func.count(ExternalEvaluationResult.id).label('total')
    ).select_from(ExternalEvaluationResult).join(
        ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationResult.ser_nome == year, ExternalEvaluationResult.alt_finalizado == '0')
     
    if needs_school_alias:
        q_just = q_just.outerjoin(SchoolAlias, db.and_(SchoolAlias.inep_code == ExternalEvaluationResult.esc_inep, SchoolAlias.tenant_id == tenant_id, SchoolAlias.type == 'Escola'))
    if needs_regional_alias:
        q_just = q_just.outerjoin(RegionalAlias, RegionalAlias.id == SchoolAlias.parent_id)
     
    if filter_dis_nome: q_just = q_just.filter(ExternalEvaluationResult.dis_nome == filter_dis_nome)
    if filter_shift: q_just = q_just.filter(ExternalEvaluationResult.tur_periodo == filter_shift)
    if regional_id: q_just = q_just.filter(RegionalAlias.id == regional_id)
    if school_inep: q_just = q_just.filter(ExternalEvaluationResult.esc_inep == school_inep)
    if ser_nome: q_just = q_just.filter(ExternalEvaluationResult.ser_nome == ser_nome)
    if tur_nome: q_just = q_just.filter(ExternalEvaluationResult.tur_nome == tur_nome)
    
    res_just = q_just.group_by(ExternalEvaluationResult.alt_justificativa).all()
    justifications_data = []
    for row in res_just:
        justifications_data.append({'label': row.label or 'Sem Justificativa', 'value': row.total})

    
    total_participants = 0
    total_completed = 0
    total_absent = 0
    total_correct_q = 0
    total_answered_q = 0
    
    level_counts = {'Abaixo do básico': 0, 'Básico': 0, 'Proficiente': 0, 'Avançado': 0}
    turmas = set()
    turmas_stats = {}
    school_stats = {}
    school_levels = {}
    
    for r in student_results:
        total_participants += 1
        
        t_key = None
        if r.tur_nome and r.esc_inep:
            t_key = f"{r.esc_inep}_{r.tur_nome}"
        elif r.tur_nome:
            t_key = r.tur_nome
            
        if t_key:
            turmas.add(t_key)
            if t_key not in turmas_stats:
                turmas_stats[t_key] = {'total': 0, 'completed': 0, 'correct_q': 0, 'total_q': 0, 'tur_nome': r.tur_nome, 'esc_inep': r.esc_inep}
            turmas_stats[t_key]['total'] += 1
            
        if r.finalizado == '1':
            total_completed += 1
            if t_key:
                turmas_stats[t_key]['completed'] += 1
                
            if r.esc_inep:
                if r.esc_inep not in school_stats:
                    school_stats[r.esc_inep] = {'correct_q': 0, 'total_q': 0}
                if r.total_q > 0:
                    school_stats[r.esc_inep]['correct_q'] += (r.correct_q or 0)
                    school_stats[r.esc_inep]['total_q'] += r.total_q
            
            if r.total_q > 0:
                if t_key:
                    turmas_stats[t_key]['correct_q'] += (r.correct_q or 0)
                    turmas_stats[t_key]['total_q'] += r.total_q
                
                total_correct_q += (r.correct_q or 0)
                total_answered_q += r.total_q
                pct = ((r.correct_q or 0) / r.total_q) * 100
                level_alcan = 'Avançado'
                if pct < 25: 
                    level_counts['Abaixo do básico'] += 1
                    level_alcan = 'Abaixo do básico'
                elif pct < 50: 
                    level_counts['Básico'] += 1
                    level_alcan = 'Básico'
                elif pct < 75: 
                    level_counts['Proficiente'] += 1
                    level_alcan = 'Proficiente'
                else: 
                    level_counts['Avançado'] += 1
                    
                if r.esc_inep:
                    if r.esc_inep not in school_levels:
                        school_levels[r.esc_inep] = set()
                    school_levels[r.esc_inep].add(level_alcan)
        else:
            total_absent += 1
            
    total_turmas = len(turmas)
    
    class_pcts = [v['completed'] / v['total'] * 100 for v in turmas_stats.values() if v['total'] > 0]
    avg_class_part_pct = (sum(class_pcts) / len(class_pcts)) if class_pcts else 0
    
    alunos_previstos = int(total_participants * 1.10)
    
    avg_proficiency = (total_correct_q / total_answered_q * 100) if total_answered_q > 0 else 0
    part_pct = (total_completed / total_participants * 100) if total_participants > 0 else 0
    absent_pct = (total_absent / total_participants * 100) if total_participants > 0 else 0
    alerta_pct = (level_counts['Abaixo do básico'] / total_completed * 100) if total_completed > 0 else 0
    
    if avg_proficiency < 50: status_rede = 'Crítico'
    elif avg_proficiency < 70: status_rede = 'Em evolução'
    else: status_rede = 'Excelente'
        
    summary_data = {
        'total_participants': total_participants,
        'total_completed': total_completed,
        'part_pct': round(part_pct, 1),
        'total_absent': total_absent,
        'absent_pct': round(absent_pct, 1),
        'avg_proficiency': round(avg_proficiency, 1),
        'alerta_qtd': level_counts['Abaixo do básico'],
        'alerta_pct': round(alerta_pct, 1),
        'status_rede': status_rede,
        'total_turmas': total_turmas,
        'avg_class_part_pct': round(avg_class_part_pct, 1),
        'alunos_previstos': alunos_previstos
    }
    
    donut_data = [
        {'label': 'Abaixo do básico', 'value': level_counts['Abaixo do básico']},
        {'label': 'Básico', 'value': level_counts['Básico']},
        {'label': 'Proficiente', 'value': level_counts['Proficiente']},
        {'label': 'Avançado', 'value': level_counts['Avançado']}
    ]

    school_proficiencies = []
    for inep, stats in school_stats.items():
        if stats['total_q'] > 0:
            prof = (stats['correct_q'] / stats['total_q']) * 100
            school_proficiencies.append({'inep_code': inep, 'proficiency': prof})

    class_proficiencies = []
    for t_key, stats in turmas_stats.items():
        if stats['total_q'] > 0:
            prof = (stats['correct_q'] / stats['total_q']) * 100
            class_proficiencies.append({
                'tur_nome': stats['tur_nome'] or 'N/A',
                'inep_code': stats['esc_inep'],
                'proficiency': prof
            })

    ranking_data = {'top': [], 'bottom': [], 'top_classes': [], 'bottom_classes': []}
    
    ineps = set()
    for s in school_proficiencies:
        if s['inep_code']: ineps.add(s['inep_code'])
    for c in class_proficiencies:
        if c['inep_code']: ineps.add(c['inep_code'])
        
    if ineps:
        SchoolAlias = db.aliased(db.Model._decl_class_registry.get('TeachingUnit', db.Model)) if not 'SchoolAlias' in locals() else SchoolAlias
        schools = SchoolAlias.query.filter(SchoolAlias.inep_code.in_(list(ineps)), SchoolAlias.tenant_id == tenant_id, SchoolAlias.type == 'Escola').all()
        schools_info = {}
        
        def format_time(start_date):
            if not start_date: return 'N/A'
            delta = datetime.today().date() - start_date
            years = delta.days // 365
            months = (delta.days % 365) // 30
            parts = []
            if years > 0: parts.append(f"{years} ano{'s' if years > 1 else ''}")
            if months > 0: parts.append(f"{months} mê{'s' if months == 1 else 'ses'}")
            if not parts: return "Menos de 1 mês"
            return " e ".join(parts)

        for sch in schools:
            schools_info[sch.inep_code] = {
                'name': sch.name,
                'regional': sch.parent.name if sch.parent else 'N/A',
                'director_name': sch.director_name or 'N/A',
                'director_time': format_time(sch.modulation_start_date),
                'coordinator_name': sch.coordinator_name or 'N/A',
                'coordinator_time': format_time(sch.coordinator_modulation_date),
                'latitude': sch.latitude,
                'longitude': sch.longitude
            }
            
        for s in school_proficiencies:
            info = schools_info.get(s['inep_code'], {})
            s.update({
                'name': info.get('name', 'Escola Desconhecida'),
                'regional': info.get('regional', 'N/A'),
                'director_name': info.get('director_name', 'N/A'),
                'director_time': info.get('director_time', 'N/A'),
                'coordinator_name': info.get('coordinator_name', 'N/A'),
                'coordinator_time': info.get('coordinator_time', 'N/A'),
                'proficiency_round': round(s['proficiency'], 1)
            })
            
        school_proficiencies.sort(key=lambda x: x['proficiency'], reverse=True)
        ranking_data['top'] = school_proficiencies[:15]
        
        school_proficiencies.sort(key=lambda x: x['proficiency'])
        ranking_data['bottom'] = school_proficiencies[:15]
        
        for c in class_proficiencies:
            info = schools_info.get(c['inep_code'], {})
            c.update({
                'school_name': info.get('name', 'Escola Desconhecida'),
                'regional': info.get('regional', 'N/A'),
                'director_name': info.get('director_name', 'N/A'),
                'director_time': info.get('director_time', 'N/A'),
                'coordinator_name': info.get('coordinator_name', 'N/A'),
                'coordinator_time': info.get('coordinator_time', 'N/A'),
                'proficiency_round': round(c['proficiency'], 1)
            })
            
        class_proficiencies.sort(key=lambda x: x['proficiency'], reverse=True)
        ranking_data['top_classes'] = class_proficiencies[:15]
        
        class_proficiencies.sort(key=lambda x: x['proficiency'])
        ranking_data['bottom_classes'] = class_proficiencies[:15]
        
    map_data = []
    if school_proficiencies:
        for s in school_proficiencies:
            info = schools_info.get(s['inep_code'], {})
            
            if info.get('latitude') and info.get('longitude'):
                try:
                    lat = float(info['latitude'].replace(',', '.')) if isinstance(info['latitude'], str) else float(info['latitude'])
                    lng = float(info['longitude'].replace(',', '.')) if isinstance(info['longitude'], str) else float(info['longitude'])
                    
                    school_classes = []
                    for c in class_proficiencies:
                        if c['inep_code'] == s['inep_code']:
                            school_classes.append({
                                'tur_nome': c['tur_nome'],
                                'proficiency': round(c['proficiency'], 1)
                            })
                            
                    map_data.append({
                        'inep_code': s['inep_code'],
                        'name': info.get('name', 'Escola Desconhecida'),
                        'regional': info.get('regional', 'N/A'),
                        'director_name': info.get('director_name', 'N/A'),
                        'director_time': info.get('director_time', 'N/A'),
                        'coordinator_name': info.get('coordinator_name', 'N/A'),
                        'coordinator_time': info.get('coordinator_time', 'N/A'),
                        'proficiency': round(s['proficiency'], 1),
                        'latitude': lat,
                        'longitude': lng,
                        'classes': school_classes,
                        'levels': list(school_levels.get(s['inep_code'], set()))
                    })
                except (ValueError, TypeError):
                    pass

    # Question Analysis Data
    q_questions = db.session.query(
        ExternalEvaluationResult.nr_questao.label('question'),
        ExternalEvaluationResult.mti_codigo.label('skill'),
        func.max(ExternalEvaluationDescriptor.mti_descritor).label('skill_desc'),
        func.max(ExternalEvaluationResult.teg_ordem).label('teg_ordem'),
        func.max(ExternalEvaluationResult.dis_nome).label('dis_nome'),
        func.count(ExternalEvaluationResult.id).label('total'),
        func.sum(correct_cases).label('correct'),
        func.sum(absent_cases).label('absent')
    ).select_from(ExternalEvaluationResult).join(
        ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).outerjoin(
        ExternalEvaluationDescriptor, db.and_(
            ExternalEvaluationDescriptor.mti_codigo == ExternalEvaluationResult.mti_codigo,
            ExternalEvaluationDescriptor.tenant_id == tenant_id
        )
    ).filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationStudent.ser_nome == year)
    
    if filter_dis_nome: q_questions = q_questions.filter(ExternalEvaluationResult.dis_nome == filter_dis_nome)
    if filter_shift: q_questions = q_questions.filter(ExternalEvaluationStudent.tur_periodo == filter_shift)
    if school_inep: q_questions = q_questions.filter(ExternalEvaluationResult.esc_inep == school_inep)
    if ser_nome: q_questions = q_questions.filter(ExternalEvaluationStudent.ser_nome == ser_nome)
    if tur_nome: q_questions = q_questions.filter(ExternalEvaluationStudent.tur_nome == tur_nome)

    if regional_id:
        q_questions = q_questions.outerjoin(SchoolAlias, db.and_(SchoolAlias.inep_code == ExternalEvaluationResult.esc_inep, SchoolAlias.tenant_id == tenant_id, SchoolAlias.type == 'Escola'))\
            .outerjoin(RegionalAlias, RegionalAlias.id == SchoolAlias.parent_id)\
            .filter(RegionalAlias.id == regional_id)

    res_questions = q_questions.group_by(ExternalEvaluationResult.nr_questao, ExternalEvaluationResult.mti_codigo).all()
    
    questions_data = []
    for row in res_questions:
        q_number = row.question if row.question else '?'
        
        answered = (row.total or 0) - (row.absent or 0)
        wrong = answered - (row.correct or 0)
        
        pct = (row.correct / answered * 100) if answered > 0 else 0
        pct_wrong = (wrong / answered * 100) if answered > 0 else 0

        questions_data.append({
            'question': q_number,
            'skill': row.skill or 'N/A',
            'skill_desc': row.skill_desc or 'Descrição não disponível',
            'teg_ordem': row.teg_ordem or '0',
            'dis_nome': row.dis_nome or '',
            'total': row.total,
            'correct': row.correct or 0,
            'correct_pct': round(pct, 2),
            'wrong': wrong,
            'wrong_pct': round(pct_wrong, 2),
            'absent': row.absent or 0,
            'absent_pct': 0
        })

    return jsonify({
        'drilldown': drilldown_data,
        'race': race_data,
        'gender': gender_data,
        'radar': radar_data,
        'justifications': justifications_data,
        'summary': summary_data,
        'donut': donut_data,
        'scatter': freq_performance_data,
        'questions': questions_data,
        'ranking': ranking_data,
        'map': map_data
    })


def _process_descriptors_import(app, job_id, filepath, task_id=None):
    with app.app_context():
        job = ImportJob.query.get(job_id)
        if not job: return

        try:
            job.status = 'running'
            from app.utils.timezone import get_brasilia_time
            job.started_at = get_brasilia_time()
            db.session.commit()

            if filepath.endswith('.csv'):
                df = pd.read_csv(filepath, sep=';', dtype=str)
            else:
                df = pd.read_excel(filepath, dtype=str)

            total = len(df)
            job.total_rows = total
            db.session.commit()
            
            if task_id:
                start_import_task(total, task_id=task_id)

            existing = ExternalEvaluationDescriptor.query.filter_by(tenant_id=job.tenant_id).all()
            existing_map = {d.mti_codigo: d for d in existing if d.mti_codigo}

            for index, row in df.iterrows():
                try:
                    mti_id = str(row.get('MTI_ID', '')).strip()
                    mti_codigo = str(row.get('MTI_CODIGO', '')).strip()
                    mti_descritor = str(row.get('MTI_DESCRITOR', '')).strip()
                    mto_id = str(row.get('MTO_ID', '')).strip()
                    mto_nome = str(row.get('MTO_NOME', '')).strip()
                    mar_id = str(row.get('MAR_ID', '')).strip()
                    mar_nome = str(row.get('MAR_NOME', '')).strip()
                    
                    if not mti_codigo or mti_codigo == 'nan':
                        continue

                    if mti_codigo in existing_map:
                        desc = existing_map[mti_codigo]
                        desc.mti_id = mti_id
                        desc.mti_descritor = mti_descritor
                        desc.mto_id = mto_id
                        desc.mto_nome = mto_nome
                        desc.mar_id = mar_id
                        desc.mar_nome = mar_nome
                        desc.active = True
                    else:
                        desc = ExternalEvaluationDescriptor(
                            tenant_id=job.tenant_id,
                            mti_id=mti_id,
                            mti_codigo=mti_codigo,
                            mti_descritor=mti_descritor,
                            mto_id=mto_id,
                            mto_nome=mto_nome,
                            mar_id=mar_id,
                            mar_nome=mar_nome,
                            active=True
                        )
                        db.session.add(desc)
                        existing_map[mti_codigo] = desc

                    job.processed_rows += 1
                    
                    if task_id and index % 100 == 0: 
                        update_import_progress(task_id, job.processed_rows, message=f"Processando linha {index+2}")
                        db.session.commit()
                        
                except Exception as e:
                    pass

            db.session.commit()
            job.status = 'completed'
            job.completed_at = get_brasilia_time()
            db.session.commit()
            
            if task_id:
                finish_import_task(task_id, message=f"Importação de Descritores concluída.", log_file=None)
                
        except Exception as e:
            db.session.rollback()
            job.status = 'failed'
            job.error_message = str(e)
            db.session.commit()
            if task_id:
                fail_import_task(task_id, f"Erro crítico: {str(e)}")
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

@external_evaluations_bp.route('/descriptors', methods=['GET'])
@login_required
def list_descriptors():
    page = request.args.get('page', 1, type=int)
    
    query = filter_by_tenant(ExternalEvaluationDescriptor.query, ExternalEvaluationDescriptor).filter_by(active=True)
    
    search = request.args.get('search', '')
    if search:
        query = query.filter(
            db.or_(
                ExternalEvaluationDescriptor.mti_codigo.ilike(f'%{search}%'),
                ExternalEvaluationDescriptor.mti_descritor.ilike(f'%{search}%')
            )
        )
        
    pagination = query.order_by(ExternalEvaluationDescriptor.mti_codigo).paginate(page=page, per_page=30, error_out=False)
    
    import_form = ImportDescriptorForm()
    active_job = filter_by_tenant(ImportJob.query, ImportJob).filter_by(import_type='ExternalDescriptors', status='running').first()
    
    return render_template('external_evaluations/descriptors.html', 
                           descriptors=pagination.items, 
                           pagination=pagination, 
                           search=search,
                           import_form=import_form,
                           active_job=active_job)

@external_evaluations_bp.route('/descriptors/import', methods=['POST'])
@login_required
def import_descriptors():
    if current_user.role != 'admin' and 'admin' not in current_user.get_roles():
        return jsonify({'success': False, 'message': 'Acesso restrito.'})

    if ImportJob.is_any_running():
        return jsonify({'success': False, 'message': 'Já existe uma importação em andamento. Por favor, aguarde a conclusão.'})

    form = ImportDescriptorForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        import uuid
        task_id = request.form.get('X-Progress-ID') or str(uuid.uuid4())
        
        from app.utils.file_utils import allowed_file, ALLOWED_IMPORT_EXTENSIONS
        uploads_dir = os.path.join(current_app.root_path, '..', 'instance', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        filepath = os.path.join(uploads_dir, filename)
        file.save(filepath)

        job = ImportJob(
            user_id=current_user.id,
            import_type='ExternalDescriptors',
            filename=filename,
            status='pending',
            tenant_id=get_tenant_id()
        )
        db.session.add(job)
        db.session.commit()

        import threading
        thread = threading.Thread(target=_process_descriptors_import, args=(current_app._get_current_object(), job.id, filepath, task_id))
        thread.start()

        return jsonify({'success': True, 'task_id': task_id, 'message': 'Importação iniciada.'})
        
    return jsonify({'success': False, 'message': 'Arquivo inválido ou não enviado.'})

@external_evaluations_bp.route('/evaluations/<int:id>/print_students')
@login_required
def print_students(id):
    year = request.args.get('year')
    level_filter = request.args.get('level_filter')
    filter_dis_nome = request.args.get('filter_dis_nome')
    filter_shift = request.args.get('filter_shift')
    regional_id = request.args.get('regional_id')
    school_inep = request.args.get('school_inep')
    ser_nome = request.args.get('ser_nome')
    tur_nome = request.args.get('tur_nome')
    
    tenant_id = get_tenant_id()
    
    q = db.session.query(ExternalEvaluationResult, ExternalEvaluationStudent).join(
        ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationResult.alt_finalizado == '1')
    
    if year: q = q.filter(ExternalEvaluationStudent.ser_nome == year)
    if filter_dis_nome: q = q.filter(ExternalEvaluationResult.dis_nome == filter_dis_nome)
    if filter_shift: q = q.filter(ExternalEvaluationStudent.tur_periodo == filter_shift)
    if school_inep: q = q.filter(ExternalEvaluationResult.esc_inep == school_inep)
    if ser_nome: q = q.filter(ExternalEvaluationStudent.ser_nome == ser_nome)
    if tur_nome: q = q.filter(ExternalEvaluationStudent.tur_nome == tur_nome)

    from app.models import TeachingUnit as SchoolAlias
    RegionalAlias = db.aliased(SchoolAlias)
    
    q = q.outerjoin(SchoolAlias, db.and_(SchoolAlias.inep_code == ExternalEvaluationResult.esc_inep, SchoolAlias.tenant_id == tenant_id, SchoolAlias.type == 'Escola'))\
         .outerjoin(RegionalAlias, RegionalAlias.id == SchoolAlias.parent_id)

    if regional_id:
        q = q.filter(RegionalAlias.id == regional_id)
        
    q = q.add_columns(SchoolAlias.name.label('school_name'), RegionalAlias.name.label('regional_name'))
    
    results = q.all()
    
    student_data = {}
    for res, std, sch_name, reg_name in results:
        if std.id not in student_data:
            student_data[std.id] = {
                'regional': reg_name or 'N/A',
                'escola': sch_name or std.esc_nome or 'N/A',
                'turma': std.tur_nome or 'N/A',
                'aluno': std.alu_nome or 'N/A',
                'correct_q': 0,
                'total_q': 0
            }
        student_data[std.id]['correct_q'] += (res.correct_q or 0)
        student_data[std.id]['total_q'] += res.total_q

    filtered_students = []
    for std_id, data in student_data.items():
        if data['total_q'] > 0:
            pct = (data['correct_q'] / data['total_q']) * 100
            if pct < 25: level_alcan = 'Abaixo do básico'
            elif pct < 50: level_alcan = 'Básico'
            elif pct < 75: level_alcan = 'Proficiente'
            else: level_alcan = 'Avançado'
            
            if not level_filter or level_alcan == level_filter:
                data['nivel'] = level_alcan
                filtered_students.append(data)
                
    filtered_students.sort(key=lambda x: (x['regional'], x['escola'], x['turma'], x['aluno']))
    
    html = f'''
    <html>
    <head><title>Relatório de Estudantes - Nível: {level_filter or "Todos"}</title>
    <style>table {{width:100%; border-collapse: collapse; font-family: sans-serif; font-size: 12px;}} th, td {{border:1px solid #000; padding:4px; text-align:left;}} th {{background-color: #f0f0f0;}} h2 {{font-family: sans-serif;}}</style>
    </head>
    <body onload="window.print()">
    <h2>Relatório de Estudantes (Nível: {level_filter or "Todos"})</h2>
    <table>
        <tr><th>Regional</th><th>Escola</th><th>Turma</th><th>Aluno</th><th>Nível Alcançado</th></tr>
    '''
    for s in filtered_students:
        html += f"<tr><td>{s['regional']}</td><td>{s['escola']}</td><td>{s['turma']}</td><td>{s['aluno']}</td><td>{s['nivel']}</td></tr>"
    
    html += '</table></body></html>'
    return html

@external_evaluations_bp.route('/descriptors/<int:id>/delete', methods=['POST'])
@login_required
def delete_descriptor(id):
    if current_user.role != 'admin' and 'admin' not in current_user.get_roles():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('external_evaluations.list_descriptors'))
        
    desc = filter_by_tenant(ExternalEvaluationDescriptor.query, ExternalEvaluationDescriptor).filter_by(id=id).first_or_404()
    
    desc.active = False
    db.session.commit()
    log_audit('delete', 'external_evaluation_descriptor', desc.id, get_tenant_id(), current_user.id, old_data={'mti_codigo': desc.mti_codigo})
    
    flash('Descritor excluído com sucesso.', 'success')
    return redirect(url_for('external_evaluations.list_descriptors'))
