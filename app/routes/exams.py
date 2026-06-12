import os
import threading
import uuid
import time
from datetime import datetime
from io import BytesIO
from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
from flask import render_template, redirect, url_for, flash, request, abort, send_file, jsonify, session, current_app
from flask_login import login_required, current_user
from app.routes import exams_bp
from app.models import Exam, ExamItem, Question, Enrollment, Student, Descriptor, ReferenceMatrix, SchoolYear, Subject, TeachingUnit, StudentResult, Class, AuditLog, AbsenceReason
from app.forms import ExamGeneratorForm
from app import db
from app.utils.tenancy import filter_by_tenant
import random
import json
import sqlalchemy as sa
from xhtml2pdf import pisa
from pypdf import PdfWriter, PdfReader
import qrcode
import base64

# Global job tracker for PDF generation
pdf_jobs = {}

@exams_bp.route('/')
def list_exams():
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import session
    query = Exam.query
    query = filter_by_tenant(query, Exam)
    is_teacher = current_user.is_authenticated and 'professor' in current_user.get_roles() and not current_user.is_admin
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')
    
    if active_role == 'unidade':
        # Unidade sees exams of their own school, exams created by themselves,
        # and exams created by professors assigned to their school.
        from app.models import Professor, TeachingAssignment, Class
        prof_user_ids = db.session.query(Professor.user_id)\
            .join(TeachingAssignment, TeachingAssignment.professor_id == Professor.id)\
            .join(Class, Class.id == TeachingAssignment.class_id)\
            .filter(Class.teaching_unit_id == active_school_id)\
            .filter(Professor.user_id.isnot(None))\
            .subquery()
            
        query = query.filter(sa.or_(
            Exam.teaching_unit_id == active_school_id,
            Exam.created_by_id == current_user.id,
            Exam.created_by_id.in_(prof_user_ids)
        ))
    elif is_teacher:
        # Teachers see their own exams AND all Approved exams (to allow analysis/recording as requested)
        query = query.filter(sa.or_(
            Exam.created_by_id == current_user.id,
            Exam.status == 'Aprovado'
        ))

    # Filter by 'has_results' if parameter present (for Diagnostics menu)
    if request.args.get('has_results') == 'true':
        query = query.filter(Exam.results.any())
        
    exams = query.order_by(Exam.created_at.desc()).all()
    
    from app.utils.analytics import get_exam_stats
    exams_with_stats = []
    for exam in exams:
        stats = get_exam_stats(exam.id)
        
        # Check if it can be deleted 
        # 1. Permission check: Admin or Creator
        is_owner = current_user.id == exam.created_by_id
        is_admin = current_user.is_admin or 'regional_manager' in current_user.get_roles()
        
        has_permission = is_admin or is_owner or (active_role == 'unidade' and exam.teaching_unit_id == active_school_id)
        
        # 2. Data integrity check: No results with actual answers
        data_allows = True
        for res in exam.results.all():
            answers = json.loads(res.answers) if res.answers else {}
            if answers:
                data_allows = False
                break
        
        can_delete = has_permission and data_allows
        
        # Permission flag for UI
        can_record = False
        if current_user.is_authenticated:
            if current_user.is_admin or 'regional_manager' in current_user.get_roles():
                can_record = True
            elif current_user.id == exam.created_by_id or exam.allow_teacher_entry:
                can_record = True
            elif active_role == 'unidade' and exam.teaching_unit_id == active_school_id:
                can_record = True
            elif is_teacher:
                # Professors can record if they teach a class in the exam's year
                professor = current_user.professor_profile
                year_ids = [a.enrolled_class.school_year_id for a in professor.assignments] if professor else []
                if exam.school_year_id in year_ids or exam.created_by_id == current_user.id:
                    can_record = True
                
        exams_with_stats.append({
            'exam': exam,
            'success': stats['success'],
            'failure': stats['failure'],
            'absent': stats['absent'],
            'can_delete': can_delete,
            'can_record': can_record
        })
        
    schools = TeachingUnit.query.filter_by(type='Escola')
    schools = filter_by_tenant(schools, TeachingUnit).order_by(TeachingUnit.name).all()
        
    return render_template('exams/list.html', exams_with_stats=exams_with_stats, schools=schools)

