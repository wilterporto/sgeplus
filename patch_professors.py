import re

with open('app/routes/professors.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Try a different regex
match = re.search(r'(@professors_bp\.route\(\'/\', methods=\[\'GET\', \'POST\'\]\)\n@login_required\ndef list_professors\(\):.*?)@professors_bp\.route\(\'/<int:id>/edit\'', content, re.DOTALL)
if not match:
    print('Not found again. Fallback.')
    match = re.search(r'(@professors_bp\.route\(\'/\'.*?)def edit_professor\(id\):', content, re.DOTALL)
    if not match:
        print('Still not found!')
        exit(1)

old_list_professors = match.group(1)

new_route = '''@professors_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_professor():
    import flask
    from flask import session
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')

    form = ProfessorForm()
    
    from app.models import DietaryRestriction, City, Country, Subject, User, Class, TeachingUnit, TeachingAssignment
    
    form.dietary_restrictions.choices = [(d.id, d.name) for d in filter_by_tenant(DietaryRestriction.query, DietaryRestriction).filter_by(active=True).order_by(DietaryRestriction.name).all()]
    
    form.birth_country.choices = [(c.name, c.name) for c in Country.query.order_by(Country.name).all()]
    if request.method == 'POST' and request.form.get('birth_state'):
        form.birth_city_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in City.query.filter_by(uf=request.form.get('birth_state')).order_by(City.name).all()]
    else:
        form.birth_city_id.choices = [(0, 'Selecione...')]

    if form.validate_on_submit():
        reg_num = Professor.generate_registration_number()
        clean_cpf = re.sub(r'[^0-9]', '', form.cpf.data)
        
        cpf_query = filter_by_tenant(Professor.query.filter_by(cpf=clean_cpf), Professor)
        if cpf_query.first():
            flash('CPF já cadastrado!', 'danger')
            return redirect(url_for('professors.new_professor'))

        professor = Professor(
            name=form.name.data,
            registration_number=reg_num,
            birth_date=form.birth_date.data,
            cpf=clean_cpf,
            sex=form.sex.data,
            race=form.race.data,
            nationality=form.nationality.data,
            birth_country=form.birth_country.data,
            special_needs=form.special_needs.data,
            email=form.email.data,
            inep_code=form.inep_code.data,
            birth_state=form.birth_state.data if form.nationality.data == 'Brasileiro' else None,
            birth_city_id=form.birth_city_id.data if form.birth_city_id.data and form.birth_city_id.data != 0 and form.nationality.data == 'Brasileiro' else None,
            residential_zone=form.residential_zone.data,
            differentiated_location=form.differentiated_location.data,
            tenant_id=current_user.tenant_id
        )
        db.session.add(professor)
        db.session.flush() 
        
        if form.assignments_data.data:
            import json
            try:
                assignments = json.loads(form.assignments_data.data)
                for item in assignments:
                    ta = TeachingAssignment(
                        professor_id=professor.id,
                        class_id=int(item['class_id']),
                        subject_id=int(item['subject_id'])
                    )
                    db.session.add(ta)
            except Exception as e:
                print(f"Error parsing assignments: {e}")

        if form.generate_user.data:
            existing_user = User.query.filter_by(username=clean_cpf).first()
            dob_str = form.birth_date.data.strftime('%d%m%Y')
            user_email = form.email.data if form.email.data else None

            if existing_user:
                existing_user.name = form.name.data
                existing_user.email = user_email
                existing_user.set_password(dob_str)
                existing_user.add_role('professor')
                if existing_user.role != 'professor':
                     existing_user.role = 'professor'
                professor.user = existing_user
            else:
                user = User(
                    username=clean_cpf, 
                    role='professor',
                    roles='professor',
                    name=form.name.data,
                    email=user_email,
                    active=True,
                    tenant_id=current_user.tenant_id
                )
                user.add_role('professor')
                user.set_password(dob_str)
                db.session.add(user)
                professor.user = user
        
        db.session.commit()
        
        from app.audit_utils import log_audit
        log_audit('CREATE', 'Professor', professor.id, f"Created professor {professor.name}")
        
        flash('Professor cadastrado com sucesso!', 'success')
        return redirect(url_for('professors.list_professors'))

    # Load subjects/units for assignment component
    from app.models import Class, TeachingUnit
    if active_role == 'unidade':
        tu_query = TeachingUnit.query.filter_by(id=active_school_id)
        c_query = Class.query.filter_by(teaching_unit_id=active_school_id)
    else:
        tu_query = filter_by_tenant(TeachingUnit.query.filter_by(type='Escola'), TeachingUnit)
        c_query = filter_by_tenant(Class.query, Class)
        
    tu_query = tu_query.order_by(TeachingUnit.name).all()
    c_query = c_query.order_by(Class.name).all()
    subjects = filter_by_tenant(Subject.query, Subject).order_by(Subject.name).all()
    
    units_data = [{'id': u.id, 'name': u.name} for u in tu_query]
    classes_data = [{'id': c.id, 'name': c.name, 'unit_id': c.teaching_unit_id} for c in c_query]
    subjects_data = [{'id': s.id, 'name': s.name} for s in subjects]

    return render_template('professors/form.html', form=form, title='Novo Professor',
                           units=units_data, classes=classes_data, subjects=subjects_data)
'''

clean_list_professors = '''@professors_bp.route('/', methods=['GET'])
@login_required
def list_professors():
    from flask import session
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')

    page = request.args.get('page', 1, type=int)
    search = request.args.get('search')
    subject_id = request.args.get('subject_id', type=int)
    school_year_id = request.args.get('school_year_id', type=int)
    unit_id = request.args.get('unit_id', type=int)

    if active_role == 'unidade':
        query = Professor.query.join(Professor.assignments).join(Class).filter(
            Class.teaching_unit_id == active_school_id
        )
        if subject_id:
            query = query.filter(TeachingAssignment.subject_id == subject_id)
        if school_year_id:
            query = query.filter(Class.school_year_id == school_year_id)
        unit_id = active_school_id
    else:
        query = Professor.query
        if subject_id or school_year_id or unit_id:
            query = query.join(Professor.assignments).join(Class)
            if subject_id:
                query = query.filter(TeachingAssignment.subject_id == subject_id)
            if school_year_id:
                query = query.filter(Class.school_year_id == school_year_id)
            if unit_id:
                query = query.filter(Class.teaching_unit_id == unit_id)
                
    query = filter_by_tenant(query, Professor)
    
    if search:
        query = query.filter(Professor.name.ilike(f'%{search}%'))
    
    professors = query.distinct().order_by(Professor.name).paginate(page=page, per_page=30)
    
    from app.models import SchoolYear, Subject
    years = SchoolYear.query.order_by(SchoolYear.name).all()
    subjects = filter_by_tenant(Subject.query, Subject).order_by(Subject.name).all()
    
    active_job = ImportJob.query.filter_by(
        tenant_id=get_tenant_id(),
        import_type='Professors',
        status='running'
    ).first()
    
    return render_template('professors/list.html', 
                          professors=professors, 
                          search=search, 
                          subject_id=subject_id,
                          school_year_id=school_year_id,
                          unit_id=unit_id,
                          subjects=subjects, 
                          years=years,
                          active_job=active_job)

'''

content = content.replace(old_list_professors, clean_list_professors + '\n' + new_route + '\n\n')
with open('app/routes/professors.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done professors.py!')
