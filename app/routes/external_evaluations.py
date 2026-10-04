import os
import io
import pandas as pd
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models import Evaluation, PartnerInstitution, ExternalEvaluationStudent, ExternalEvaluationResult
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
    available_disciplines = []
    
    if selected_id:
        evaluation = filter_by_tenant(Evaluation.query, Evaluation).filter_by(id=selected_id, origin='Externa').first()
        if evaluation:
            available_disciplines = [r[0] for r in db.session.query(ExternalEvaluationResult.dis_nome).filter_by(evaluation_id=selected_id).distinct().all() if r[0]]
                
    return render_template('external_evaluations/dashboard.html', evaluations=evaluations, evaluation=evaluation, available_disciplines=available_disciplines, active_page='external_evaluations')

@external_evaluations_bp.route('/evaluations/<int:id>/dashboard_filters_api')
@login_required
def dashboard_filters_api(id):
    dis_nome = request.args.get('dis_nome')
    if not dis_nome:
        return jsonify({'years': [], 'shifts': []})
        
    q_base = db.session.query(ExternalEvaluationStudent).join(
        ExternalEvaluationResult, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationResult.dis_nome == dis_nome)
    
    available_years = [r[0] for r in q_base.with_entities(ExternalEvaluationStudent.ser_nome).distinct().all() if r[0]]
    available_shifts = [r[0] for r in q_base.with_entities(ExternalEvaluationStudent.tur_periodo).distinct().all() if r[0]]
    
    return jsonify({
        'years': available_years,
        'shifts': available_shifts
    })