@exams_bp.route('/generate', methods=['GET', 'POST'])
def generate_exam():
    from app.utils.file_utils import allowed_file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMPORT_EXTENSIONS
    from flask import session
    form = ExamGeneratorForm()
    
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')
    active_school_name = session.get('active_school_name')
    is_unidade = (active_role == 'unidade')
    
    # Populate choices
    from app.models import Evaluation
    evaluation_query = Evaluation.query
    evaluation_query = filter_by_tenant(evaluation_query, Evaluation)
    form.evaluation_id.choices = [(0, 'Selecione...')] + [(e.id, e.name) for e in evaluation_query.order_by(Evaluation.name).all()]
    matrix_query = filter_by_tenant(ReferenceMatrix.query, ReferenceMatrix)
    form.matrix_id.choices = [(0, 'Selecione...')] + [(m.id, m.name) for m in matrix_query.order_by(ReferenceMatrix.name).all()]
    school_year_query = filter_by_tenant(SchoolYear.query, SchoolYear)
    form.school_year_id.choices = [(0, 'Selecione...')] + [(y.id, y.name) for y in school_year_query.order_by(SchoolYear.name).all()]
    
    subject_query = filter_by_tenant(Subject.query, Subject)
    form.subject_id.choices = [(0, 'Selecione...')] + [(s.id, s.name) for s in subject_query.order_by(Subject.name).all()]
    form.subject_ids.choices = [(s.id, s.name) for s in subject_query.order_by(Subject.name).all()]
    
    # Scoping choices
    default_scopes = [
        ('', 'Selecione...'),
        ('global', 'Todas as Escolas'),
        ('regional', 'Regional Específica'),
        ('school', 'Escolas Específicas')
    ]
    if current_user.tenant.type == 'Estadual':
        default_scopes.append(('city', 'Município Específico'))
    form.scope_type.choices = default_scopes

    if current_user.tenant.type == 'Estadual' and current_user.tenant.uf:
        from app.models import City
        cities = City.query.filter_by(uf=current_user.tenant.uf).order_by(City.name).all()
        form.target_cities.choices = [(c.name, c.name) for c in cities]
    else:
        form.target_cities.choices = []

    if is_unidade:
        form.teaching_unit_id.choices = [(active_school_id, active_school_name)]
        form.regional_id.choices = []
    else:
        tu_query_reg = TeachingUnit.query.filter_by(type='Regional')
        tu_query_reg = filter_by_tenant(tu_query_reg, TeachingUnit)
        form.regional_id.choices = [(0, 'Selecione a Regional')] + [(tu.id, tu.name) for tu in tu_query_reg.all()]
        
        tu_query_esc = TeachingUnit.query.filter_by(type='Escola')
        tu_query_esc = filter_by_tenant(tu_query_esc, TeachingUnit)
        form.teaching_unit_id.choices = [(tu.id, f"{tu.inep_code or 'S/INEP'} - {tu.name} - {tu.municipio or ''}") for tu in tu_query_esc.order_by(TeachingUnit.name).all()]
    
    # Determine if current user is ONLY a professor (not admin)
    is_teacher = 'professor' in current_user.get_roles() and not current_user.is_admin
    
    # We populate choices on submission to allow validation of selected IDs
    # On GET, it starts empty as requested for professors
    if request.method == 'POST':
        form.descriptor_ids.choices = [(d.id, f"{d.code} - {d.description[:50]}...") for d in Descriptor.query.all()]
        if is_teacher:
            prof_profile = current_user.professor_profile
            if prof_profile:
                form.class_ids.choices = [(a.enrolled_class.id, f"{a.enrolled_class.teaching_unit.name} - {a.enrolled_class.name}") for a in prof_profile.assignments]
        elif is_unidade:
            class_query = Class.query.filter_by(teaching_unit_id=active_school_id)
            class_query = filter_by_tenant(class_query, Class)
            form.class_ids.choices = [(c.id, c.name) for c in class_query.all()]
        else:
            class_query = Class.query
            class_query = filter_by_tenant(class_query, Class)
            form.class_ids.choices = [(c.id, f"{c.teaching_unit.name} - {c.name}") for c in class_query.all()]
    else:
        # GET
        if is_teacher:
            form.class_ids.choices = []
        elif is_unidade:
            class_query = Class.query.filter_by(teaching_unit_id=active_school_id)
            class_query = filter_by_tenant(class_query, Class)
            form.class_ids.choices = [(c.id, c.name) for c in class_query.all()]
        else:
            class_query = Class.query
            class_query = filter_by_tenant(class_query, Class)
            form.class_ids.choices = [(c.id, f"{c.teaching_unit.name} - {c.name}") for c in class_query.all()]
        
        # Pre-fill from query params if available (Reinforcement Sugerido)
        if request.args.get('matrix_id'):
            form.matrix_id.data = int(request.args.get('matrix_id'))
        if request.args.get('school_year_id'):
            form.school_year_id.data = int(request.args.get('school_year_id'))
        if request.args.get('subject_id'):
            form.subject_id.data = int(request.args.get('subject_id'))

    # Pass evaluations to the template context
    evaluations_query = Evaluation.query
    evaluations_query = filter_by_tenant(evaluations_query, Evaluation)
    evaluations = evaluations_query.order_by(Evaluation.name).all()

    if form.validate_on_submit():
        # Custom validation for multiple components
        is_multiple = False
        evaluation = None
        if form.evaluation_id.data and form.evaluation_id.data != 0:
            evaluation_query = Evaluation.query.filter_by(id=form.evaluation_id.data)
            evaluation_query = filter_by_tenant(evaluation_query, Evaluation)
            evaluation = evaluation_query.first()
            if evaluation and evaluation.multiple_components:
                is_multiple = True

        validation_failed = False
        if is_multiple:
            if not form.subject_ids.data:
                form.subject_ids.errors.append('Selecione pelo menos um componente curricular.')
                validation_failed = True
            else:
                total_qty = 0
                for subj_id in form.subject_ids.data:
                    try:
                        total_qty += int(request.form.get(f'component_quantity_{subj_id}', '0'))
                    except ValueError:
                        pass
                if total_qty != form.quantity.data:
                    form.quantity.errors.append(f'A soma das questões por componente ({total_qty}) deve ser exatamente igual à quantidade total da prova ({form.quantity.data}).')
                    validation_failed = True
        else:
            if not form.subject_id.data or form.subject_id.data == 0:
                form.subject_id.errors.append('Selecione um componente curricular.')
                validation_failed = True

        if validation_failed:
            return render_template('exams/generate.html', form=form, is_teacher=is_teacher, is_unidade=is_unidade, evaluations=evaluations)
        # Check for active imports
        from app.models import ImportJob
        if ImportJob.is_any_running():
            flash('Não é possível gerar provas enquanto houver uma importação em andamento. Por favor, aguarde a conclusão na Administração.', 'warning')
            return redirect(url_for('exams.list_exams'))

        # Base query that applies to all
        base_query = Question.query
        base_query = filter_by_tenant(base_query, Question)
        
        if is_unidade:
            base_query = base_query.join(Question.validated_units).filter(TeachingUnit.id == active_school_id)
        
        # Difficulty Filter
        if form.difficulty.data != 'Any':
            base_query = base_query.filter(db.func.lower(Question.difficulty) == form.difficulty.data.lower())

        selected_questions = []

        if is_multiple and form.subject_ids.data:
            total_selected = 0
            for subj_id in form.subject_ids.data:
                qty_str = request.form.get(f'component_quantity_{subj_id}', '0')
                try:
                    qty = int(qty_str)
                except ValueError:
                    qty = 0

                if qty <= 0:
                    continue

                q_query = base_query
                # Needs descriptors join for subject filter
                if not any(isinstance(j, sa.sql.selectable.Join) for j in q_query.get_execution_options().get('joins', [])):
                    q_query = q_query.join(Question.descriptors)
                q_query = q_query.filter(Descriptor.subject_id == subj_id)

                if form.matrix_id.data and form.matrix_id.data != 0:
                    q_query = q_query.filter(Descriptor.matrix_id == form.matrix_id.data)
                    
                if form.school_year_id.data and form.school_year_id.data != 0:
                    q_query = q_query.filter(Descriptor.school_year_id == form.school_year_id.data)

                if form.descriptor_ids.data:
                    q_query = q_query.filter(Descriptor.id.in_(form.descriptor_ids.data))

                available_for_subj = q_query.distinct().all()
                if len(available_for_subj) < qty:
                    flash(f'Não há questões suficientes para o componente selecionado ({len(available_for_subj)} disponíveis, {qty} solicitadas).', 'danger')
                    return render_template('exams/generate.html', form=form, is_teacher=is_teacher, is_unidade=is_unidade, evaluations=evaluations)
                
                num_to_select = qty
                selected_questions.extend(random.sample(available_for_subj, num_to_select))
                total_selected += num_to_select
                
            if total_selected == 0:
                flash('Não foi possível gerar a prova pois não há questões suficientes para os componentes selecionados.', 'danger')
                return render_template('exams/generate.html', form=form, is_teacher=is_teacher, is_unidade=is_unidade, evaluations=evaluations)
        else:
            # Matrix/Year/Subject Filters
            if form.matrix_id.data and form.matrix_id.data != 0:
                base_query = base_query.join(Question.descriptors).filter(Descriptor.matrix_id == form.matrix_id.data)
                
            if form.school_year_id.data and form.school_year_id.data != 0:
                if not any(isinstance(j, sa.sql.selectable.Join) for j in base_query.get_execution_options().get('joins', [])):
                    base_query = base_query.join(Question.descriptors)
                base_query = base_query.filter(Descriptor.school_year_id == form.school_year_id.data)

            if form.subject_id.data and form.subject_id.data != 0:
                if not (form.matrix_id.data and form.matrix_id.data != 0) and not (form.school_year_id.data and form.school_year_id.data != 0):
                    base_query = base_query.join(Question.descriptors)
                base_query = base_query.filter(Descriptor.subject_id == form.subject_id.data)

            # Descriptor IDs Filter (Exclusive)
            if form.descriptor_ids.data:
                if not any(isinstance(j, sa.sql.selectable.Join) for j in base_query.get_execution_options().get('joins', [])):
                    base_query = base_query.join(Question.descriptors)
                base_query = base_query.filter(Descriptor.id.in_(form.descriptor_ids.data))
                
            available_questions = base_query.distinct().all()
            
            if len(available_questions) < form.quantity.data:
                flash(f'Não há questões suficientes no banco com os filtros selecionados ({len(available_questions)} disponíveis, {form.quantity.data} solicitadas).', 'danger')
                return render_template('exams/generate.html', form=form, is_teacher=is_teacher, is_unidade=is_unidade, evaluations=evaluations)
            
            num_to_select = form.quantity.data
            selected_questions = random.sample(available_questions, num_to_select)
        
        # Academic Year from date
        acad_year = str(form.application_date.data.year)
        
        # Determine target units and scoping
        target_unit_ids = []
        target_classes = []
        
        if is_teacher:
            # Teacher scoping is class-based
            target_classes_query = Class.query.filter(Class.id.in_(form.class_ids.data))
            target_classes_query = filter_by_tenant(target_classes_query, Class)
            target_classes = target_classes_query.all()
            target_unit_ids = [None] # We'll handle class linkage after create
        elif is_unidade:
            target_classes_query = Class.query.filter(Class.id.in_(form.class_ids.data))
            target_classes_query = filter_by_tenant(target_classes_query, Class)
            target_classes = target_classes_query.all()
            target_unit_ids = [active_school_id]
        else:
            if form.scope_type.data == 'school' and form.teaching_unit_id.data:
                target_unit_ids = form.teaching_unit_id.data
            elif form.scope_type.data == 'regional' and form.regional_id.data:
                schools_query = TeachingUnit.query.filter(TeachingUnit.parent_id.in_(form.regional_id.data), TeachingUnit.type == 'Escola')
                schools_query = filter_by_tenant(schools_query, TeachingUnit)
                schools = schools_query.all()
                target_unit_ids = [s.id for s in schools]
            elif form.scope_type.data == 'city' and form.target_cities.data:
                schools_query = TeachingUnit.query.filter(TeachingUnit.municipio.in_(form.target_cities.data), TeachingUnit.type == 'Escola')
                schools_query = filter_by_tenant(schools_query, TeachingUnit)
                schools = schools_query.all()
                target_unit_ids = [s.id for s in schools]
            else:
                target_unit_ids = [None]

        from app.models import ImportJob
        import threading
        from flask import current_app
        from app.utils.tenancy import get_tenant_id
        
        job = ImportJob(
            user_id=current_user.id,
            tenant_id=get_tenant_id(),
            import_type='exam_generation',
            status='running',
            total_rows=len(target_unit_ids),
            processed_rows=0,
            started_at=datetime.utcnow()
        )
        db.session.add(job)
        db.session.commit()
        
        form_data = {
            'school_year_id': form.school_year_id.data,
            'subject_id': form.subject_id.data,
            'subject_ids': form.subject_ids.data,
            'scoring_type': form.scoring_type.data,
            'total_value': form.total_value.data,
            'application_date': form.application_date.data,
            'allow_teacher_entry': form.allow_teacher_entry.data,
            'allow_teacher_view_answers': form.allow_teacher_view_answers.data,
            'target_nationality': form.target_nationality.data,
            'special_needs_filter': form.special_needs_filter.data,
            'evaluation_id': evaluation.id if evaluation else None,
            'evaluation_type': evaluation.type if evaluation else 'Indiferente',
            'evaluation_name': evaluation.name if evaluation else None,
            'is_multiple': is_multiple,
            'is_teacher': is_teacher,
            'is_unidade': is_unidade,
            'target_classes_ids': [c.id for c in target_classes],
            'selected_questions_ids': [q.id for q in selected_questions],
            'acad_year': acad_year,
            'target_unit_ids': target_unit_ids,
            'user_id': current_user.id,
            'tenant_id': get_tenant_id()
        }

        app_obj = current_app._get_current_object()
        thread = threading.Thread(target=async_generate_exams, args=(app_obj, job.id, form_data))
        thread.start()

        return redirect(url_for('exams.generation_progress', job_id=job.id))
        
    return render_template('exams/generate.html', form=form, is_teacher=is_teacher, is_unidade=is_unidade, evaluations=evaluations)


def async_generate_exams(app_obj, job_id, form_data):
    with app_obj.app_context():
        from app.models import ImportJob, Exam, ExamItem, SchoolYear, Subject, TeachingUnit, Class, Question
        from app import db
        import json
        from datetime import datetime
        from app.audit_utils import log_audit
        
        job = ImportJob.query.get(job_id)
        if not job:
            return
            
        try:
            first_exam_id = None
            target_unit_ids = form_data['target_unit_ids']
            is_multiple = form_data['is_multiple']
            scoring_type = form_data['scoring_type']
            total_val_raw = form_data['total_value']
            is_teacher = form_data['is_teacher']
            is_unidade = form_data['is_unidade']
            
            selected_questions = Question.query.filter(Question.id.in_(form_data['selected_questions_ids'])).all()
            target_classes = Class.query.filter(Class.id.in_(form_data['target_classes_ids'])).all()
            school_year = SchoolYear.query.get(form_data['school_year_id'])
            
            total_val = 0.0
            if total_val_raw:
                try:
                    total_val = float(str(total_val_raw).replace(',', '.'))
                except ValueError:
                    total_val = 0.0
            
            for unit_id in target_unit_ids:
                if is_multiple:
                    exam_title = form_data['evaluation_name'] if form_data['evaluation_name'] else f"Multidisciplinar - {school_year.name} - {form_data['application_date'].strftime('%d/%m/%Y')}"
                    subject_id_val = None
                else:
                    subject = Subject.query.get(form_data['subject_id'])
                    exam_title = form_data['evaluation_name'] if form_data['evaluation_name'] else f"{subject.name} - {school_year.name} - {form_data['application_date'].strftime('%d/%m/%Y')}"
                    subject_id_val = form_data['subject_id'] if form_data['subject_id'] != 0 else None

                target_regional_id = None
                if unit_id:
                    school_unit = TeachingUnit.query.get(unit_id)
                    if school_unit:
                        target_regional_id = school_unit.parent_id

                exam = Exam(
                    evaluation_id=form_data['evaluation_id'],
                    title=exam_title,
                    evaluation_type=form_data['evaluation_type'],
                    academic_year=form_data['acad_year'],
                    application_date=form_data['application_date'],
                    subject_id=subject_id_val,
                    school_year_id=form_data['school_year_id'] if form_data['school_year_id'] != 0 else None,
                    regional_id=target_regional_id,
                    teaching_unit_id=unit_id,
                    created_by_id=form_data['user_id'],
                    allow_teacher_entry=form_data['allow_teacher_entry'] if not is_teacher else True,
                    allow_teacher_view_answers=form_data['allow_teacher_view_answers'] if not is_teacher else True,
                    scoring_type=scoring_type,
                    total_value=total_val if scoring_type == 'total' else (total_val * len(selected_questions) if scoring_type == 'fixed' else 0.0),
                    target_nationality=form_data['target_nationality'],
                    target_special_needs='Somente Deficientes' if form_data['special_needs_filter'] == 'only_special' else 'Todos',
                    tenant_id=form_data['tenant_id']
                )
                
                if is_teacher or is_unidade:
                    for c in target_classes:
                        exam.classes.append(c)
                        
                db.session.add(exam)
                db.session.flush()
                
                if not first_exam_id: first_exam_id = exam.id
                
                question_values = {}
                if scoring_type == 'fixed':
                    val_per_q = total_val
                    for q in selected_questions:
                        question_values[q.id] = val_per_q
                elif scoring_type == 'total' and total_val > 0:
                    weights = {'Facil': 1.0, 'Medio': 1.5, 'Dificil': 2.0}
                    total_weight = sum([weights.get(q.difficulty or 'Facil', 1.0) for q in selected_questions])
                    base_val = total_val / total_weight if total_weight > 0 else 0
                    for q in selected_questions:
                        question_values[q.id] = base_val * weights.get(q.difficulty or 'Facil', 1.0)
                else:
                    for q in selected_questions:
                        question_values[q.id] = 0.0

                for q in selected_questions:
                    item = ExamItem(exam_id=exam.id, question_id=q.id, value=question_values.get(q.id, 0.0))
                    db.session.add(item)
                
                db.session.commit()
                job.processed_rows += 1
                db.session.commit()
                
            job.status = 'completed'
            job.finished_at = datetime.utcnow()
            job.errors = json.dumps({'first_exam_id': first_exam_id})
            db.session.commit()
            
            if first_exam_id:
                log_audit('CREATE', 'Exam', first_exam_id, "Gerou prova(s) a partir do sorteador automático em background")

        except Exception as e:
            db.session.rollback()
            job.status = 'error'
            job.errors = str(e)
            job.finished_at = datetime.utcnow()
            db.session.commit()
            import traceback
            traceback.print_exc()

