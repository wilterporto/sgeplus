from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
from flask import render_template, redirect, url_for, flash, request
from app.routes import questions_bp
from app.models import Question, Descriptor, User, ImportJob
from flask_login import current_user, login_required
from app.utils.tenancy import filter_by_tenant
from app.forms import QuestionForm, ImportQuestionForm
from app import db
import os, threading, json, pandas as pd
from datetime import datetime
from werkzeug.utils import secure_filename

def get_descriptors_json():
    # Prepare Descriptors JSON for Frontend Filter
    # Structure: { id, label, theme_id, filter_label }
    # filter_label = "Matrix - Theme - Year - Subject"
    descriptors_data = []
    # Fetch all to build metadata (could optmize with joins)
    all_descriptors = filter_by_tenant(Descriptor.query, Descriptor).all()
    
    for d in all_descriptors:
        # Safe access to optional relations
        matrix_name = d.theme.matrix.name if (d.theme and d.theme.matrix) else (d.matrix.name if d.matrix else "N/A")
        theme_name = d.theme.name if d.theme else "Outros"
        year_name = d.school_year.name if d.school_year else ""
        subject_name = d.subject.name if d.subject else ""
        
        # Construct Filter Label (Matrix - Theme - Year - Subject)
        filter_parts = [matrix_name, theme_name]
        if year_name: filter_parts.append(year_name)
        if subject_name: filter_parts.append(subject_name)
        
        filter_label = " - ".join(filter_parts)
        
        descriptors_data.append({
            'id': d.id,
            'full_text': f"{d.code}: {d.description}",
            'theme_id': d.theme_id if d.theme_id else 0,
            'filter_label': filter_label
        })
    return descriptors_data

@questions_bp.route('/', methods=['GET', 'POST'])
@login_required
def list_questions():
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import session
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')

    form = QuestionForm()
    # Populate choices for descriptors
    # Format: "D1 - Math - Some desc..."
    all_descriptors = filter_by_tenant(Descriptor.query, Descriptor).all()
    form.descriptors.choices = [(d.id, f"{d.code} - {d.description}") for d in all_descriptors]
    
    if form.validate_on_submit():
        # Handle different question types
        if form.type.data == 'ASSOCIAR_COLUNAS':
            # Structure for Association: Key=1..5, Value={item, response}
            alternatives = {}
            for i in range(1, 6):
                item = request.form.get(f'assoc_item_{i}')
                resp = request.form.get(f'assoc_resp_{i}')
                if item or resp: # Store if non-empty
                    alternatives[str(i)] = {'item': item, 'response': resp}
            # Correct alternative doesn't apply the standard way, set dummy or handle validation
            correct_alt = 'X' 
        else:
            # Standard alternatives
            alternatives = {
                'A': form.alt_a.data,
                'B': form.alt_b.data,
                'C': form.alt_c.data,
                'D': form.alt_d.data,
                'E': form.alt_e.data
            }
            correct_alt = form.correct_alternative.data
        
        question = Question(
            statement=clean_html(form.statement.data),
            type=form.type.data,
            difficulty=form.difficulty.data,
            correct_alternative=correct_alt,
            created_by_id=current_user.id,
            tenant_id=current_user.tenant_id
        )
        
        # Status Logic
        action = request.form.get('action', 'finalize')
        if action == 'draft':
            question.status = 'rascunho'
            question.approved_by_secretaria = False
        else:
            question.status = 'aprovada'
            if current_user.is_admin:
                question.approved_by_secretaria = True
            else:
                question.approved_by_secretaria = False
        
        question.set_alternatives(alternatives)
        
        # M2M Descriptors
        selected_descriptors = [Descriptor.query.get(did) for did in form.descriptors.data]
        question.descriptors = selected_descriptors
        
        db.session.add(question)
        db.session.commit()
        from app.audit_utils import log_audit
        log_audit('CREATE', 'Question', question.id, f"Criou a questão ID {question.id}")
        flash('Questão criada com sucesso!', 'success')
        return redirect(url_for('questions.list_questions'))

    page = request.args.get('page', 1, type=int)
    
    if active_role == 'unidade':
        from app.models import Professor, TeachingAssignment, Class
        prof_user_ids = db.session.query(Professor.user_id)\
            .join(TeachingAssignment, TeachingAssignment.professor_id == Professor.id)\
            .join(Class, Class.id == TeachingAssignment.class_id)\
            .filter(Class.teaching_unit_id == active_school_id)\
            .filter(Professor.user_id.isnot(None))\
            .subquery()
        questions_query = Question.query.filter(Question.created_by_id.in_(prof_user_ids))
    else:
        questions_query = Question.query

    questions_query = filter_by_tenant(questions_query, Question)
    questions = questions_query.order_by(Question.created_at.desc()).paginate(page=page, per_page=30)
    
    # Prepare Descriptors JSON for Frontend Filter
    descriptors_data_json = get_descriptors_json()

    # Calculate counts for summary cards
    from sqlalchemy import func
    status_counts_query = db.session.query(Question.status, func.count(Question.id))
    status_counts_query = filter_by_tenant(status_counts_query, Question)
    if active_role == 'unidade':
        status_counts_query = status_counts_query.filter(Question.created_by_id.in_(prof_user_ids))
        
    status_counts_data = status_counts_query.group_by(Question.status).all()
        
    counts_map = {s: c for s, c in status_counts_data}
    
    # Ensure all statuses are present in the dictionary
    for s_label in ['rascunho', 'pendente', 'aprovada', 'inativa']:
        if s_label not in counts_map:
            counts_map[s_label] = 0
    counts_map['total'] = sum(counts_map.values())

    active_job = filter_by_tenant(ImportJob.query, ImportJob).filter_by(import_type='Questions', status='running').first()
    import_form = ImportQuestionForm()

    return render_template('questions/list.html', 
                         questions=questions, 
                         form=form, 
                         import_form=import_form,
                         descriptors_json=descriptors_data_json,
                         stats=counts_map,
                         active_job=active_job)

