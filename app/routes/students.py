from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.utils.tenancy import filter_by_tenant, get_tenant_id
from app import db
from app.models import Student, Class, Enrollment, TeachingUnit, ImportJob
from app.forms import StudentForm, EnrollmentForm
from datetime import datetime
import re
import random

students_bp = Blueprint('students', __name__)

@students_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_student(id):
    if not current_user.is_admin:
        abort(403)
    student = Student.query.get_or_404(id)
    if not current_user.is_system_admin and student.tenant_id != current_user.tenant_id:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('students.list_students'))
    s_name = student.name
    s_id = student.id
    
    # Delete student (associated enrollments will be handled by cascade or manual cleanup if needed)
    # Enrollments don't have cascade delete on student side by default in my model inspection, 
    # but let's check. 
    # Student: enrollments = db.relationship('Enrollment', backref='student', lazy='dynamic')
    # No cascade specified. We should manually delete enrollments.
    
    student.enrollments.delete()
    db.session.delete(student)
    db.session.commit()
    
    from app.audit_utils import log_audit
    log_audit('DELETE', 'Student', s_id, f"Deleted Student {s_name}")
    
    flash('Excluído com sucesso', 'success_delete')
    # Return to previous page if possible, or list
    return redirect(request.referrer or url_for('students.list_students'))

@students_bp.route('/', methods=['GET'])
@login_required
def list_students():
    from flask import session
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')

    page = request.args.get('page', 1, type=int)
    
    if active_role == 'unidade':
        students_query = Student.query.join(Enrollment).join(Class).filter(Class.teaching_unit_id == active_school_id).order_by(Student.name)
    else:
        students_query = Student.query.order_by(Student.name)
        
    students_query = filter_by_tenant(students_query, Student)
    
    search = request.args.get('search')
    if search:
        from sqlalchemy import or_
        date_filter = None
        if '/' in search:
            try:
                date_filter = datetime.strptime(search, '%d/%m/%Y').date()
            except: pass

        clean_search = re.sub(r'[^0-9]', '', search)
        search_filter = or_(
            Student.name.ilike(f'%{search}%'),
            Student.registration_number.ilike(f'%{search}%'),
            Student.cpf.ilike(f'%{clean_search}%')
        )
        if date_filter:
            search_filter = or_(search_filter, Student.birth_date == date_filter)
            
        students_query = students_query.filter(search_filter)
        
    students = students_query.paginate(page=page, per_page=30)
    
    active_job = ImportJob.query.filter_by(
        tenant_id=get_tenant_id(),
        import_type='Students',
        status='running'
    ).first()
    
    return render_template('students/list.html', students=students, active_job=active_job)