@exams_bp.route('/generation-progress/<int:job_id>')
@login_required
def generation_progress(job_id):
    from app.models import ImportJob
    job = ImportJob.query.get_or_404(job_id)
    if job.user_id != current_user.id:
        abort(403)
    return render_template('exams/generation_progress.html', job=job)

@exams_bp.route('/api/jobs/<int:job_id>')
@login_required
def check_generation_status(job_id):
    from app.models import ImportJob
    import json
    from flask import url_for
    job = ImportJob.query.get_or_404(job_id)
    if job.user_id != current_user.id:
        abort(403)
    
    response = {
        'status': job.status,
        'total_rows': job.total_rows,
        'processed_rows': job.processed_rows,
        'progress_percentage': job.progress_percentage
    }
    
    if job.status == 'completed':
        try:
            data = json.loads(job.errors) if job.errors else {}
            exam_id = data.get('first_exam_id')
            if exam_id:
                response['redirect_url'] = url_for('exams.view_exam', id=exam_id)
            else:
                response['redirect_url'] = url_for('exams.list_exams')
        except:
            response['redirect_url'] = url_for('exams.list_exams')
    elif job.status == 'error':
        response['errors'] = job.errors
        
    return jsonify(response)

@exams_bp.route('/api/descriptors/search')
@login_required
def search_descriptors_api():
    matrix_id = request.args.get('matrix_id', type=int)
    year_id = request.args.get('year_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    subject_ids_str = request.args.get('subject_ids')
    
    query = Descriptor.query
    query = filter_by_tenant(query, Descriptor)
    if matrix_id and matrix_id != 0:
        query = query.filter(Descriptor.matrix_id == matrix_id)
    if year_id and year_id != 0:
        query = query.filter(Descriptor.school_year_id == year_id)
        
    if subject_ids_str:
        try:
            subject_ids = [int(x) for x in subject_ids_str.split(',') if x]
            if subject_ids:
                query = query.filter(Descriptor.subject_id.in_(subject_ids))
        except ValueError:
            pass
    elif subject_id and subject_id != 0:
        query = query.filter(Descriptor.subject_id == subject_id)
        
    descriptors = query.order_by(Descriptor.code).all()
    return jsonify([{
        'id': d.id,
        'code': d.code,
        'description': d.description,
        'subject_name': d.subject.name if d.subject else ''
    } for d in descriptors])

@exams_bp.route('/api/matrix_years/<int:matrix_id>')
@login_required
def get_matrix_years(matrix_id):
    from app.models import SchoolYear, Descriptor
    from app.utils.tenancy import filter_by_tenant
    
    query = SchoolYear.query.join(Descriptor, Descriptor.school_year_id == SchoolYear.id)\
        .filter(Descriptor.matrix_id == matrix_id)
    query = filter_by_tenant(query, SchoolYear)
    
    years = query.distinct().order_by(SchoolYear.name).all()
    return jsonify([{'id': y.id, 'name': y.name} for y in years])

@exams_bp.route('/api/matrix_year_subjects')
@login_required
def get_matrix_year_subjects():
    from app.models import Subject, Descriptor, Question, question_descriptors, TeachingUnit
    from app.utils.tenancy import get_tenant_id
    from flask import request, session
    from sqlalchemy import func
    import sqlalchemy as sa
    
    matrix_id = request.args.get('matrix_id', type=int)
    year_id = request.args.get('year_id', type=int)
    
    if not matrix_id or not year_id:
        return jsonify([])
        
    tenant_id = get_tenant_id()
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')
    is_unidade = (active_role == 'unidade')

    # Subquery to count active distinct questions per descriptor
    q_query = db.session.query(
        question_descriptors.c.descriptor_id,
        func.count(db.distinct(Question.id)).label('q_count')
    ).join(Question, Question.id == question_descriptors.c.question_id)

    if is_unidade:
        q_query = q_query.join(Question.validated_units).filter(TeachingUnit.id == active_school_id)

    q_query = q_query.filter(Question.tenant_id == tenant_id)\
        .group_by(question_descriptors.c.descriptor_id).subquery()
        
    # Main query
    query = db.session.query(
        Subject.id,
        Subject.name,
        func.coalesce(func.sum(q_query.c.q_count), 0).label('total_questions')
    ).join(Descriptor, Descriptor.subject_id == Subject.id)\
     .outerjoin(q_query, q_query.c.descriptor_id == Descriptor.id)\
     .filter(Descriptor.matrix_id == matrix_id, Descriptor.school_year_id == year_id)\
     .filter(Subject.tenant_id == tenant_id)\
     .group_by(Subject.id, Subject.name)\
     .order_by(Subject.name)
     
    results = query.all()
    return jsonify([{'id': r.id, 'name': r.name, 'question_count': int(r.total_questions)} for r in results])

@exams_bp.route('/api/curriculum_subjects/<int:year_id>')
@login_required
def get_curriculum_subjects(year_id):
    from app.models import CurriculumStructure
    query = CurriculumStructure.query.filter_by(school_year_id=year_id)
    query = filter_by_tenant(query, CurriculumStructure)
    structures = query.all()
    subjects = []
    seen = set()
    for struct in structures:
        for s in struct.subjects:
            if s.id not in seen:
                seen.add(s.id)
                subjects.append(s)
    if not subjects:
        subjects_query = filter_by_tenant(Subject.query, Subject)
        subjects = subjects_query.order_by(Subject.name).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in subjects])