def _process_questions_import(app, job_id, filepath, task_id=None):
    with app.app_context():
        from app.import_utils import start_import_task, update_import_progress, finish_import_task, fail_import_task
        job = ImportJob.query.get(job_id)
        if not job: return

        try:
            job.status = 'running'
            from app.utils.timezone import get_brasilia_time
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
            
            descriptors_map = {d.code.strip().upper(): d for d in Descriptor.query.filter_by(tenant_id=job.tenant_id).all()}
            
            difficulty_map = {
                'facil': 'Facil', 'fácil': 'Facil',
                'medio': 'Medio', 'médio': 'Medio', 'intermediario': 'Medio', 'intermediário': 'Medio',
                'dificil': 'Dificil', 'difícil': 'Dificil', 'complexa': 'Dificil'
            }

            for index, row in df.iterrows():
                try:
                    statement = str(row.get('Enunciado', '')).strip()
                    diff_raw = str(row.get('Dificuldade', '')).strip().lower()
                    desc_code = str(row.get('Descritor', '')).strip().upper()
                    correct = str(row.get('Correta', '')).strip().upper()
                    
                    if not statement or statement == 'nan':
                        errors.append(f"Linha {index+2}: Enunciado obrigatório.")
                        job.processed_rows += 1
                        if task_id and index % 10 == 0: update_import_progress(task_id, job.processed_rows, message=f"Processando linha {index+2}")
                        continue

                    difficulty = difficulty_map.get(diff_raw, 'Medio')
                    
                    user = User.query.get(job.user_id)
                    tenant_id = user.tenant_id if user else None
                    
                    question = Question(
                        statement=statement,
                        type='MULTIPLA_ESCOLHA', # Default
                        difficulty=difficulty,
                        correct_alternative=correct if correct in ['A', 'B', 'C', 'D', 'E'] else 'A',
                        status='aprovada',
                        approved_by_secretaria=True,
                        created_by_id=job.user_id,
                        tenant_id=tenant_id
                    )
                    
                    alternatives = {
                        'A': str(row.get('A', '')),
                        'B': str(row.get('B', '')),
                        'C': str(row.get('C', '')),
                        'D': str(row.get('D', '')),
                        'E': str(row.get('E', ''))
                    }
                    question.set_alternatives(alternatives)
                    
                    if desc_code and desc_code in descriptors_map:
                        question.descriptors.append(descriptors_map[desc_code])
                    elif desc_code:
                        errors.append(f"Linha {index+2}: Descritor '{desc_code}' não encontrado.")

                    db.session.add(question)
                    success_count += 1
                    job.processed_rows += 1
                    
                    if task_id and index % 10 == 0:
                        update_import_progress(task_id, job.processed_rows, message=f"Processando questão {index+1}")
                    
                    if success_count % 100 == 0:
                        job.errors = json.dumps(errors)
                        db.session.commit()

                except Exception as e:
                    db.session.rollback()
                    errors.append(f"Linha {index+2}: Erro: {str(e)}")
                    job.processed_rows += 1
                    if task_id and index % 10 == 0: update_import_progress(task_id, job.processed_rows, message=f"Processando linha {index+2}")

            job.status = 'completed'
            job.finished_at = get_brasilia_time()
            job.errors = json.dumps(errors)
            db.session.commit()
            
            if task_id:
                finish_import_task(task_id, message=f"Importação de Questões concluída.", log_file=None)

        except Exception as e:
            job.status = 'failed'
            job.errors = json.dumps([f"Erro crítico: {str(e)}"])
            job.finished_at = get_brasilia_time()
            db.session.commit()
            
            if task_id:
                fail_import_task(task_id, f"Erro crítico: {str(e)}")
        finally:
            if os.path.exists(filepath):
                os.remove(filepath)