@students_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_student():
    from flask import session
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')
    active_school_name = session.get('active_school_name')

    form = StudentForm()
    
    from app.models import DietaryRestriction, City, Country, User, QuilombolaCommunity, IndigenousPeople
    
    if active_role == 'unidade':
        form.teaching_unit_id.choices = [(active_school_id, active_school_name)]
        c_query = Class.query.filter_by(teaching_unit_id=active_school_id)
        c_query = filter_by_tenant(c_query, Class)
        form.class_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in c_query.all()]
    else:
        tu_query = TeachingUnit.query.filter_by(type='Escola')
        tu_query = filter_by_tenant(tu_query, TeachingUnit)
        form.teaching_unit_id.choices = [(0, 'Selecione...')] + [(u.id, u.name) for u in tu_query.all()]
        
        c_query = Class.query
        c_query = filter_by_tenant(c_query, Class)
        form.class_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in c_query.all()]
        
    form.dietary_restrictions.choices = [(d.id, d.name) for d in filter_by_tenant(DietaryRestriction.query, DietaryRestriction).filter_by(active=True).order_by(DietaryRestriction.name).all()]
    
    form.birth_country.choices = [(c.name, c.name) for c in Country.query.order_by(Country.name).all()]
    if request.method == 'POST' and request.form.get('birth_state'):
        form.birth_city_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in City.query.filter_by(uf=request.form.get('birth_state')).order_by(City.name).all()]
    else:
        form.birth_city_id.choices = [(0, 'Selecione...')]
        
    form.quilombola_community_id.choices = [(0, 'Selecione...')] + [(q.id, q.name) for q in filter_by_tenant(QuilombolaCommunity.query, QuilombolaCommunity).order_by(QuilombolaCommunity.name).all()]
    form.indigenous_people_id.choices = [(0, 'Selecione...')] + [(ip.id, ip.name) for ip in filter_by_tenant(IndigenousPeople.query, IndigenousPeople).order_by(IndigenousPeople.name).all()]

    if form.validate_on_submit():
        if form.teaching_unit_id.data == 0 or form.class_id.data == 0:
            flash('Selecione a Escola e a Turma.', 'danger')
            return redirect(url_for('students.new_student'))

        reg_num = Student.generate_registration_number()
        clean_cpf = re.sub(r'[^0-9]', '', form.cpf.data)
        
        cpf_query = Student.query.filter_by(cpf=clean_cpf)
        cpf_query = filter_by_tenant(cpf_query, Student)
        if cpf_query.first():
            flash('CPF já cadastrado!', 'danger')
            return redirect(url_for('students.new_student'))

        student = Student(
            name=form.name.data,
            registration_number=reg_num,
            birth_date=form.birth_date.data,
            cpf=clean_cpf,
            sex=form.sex.data,
            race=form.race.data,
            nationality=form.nationality.data,
            birth_country=form.birth_country.data,
            special_needs=form.special_needs.data,
            family_income=form.family_income.data,
            email=form.email.data,
            inep_code=form.inep_code.data,
            sus_card=form.sus_card.data,
            bolsa_familia=form.bolsa_familia.data,
            birth_state=form.birth_state.data if form.nationality.data == 'Brasileiro' else None,
            birth_city_id=form.birth_city_id.data if form.birth_city_id.data and form.birth_city_id.data != 0 and form.nationality.data == 'Brasileiro' else None,
            residential_zone=form.residential_zone.data,
            differentiated_location=form.differentiated_location.data,
            is_quilombola=form.is_quilombola.data,
            quilombola_community_id=form.quilombola_community_id.data if form.is_quilombola.data and form.quilombola_community_id.data != 0 else None,
            indigenous_people_id=form.indigenous_people_id.data if form.race.data == 'Indigena' and form.indigenous_people_id.data != 0 else None,
            tenant_id=current_user.tenant_id
        )
        selected_restrictions = filter_by_tenant(DietaryRestriction.query, DietaryRestriction).filter(DietaryRestriction.id.in_(form.dietary_restrictions.data)).all()
        student.dietary_restrictions = selected_restrictions
        if form.generate_user.data:
            existing_user = User.query.filter_by(username=clean_cpf).first()
            dob_str = form.birth_date.data.strftime('%d%m%Y')
            user_email = form.email.data if form.email.data else None

            if existing_user:
                 existing_user.name = form.name.data
                 existing_user.email = user_email
                 existing_user.set_password(dob_str)
                 existing_user.add_role('student')
                 if existing_user.role == 'professor' and 'student' in existing_user.get_roles():
                      existing_user.role = 'student'
                 student.user = existing_user
            else:
                user = User(
                    username=clean_cpf, 
                    role='student',
                    roles='student',
                    name=form.name.data,
                    email=user_email,
                    active=True,
                    tenant_id=current_user.tenant_id
                )
                user.add_role('student')
                user.set_password(dob_str)
                db.session.add(user)
                student.user = user

        db.session.add(student)
        db.session.commit()
        
        enrollment = Enrollment(student_id=student.id, class_id=form.class_id.data)
        db.session.add(enrollment)
        db.session.commit()

        from app.audit_utils import log_audit
        log_audit('CREATE', 'Student', student.id, f"Created student {student.name}, enrolled in class {form.class_id.data}")
        
        flash(f"Aluno cadastrado com sucesso.", "success")
        return redirect(url_for("students.list_students"))

    return render_template("students/form.html", form=form, title="Novo Aluno")