@external_evaluations_bp.route('/evaluations/<int:id>/dashboard_api')
@login_required
def dashboard_api(id):
    dis_nome = request.args.get('dis_nome')
    if not dis_nome:
        return jsonify({'drilldown': [], 'race': [], 'gender': [], 'radar': [], 'justifications': []})
    level = request.args.get('level', 'rede')
    
    filter_year = request.args.get('filter_year')
    filter_shift = request.args.get('filter_shift')
    
    regional_id = request.args.get('regional_id')
    school_inep = request.args.get('school_inep')
    ser_nome = request.args.get('ser_nome')
    tur_nome = request.args.get('tur_nome')
    
    tenant_id = get_tenant_id()
    
    # Base query for results
    q = db.session.query(ExternalEvaluationResult, ExternalEvaluationStudent).join(
        ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationResult.dis_nome == dis_nome)
    
    if filter_year:
        q = q.filter(ExternalEvaluationStudent.ser_nome == filter_year)
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
    
    # Helper for drilldown
    if level == 'rede':
        group_col = db.literal('Consolidado da Rede')
        id_col = db.literal('rede_total')
    elif level == 'regionals':
        group_col = RegionalAlias.name
        id_col = RegionalAlias.id
    elif level == 'school':
        group_col = SchoolAlias.name
        id_col = ExternalEvaluationResult.esc_inep
    elif level == 'school':
        group_col = ExternalEvaluationStudent.ser_nome
        id_col = ExternalEvaluationStudent.ser_nome
    elif level == 'year':
        group_col = ExternalEvaluationStudent.tur_nome
        id_col = ExternalEvaluationStudent.tur_nome
    elif level == 'class':
        group_col = ExternalEvaluationStudent.alu_nome
        id_col = ExternalEvaluationStudent.alu_id
    else:
        group_col = ExternalEvaluationStudent.alu_nome
        id_col = ExternalEvaluationStudent.alu_id
        
    drill_query = db.session.query(
        id_col.label('id'),
        group_col.label('label'),
        func.count(ExternalEvaluationResult.id).label('total'),
        func.sum(correct_cases).label('correct'),
        func.sum(absent_cases).label('absent')
    ).select_from(ExternalEvaluationResult).join(
        ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).outerjoin(SchoolAlias, db.and_(SchoolAlias.inep_code == ExternalEvaluationResult.esc_inep, SchoolAlias.tenant_id == tenant_id, SchoolAlias.type == 'Escola'))\
     .outerjoin(RegionalAlias, RegionalAlias.id == SchoolAlias.parent_id)\
     .filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationResult.dis_nome == dis_nome)
     
    if filter_year:
        drill_query = drill_query.filter(ExternalEvaluationStudent.ser_nome == filter_year)
    if filter_shift:
        drill_query = drill_query.filter(ExternalEvaluationStudent.tur_periodo == filter_shift)
    if regional_id:
        drill_query = drill_query.filter(RegionalAlias.id == regional_id)
    if school_inep:
        drill_query = drill_query.filter(ExternalEvaluationResult.esc_inep == school_inep)
    if ser_nome:
        drill_query = drill_query.filter(ExternalEvaluationStudent.ser_nome == ser_nome)
    if tur_nome:
        drill_query = drill_query.filter(ExternalEvaluationStudent.tur_nome == tur_nome)
        
    drill_results = drill_query.group_by(id_col, group_col).all()
    
    for row in drill_results:
        label = row.label or 'Não Informado'
        pct = (row.correct / row.total * 100) if row.total and row.total > 0 else 0
        pct_absent = (row.absent / row.total * 100) if row.total and row.total > 0 else 0
        drilldown_data.append({
            'id': row.id,
            'label': label,
            'value': round(pct, 2),
            'absent': round(pct_absent, 2)
        })
        
    # Helper to calculate secondary charts using the SAME base filters
    def get_chart_data(group_col):
        q = db.session.query(
            group_col.label('label'),
            func.count(ExternalEvaluationResult.id).label('total'),
            func.sum(correct_cases).label('correct'),
            func.sum(absent_cases).label('absent')
        ).select_from(ExternalEvaluationResult).join(
            ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
        ).filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationResult.dis_nome == dis_nome)

        if regional_id or school_inep:
            q = q.outerjoin(SchoolAlias, db.and_(SchoolAlias.inep_code == ExternalEvaluationResult.esc_inep, SchoolAlias.tenant_id == tenant_id, SchoolAlias.type == 'Escola'))\
                 .outerjoin(RegionalAlias, RegionalAlias.id == SchoolAlias.parent_id)
         
        if filter_year: q = q.filter(ExternalEvaluationStudent.ser_nome == filter_year)
        if filter_shift: q = q.filter(ExternalEvaluationStudent.tur_periodo == filter_shift)
        if regional_id: q = q.filter(RegionalAlias.id == regional_id)
        if school_inep: q = q.filter(ExternalEvaluationResult.esc_inep == school_inep)
        if ser_nome: q = q.filter(ExternalEvaluationStudent.ser_nome == ser_nome)
        if tur_nome: q = q.filter(ExternalEvaluationStudent.tur_nome == tur_nome)
        
        res = q.group_by(group_col).all()
        data = []
        for row in res:
            pct = (row.correct / row.total * 100) if row.total and row.total > 0 else 0
            pct_absent = (row.absent / row.total * 100) if row.total and row.total > 0 else 0
            data.append({'label': row.label or 'Não Informado', 'value': round(pct, 2), 'absent': round(pct_absent, 2)})
        return data

    race_data = get_chart_data(ExternalEvaluationStudent.pel_nome)
    gender_data = get_chart_data(ExternalEvaluationStudent.gen_nome)
    radar_data = get_chart_data(ExternalEvaluationResult.mti_codigo)
    

    # Justifications for absence
    q_just = db.session.query(
        ExternalEvaluationResult.alt_justificativa.label('label'),
        func.count(ExternalEvaluationResult.id).label('total')
    ).select_from(ExternalEvaluationResult).join(
        ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).outerjoin(SchoolAlias, db.and_(SchoolAlias.inep_code == ExternalEvaluationResult.esc_inep, SchoolAlias.tenant_id == tenant_id, SchoolAlias.type == 'Escola'))\
     .outerjoin(RegionalAlias, RegionalAlias.id == SchoolAlias.parent_id)\
     .filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationResult.dis_nome == dis_nome, ExternalEvaluationResult.alt_finalizado == '0')
     
    if filter_year: q_just = q_just.filter(ExternalEvaluationStudent.ser_nome == filter_year)
    if filter_shift: q_just = q_just.filter(ExternalEvaluationStudent.tur_periodo == filter_shift)
    if regional_id: q_just = q_just.filter(RegionalAlias.id == regional_id)
    if school_inep: q_just = q_just.filter(ExternalEvaluationResult.esc_inep == school_inep)
    if ser_nome: q_just = q_just.filter(ExternalEvaluationStudent.ser_nome == ser_nome)
    if tur_nome: q_just = q_just.filter(ExternalEvaluationStudent.tur_nome == tur_nome)
    
    res_just = q_just.group_by(ExternalEvaluationResult.alt_justificativa).all()
    justifications_data = []
    for row in res_just:
        justifications_data.append({'label': row.label or 'Sem Justificativa', 'value': row.total})
        

    # Summary and Donut Stats (Optimized)
    q_student = db.session.query(
        ExternalEvaluationResult.external_evaluation_student_id,
        func.count(ExternalEvaluationResult.id).label('total_q'),
        func.sum(correct_cases).label('correct_q'),
        func.max(ExternalEvaluationResult.alt_finalizado).label('finalizado')
    ).filter(ExternalEvaluationResult.evaluation_id == id, ExternalEvaluationResult.dis_nome == dis_nome)
    
    if filter_year: q_student = q_student.filter(ExternalEvaluationResult.ser_nome == filter_year)
    if filter_shift: q_student = q_student.filter(ExternalEvaluationResult.tur_periodo == filter_shift)
    if school_inep: q_student = q_student.filter(ExternalEvaluationResult.esc_inep == school_inep)
    if ser_nome: q_student = q_student.filter(ExternalEvaluationResult.ser_nome == ser_nome)
    if tur_nome: q_student = q_student.filter(ExternalEvaluationResult.tur_nome == tur_nome)

    if regional_id:
        q_student = q_student.outerjoin(SchoolAlias, db.and_(SchoolAlias.inep_code == ExternalEvaluationResult.esc_inep, SchoolAlias.tenant_id == tenant_id, SchoolAlias.type == 'Escola'))\
            .outerjoin(RegionalAlias, RegionalAlias.id == SchoolAlias.parent_id)\
            .filter(RegionalAlias.id == regional_id)
            
    student_results = q_student.group_by(ExternalEvaluationResult.external_evaluation_student_id).all()
    
    total_participants = 0
    total_completed = 0
    total_absent = 0
    total_correct_q = 0
    total_answered_q = 0
    
    level_counts = {'Abaixo do básico': 0, 'Básico': 0, 'Proficiente': 0, 'Avançado': 0}
    
    for r in student_results:
        total_participants += 1
        if r.finalizado == '1':
            total_completed += 1
            if r.total_q > 0:
                total_correct_q += (r.correct_q or 0)
                total_answered_q += r.total_q
                pct = ((r.correct_q or 0) / r.total_q) * 100
                if pct < 25: level_counts['Abaixo do básico'] += 1
                elif pct < 50: level_counts['Básico'] += 1
                elif pct < 75: level_counts['Proficiente'] += 1
                else: level_counts['Avançado'] += 1
        else:
            total_absent += 1
            
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
        'status_rede': status_rede
    }
    
    donut_data = [
        {'label': 'Abaixo do básico', 'value': level_counts['Abaixo do básico']},
        {'label': 'Básico', 'value': level_counts['Básico']},
        {'label': 'Proficiente', 'value': level_counts['Proficiente']},
        {'label': 'Avançado', 'value': level_counts['Avançado']}
    ]

    return jsonify({
        'drilldown': drilldown_data,
        'race': race_data,
        'gender': gender_data,
        'radar': radar_data,
        'justifications': justifications_data,
        'summary': summary_data,
        'donut': donut_data
    })