@exams_bp.route('/<int:id>')
def view_exam(id):
    exam_query = Exam.query.filter_by(id=id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    
    # Filter schools that have classes of the same school year as the exam
    # and were optionally scoped to the exam (if exam is scoped)
    schools_query = TeachingUnit.query.filter_by(type='Escola')\
        .join(Class, Class.teaching_unit_id == TeachingUnit.id)\
        .filter(Class.school_year_id == exam.school_year_id)
    schools_query = filter_by_tenant(schools_query, TeachingUnit)
        
    if exam.classes.count() > 0:
        scoped_school_ids = [c.teaching_unit_id for c in exam.classes]
        schools_query = schools_query.filter(TeachingUnit.id.in_(scoped_school_ids))
    elif exam.teaching_unit_id:
        schools_query = schools_query.filter(TeachingUnit.id == exam.teaching_unit_id)
    elif exam.regional_id:
        schools_query = schools_query.filter(TeachingUnit.parent_id == exam.regional_id)
        
    # Restrict schools to professor's assignments if not admin
    if 'professor' in current_user.get_roles() and not current_user.is_admin and 'regional_manager' not in current_user.get_roles():
        prof_profile = current_user.professor_profile
        if prof_profile:
            # Only consider schools where the professor has an assignment matching the exam's school year
            prof_school_ids = [
                a.enrolled_class.teaching_unit_id 
                for a in prof_profile.assignments 
                if a.enrolled_class.school_year_id == exam.school_year_id
            ]
            schools_query = schools_query.filter(TeachingUnit.id.in_(prof_school_ids))

    schools = schools_query.distinct().order_by(TeachingUnit.name).all()
    
    # Identificar se o usuário pode analisar (Admin ou Professor com turma vinculada)
    can_analyze = False
    if current_user.is_authenticated:
        if current_user.is_admin or 'regional_manager' in current_user.get_roles():
            can_analyze = True
        elif current_user.id == exam.created_by_id:
            can_analyze = True
        elif 'professor' in current_user.get_roles():
            professor = current_user.professor_profile
            # Allow analyze if they teach the same year as the exam
            year_ids = [a.enrolled_class.school_year_id for a in professor.assignments] if professor else []
            if exam.school_year_id in year_ids or exam.created_by_id == current_user.id:
                can_analyze = True

    return render_template('exams/view.html', exam=exam, schools=schools, mode='teacher', can_analyze=can_analyze)

@exams_bp.route('/<int:id>/suggest-reinforcement')
@login_required
def suggest_reinforcement(id):
    exam_query = Exam.query.filter_by(id=id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    if exam.results.count() == 0:
        flash('Nenhum resultado encontrado para esta prova para sugerir reforço.', 'warning')
        return redirect(url_for('exams.view_exam', id=id))

    school_id = request.args.get('school_id', type=int)
    class_id = request.args.get('class_id', type=int)

    # Restriction for professor
    if 'professor' in current_user.get_roles() and not current_user.is_admin and 'regional_manager' not in current_user.get_roles():
        prof_profile = current_user.professor_profile
        if class_id:
            prof_class_ids = [a.class_id for a in prof_profile.assignments] if prof_profile else []
            if class_id not in prof_class_ids:
                flash('Você não tem permissão para analisar esta turma.', 'danger')
                return redirect(url_for('exams.view_exam', id=id))
        elif school_id:
            prof_school_ids = [a.enrolled_class.teaching_unit_id for a in prof_profile.assignments] if prof_profile else []
            if school_id not in prof_school_ids:
                flash('Você não tem permissão para analisar esta escola.', 'danger')
                return redirect(url_for('exams.view_exam', id=id))

    # Identificar resultados filtrados
    query = exam.results
    if class_id:
        query = query.join(Student).join(Enrollment).filter(Enrollment.class_id == class_id, Enrollment.active == True)
    elif school_id:
        query = query.join(Student).join(Enrollment).join(Class).filter(Class.teaching_unit_id == school_id, Enrollment.active == True)
    
    results = query.all()
    if not results:
        flash('Nenhum resultado encontrado para os filtros selecionados.', 'warning')
        return redirect(url_for('exams.view_exam', id=id))

    descriptor_scores = {} # descriptor_id -> {total_correct, total_answers}
    for res in results:
        answers = json.loads(res.answers) if res.answers else {}
        for item in exam.items:
            if not item.question:
                continue
            q = item.question
            ans = answers.get(str(q.id))
            if ans:
                for desc in q.descriptors:
                    if desc.id not in descriptor_scores:
                        descriptor_scores[desc.id] = {'correct': 0, 'total': 0}
                    descriptor_scores[desc.id]['total'] += 1
                    if ans == q.correct_alternative:
                        descriptor_scores[desc.id]['correct'] += 1
    
    # Calculate percentages and sort
    low_performers = []
    for d_id, score in descriptor_scores.items():
        perc = (score['correct'] / score['total'] * 100) if score['total'] > 0 else 100
        low_performers.append((d_id, perc))
    
    # Sort by percentage (ascending)
    low_performers.sort(key=lambda x: x[1])
    
    # Take top 3 with less than 60% success
    target_descriptors = [str(d[0]) for d in low_performers[:3] if d[1] < 60]
    
    if not target_descriptors:
        flash('Bom desempenho geral! Não há descritores críticos (abaixo de 60%) para sugerir reforço.', 'info')
        return redirect(url_for('exams.view_exam', id=id))
    
    flash(f'Sugestão baseada em {len(target_descriptors)} descritores com baixo desempenho.', 'info')
    
    first_item = exam.items.first()
    matrix_id = 0
    if first_item and first_item.question.descriptors:
        matrix_id = first_item.question.descriptors[0].matrix_id

    # Redirect to generator with params
    return redirect(url_for('exams.generate_exam', 
                           matrix_id=matrix_id,
                           school_year_id=exam.school_year_id,
                           subject_id=exam.subject_id,
                           descriptor_ids=",".join(target_descriptors)))

@exams_bp.route('/<int:id>/student')
def student_view(id):
    exam_query = Exam.query.filter_by(id=id)
    if current_user.is_authenticated:
        exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    
    # Shuffle alternatives for each question
    questions_data = []
    
    # Seed with exam ID + Student ID (simulated by random here as we don't have session yet)
    # Ideally use a session-based seed
    rng = random.Random(id) 
    
    for item in exam.items:
        if not item.question:
            continue
        q = item.question
        alts = q.get_alternatives()
        
        # Create list of (key, text) tuples
        alt_list = list(alts.items())
        rng.shuffle(alt_list)
        
        # Re-assign keys A, B, C, D, E for display, but keep track of original key for correctness
        # Wait, usually for student view, we just show options.
        # If we need to process answers later, we need to know that Option 1 corresponds to Original C.
        
        shuffled_alts = []
        labels = ['A', 'B', 'C', 'D', 'E']
        for i, (orig_key, text) in enumerate(alt_list):
            if i < len(labels):
                shuffled_alts.append({
                    'label': labels[i],
                    'text': text,
                    'original_key': orig_key
                })
        
        questions_data.append({
            'question': q,
            'alternatives': shuffled_alts
        })
        
    return render_template('exams/view.html', exam=exam, mode='student', questions_data=questions_data)

@exams_bp.route('/<int:id>/delete', methods=['GET', 'POST'])
@login_required
def delete_exam(id):
    # GET só ocorre após redirect de login (sessão expirada): retorna para a lista
    if request.method == 'GET':
        flash('Sessão expirada. Por favor, tente excluir novamente.', 'warning')
        return redirect(url_for('exams.list_exams'))
    exam_query = Exam.query.filter_by(id=id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    
    # Permission check
    is_owner = current_user.id == exam.created_by_id
    is_admin = current_user.is_admin or 'regional_manager' in current_user.get_roles()
    if not (is_owner or is_admin):
        flash('Você não tem permissão para excluir esta prova.', 'danger')
        return redirect(url_for('exams.list_exams'))
    
    results = exam.results.all()
    has_real_answers = False
    for res in results:
        answers = json.loads(res.answers) if res.answers else {}
        if answers:
            has_real_answers = True
            break
            
    if has_real_answers:
        flash('Esta prova possui respostas de alunos e não pode ser excluída. Tente inativá-la.', 'danger')
        return redirect(url_for('exams.list_exams'))
    
    # Delete empty results first to avoid FK constraint issues
    for res in results:
        db.session.delete(res)
        
    db.session.delete(exam)
    db.session.commit()
    from app.audit_utils import log_audit
    log_audit('DELETE', 'Exam', id, f"Excluiu a prova ID {id}")
    flash('Excluído com sucesso', 'success_delete')
    return redirect(url_for('exams.list_exams'))

@exams_bp.route('/<int:id>/approve', methods=['POST'])
@login_required
def approve_exam(id):
    exam_query = Exam.query.filter_by(id=id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    
    # Check authorization
    is_admin = current_user.is_admin or 'regional_manager' in current_user.get_roles()
    is_creator_prof = current_user.id == exam.created_by_id and 'professor' in current_user.get_roles()
    
    if not (is_admin or is_creator_prof):
        flash('Você não tem permissão para aprovar esta prova.', 'danger')
        return redirect(url_for('exams.list_exams'))
        
    exam.status = 'Aprovado'
    exam.authorized_by_id = current_user.id
    db.session.commit()
    from app.audit_utils import log_audit
    log_audit('UPDATE', 'Exam', exam.id, f"Aprovou a prova ID {exam.id} para aplicação")
    flash(f'Prova "{exam.title}" aprovada e publicada!', 'success')
    return redirect(url_for('exams.list_exams'))

@exams_bp.route('/<int:id>/inactivate', methods=['POST'])
@login_required
def inactivate_exam(id):
    exam_query = Exam.query.filter_by(id=id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    reason = request.form.get('reason')
    
    if not reason:
        flash('É obrigatório informar um motivo para inativar a prova.', 'danger')
        return redirect(url_for('exams.list_exams'))
        
    previous_status = exam.status
    exam.status = 'Inativo'
    db.session.commit()
    
    from app.audit_utils import log_audit
    log_audit('UPDATE', 'Exam', exam.id, {
        'reason': reason,
        'previous_status': previous_status,
        'exam_title': exam.title
    })
    
    flash(f'Prova "{exam.title}" inativada com sucesso.', 'info')
    return redirect(url_for('exams.list_exams'))

@exams_bp.route('/available')
@login_required
def list_available_exams():
    if 'student' not in current_user.get_roles():
        flash('Acesso restrito a alunos.', 'warning')
        return redirect(url_for('main.index'))
    
    student = current_user.student_profile
    if not student:
        flash('Perfil de aluno não encontrado.', 'danger')
        return redirect(url_for('main.index'))
    
    # Encontrar matrícula ativa para determinar escola e regional
    enrollment = student.enrollments.filter_by(active=True).first()
    if not enrollment:
        flash('Você não está matriculado em nenhuma turma ativa.', 'warning')
        return render_template('exams/student_available.html', exams=[])

    school = enrollment.enrolled_class.teaching_unit
    regional = school.parent if school else None
    school_year = enrollment.enrolled_class.school_year
    
    # Buscar provas: Global OU da minha Regional OU da minha Escola OU da minha Turma
    # E que correspondam ao meu Ano Escolar (ex: 5º Ano)
    # Mostramos tanto Aprovado quanto Rascunho para garantir que o aluno veja
    exams_query = Exam.query.filter(
        Exam.school_year_id == school_year.id,
        Exam.status.in_(['Aprovado', 'Rascunho']),
        sa.or_(
            sa.and_(Exam.regional_id == None, Exam.teaching_unit_id == None, ~Exam.classes.any()), # Global
            Exam.regional_id == (regional.id if regional else -1),
            Exam.teaching_unit_id == school.id,
            Exam.classes.any(id=enrollment.class_id)
        )
    )
    exams_query = filter_by_tenant(exams_query, Exam).order_by(Exam.application_date.desc())
    
    # Apply Filters for Students
    all_exams = exams_query.all()
    filtered_exams = []
    
    for exam in all_exams:
        # Nationality Filter
        if exam.target_nationality == 'Brasileiro' and student.nationality != 'Brasileiro':
            continue
        
        # Special Needs Filter
        if exam.target_special_needs == 'Somente Deficientes' and not student.special_needs:
            continue
            
        filtered_exams.append(exam)
    
    return render_template('exams/student_available.html', exams=filtered_exams, student=student)

@exams_bp.route('/<int:id>/test_route')
def test_route(id):
    """Simple test route"""
    return f"<h1>TEST ROUTE WORKS! Exam ID: {id}</h1>"

@exams_bp.route('/<int:id>/record', methods=['GET', 'POST'])
@exams_bp.route('/<int:id>/record', methods=['GET', 'POST'])
@login_required
def record_answers(id):
    exam_query = Exam.query.filter_by(id=id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    
    # 1. Permission Check
    # ---------------------------------------------------------
    is_admin = current_user.is_admin or 'regional_manager' in current_user.get_roles()
    is_creator = current_user.id == exam.created_by_id
    
    is_assigned_teacher = False
    if 'professor' in current_user.get_roles():
        professor = current_user.professor_profile
        if professor:
            class_ids = [a.class_id for a in professor.assignments]
            # Check if exam is linked to any of the professor's classes
            if exam.classes.filter(Class.id.in_(class_ids)).first() is not None:
                is_assigned_teacher = True
            # Or if the exam is global/regional but matches the professor's school year/subject
            # (Logic depends on business rules, stricter rule: must be creator or assigned)
            
    can_record = is_admin or is_creator or exam.allow_teacher_entry or is_assigned_teacher
    
    if not can_record:
        flash('Você não tem permissão para registrar respostas nesta prova.', 'danger')
        return redirect(url_for('exams.view_exam', id=id))

    # 2. Setup Context (Schools, Absence Reasons)
    # ---------------------------------------------------------
    absence_query = AbsenceReason.query
    absence_query = filter_by_tenant(absence_query, AbsenceReason)
    absence_reasons = absence_query.all()
    
    # Filter schools available to the user
    schools_query = TeachingUnit.query.filter_by(type='Escola')\
        .join(Class, Class.teaching_unit_id == TeachingUnit.id)\
        .filter(Class.school_year_id == exam.school_year_id)
    schools_query = filter_by_tenant(schools_query, TeachingUnit)
        
    if exam.classes.count() > 0:
        scoped_school_ids = [c.teaching_unit_id for c in exam.classes]
        schools_query = schools_query.filter(TeachingUnit.id.in_(scoped_school_ids))
        
    if 'professor' in current_user.get_roles() and not current_user.is_admin and 'regional_manager' not in current_user.get_roles():
        prof_profile = current_user.professor_profile
        if prof_profile:
            prof_school_ids = [
                a.enrolled_class.teaching_unit_id 
                for a in prof_profile.assignments 
                if a.enrolled_class.school_year_id == exam.school_year_id
            ]
            schools_query = schools_query.filter(TeachingUnit.id.in_(prof_school_ids))

    schools = schools_query.distinct().order_by(TeachingUnit.name).all()

    # 3. Handle POST (Save Answers)
    # ---------------------------------------------------------
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        absence_reason_id = request.form.get('absence_reason_id')
        
        if not student_id:
            flash('Selecione um aluno.', 'danger')
            return redirect(url_for('exams.record_answers', id=id))
            
        student_query = Student.query.filter_by(id=student_id)
        student_query = filter_by_tenant(student_query, Student)
        student = student_query.first_or_404()
        
        # Check if result already exists
        result = StudentResult.query.filter_by(exam_id=exam.id, student_id=student.id).first()
        if not result:
            result = StudentResult(exam_id=exam.id, student_id=student.id)
            db.session.add(result)
            
        # Handle Absence
        if absence_reason_id:
            result.absence_reason_id = absence_reason_id
            result.answers = "{}"
            result.score_percentage = 0.0
            flash(f'Ausência registrada para {student.name}.', 'warning')
        else:
            # Handle Answers
            result.absence_reason_id = None
            answers = {}
            score_points = 0.0
            
            # Retrieve answer for each question
            for item in exam.items:
                if not item.question:
                    continue
                qid_str = str(item.question.id)
                selected_option = request.form.get(f'q_{item.question.id}')
                
                if selected_option:
                    answers[qid_str] = selected_option
                    
                    # Calculate Score
                    if selected_option == item.question.correct_alternative:
                        if exam.scoring_type == 'fixed' or exam.scoring_type == 'total':
                            score_points += (item.value or 0.0)
                        else:
                            # If no value defined, we just count raw correct (handled in percentage calc below)
                            score_points += 1.0 
                            
            result.answers = json.dumps(answers)
            
            # Calculate Percentage
            if exam.scoring_type == 'total':
                 # score_points is the sum of values
                 if exam.total_value and exam.total_value > 0:
                     result.score_percentage = (score_points / exam.total_value) * 100
                 else:
                     result.score_percentage = 0.0
            else:
                # Based on number of correct questions vs total questions
                total_questions = exam.items.count()
                correct_count = 0
                for qid, ans in answers.items():
                    # Find question to check correct alternative (optimized check)
                    # For now, re-check logic or trust the loop above. 
                    # Let's count correct answers from the loop above strictly.
                    pass # We did points above.
                    
                # Creating a simpler loop for percentage to be robust
                correct_count = 0
                for item in exam.items:
                    if not item.question:
                        continue
                    qid_str = str(item.question.id)
                    if answers.get(qid_str) == item.question.correct_alternative:
                        correct_count += 1
                
                if total_questions > 0:
                    result.score_percentage = (correct_count / total_questions) * 100
                else:
                    result.score_percentage = 0.0

            flash(f'Respostas registradas para {student.name} com sucesso!', 'success')
            
        result.finished_at = datetime.utcnow()
        db.session.commit()
        
        from app.audit_utils import log_audit
        log_audit('UPDATE', 'StudentResult', result.id, f"Registrou/alterou respostas do aluno {student.name} na prova ID {exam.id}")
        
        # Clear Session OMR Data if it matched this student
        if session.get('detected_student_id') == student_id:
            session.pop('detected_student_id', None)
            session.pop('detected_answers', None)
            
        # Redirect keeping the context (School/Class)
        school_id = request.form.get('school_id')     # From hidden or select? The select is enabled.
        # Actually the select might be disabled in UI if we are in OMR mode, but we can grab from query or recreating logic
        # For better UX, we assume the user is entering data for a class.
        # We need to find the class of the student to keep context
        enrollment = student.enrollments.filter_by(active=True).first()
        redirect_args = {'id': id}
        if enrollment:
            redirect_args['school_id'] = enrollment.enrolled_class.teaching_unit_id
            redirect_args['class_id'] = enrollment.class_id
            
        return redirect(url_for('exams.record_answers', **redirect_args))

    # 4. Handle GET (Render Form)
    # ---------------------------------------------------------
    # Check for OMR Data in Session
    detected_answers = session.get('detected_answers', {})
    detected_student_id = session.get('detected_student_id')
    
    pre_school_id = request.args.get('school_id', type=int)
    pre_class_id = request.args.get('class_id', type=int)
    
    # If OMR student detected, override context to that student's class
    if detected_student_id:
        student_query = Student.query.filter_by(id=detected_student_id)
        student_query = filter_by_tenant(student_query, Student)
        student = student_query.first()
        if student:
            enrollment = student.enrollments.filter_by(active=True).first()
            if enrollment:
                pre_class_id = enrollment.class_id
                pre_school_id = enrollment.enrolled_class.teaching_unit_id
                
    return render_template('exams/record_answers.html', 
                          exam=exam, 
                          schools=schools,
                          absence_reasons=absence_reasons,
                          detected_answers=detected_answers,
                          detected_student_id=detected_student_id,
                          pre_school_id=pre_school_id,
                          pre_class_id=pre_class_id)


@exams_bp.route('/api/classes_for_school/<int:school_id>')
@login_required
def api_classes_for_school(school_id):
    exam_id = request.args.get('exam_id', type=int)
    query = Class.query.filter_by(teaching_unit_id=school_id)
    query = filter_by_tenant(query, Class)
    
    if exam_id:
        exam_query = Exam.query.filter_by(id=exam_id)
        exam_query = filter_by_tenant(exam_query, Exam)
        exam = exam_query.first()
        if exam:
            # Filter by school year of the exam
            query = query.filter_by(school_year_id=exam.school_year_id)
            
            # If the exam is scoped to specific classes, filter further
            if exam.classes.count() > 0:
                query = query.filter(Class.id.in_([c.id for c in exam.classes]))
    
    # Restrict to professor's own classes if not admin
    if 'professor' in current_user.get_roles() and not current_user.is_admin and 'regional_manager' not in current_user.get_roles():
        prof_profile = current_user.professor_profile
        prof_class_ids = [a.class_id for a in prof_profile.assignments] if prof_profile else []
        query = query.filter(Class.id.in_(prof_class_ids))
            
    classes = query.order_by(Class.name).all()
    return jsonify([{'id': c.id, 'name': c.name} for c in classes])

@exams_bp.route('/api/professor_classes')
@login_required
def api_professor_classes():
    year_id = request.args.get('school_year_id', type=int)
    subject_id = request.args.get('subject_id', type=int)
    
    if 'professor' not in current_user.get_roles() or current_user.is_admin:
        return jsonify([])
        
    prof_profile = current_user.professor_profile
    if not prof_profile:
        return jsonify([])
        
    classes = []
    seen_ids = set()
    # Use .all() to resolve dynamic relationship
    for assignment in prof_profile.assignments.all():
        c = assignment.enrolled_class
        # Filter by year (only if provided)
        if year_id and c.school_year_id != year_id:
            continue
        # Filter by subject (only if provided)
        if subject_id and assignment.subject_id != subject_id:
            continue
            
        if c.id not in seen_ids:
            classes.append({'id': c.id, 'name': f"{c.teaching_unit.name} - {c.name}"})
            seen_ids.add(c.id)
            
    return jsonify(classes)

@exams_bp.route('/api/students_for_class/<int:class_id>')
@login_required
def api_students_for_class(class_id):
    exam_id = request.args.get('exam_id', type=int)
    from app.models import Student, Enrollment
    
    query = Student.query.join(Enrollment)\
        .filter(Enrollment.class_id == class_id, Enrollment.active == True)
    query = filter_by_tenant(query, Student)
    
    if exam_id:
        exam_query = Exam.query.filter_by(id=exam_id)
        exam_query = filter_by_tenant(exam_query, Exam)
        exam = exam_query.first()
        if exam:
            if exam.target_nationality == 'Brasileiro':
                query = query.filter(Student.nationality == 'Brasileiro')
            
            if exam.target_special_needs == 'Somente Deficientes':
                query = query.filter(Student.special_needs == True)
                
    students = query.order_by(Student.name).all()
    return jsonify([{'id': s.id, 'name': f"{s.name} ({s.registration_number})"} for s in students])

@exams_bp.route('/scan', defaults={'id': None}, methods=['GET', 'POST'])
@exams_bp.route('/<int:id>/scan', methods=['GET', 'POST'])
@login_required
def scan_answers(id):
    exam = None
    if id:
        exam_query = Exam.query.filter_by(id=id)
        exam_query = filter_by_tenant(exam_query, Exam)
        exam = exam_query.first_or_404()
        # Permission check
        is_admin = current_user.is_admin or 'regional_manager' in current_user.get_roles()
        is_creator = current_user.id == exam.created_by_id
        
        is_assigned_teacher = False
        if 'professor' in current_user.get_roles():
            professor = current_user.professor_profile
            class_ids = [a.class_id for a in professor.assignments] if professor else []
            if exam.classes.filter(Class.id.in_(class_ids)).first() is not None:
                is_assigned_teacher = True

        can_record = is_admin or is_creator or exam.allow_teacher_entry or is_assigned_teacher
        
        if not can_record:
            flash('Você não tem permissão para escanear respostas nesta prova.', 'danger')
            return redirect(url_for('exams.view_exam', id=id))

    exams = []
    if not id:
        # If no specific id, we need to pass a list of exams for the user to select
        if current_user.is_admin:
            exams_query = Exam.query
            exams_query = filter_by_tenant(exams_query, Exam)
            exams = exams_query.order_by(Exam.application_date.desc()).all()
        else:
            # Regional managers or teachers see their relevant exams
            roles = current_user.get_roles()
            if 'regional_manager' in roles:
                exams_query = Exam.query.filter(Exam.regional_id != None)
                exams_query = filter_by_tenant(exams_query, Exam)
                exams = exams_query.order_by(Exam.application_date.desc()).all()
            else:
                exams_query = Exam.query.filter_by(created_by_id=current_user.id)
                exams_query = filter_by_tenant(exams_query, Exam)
                exams = exams_query.order_by(Exam.application_date.desc()).all()
    # Scope check for breadcrumbs / context
    if exam:
        is_admin = current_user.is_admin or 'regional_manager' in current_user.get_roles()
        is_creator = current_user.id == exam.created_by_id
        can_record = is_admin or is_creator or exam.allow_teacher_entry
        
        if not can_record:
            flash('Você não tem permissão para escanear respostas nesta prova.', 'danger')
            return redirect(url_for('exams.view_exam', id=id))

    if request.method == 'POST':
        submitted_exam_id = request.form.get('exam_id') or id
        if not submitted_exam_id:
            flash('Selecione a prova.', 'warning')
            return redirect(url_for('exams.scan_answers'))
        
        current_exam_query = Exam.query.filter_by(id=submitted_exam_id)
        current_exam_query = filter_by_tenant(current_exam_query, Exam)
        current_exam = current_exam_query.first_or_404()
        student_id = request.form.get('student_id')
        file = request.files.get('card_image')
        
        if not student_id or not file:
            flash('Selecione o aluno e envie a imagem do cartão.', 'warning')
            return redirect(url_for('exams.scan_answers', id=submitted_exam_id))
            
        # Save temp file
        import os
        from werkzeug.utils import secure_filename
        from app.utils.omr import process_omr_sheet
        
        filename = secure_filename(file.filename)
        temp_path = os.path.join('instance', 'temp_' + filename)
        file.save(temp_path)
        
        try:
            detected = process_omr_sheet(temp_path, current_exam.items.count())
            os.remove(temp_path)
            
            if "error" in detected:
                flash(detected["error"], "danger")
                return redirect(url_for('exams.scan_answers', id=submitted_exam_id))
                
            session['detected_answers'] = detected
            session['detected_student_id'] = student_id
            
            flash('Cartão processado! Verifique as respostas detectadas abaixo e clique em Salvar.', 'success')
            return redirect(url_for('exams.record_answers', id=submitted_exam_id))
            
        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            flash(f'Erro ao processar imagem: {str(e)}', 'danger')
            return redirect(url_for('exams.scan_answers', id=submitted_exam_id))

    return render_template('exams/scan_answers.html', exam=exam, exams=exams)

@exams_bp.route('/api/schools_for_exam/<int:exam_id>')
@login_required
def api_schools_for_exam(exam_id):
    from app.models import TeachingUnit, SchoolYear
    exam_query = Exam.query.filter_by(id=exam_id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    
    # We want schools that have at least one class in the exam's school year
    # OR schools that are in the exam's regional scope if applicable
    query = TeachingUnit.query.filter_by(type='Escola')
    query = filter_by_tenant(query, TeachingUnit)
    
    if exam.classes.count() > 0:
        # If exam is restricted to specific classes, only show schools that have those classes
        school_ids = db.session.query(Class.teaching_unit_id).filter(Class.id.in_([c.id for c in exam.classes])).distinct().all()
        query = query.filter(TeachingUnit.id.in_([s[0] for s in school_ids]))
    elif exam.teaching_unit_id:
        query = query.filter_by(id=exam.teaching_unit_id)
    elif exam.regional_id:
        query = query.filter_by(parent_id=exam.regional_id)
        
    # Filter by school year matching
    query = query.join(Class).filter(Class.school_year_id == exam.school_year_id).distinct()
    
    schools = query.order_by(TeachingUnit.name).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in schools])

@exams_bp.route('/take/<int:id>', methods=['GET', 'POST'])
@login_required
def take_exam(id):
    if current_user.role != 'student':
        flash('Apenas alunos podem responder provas.', 'danger')
        return redirect(url_for('main.index'))
        
    exam_query = Exam.query.filter_by(id=id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    student = current_user.student_profile
    
    # Access Control Validation
    enrollment = student.enrollments.filter_by(active=True).first()
    if not enrollment:
        flash('Você não está matriculado em nenhuma turma ativa.', 'danger')
        return redirect(url_for('exams.list_available_exams'))
        
    school = enrollment.enrolled_class.teaching_unit
    regional = school.parent if school else None
    school_year = enrollment.enrolled_class.school_year
    
    # Check if exam is for this student's year
    if exam.school_year_id != school_year.id:
        flash('Esta prova não corresponde ao seu ano escolar.', 'danger')
        return redirect(url_for('exams.list_available_exams'))
        
    # Check scope
    is_global = (exam.regional_id == None and exam.teaching_unit_id == None and exam.classes.count() == 0)
    is_regional = (exam.regional_id == regional.id) if regional else False
    is_school = (exam.teaching_unit_id == school.id)
    is_class = any(c.id == enrollment.class_id for c in exam.classes)
    
    if not (is_global or is_regional or is_school or is_class):
        flash('Você não tem autorização para realizar esta prova.', 'danger')
        return redirect(url_for('exams.list_available_exams'))
    
    # Filter Checks (Nationality / Special Needs)
    if exam.target_nationality == 'Brasileiro' and student.nationality != 'Brasileiro':
        flash('Esta prova é restrita a alunos de nacionalidade brasileira.', 'warning')
        return redirect(url_for('exams.list_available_exams'))
        
    if exam.target_special_needs == 'Somente Deficientes' and not student.special_needs:
        flash('Esta prova é exclusiva para alunos com deficiência.', 'warning')
        return redirect(url_for('exams.list_available_exams'))

    # Verificar se já respondeu (finalizou)
    existing_result = StudentResult.query.filter_by(
        exam_id=exam.id, 
        student_id=student.id
    ).filter(StudentResult.finished_at != None).first()
    
    if existing_result:
        flash('Você já respondeu esta prova.', 'info')
        return redirect(url_for('exams.list_available_exams'))
    
    # Buscar ou criar resultado temporário (progresso)
    result = StudentResult.query.filter_by(
        exam_id=exam.id, 
        student_id=student.id
    ).filter(StudentResult.finished_at == None).first()
    
    if not result:
        result = StudentResult(exam_id=exam.id, student_id=student.id, answers=json.dumps({}))
        db.session.add(result)
        db.session.commit()
    
    saved_answers = json.loads(result.answers) if result.answers else {}
    
    if request.method == 'POST':
        answers = {}
        correct_count = 0
        total_count = exam.items.count()
        absolute_score = 0
        total_value = exam.total_value or 0
        
        for item in exam.items:
            if not item.question:
                continue
            field_name = f"q_{item.question.id}"
            selected = request.form.get(field_name)
            answers[str(item.question.id)] = selected
            
            if selected == item.question.correct_alternative:
                correct_count += 1
                if exam.scoring_type == 'fixed':
                    absolute_score += (item.value or 0)
        
        if exam.scoring_type == 'total' and total_count > 0:
            absolute_score = (correct_count / total_count) * total_value
        elif exam.scoring_type == 'none' or not exam.scoring_type:
             absolute_score = correct_count
             
        score_pct = (correct_count / total_count * 100) if total_count > 0 else 0
        
        result.answers = json.dumps(answers)
        result.score_percentage = score_pct
        # We don't have a score_points column, so we'll just flash it for now 
        # and calculate on the fly in templates if needed for persistence.
        result.finished_at = datetime.utcnow()
        db.session.commit()
        
        from app.audit_utils import log_audit
        log_audit('UPDATE', 'StudentResult', result.id, f"O aluno {student.name} respondeu autonomamente a prova {exam.title}")
        
        msg = f'Prova finalizada! Seu aproveitamento foi de {score_pct:.1f}%.'
        if total_value > 0:
            msg = f'Prova finalizada! Você obteve {absolute_score:.1f} de {total_value:.1f} pontos ({score_pct:.1f}%).'
        
        flash(msg, 'success')
        return redirect(url_for('exams.list_available_exams'))
        
    return render_template('exams/take.html', exam=exam, saved_answers=saved_answers)

@exams_bp.route('/take/<int:id>/save_progress', methods=['POST'])
@login_required
def save_exam_progress(id):
    if current_user.role != 'student':
        return jsonify({'error': 'Unauthorized'}), 403
        
    exam_query = Exam.query.filter_by(id=id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    student = current_user.student_profile
    
    # Find unfinished result
    result = StudentResult.query.filter_by(
        exam_id=exam.id, 
        student_id=student.id
    ).filter(StudentResult.finished_at == None).first()
    
    if not result:
        return jsonify({'error': 'Progress not found'}), 404
        
    data = request.json
    question_id = data.get('question_id')
    answer = data.get('answer')
    
    if question_id:
        answers = json.loads(result.answers) if result.answers else {}
        answers[str(question_id)] = answer
        result.answers = json.dumps(answers)
        db.session.commit()
        return jsonify({'status': 'success'})
        
    return jsonify({'error': 'Invalid data'}), 400
        
@exams_bp.route('/<int:id>/intervention')
@login_required
def intervention_plan(id):
    if current_user.role == 'student':
        abort(403)
        
    exam_query = Exam.query.filter_by(id=id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    
    school_id = request.args.get('school_id', type=int)
    class_id = request.args.get('class_id', type=int)

    # Restriction for professor
    if 'professor' in current_user.get_roles() and not current_user.is_admin and 'regional_manager' not in current_user.get_roles():
        prof_profile = current_user.professor_profile
        if class_id:
            prof_class_ids = [a.class_id for a in prof_profile.assignments] if prof_profile else []
            if class_id not in prof_class_ids:
                flash('Você não tem permissão para realizar esta análise.', 'danger')
                return redirect(url_for('exams.view_exam', id=id))
        elif school_id:
            prof_school_ids = [a.enrolled_class.teaching_unit_id for a in prof_profile.assignments] if prof_profile else []
            if school_id not in prof_school_ids:
                flash('Acesso restrito a unidades de ensino vinculadas ao seu perfil.', 'danger')
                return redirect(url_for('exams.view_exam', id=id))

    # Identificar resultados filtrados
    query = exam.results
    if class_id:
        query = query.join(Student).join(Enrollment).filter(Enrollment.class_id == class_id, Enrollment.active == True)
    elif school_id:
        query = query.join(Student).join(Enrollment).join(Class).filter(Class.teaching_unit_id == school_id, Enrollment.active == True)
    
    results = query.all()
    
    if not results:
        flash('Nenhum resultado registrado para os filtros selecionados.', 'warning')
        return redirect(url_for('exams.view_exam', id=id))

    # Calculate stats per question
    item_stats = []
    descriptor_totals = {} # {id: {code: str, desc: str, correct: int, total: int}}

    import json
    for item in exam.items:
        if not item.question:
            continue
        correct_count = 0
        total_results = 0
        
        for res in results:
            answers = json.loads(res.answers) if res.answers else {}
            selected = answers.get(str(item.question.id))
            if selected:
                total_results += 1
                if selected == item.question.correct_alternative:
                    correct_count += 1
        
        correct_rate = (correct_count / total_results * 100) if total_results > 0 else 0
        item_stats.append({
            'question': item.question,
            'correct_rate': correct_rate
        })

        # Track descriptors
        for d in item.question.descriptors:
            if d.id not in descriptor_totals:
                descriptor_totals[d.id] = {'code': d.code, 'description': d.description, 'correct': 0, 'total': 0}
            descriptor_totals[d.id]['correct'] += correct_count
            descriptor_totals[d.id]['total'] += total_results

    # identify critical descriptors
    critical_descriptors = []
    for d_id, stats in descriptor_totals.items():
        error_rate = 100 - (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        
        # Simple generic suggestions based on common teacher needs
        suggestion = f"Revisar o conceito base de {stats['description']} com atividades práticas e exemplos do cotidiano. Realizar reforço em pequenos grupos com os alunos que apresentarem maior dificuldade."
        
        critical_descriptors.append({
            'code': stats['code'],
            'description': stats['description'],
            'error_rate': error_rate,
            'suggestion': suggestion
        })

    # Sort critical ones by error rate DESC
    critical_descriptors.sort(key=lambda x: x['error_rate'], reverse=True)
    critical_descriptors = critical_descriptors[:5] # Top 5

    from datetime import datetime
    html = render_template('exams/intervention_plan_pdf.html',
                          exam=exam,
                          results_count=len(results),
                          critical_descriptors=critical_descriptors,
                          item_stats=item_stats,
                          now=datetime.now())

    from io import BytesIO
    from xhtml2pdf import pisa
    dest = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=dest)
    
    if pisa_status.err:
        return "Erro ao gerar PDF do Plano", 500
    
    dest.seek(0)
    return send_file(dest, 
                     download_name=f"plano_intervencao_{exam.id}.pdf",
                     as_attachment=True,
                     mimetype='application/pdf')

@exams_bp.route('/<int:id>/classes-diagnosis')
@login_required
def classes_diagnosis(id):
    if current_user.role == 'student':
        abort(403)
        
    exam_query = Exam.query.filter_by(id=id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    
    regional_id = request.args.get('regional_id', type=int)
    municipio = request.args.get('municipio', type=str)
    school_id = request.args.get('school_id', type=int)
    shift = request.args.get('shift', type=str)

    # Restriction for professor
    if 'professor' in current_user.get_roles() and not current_user.is_admin and 'regional_manager' not in current_user.get_roles():
        prof_profile = current_user.professor_profile
        prof_class_ids = [a.class_id for a in prof_profile.assignments] if prof_profile else []
    else:
        prof_class_ids = None

    # Construct the query
    query = db.session.query(
        Class.id,
        Class.name,
        TeachingUnit.id.label('school_id'),
        TeachingUnit.name.label('school_name'),
        TeachingUnit.inep_code,
        TeachingUnit.municipio,
        db.func.count(StudentResult.id).label('total_students'),
        db.func.sum(db.case((StudentResult.absence_reason_id.isnot(None), 1), else_=0)).label('absences'),
        db.func.sum(db.case((StudentResult.absence_reason_id.is_(None), 1), else_=0)).label('present'),
        db.func.avg(StudentResult.score_percentage).label('avg_score')
    ).select_from(StudentResult)\
    .join(Student, StudentResult.student_id == Student.id)\
    .join(Enrollment, (Enrollment.student_id == Student.id) & (Enrollment.active == True))\
    .join(Class, Enrollment.class_id == Class.id)\
    .join(TeachingUnit, Class.teaching_unit_id == TeachingUnit.id)\
    .filter(StudentResult.exam_id == exam.id)

    if regional_id:
        query = query.filter(TeachingUnit.parent_id == regional_id)
    if municipio:
        query = query.filter(TeachingUnit.municipio == municipio)
    if school_id:
        query = query.filter(TeachingUnit.id == school_id)
    if shift:
        query = query.filter(Class.shift == shift)

    if prof_class_ids is not None:
        query = query.filter(Class.id.in_(prof_class_ids))

    classes_stats = query.group_by(Class.id, Class.name, TeachingUnit.id, TeachingUnit.name, TeachingUnit.inep_code, TeachingUnit.municipio)\
                         .order_by(TeachingUnit.name, Class.name).all()

    stats_list = []
    for row in classes_stats:
        avg_score = row.avg_score or 0
        # Consider errors as percentage of present students only? Wait, avg_score is calculated based on present students.
        error_rate = 100 - avg_score
        absence_perc = (row.absences / row.total_students * 100) if row.total_students > 0 else 0
        stats_list.append({
            'class_id': row.id,
            'class_name': row.name,
            'school_id': row.school_id,
            'school_name': row.school_name,
            'inep_code': row.inep_code,
            'municipio': row.municipio,
            'total_students': row.total_students,
            'absences': row.absences,
            'present': row.present,
            'avg_score': avg_score,
            'error_rate': error_rate,
            'absence_perc': absence_perc
        })

    # Prepare filter choices
    # Regionals
    regionals = filter_by_tenant(TeachingUnit.query.filter_by(type='Regional'), TeachingUnit).order_by(TeachingUnit.name).all()
    
    # Municipios (only if Estadual)
    municipios = []
    if exam.tenant.type == 'Estadual':
        mun_query = db.session.query(TeachingUnit.municipio).filter(TeachingUnit.type != 'Regional', TeachingUnit.municipio != None)
        mun_query = filter_by_tenant(mun_query, TeachingUnit)
        if regional_id:
            mun_query = mun_query.filter(TeachingUnit.parent_id == regional_id)
        municipios = [m[0] for m in mun_query.distinct().order_by(TeachingUnit.municipio).all()]

    # Schools (Filtered to only targets of this exam)
    schools_query = db.session.query(TeachingUnit)\
        .join(Class, Class.teaching_unit_id == TeachingUnit.id)\
        .join(Enrollment, Enrollment.class_id == Class.id)\
        .join(Student, Enrollment.student_id == Student.id)\
        .join(StudentResult, StudentResult.student_id == Student.id)\
        .filter(StudentResult.exam_id == exam.id, Enrollment.active == True)
        
    if regional_id:
        schools_query = schools_query.filter(TeachingUnit.parent_id == regional_id)
    if municipio:
        schools_query = schools_query.filter(TeachingUnit.municipio == municipio)
        
    schools = schools_query.distinct().order_by(TeachingUnit.name).all()

    return render_template('exams/classes_diagnosis.html', 
                           exam=exam, 
                           classes_stats=stats_list,
                           regionals=regionals,
                           municipios=municipios,
                           schools=schools,
                           current_regional_id=regional_id,
                           current_municipio=municipio,
                           current_school_id=school_id,
                           current_shift=shift)

@exams_bp.route('/<int:id>/diagnosis')
@login_required
def class_diagnosis(id):
    if current_user.role == 'student':
        abort(403)
        
    exam_query = Exam.query.filter_by(id=id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first_or_404()
    
    school_id = request.args.get('school_id', type=int)
    class_id = request.args.get('class_id', type=int)
    
    school_name = None
    class_name = None
    if school_id:
        school = TeachingUnit.query.get(school_id)
        if school: school_name = school.name
    if class_id:
        cls = Class.query.get(class_id)
        if cls: class_name = cls.name

    # Restriction for professor
    if 'professor' in current_user.get_roles() and not current_user.is_admin and 'regional_manager' not in current_user.get_roles():
        prof_profile = current_user.professor_profile
        if class_id:
            prof_class_ids = [a.class_id for a in prof_profile.assignments] if prof_profile else []
            if class_id not in prof_class_ids:
                flash('Você não tem permissão para visualizar o diagnóstico desta turma.', 'danger')
                return redirect(url_for('exams.view_exam', id=id))
        elif school_id:
            prof_school_ids = [a.enrolled_class.teaching_unit_id for a in prof_profile.assignments] if prof_profile else []
            if school_id not in prof_school_ids:
                flash('Você não tem permissão para visualizar dados desta escola.', 'danger')
                return redirect(url_for('exams.view_exam', id=id))

    # Only consider finished exams for diagnosis
    query = exam.results.filter(StudentResult.finished_at != None)
    if class_id:
        query = query.join(Student).join(Enrollment).filter(Enrollment.class_id == class_id, Enrollment.active == True)
    elif school_id:
        query = query.join(Student).join(Enrollment).join(Class).filter(Class.teaching_unit_id == school_id, Enrollment.active == True)
    
    results = query.all()
    
    if not results:
        flash('Nenhum resultado finalizado encontrado para os filtros selecionados.', 'warning')
        return redirect(url_for('exams.view_exam', id=id))

    # 1. Radar Chart Data (Performance per Descriptor)
    descriptor_stats = {} # {desc_id: {code, description, correct, total}}
    
    import json
    for item in exam.items:
        if not item.question:
            continue
        q_id_str = str(item.question.id)
        q_correct = 0
        q_total = 0
        
        for res in results:
            answers = json.loads(res.answers) if res.answers else {}
            selected = answers.get(q_id_str)
            if selected:
                q_total += 1
                if selected == item.question.correct_alternative:
                    q_correct += 1
        
        for d in item.question.descriptors:
            if d.id not in descriptor_stats:
                descriptor_stats[d.id] = {'code': d.code, 'description': d.description, 'correct': 0, 'total': 0}
            descriptor_stats[d.id]['correct'] += q_correct
            descriptor_stats[d.id]['total'] += q_total

    radar_labels = []
    radar_data = []
    for d_id, stats in descriptor_stats.items():
        radar_labels.append(stats['code'])
        perc = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        radar_data.append(round(perc, 1))

    # 2. Heatmap Matrix (Students x Questions)
    # Header: Q1, Q2, ...
    # Rows: Student Name, Q1_status, Q2_status, ...
    heatmap_data = []
    for res in results:
        student_row = {'name': res.student.name, 'answers': [], 'score': res.score_percentage}
        answers = json.loads(res.answers) if res.answers else {}
        for item in exam.items:
            if not item.question:
                continue
            selected = answers.get(str(item.question.id))
            is_correct = (selected == item.question.correct_alternative) if selected else None
            student_row['answers'].append({
                'q_idx': item.id,
                'status': is_correct # True, False, None (skipped)
            })
        heatmap_data.append(student_row)
    
    # Sort students by score DESC (handle None just in case)
    heatmap_data.sort(key=lambda x: x['score'] or 0, reverse=True)

    # 3. Recommended Actions
    critical_questions = []
    for idx, item in enumerate(exam.items):
        if not item.question:
            continue
        correct_in_class = 0
        total_in_class = 0
        for res in results:
            ans = (json.loads(res.answers) if res.answers else {}).get(str(item.question.id))
            if ans:
                total_in_class += 1
                if ans == item.question.correct_alternative:
                    correct_in_class += 1
        
        error_rate = 100 - (correct_in_class / total_in_class * 100) if total_in_class > 0 else 0
        if error_rate > 60:
            critical_questions.append({
                'num': idx + 1,
                'error_rate': error_rate,
                'descriptor': ", ".join([d.code for d in item.question.descriptors])
            })

    low_performers = [s['name'] for s in heatmap_data if (s['score'] or 0) < 50]

    return render_template('exams/diagnosis.html', 
                           exam=exam,
                           results_count=len(results),
                           radar_labels=radar_labels,
                           radar_data=radar_data,
                           heatmap_data=heatmap_data,
                           critical_questions=critical_questions,
                           low_performers=low_performers,
                           school_name=school_name,
                           class_name=class_name)

def generate_pdf_worker(app, job_id, exam_id, students_list, evaluation_id, logo_url, font_size='12pt', layout_columns='1'):
    with app.app_context():
        try:
            from app.models import Exam, Evaluation
            exam = Exam.query.get(exam_id)
            evaluation = Evaluation.query.get(evaluation_id) if evaluation_id else None
            
            writer = PdfWriter()
            total = len(students_list)
            
            for i, student_data in enumerate(students_list):
                # Generate HTML for a single student
                html = render_template('exams/print_student.html', 
                                      exam=exam, 
                                      evaluation=evaluation,
                                      logo_url=logo_url,
                                      students_list=[student_data],
                                      now=datetime.now(),
                                      font_size=font_size,
                                      layout_columns=layout_columns)
                
                # Convert to PDF
                student_pdf_io = BytesIO()
                pisa.CreatePDF(html, dest=student_pdf_io)
                student_pdf_io.seek(0)
                
                # Add to main writer
                reader = PdfReader(student_pdf_io)
                for page in reader.pages:
                    writer.add_page(page)
                
                # Update progress
                pdf_jobs[job_id]['processed'] = i + 1
                pdf_jobs[job_id]['percent'] = int(((i + 1) / total) * 100)
                
            # Finish
            final_io = BytesIO()
            writer.write(final_io)
            final_io.seek(0)
            
            pdf_jobs[job_id]['status'] = 'completed'
            pdf_jobs[job_id]['result'] = final_io.getvalue()
            pdf_jobs[job_id]['completed_at'] = time.time()
            
        except Exception as e:
            print(f"Error in PDF worker: {e}")
            pdf_jobs[job_id]['status'] = 'failed'
            pdf_jobs[job_id]['error'] = str(e)

@exams_bp.route('/api/pdf-progress/<job_id>')
@login_required
def get_pdf_progress(job_id):
    job = pdf_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({
        'status': job['status'],
        'processed': job['processed'],
        'total': job['total'],
        'percent': job['percent'],
        'error': job.get('error')
    })

@exams_bp.route('/api/pdf-result/<job_id>')
@login_required
def get_pdf_result(job_id):
    job = pdf_jobs.get(job_id)
    if not job or job['status'] != 'completed':
        return abort(404)
        
    # Clean up old jobs (optional, but good for memory)
    # for jid in list(pdf_jobs.keys()):
    #     if pdf_jobs[jid].get('completed_at', 0) < time.time() - 3600:
    #         del pdf_jobs[jid]
            
    return send_file(BytesIO(job['result']), 
                     download_name=job['filename'],
                     as_attachment=True,
                     mimetype='application/pdf')

@exams_bp.route('/<int:id>/download')
@login_required
def download_exam_pdf(id):
    try:
        print(f"DEBUG: download_exam_pdf hit for id={id}")
        if current_user.role == 'student':
            abort(403)
            
        exam = Exam.query.get_or_404(id)
        evaluation = exam.evaluation
        
        school_id = request.args.get('school_id', type=int)
        class_id = request.args.get('class_id', type=int)
        is_async = request.args.get('async', type=int, default=0)
        font_size = request.args.get('font_size', default='12pt')
        layout_columns = request.args.get('layout_columns', default='1')
        
        blank_student = request.args.get('blank_student', type=int, default=0)
        
        print(f"DEBUG: school_id={school_id}, class_id={class_id}, is_async={is_async}, font_size={font_size}, layout_columns={layout_columns}, blank_student={blank_student}, filters=[{exam.target_nationality}, {exam.target_special_needs}]")
        
        def generate_qr(student_id):
            if not student_id:
                return None
            qr = qrcode.QRCode(version=1, box_size=3, border=1)
            qr.add_data(f"exam_id:{exam.id},student_id:{student_id}")
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            return f"data:image/png;base64,{img_str}"

        students_list = []
        
        def filter_enrollment(enrollment):
            # Nationality filter
            if exam.target_nationality == 'Brasileiro':
                if enrollment.student.nationality != 'Brasileiro':
                    return False
            # Special Needs filter
            if exam.target_special_needs == 'Somente Deficientes':
                if not enrollment.student.special_needs:
                    return False
            return True

        if blank_student:
            school_name = ""
            class_name = ""
            shift_name = ""
            if class_id:
                class_query = Class.query.filter_by(id=class_id)
                class_query = filter_by_tenant(class_query, Class)
                target_class = class_query.first()
                if target_class:
                    school_name = target_class.teaching_unit.name
                    class_name = target_class.name
                    shift_name = target_class.shift
            elif school_id:
                school_query = TeachingUnit.query.filter_by(id=school_id)
                school_query = filter_by_tenant(school_query, TeachingUnit)
                school = school_query.first()
                if school:
                    school_name = school.name
            
            students_list = [{
                'student_name': "________________________________________________",
                'school_name': school_name or "________________________________________________",
                'class_name': class_name or "_________________________",
                'shift': shift_name or "_________________________"
            }]
        elif class_id:
            class_query = Class.query.filter_by(id=class_id)
            class_query = filter_by_tenant(class_query, Class)
            target_class = class_query.first()
            if target_class:
                for enrollment in target_class.enrollments.filter_by(active=True).all():
                    if filter_enrollment(enrollment):
                        students_list.append({
                            'student_name': enrollment.student.name,
                            'school_name': target_class.teaching_unit.name,
                            'class_name': target_class.name,
                            'shift': target_class.shift,
                            'qr_code': generate_qr(enrollment.student.id)
                        })
        elif school_id:
            school_query = TeachingUnit.query.filter_by(id=school_id)
            school_query = filter_by_tenant(school_query, TeachingUnit)
            school = school_query.first()
            if school:
                classes_query = Class.query.filter_by(teaching_unit_id=school_id, school_year_id=exam.school_year_id)
                classes_query = filter_by_tenant(classes_query, Class)
                classes = classes_query.all()
                for cls in classes:
                    for enrollment in cls.enrollments.filter_by(active=True).all():
                        if filter_enrollment(enrollment):
                            students_list.append({
                                'student_name': enrollment.student.name,
                                'school_name': school.name,
                                'class_name': cls.name,
                                'shift': cls.shift,
                                'qr_code': generate_qr(enrollment.student.id)
                            })

        if not students_list:
            students_list = [{
                'student_name': "________________________________________________",
                'school_name': "________________________________________________",
                'class_name': "_________________________",
                'shift': "_________________________"
            }]

        # Filename
        filename = f"prova_{exam.id}"
        if class_id:
            filename += f"_turma_{class_id}"
        elif school_id:
            filename += f"_escola_{school_id}"
        filename += ".pdf"

        logo_url = ""
        if evaluation and evaluation.logo_path:
            logo_url = os.path.join(current_app.root_path, 'static', evaluation.logo_path)

        if is_async:
            print(f"DEBUG: Entering async block for job_id generation")
            job_id = str(uuid.uuid4())
            pdf_jobs[job_id] = {
                'status': 'processing',
                'processed': 0,
                'total': len(students_list),
                'percent': 0,
                'filename': filename,
                'created_at': time.time()
            }
            
            # Start background thread
            app_obj = current_app._get_current_object()
            eval_id = evaluation.id if evaluation else None
            
            thread = threading.Thread(target=generate_pdf_worker, 
                                      args=(app_obj, job_id, id, students_list, eval_id, logo_url, font_size, layout_columns))
            thread.daemon = True # Ensure thread doesn't block app exit
            thread.start()
            return jsonify({'job_id': job_id})

        # Synchronous fallback (or default download)
        html = render_template('exams/print_student.html', 
                            exam=exam, 
                            evaluation=evaluation,
                            logo_url=logo_url,
                            students_list=students_list,
                            now=datetime.now(),
                            font_size=font_size,
                            layout_columns=layout_columns)
        
        dest = BytesIO()
        pisa.CreatePDF(html, dest=dest)
        dest.seek(0)
        
        return send_file(dest, 
                        download_name=filename,
                        as_attachment=True,
                        mimetype='application/pdf')
    except Exception as e:
        import traceback
        print(f"DEBUG: GLOBAL ERROR in download_exam_pdf: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