@students_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_student(id):
    from flask import session
    student = Student.query.get_or_404(id)
    
    # Validar isolamento por tenant
    if not current_user.is_system_admin and student.tenant_id != current_user.tenant_id:
        flash('Acesso não autorizado.', 'danger')
        return redirect(url_for('students.list_students'))
        
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')
    active_school_name = session.get('active_school_name')
    
    if active_role == 'unidade':
        has_access = student.enrollments.join(Class).filter(Class.teaching_unit_id == active_school_id).first() is not None
        if not has_access:
            abort(403)
            
    form = StudentForm(obj=student)
    
    if request.method == 'GET':
        active = student.enrollments.filter_by(active=True).first()
        if active:
            form.class_id.choices = [(active.class_id, active.enrolled_class.name)] # Hack to pass validation
            form.class_id.data = active.class_id
            form.teaching_unit_id.choices = [(active.enrolled_class.teaching_unit_id, active.enrolled_class.teaching_unit.name)]
            form.teaching_unit_id.data = active.enrolled_class.teaching_unit_id
        else:
             # Populate generic choices
             pass
        # Pre-select dietary restrictions
        form.dietary_restrictions.data = [d.id for d in student.dietary_restrictions]

    from app.models import DietaryRestriction, City
    from sqlalchemy import or_
    
    if active_role == 'unidade':
        form.teaching_unit_id.choices = [(active_school_id, active_school_name)]
        c_query = Class.query.filter_by(teaching_unit_id=active_school_id)
        c_query = filter_by_tenant(c_query, Class)
        form.class_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in c_query.all()]
    else:
        tu_query = TeachingUnit.query.filter_by(type='Escola')
        tu_query = filter_by_tenant(tu_query, TeachingUnit)
        form.teaching_unit_id.choices = [(0, 'Selecione...')] + [(u.id, u.name) for u in tu_query.all()]
        
        c_query = Class.query
        c_query = filter_by_tenant(c_query, Class)
        form.class_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in c_query.all()]
    
    from app.models import City, Country, QuilombolaCommunity, IndigenousPeople
    form.birth_country.choices = [(c.name, c.name) for c in Country.query.order_by(Country.name).all()]
    if request.method == 'POST' and request.form.get('birth_state'):
        form.birth_city_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in City.query.filter_by(uf=request.form.get('birth_state')).order_by(City.name).all()]
    elif student.birth_state:
        form.birth_city_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in City.query.filter_by(uf=student.birth_state).order_by(City.name).all()]
    else:
        form.birth_city_id.choices = [(0, 'Selecione...')]

    form.quilombola_community_id.choices = [(0, 'Selecione...')] + [(q.id, q.name) for q in filter_by_tenant(QuilombolaCommunity.query, QuilombolaCommunity).order_by(QuilombolaCommunity.name).all()]
    form.indigenous_people_id.choices = [(0, 'Selecione...')] + [(ip.id, ip.name) for ip in filter_by_tenant(IndigenousPeople.query, IndigenousPeople).order_by(IndigenousPeople.name).all()]

    
    existing_rep_ids = [d.id for d in student.dietary_restrictions]
    rep_query = filter_by_tenant(DietaryRestriction.query, DietaryRestriction)
    if existing_rep_ids:
        rep_query = rep_query.filter(or_(DietaryRestriction.active == True, DietaryRestriction.id.in_(existing_rep_ids)))
    else:
        rep_query = rep_query.filter_by(active=True)
    form.dietary_restrictions.choices = [(d.id, d.name) for d in rep_query.order_by(DietaryRestriction.name).all()]

    if form.validate_on_submit():
        if form.teaching_unit_id.data == 0 or form.class_id.data == 0:
            flash('Selecione a Escola e a Turma.', 'danger')
            # Fallthrough to render template

        from app.models import User
        
        clean_cpf = re.sub(r'[^0-9]', '', form.cpf.data)

        # Check unique only if changed
        existing = Student.query.filter_by(cpf=clean_cpf).first()
        if existing and existing.id != student.id:
             flash('CPF já cadastrado!', 'danger')
        else:
            student.name = form.name.data
            # student.registration_number = form.registration_number.data # Usually immutable or distinct logic
            student.birth_date = form.birth_date.data
            student.cpf = clean_cpf
            student.sex = form.sex.data
            student.race = form.race.data
            student.nationality = form.nationality.data
            student.birth_country = form.birth_country.data
            student.special_needs = form.special_needs.data
            student.family_income = form.family_income.data
            student.email = form.email.data
            
            student.inep_code = form.inep_code.data
            student.sus_card = form.sus_card.data
            student.bolsa_familia = form.bolsa_familia.data
            student.residential_zone = form.residential_zone.data
            student.differentiated_location = form.differentiated_location.data
            student.is_quilombola = form.is_quilombola.data
            student.quilombola_community_id = form.quilombola_community_id.data if form.is_quilombola.data and form.quilombola_community_id.data != 0 else None
            student.indigenous_people_id = form.indigenous_people_id.data if form.race.data == 'Indigena' and form.indigenous_people_id.data != 0 else None
            
            if form.nationality.data == 'Brasileiro':
                student.birth_state = form.birth_state.data
                student.birth_city_id = form.birth_city_id.data if form.birth_city_id.data and form.birth_city_id.data != 0 else None
            else:
                student.birth_state = None
                student.birth_city_id = None
            
            if form.dietary_restrictions.data:
                student.dietary_restrictions = filter_by_tenant(DietaryRestriction.query, DietaryRestriction).filter(DietaryRestriction.id.in_(form.dietary_restrictions.data)).all()
            else:
                student.dietary_restrictions = []
            
            # Sync user if exists
            user_email = form.email.data if form.email.data else None
            
            if student.user:
                student.user.email = user_email
                student.user.name = form.name.data
                student.user.role = 'student'
                student.user.roles = 'student'
            
            if form.generate_user.data and not student.user_id:
                 existing_user = User.query.filter_by(username=clean_cpf).first()
                 dob_str = form.birth_date.data.strftime('%d%m%Y')
                 # user_email defined above
                 
                 if existing_user:
                     existing_user.name = form.name.data
                     existing_user.email = user_email
                     existing_user.set_password(dob_str)
                     existing_user.add_role('student')
                     # Update primary role only if it was default
                     if existing_user.role == 'professor':
                          existing_user.role = 'student'
                     
                     student.user = existing_user
                     flash(f'Usuário existente ({clean_cpf}) atualizado e vinculado.', 'info')
                 else:
                    user = User(
                        username=clean_cpf, 
                        role='student',
                        roles='student', # Force overwrite of default 'professor'
                        name=form.name.data,
                        email=user_email,
                        active=True,
                        tenant_id=current_user.tenant_id
                    )
                    user.add_role('student')
                    user.set_password(dob_str)
                    db.session.add(user)
                    student.user = user

            db.session.commit()
            
            from app.audit_utils import log_audit
            log_audit('UPDATE', 'Student', student.id, f"Updated student {student.name}")

            flash('Aluno atualizado.', 'success')
            return redirect(url_for('students.list_students'))
            
    return render_template('students/form.html', form=form, title="Editar Aluno")