@questions_bp.route('/import', methods=['POST'])
@login_required
def import_questions():
    if current_user.role != 'admin' and 'admin' not in current_user.get_roles():
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('questions.list_questions'))

    # Check for active job
    if ImportJob.is_any_running():
        flash('Já existe uma importação em andamento. Por favor, aguarde a conclusão.', 'warning')
        return redirect(url_for('questions.list_questions'))

    form = ImportQuestionForm()
    if form.validate_on_submit():
        file = form.file.data
        filename = secure_filename(file.filename)
        task_id = request.form.get('X-Progress-ID')
        
        # Use current_app
        from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
        from flask import current_app
        uploads_dir = os.path.join(current_app.root_path, '..', 'instance', 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        filepath = os.path.join(uploads_dir, filename)
        file.save(filepath)

        from app.utils.tenancy import get_tenant_id
        job = ImportJob(
            user_id=current_user.id,
            import_type='Questions',
            filename=filename,
            status='pending',
            tenant_id=get_tenant_id()
        )
        db.session.add(job)
        db.session.commit()

        thread = threading.Thread(target=_process_questions_import, args=(current_app._get_current_object(), job.id, filepath, task_id))
        thread.start()

        flash('A importação de questões foi iniciada em segundo plano.', 'info')
        
    return redirect(url_for('questions.list_questions'))

@questions_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_question(id):
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import session, abort
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')
    
    question_query = Question.query.filter_by(id=id)
    question_query = filter_by_tenant(question_query, Question)
    question = question_query.first_or_404()
    
    if active_role == 'unidade':
        from app.models import Professor, TeachingAssignment, Class
        prof_user_ids = db.session.query(Professor.user_id)\
            .join(TeachingAssignment, TeachingAssignment.professor_id == Professor.id)\
            .join(Class, Class.id == TeachingAssignment.class_id)\
            .filter(Class.teaching_unit_id == active_school_id)\
            .filter(Professor.user_id.isnot(None))\
            .subquery()
        is_authorized = db.session.query(Question.id).filter(
            Question.id == id,
            Question.created_by_id.in_(prof_user_ids)
        ).first() is not None
        if not is_authorized:
            abort(403)
    form = QuestionForm(obj=question)
    
    # Populate choices
    all_descriptors = filter_by_tenant(Descriptor.query, Descriptor).all()
    form.descriptors.choices = [(d.id, f"{d.code} - {d.description}") for d in all_descriptors]
    
    if request.method == 'GET':
        alts = question.get_alternatives()
        form.alt_a.data = alts.get('A')
        form.alt_b.data = alts.get('B')
        form.alt_c.data = alts.get('C')
        form.alt_d.data = alts.get('D')
        form.alt_e.data = alts.get('E')
        # Pre-select M2M
        form.descriptors.data = [d.id for d in question.descriptors]
            
    if form.validate_on_submit():
        # Handle Alternatives depending on Type
        if form.type.data == 'ASSOCIAR_COLUNAS':
            # Structure for Association: Key=1..5, Value={item, response}
            alternatives = {}
            for i in range(1, 6):
                item = request.form.get(f'assoc_item_{i}')
                resp = request.form.get(f'assoc_resp_{i}')
                if item or resp: # Store if non-empty
                    alternatives[str(i)] = {'item': item, 'response': resp}
            # Correct alternative doesn't apply the standard way, set dummy or handle validation
            correct_alt = 'X' 
        else:
            # Standard alternatives
            alternatives = {
                'A': form.alt_a.data,
                'B': form.alt_b.data,
                'C': form.alt_c.data,
                'D': form.alt_d.data,
                'E': form.alt_e.data
            }
            correct_alt = form.correct_alternative.data
        
        question.statement = clean_html(form.statement.data)
        question.type = form.type.data
        question.difficulty = form.difficulty.data
        question.correct_alternative = correct_alt
        
        # Status Logic on Edit
        action = request.form.get('action', 'finalize')
        if action == 'draft':
            question.status = 'rascunho'
        else:
            # If it was a draft and now finalizing
            question.status = 'aprovada'
            # If Admin edits/finalizes, it becomes approved by secretaria
            if current_user.is_admin:
                question.approved_by_secretaria = True
        
        question.set_alternatives(alternatives)
        
        # Update M2M
        selected_descriptors = [Descriptor.query.get(did) for did in form.descriptors.data]
        question.descriptors = selected_descriptors
        
        db.session.commit()
        from app.audit_utils import log_audit
        log_audit('UPDATE', 'Question', question.id, f"Editou a questão ID {question.id}")
        flash('Questão atualizada com sucesso!', 'success')
        return redirect(url_for('questions.list_questions'))
        
    # Get Descriptors for Wizard
    descriptors_data_json_edit = get_descriptors_json()
    assoc_data = question.get_alternatives() if question.type == 'ASSOCIAR_COLUNAS' else {}

    return render_template('questions/form.html', form=form, title="Editar Questão", descriptors_json=descriptors_data_json_edit, is_edit=True, assoc_data=assoc_data)

@questions_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_question(id):
    question_query = Question.query.filter_by(id=id)
    question_query = filter_by_tenant(question_query, Question)
    question = question_query.first_or_404()
    db.session.delete(question)
    db.session.commit()
    from app.audit_utils import log_audit
    log_audit('DELETE', 'Question', id, f"Excluiu a questão ID {id}")
    flash('Excluído com sucesso', 'success_delete')
    return redirect(url_for('questions.list_questions'))

@questions_bp.route('/<int:id>/approve', methods=['POST'])
@login_required
def approve_question(id):
    if not current_user.is_admin:
        abort(403)
    question_query = Question.query.filter_by(id=id)
    question_query = filter_by_tenant(question_query, Question)
    question = question_query.first_or_404()
    question.approved_by_secretaria = True
    question.status = 'aprovada' # Ensure it's approved if it was pending or draft
    db.session.commit()
    from app.audit_utils import log_audit
    log_audit('UPDATE', 'Question', question.id, f"Aprovou a questão ID {question.id} pela Secretaria")
    flash('Questão aprovada pela Secretaria!', 'success')
    return redirect(url_for('questions.list_questions'))

@questions_bp.route('/<int:id>/toggle_unit_validation', methods=['POST'])
@login_required
def toggle_unit_validation(id):
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import session, abort
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')
    
    if active_role != 'unidade' or not active_school_id:
        abort(403)
        
    question_query = Question.query.filter_by(id=id)
    question_query = filter_by_tenant(question_query, Question)
    question = question_query.first_or_404()
    from app.models import TeachingUnit
    unit_query = TeachingUnit.query.filter_by(id=active_school_id)
    unit_query = filter_by_tenant(unit_query, TeachingUnit)
    unit = unit_query.first_or_404()
    if not unit:
        abort(404)
        
    if unit in question.validated_units:
        question.validated_units.remove(unit)
        db.session.commit()
        from app.audit_utils import log_audit
        log_audit('UPDATE', 'Question', question.id, f"Removeu a validação da unidade {unit.name} para a questão {question.id}")
        flash('Validação da unidade removida com sucesso!', 'success')
    else:
        question.validated_units.append(unit)
        db.session.commit()
        from app.audit_utils import log_audit
        log_audit('UPDATE', 'Question', question.id, f"Validou a questão {question.id} para a unidade {unit.name}")
        flash('Questão validada pela unidade com sucesso!', 'success')
        
    return redirect(url_for('questions.list_questions'))
