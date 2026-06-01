import re

with open('app/routes/students.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract list_students method
match = re.search(r'(@students_bp\.route\(\'/\', methods=\[\'GET\', \'POST\'\]\)\n@login_required\ndef list_students\(\):.*?)def edit_student\(id\):', content, re.DOTALL)
if not match:
    print('Not found')
    exit(1)

old_list_students = match.group(1)

# we will create new_student
new_route = '''@students_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_student():
    from flask import session
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')
    active_school_name = session.get('active_school_name')

    form = StudentForm()
    
    from app.models import DietaryRestriction, City, Country, User
    
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
'''

# New clean list_students
clean_list_students = '''@students_bp.route('/', methods=['GET'])
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

'''

content = content.replace(old_list_students, clean_list_students + '\n' + new_route + '\n\n')
with open('app/routes/students.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')