# Enrollment Logic
@students_bp.route('/<int:id>/enroll', methods=['GET', 'POST'])
@login_required
def enroll_student(id):
    student = Student.query.get_or_404(id)
    if not current_user.is_system_admin and student.tenant_id != current_user.tenant_id:
        abort(403)
        
    form = EnrollmentForm()
    
    # Populate classes filtradas por tenant
    c_query = Class.query
    c_query = filter_by_tenant(c_query, Class)
    form.class_id.choices = [(0, 'Selecione...')] + [(c.id, f"{c.name} - {c.school_year.name}") for c in c_query.all()]
    
    if form.validate_on_submit():
        if form.class_id.data == 0:
            flash('Selecione a Turma.', 'danger')
            return redirect(url_for('students.enroll_student', id=id))

        # Check if already enrolled in this class
        existing = Enrollment.query.filter_by(student_id=student.id, class_id=form.class_id.data, active=True).first()
        if existing:
             flash('Aluno já matriculado nesta turma.', 'warning')
        else:
            enrollment = Enrollment(student_id=student.id, class_id=form.class_id.data)
            db.session.add(enrollment)
            db.session.commit()
            
            from app.audit_utils import log_audit
            log_audit('CREATE', 'Enrollment', enrollment.id, f"Enrolled student {student.name} in class ID {form.class_id.data}")

            flash('Matrícula realizada com sucesso.', 'success')
            return redirect(url_for('students.list_students'))
            
    # Get current enrollments
    active_enrollments = student.enrollments.filter_by(active=True).all()
    
    return render_template('students/enroll.html', form=form, student=student, enrollments=active_enrollments)

@students_bp.route('/download-layout')
@login_required
def download_student_layout():
    import pandas as pd
    from io import BytesIO
    from flask import send_file
    
    data = {
        'INEP da Escola': ['12345678', ''],
        'Unidade de Ensino': ['Escola Exemplo 1', 'Escola Exemplo 1'],
        'Nome da Turma': ['101', '102'],
        'Nome Completo': ['João Silva', 'Maria Souza'],
        'Data de Nascimento': ['01/05/2010', '15/08/2010'],
        'Sexo': ['M', 'F'],
        'Cor/Raça': ['Branca', 'Parda'],
        'CPF': ['111.222.333-44', '555.666.777-88'],
        'Código INEP': ['123456789012', '987654321098'],
        'Cartão SUS': ['123456789012345', ''],
        'Nacionalidade': ['Brasileiro', 'Brasileiro'],
        'País nascimento': ['Brasil', 'Brasil'],
        'UF Naturalidade': ['SP', 'MG'],
        'Município Naturalidade': ['São Paulo', 'Belo Horizonte'],
        'Zona Residencial': ['Urbana', 'Rural'],
        'Localização Diferenciada de Residência': ['Não está em área de localização diferenciada', 'Não está em área de localização diferenciada'],
        'Deficiência': ['Não', 'Não'],
        'E-mail': ['joao@email.com', 'maria@email.com'],
        'Renda Familiar': ['1 a 2 SM', ''],
        'Bolsa Família': ['Não', 'Sim'],
        'Restrições Alimentares': ['Lactose, Amendoim', ''],
        'É Quilombola?': ['Não', 'Sim'],
        'Comunidade Quilombola': ['', 'Comunidade X'],
        'Povo Indígena': ['', '']
    }
    
    df = pd.DataFrame(data)
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Layout Alunos')
        worksheet = writer.sheets['Layout Alunos']
        for idx, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.column_dimensions[chr(65 + idx)].width = max_len
            
    output.seek(0)
    
    return send_file(
        output,
        download_name='layout_importacao_alunos.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@students_bp.route('/import', methods=['POST'])
@login_required
def import_students():
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('students.list_students'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('students.list_students'))
        
    if file:
        from app.services.import_service import ImportService
        from app.models import User
        from app.import_utils import start_import_task, update_import_progress, finish_import_task, fail_import_task
        import random
        
        task_id = request.form.get('X-Progress-ID')
        
        result = ImportService.process_file(file, type='student')
        
        if not result['success']:
            flash(result['error'], 'danger')
        else:
            # Performance optimizations: Normalize CPFs for comparison
            import re
            def clean_val(v): return re.sub(r'[^0-9]', '', v) if v else ""
            
            from app.models import DietaryRestriction, QuilombolaCommunity, IndigenousPeople
            all_dr = filter_by_tenant(DietaryRestriction.query, DietaryRestriction).all()
            dr_map = {d.name.lower(): d for d in all_dr}
            
            existing_students_by_cpf_clean = {clean_val(s.cpf): s for s in filter_by_tenant(Student.query, Student).all()}
            existing_usernames = {u.username for u in filter_by_tenant(User.query.with_entities(User.username), User).all()}
            
            quilombola_cache = {q.name.lower(): q for q in filter_by_tenant(QuilombolaCommunity.query, QuilombolaCommunity).all()}
            indigenous_cache = {ip.name.lower(): ip for ip in filter_by_tenant(IndigenousPeople.query, IndigenousPeople).all()}
            
            # Pre-calculate registration number sequence
            from datetime import datetime
            prefix = datetime.now().strftime('%Y%m%d')
            # Query for all registration numbers today to find the absolute max numerically
            all_today = Student.query.with_entities(Student.registration_number).filter(Student.registration_number.like(f"{prefix}%")).all()
            
            max_seq = 0
            for row in all_today:
                reg = row[0]
                try:
                    # Try to extract the last 6 digits and see if it's the max
                    num_part = reg[-6:]
                    num = int(num_part)
                    if num > max_seq:
                        max_seq = num
                except (ValueError, TypeError):
                    continue
            
            reg_seq = max_seq + 1
            count = 0
            created = 0
            updated = 0
            
            errors = result['errors']
            total = len(result['data'])
            if task_id:
                start_import_task(total, task_id=task_id)
            
            from app.models import DietaryRestriction
            dr_cache = {d.name.strip().lower(): d for d in filter_by_tenant(DietaryRestriction.query, DietaryRestriction).all()}
            
            updated = 0
            for i, item in enumerate(result['data']):
                try:
                    # Match DRs
                    dr_objs = []
                    item_drs = item.get('dietary_restrictions', [])
                    for dr_name in item_drs:
                        dr_obj = dr_cache.get(dr_name.lower())
                        if dr_obj:
                            dr_objs.append(dr_obj)
                        else:
                            errors.append(f"Atenção: Restrição '{dr_name}' não encontrada (ignorada para aluno {item['name']}).")
                            
                    # Quilombola Community
                    qc_id = None
                    if item.get('is_quilombola') and item.get('quilombola_community_name'):
                        qc_name = item['quilombola_community_name']
                        qc_name_lower = qc_name.lower()
                        if qc_name_lower in quilombola_cache:
                            qc_id = quilombola_cache[qc_name_lower].id
                        else:
                            new_qc = QuilombolaCommunity(name=qc_name, tenant_id=get_tenant_id())
                            db.session.add(new_qc)
                            db.session.flush()
                            quilombola_cache[qc_name_lower] = new_qc
                            qc_id = new_qc.id

                    # Indigenous People
                    ip_id = None
                    if item.get('race') == 'Indigena' and item.get('indigenous_people_name'):
                        ip_name = item['indigenous_people_name']
                        ip_name_lower = ip_name.lower()
                        if ip_name_lower in indigenous_cache:
                            ip_id = indigenous_cache[ip_name_lower].id
                        else:
                            new_ip = IndigenousPeople(name=ip_name, tenant_id=get_tenant_id())
                            db.session.add(new_ip)
                            db.session.flush()
                            indigenous_cache[ip_name_lower] = new_ip
                            ip_id = new_ip.id
                
                    # Check exist (In-memory, normalized)
                    curr_cpf_clean = item.get('cpf_clean') or clean_val(item['cpf'])
                    email_val = item.get('email')
                    
                    # 1. Update or Create Student
                    # Student table uses formatted CPF (000.000.000-00), so we use the raw item['cpf'] or format it
                    formatted_cpf = item['cpf'] 
                    
                    student = existing_students_by_cpf_clean.get(curr_cpf_clean)
                    
                    if student:
                        # Update existing student
                        changed = False
                        if email_val and student.email != email_val:
                            student.email = email_val
                            if student.user:
                                student.user.email = email_val
                            changed = True
                            
                        updateable_fields = [
                            'name', 'birth_date', 'sex', 'race', 
                            'inep_code', 'sus_card', 'nationality', 'birth_country',
                            'birth_state', 'birth_city_id', 'residential_zone', 
                            'differentiated_location', 'special_needs', 'bolsa_familia', 'family_income',
                            'is_quilombola'
                        ]
                        for field in updateable_fields:
                            if field in item and item[field] is not None and getattr(student, field) != item[field]:
                                setattr(student, field, item[field])
                                changed = True
                        
                        current_dr_ids = {d.id for d in student.dietary_restrictions}
                        new_dr_ids = {d.id for d in dr_objs}
                        if current_dr_ids != new_dr_ids:
                            student.dietary_restrictions = dr_objs
                            changed = True
                            
                        if student.quilombola_community_id != qc_id:
                            student.quilombola_community_id = qc_id
                            changed = True
                            
                        if student.indigenous_people_id != ip_id:
                            student.indigenous_people_id = ip_id
                            changed = True
                        
                        if changed:
                            db.session.add(student)
                            updated += 1
                            log_msg = f"Atualizei dados do aluno {student.name} (CPF: {curr_cpf_clean})."
                            if task_id: update_import_progress(task_id, i+1, message=log_msg)
                        else:
                            log_msg = f"Aluno {student.name} (CPF: {curr_cpf_clean}) já existe e dados estão atualizados. Pulei."
                            if task_id: update_import_progress(task_id, i+1, message=log_msg)
                        
                        # Check for enrollment in the current class
                        existing_enrollment = Enrollment.query.filter_by(student_id=student.id, class_id=item['class_id'], active=True).first()
                        if not existing_enrollment:
                            enrollment = Enrollment(student_id=student.id, class_id=item['class_id'])
                            db.session.add(enrollment)
                            log_msg += f" E matriculei na turma {item['class_id']}."
                            if task_id: update_import_progress(task_id, i+1, message=log_msg)
                        
                    else:
                        # Create Student
                        reg_num = f"{prefix}{reg_seq:06d}"
                        reg_seq += 1

                        student = Student(
                            name=item['name'],
                            registration_number=reg_num,
                            cpf=curr_cpf_clean,
                            birth_date=item['birth_date'],
                            sex=item['sex'],
                            race=item['race'],
                            email=email_val,
                            nationality=item.get('nationality'),
                            birth_country=item.get('birth_country'),
                            special_needs=item.get('special_needs', False),
                            inep_code=item.get('inep_code'),
                            sus_card=item.get('sus_card'),
                            birth_state=item.get('birth_state'),
                            birth_city_id=item.get('birth_city_id'),
                            residential_zone=item.get('residential_zone'),
                            differentiated_location=item.get('differentiated_location'),
                            bolsa_familia=item.get('bolsa_familia', False),
                            family_income=item.get('family_income'),
                            is_quilombola=item.get('is_quilombola', False),
                            quilombola_community_id=qc_id,
                            indigenous_people_id=ip_id,
                            tenant_id=get_tenant_id()
                        )
                        student.dietary_restrictions = dr_objs
                        
                        # User Logic
                        username = curr_cpf_clean
                        if username not in existing_usernames:
                            dob_str = item['birth_date'].strftime('%d%m%Y')
                            user = User(
                                username=username,
                                name=item['name'],
                                role='student',
                                roles='student',
                                email=email_val,
                                active=True,
                                tenant_id=get_tenant_id()
                            )
                            user.add_role('student')
                            user.set_password(dob_str)
                            db.session.add(user)
                            student.user = user
                            existing_usernames.add(username)
                        
                        db.session.add(student)
                        db.session.flush() # get ID for enrollment
                        
                        enrollment = Enrollment(student_id=student.id, class_id=item['class_id'])
                        db.session.add(enrollment)
                        
                        created += 1
                        existing_students_by_cpf_clean[curr_cpf_clean] = student
                    
                    count += 1

                    # Batch commit every 100 or final
                    if count % 100 == 0 or i == total - 1:
                        db.session.commit()
                        if task_id: update_import_progress(task_id, i+1, message=f"Lote processado ({count})")
                    else:
                        if task_id and (i % 10 == 0): # Progress every 10 for smaller steps
                            update_import_progress(task_id, i+1, message=f"Processando: {item['name']}")

                except Exception as e:
                    db.session.rollback()
                    from sqlalchemy.exc import IntegrityError
                    if isinstance(e, IntegrityError):
                        err_msg = f"Erro de duplicidade para {item.get('name')}. Verifique CPF."
                    else:
                        err_msg = f"Erro ao processar {item.get('name')}: {str(e)}"
                    errors.append(err_msg)
                    if task_id: update_import_progress(task_id, i+1, message=f"Erro em {item['name']}", error=err_msg)
            
            log_filename = None
            if errors:
                from app.import_utils import save_error_log
                log_filename = save_error_log(errors)
            
            finish_import_task(task_id, message=f"Importação concluída: {created} criados, {updated} atualizados.", log_file=log_filename)
            
            if count > 0:
                flash(f'Importação concluída: {created} novos alunos e {updated} atualizações.', 'success')
            
            if errors:
                for err in errors[:5]: # Show first 5 errors to avoid spam
                    flash(err, 'warning')
                if len(errors) > 5:
                    flash(f'e mais {len(errors)-5} erros.', 'warning')
                    
    return redirect(url_for('students.list_students'))
