from flask import Blueprint, render_template, redirect, url_for, flash, request
import flask
import flask_login
from flask_login import current_user, login_required
from app.utils.tenancy import filter_by_tenant, get_tenant_id
from app import db
from app.models import Professor, Subject, TeachingUnit, Class, User, TeachingAssignment, Student, ImportJob
from app.forms import ProfessorForm
import re
import json

professors_bp = Blueprint('professors', __name__, url_prefix='/professors')

@professors_bp.route('/', methods=['GET'])
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
        from sqlalchemy import func
        import re
        search_clean = re.sub(r'[^0-9]', '', search)
        if search_clean:
            query = query.filter(db.or_(
                Professor.name.ilike(f'%{search}%'),
                Professor.cpf.ilike(f'%{search}%'),
                func.replace(func.replace(Professor.cpf, '.', ''), '-', '').ilike(f'%{search_clean}%')
            ))
        else:
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


@professors_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_professor():
    import flask
    from flask import session
    active_role = session.get('active_role')
    active_school_id = session.get('active_school_id')

    form = ProfessorForm()
    
    from app.models import DietaryRestriction, City, Country, Subject, User, Class, TeachingUnit, TeachingAssignment
    
    form.birth_country.choices = [(c.name, c.name) for c in Country.query.order_by(Country.name).all()]
    if request.method == 'POST' and request.form.get('birth_state'):
        form.birth_city_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in City.query.filter_by(uf=request.form.get('birth_state')).order_by(City.name).all()]
    else:
        form.birth_city_id.choices = [(0, 'Selecione...')]

    if form.validate_on_submit():

        clean_cpf = re.sub(r'[^0-9]', '', form.cpf.data)
        
        cpf_query = filter_by_tenant(Professor.query.filter_by(cpf=clean_cpf), Professor)
        if cpf_query.first():
            flash('CPF já cadastrado!', 'danger')
            return redirect(url_for('professors.new_professor'))

        professor = Professor(
            name=form.name.data,
            birth_date=form.birth_date.data,
            cpf=clean_cpf,
            sex=form.sex.data,
            race=form.race.data,
            nationality=form.nationality.data,
            birth_country=form.birth_country.data,
            email=form.email.data,
            inep_code=form.inep_code.data,
            sus_card=form.sus_card.data,
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

@professors_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_professor(id):
    active_role = flask.session.get('active_role')
    active_school_id = flask.session.get('active_school_id')
    active_school_name = flask.session.get('active_school_name')
    
    professor_query = Professor.query.filter_by(id=id)
    professor_query = filter_by_tenant(professor_query, Professor)
    professor = professor_query.first_or_404()
    
    if active_role == 'unidade':
        has_access = professor.assignments.join(Class).filter(Class.teaching_unit_id == active_school_id).first() is not None
        if not has_access:
            flask.abort(403)
            
    form = ProfessorForm(obj=professor)
    
    if active_role == 'unidade':
        schools = TeachingUnit.query.filter_by(id=active_school_id).all()
        form.teaching_unit_id.choices = [(active_school_id, active_school_name)]
    else:
        schools = TeachingUnit.query.filter_by(type='Escola').all()
        form.teaching_unit_id.choices = [(0, 'Selecione...')] + [(u.id, u.name) for u in schools]
        
    subjects = Subject.query.all()

    from app.models import City, Country
    form.birth_country.choices = [(c.name, c.name) for c in Country.query.order_by(Country.name).all()]
    if request.method == 'POST' and request.form.get('birth_state'):
        form.birth_city_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in City.query.filter_by(uf=request.form.get('birth_state')).order_by(City.name).all()]
    elif professor.birth_state:
        form.birth_city_id.choices = [(0, 'Selecione...')] + [(c.id, c.name) for c in City.query.filter_by(uf=professor.birth_state).order_by(City.name).all()]
    else:
        form.birth_city_id.choices = [(0, 'Selecione...')]

    if request.method == 'GET':
        # Serialize existing assignments
        # Data format: [{id: 1, school_name: "X", class_id: 1, class_name: "Y", subject_id: 1, subject_name: "Z"}]
        # Need to structure for JS
        data = []
        for a in professor.assignments:
            # Robustness check: Ensure related objects exist before accessing their attributes
            if not a.enrolled_class or not a.enrolled_class.teaching_unit or not a.subject:
                continue # Skip this assignment if critical related data is missing
            data.append({
                'school_id': a.enrolled_class.teaching_unit_id,
                'school_name': a.enrolled_class.teaching_unit.name,
                'class_id': a.class_id,
                'class_name': a.enrolled_class.name,
                'subject_id': a.subject_id,
                'subject_name': a.subject.name
            })
        form.assignments_data.data = json.dumps(data)
    
    if form.validate_on_submit():
        clean_cpf = re.sub(r'[^0-9]', '', form.cpf.data)
        
        existing = Professor.query.filter_by(cpf=clean_cpf).first()
        if existing and existing.id != professor.id:
            flash('CPF já cadastrado!', 'danger')
        else:
            professor.name = form.name.data
            professor.cpf = clean_cpf
            professor.sex = form.sex.data
            professor.race = form.race.data
            professor.birth_date = form.birth_date.data
            professor.email = form.email.data
            professor.nationality = form.nationality.data
            professor.birth_country = form.birth_country.data
            professor.inep_code = form.inep_code.data
            professor.sus_card = form.sus_card.data
            professor.residential_zone = form.residential_zone.data
            professor.differentiated_location = form.differentiated_location.data
            if form.nationality.data == 'Brasileiro':
                professor.birth_state = form.birth_state.data
                professor.birth_city_id = form.birth_city_id.data if form.birth_city_id.data and form.birth_city_id.data != 0 else None
            else:
                professor.birth_state = None
                professor.birth_city_id = None
            
            # Sync User
            user_email = form.email.data if form.email.data else None
            
            if professor.user:
                professor.user.email = user_email
                professor.user.name = form.name.data
                professor.user.role = 'professor'
                professor.user.roles = 'professor'
            
            # Update Assignments
            # Strategy: Delete all and recreate. 
            # professor.assignments.delete() # Helper delete on dynamic rel? No.
            # professor.assignments is dynamic query object.
            TeachingAssignment.query.filter_by(professor_id=professor.id).delete()
            
            if form.assignments_data.data:
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
                     print(f"Error updating assignments: {e}")

            # User generation on edit
            if form.generate_user.data and not professor.user_id:
                existing_user = User.query.filter_by(username=clean_cpf).first()
                dob_str = form.birth_date.data.strftime('%d%m%Y')
                # user_email defined above

                if existing_user:
                    existing_user.name = form.name.data
                    existing_user.email = user_email
                    existing_user.set_password(dob_str)
                    existing_user.add_role('professor')
                    existing_user.role = 'professor'
                    
                    professor.user = existing_user
                    flash(f'Usuário existente ({clean_cpf}) atualizado e vinculado.', 'info')
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
            log_audit('UPDATE', 'Professor', professor.id, f"Updated professor {professor.name}")
            
            flash('Professor atualizado!', 'success')
            return redirect(url_for('professors.list_professors'))

    return render_template('professors/form.html', form=form, title='Editar Professor', subjects=subjects, schools=schools) 

@professors_bp.route('/<int:id>/delete', methods=['POST'])
def delete_professor(id):
    professor_query = Professor.query.filter_by(id=id)
    professor_query = filter_by_tenant(professor_query, Professor)
    professor = professor_query.first_or_404()
    prof_id = professor.id
    prof_name = professor.name
    
    db.session.delete(professor)
    db.session.commit()
    
    from app.audit_utils import log_audit
    log_audit('DELETE', 'Professor', prof_id, f"Deleted professor {prof_name}")

    flash('Professor excluído.', 'success')
    return redirect(url_for('professors.list_professors'))

@professors_bp.route('/download-professor-layout')
@login_required
def download_professor_layout():
    import pandas as pd
    from io import BytesIO
    from flask import send_file
    
    data = {
        'Nome Completo': ['João Silva Professor', 'Maria Souza Professora'],
        'Data de Nascimento': ['01/05/1980', '15/08/1985'],
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
        'E-mail': ['joao.prof@email.com', 'maria.prof@email.com']
    }
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Professores')
        
    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name='layout_importacao_professores.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@professors_bp.route('/download-modulation-layout')
@login_required
def download_modulation_layout():
    import pandas as pd
    from io import BytesIO
    from flask import send_file
    
    data = {
        'INEP da Escola': ['12345678', ''],
        'Unidade de Ensino': ['Escola Exemplo 1', 'Escola Exemplo 1'],
        'Nome da Turma': ['101', '102'],
        'CPF': ['111.222.333-44', '555.666.777-88'],
        'Componente': ['Matemática', 'Língua Portuguesa']
    }
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Modulacao')
        
    output.seek(0)
    
    return send_file(
        output,
        as_attachment=True,
        download_name='layout_importacao_modulacoes.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@professors_bp.route('/import', methods=['POST'])
def import_professors():
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('professors.list_professors'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('professors.list_professors'))
        
    from app.services.import_service import ImportService
    from app.import_utils import start_import_task, update_import_progress, finish_import_task
    task_id = request.form.get('X-Progress-ID')
    
    result = ImportService.process_file(file, type='professor', task_id=task_id)
    
    if not result['success']:
        flash(result['error'], 'danger')
    else:
        # Performance optimizations
        from app.models import Professor, User
        prof_query = Professor.query
        prof_query = filter_by_tenant(prof_query, Professor)
        import re
        prof_map = {re.sub(r'[^0-9]', '', p.cpf): p for p in prof_query.all() if p.cpf}
        
        user_query = User.query
        user_query = filter_by_tenant(user_query, User)
        user_map = {u.username: u for u in user_query.all()}
        
        email_query = User.query.with_entities(User.email, User.username).filter(User.email.isnot(None))
        email_query = filter_by_tenant(email_query, User)
        email_map = {u.email: u.username for u in email_query.all()}
        
        created = 0
        updated = 0
        errors = result['errors']
        
        # Use valid data count for progress
        valid_data = result['data']
        total = len(valid_data)
        if task_id:
            start_import_task(total, task_id=task_id)
            
        for i, item in enumerate(valid_data):
            try:
                clean_cpf = re.sub(r'[^0-9]', '', item['cpf'])
                email_val = item.get('email')
                
                # 0. Check for email uniqueness (In-memory)
                if email_val:
                    conflict_username = email_map.get(email_val)
                    if conflict_username and conflict_username != clean_cpf:
                        err_msg = f"Aviso: CPF {item['cpf']} - {item['name']} importado com sucesso, mas ficou com e-mail vazio (o e-mail '{email_val}' já pertence a outro cadastro)."
                        errors.append(err_msg)
                        if task_id: update_import_progress(task_id, i+1, message=f"Aviso em {item['name']}", error=err_msg)
                        email_val = None
                    else:
                        email_map[email_val] = clean_cpf
                        
                # 1. Update or Create Professor
                professor = prof_map.get(item['cpf'])
                if professor:
                    changed = False
                    if email_val and professor.email != email_val:
                        professor.email = email_val
                        changed = True
                        
                    updateable_fields = [
                        'name', 'birth_date', 'sex', 'race', 
                        'inep_code', 'sus_card', 'nationality', 'birth_country',
                        'birth_state', 'birth_city_id', 'residential_zone', 
                        'differentiated_location'
                    ]
                    for field in updateable_fields:
                        if field in item and item[field] is not None and getattr(professor, field) != item[field]:
                            setattr(professor, field, item[field])
                            changed = True
                            
                    if changed:
                        updated += 1
                else:
                    professor = Professor(
                        name=item['name'],
                        cpf=item['cpf'],
                        birth_date=item['birth_date'],
                        sex=item.get('sex'),
                        race=item['race'],
                        email=email_val,
                        inep_code=item.get('inep_code'),
                        sus_card=item.get('sus_card'),
                        nationality=item.get('nationality'),
                        birth_country=item.get('birth_country'),
                        birth_state=item.get('birth_state'),
                        birth_city_id=item.get('birth_city_id'),
                        residential_zone=item.get('residential_zone'),
                        differentiated_location=item.get('differentiated_location'),
                        tenant_id=current_user.tenant_id
                    )
                    db.session.add(professor)
                    prof_map[item['cpf']] = professor # Add to local map for same-batch consistency
                    created += 1
                
                # (Removed flush to allow SQLAlchemy to batch inserts)
                
                # 2. Sync User
                user = user_map.get(clean_cpf)
                dob_str = item['birth_date'].strftime('%d%m%Y')
                
                if user:
                    user.name = item['name']
                    if email_val: user.email = email_val
                    user.set_password(dob_str)
                    user.add_role('professor')
                else:
                    user = User(
                        username=clean_cpf,
                        name=item['name'],
                        email=email_val,
                        role='professor',
                        roles='professor',
                        active=True,
                        tenant_id=current_user.tenant_id
                    )
                    user.add_role('professor')
                    user.set_password(dob_str)
                    db.session.add(user)
                    user_map[clean_cpf] = user
                
                professor.user = user
                
                # (Email uniqueness was checked at step 0)
                
                # Batch commit every 500 or final
                if (created + updated) % 500 == 0 or i == total - 1:
                    db.session.commit()
                    if task_id: update_import_progress(task_id, i+1, message=f"Lote processado ({created + updated})")
                else:
                    if task_id and (i % 10 == 0):
                        update_import_progress(task_id, i+1, message=f"Processando: {item['name']}")

            except ValueError as ve:
                db.session.rollback()
                err_msg = str(ve)
                errors.append(err_msg)
                if task_id: update_import_progress(task_id, i+1, message=f"Erro em {item['name']}", error=err_msg)
            except Exception as e:
                db.session.rollback()
                from sqlalchemy.exc import IntegrityError
                if isinstance(e, IntegrityError):
                    err_msg = f"Erro de duplicidade no banco de dados para {item.get('name')}. Verifique CPF/E-mail."
                else:
                    err_msg = f"Erro ao processar {item.get('name')}: {str(e)}"
                
                errors.append(err_msg)
                if task_id: update_import_progress(task_id, i+1, message=f"Erro em {item['name']}", error=err_msg)
    
        log_filename = None
        if errors:
            from app.import_utils import save_error_log
            log_filename = save_error_log(errors)
            
        if created > 0 or updated > 0:
            from app.audit_utils import log_audit
            log_audit('IMPORT', 'Professor', 0, f"Imported professors: {created} created, {updated} updated")
            flash(f'Importação concluída: {created} criados, {updated} atualizados.', 'success')
            finish_import_task(task_id, message=f"Concluído: {created} criados, {updated} atualizados.", log_file=log_filename)
        elif errors:
            # Case where only errors occurred
            finish_import_task(task_id, message="Importação finalizada com erros.", log_file=log_filename)
        
        if errors:
            for err in errors[:5]:
                flash(err, 'warning')
            if len(errors) > 5:
                flash(f'e mais {len(errors)-5} erros.', 'warning')
                
    return redirect(url_for('professors.list_professors'))

@professors_bp.route('/import-modulation', methods=['POST'])
def import_modulation():
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'danger')
        return redirect(url_for('professors.list_professors'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('professors.list_professors'))
        
    from app.services.import_service import ImportService
    from app.import_utils import start_import_task, update_import_progress, finish_import_task
    task_id = request.form.get('X-Progress-ID')
    
    result = ImportService.process_file(file, type='modulation', task_id=task_id)
    
    if not result['success']:
        flash(result['error'], 'danger')
    else:
        from app.models import Professor, TeachingAssignment, Class
        # Pre-fetch for performance: Map (class_id, subject_id) -> Existing TeachingAssignment
        prof_query = Professor.query.with_entities(Professor.cpf, Professor.id)
        prof_query = filter_by_tenant(prof_query, Professor)
        import re
        prof_id_map = {re.sub(r'[^0-9]', '', p.cpf): p.id for p in prof_query.all() if p.cpf}
        
        # We need the full object to update professor_id
        all_assignments = TeachingAssignment.query.join(Class).filter(Class.tenant_id == current_user.tenant_id).all()
        existing_assignments = {(a.class_id, a.subject_id): a for a in all_assignments}
        
        created = 0
        updated = 0
        errors = result['errors']
        
        # Use valid data count for progress
        valid_data = result['data']
        total = len(valid_data)
        if task_id:
            start_import_task(total, task_id=task_id)
        
        for i, item in enumerate(valid_data):
            try:
                prof_id = prof_id_map.get(item['cpf'])
                if not prof_id:
                    err_msg = f"Professor com CPF {item['cpf']} não encontrado."
                    errors.append(err_msg)
                    if task_id: update_import_progress(task_id, i+1, message=f"Erro em {item['cpf']}", error=err_msg)
                    continue
                
                # Check if assignment already exists for this Class and Subject
                key = (item['class_id'], item['subject_id'])
                assignment = existing_assignments.get(key)
                
                if assignment:
                    # Update if professor changed
                    if assignment.professor_id != prof_id:
                        assignment.professor_id = prof_id
                        updated += 1
                        if task_id and (i % 10 == 0):
                            update_import_progress(task_id, i+1, message=f"Atualizando: {item['cpf']}")
                else:
                    # Create new
                    assignment = TeachingAssignment(
                        professor_id=prof_id,
                        class_id=item['class_id'],
                        subject_id=item['subject_id']
                    )
                    db.session.add(assignment)
                    existing_assignments[key] = assignment # Track in memory for same batch
                    created += 1
                    if task_id and (i % 10 == 0):
                        update_import_progress(task_id, i+1, message=f"Atribuindo: {item['cpf']}")
                
                # Batch commit
                if (created + updated) % 100 == 0 or i == total - 1:
                    db.session.commit()
                    if task_id: update_import_progress(task_id, i+1, message=f"Lote gravado ({created + updated})")

            except Exception as e:
                db.session.rollback()
                from sqlalchemy.exc import IntegrityError
                if isinstance(e, IntegrityError):
                    err_msg = f"Erro de duplicidade para CPF {item['cpf']}. Modulação inconsistente."
                else:
                    err_msg = f"Erro na modulação CPF {item['cpf']}: {str(e)}"
                errors.append(err_msg)
                if task_id: update_import_progress(task_id, i+1, message=f"Erro em {item['cpf']}", error=err_msg)
    
    log_filename = None
    if errors:
        from app.import_utils import save_error_log
        log_filename = save_error_log(errors)
        
    finish_import_task(task_id, message=f"Concluído: {created} criados, {updated} atualizados.", log_file=log_filename)
    
    if created == 0 and updated == 0 and errors:
        # Case where only errors occurred
         finish_import_task(task_id, message="Importação finalizada com erros.", log_file=log_filename)
        
    if created > 0 or updated > 0:
        from app.audit_utils import log_audit
        log_audit('IMPORT', 'TeachingAssignment', 0, f"Imported assignments: {created} created, {updated} updated")
        flash(f'Importação concluída: {created} criadas, {updated} atualizadas.', 'success')
        
    if errors:
        for err in errors[:5]:
            flash(err, 'warning')
        if len(errors) > 5:
            flash(f'e mais {len(errors)-5} erros.', 'warning')
            
    return redirect(url_for('professors.list_professors'))

# --- TEACHER PORTAL ROUTES ---

@professors_bp.route('/dashboard')
@flask_login.login_required
def dashboard():
    # Check if user is a professor AND has active role professor
    from flask import session
    if not flask_login.current_user.professor_profile or session.get('active_role') != 'professor':
        flask.flash('Acesso restrito a professores.', 'danger')
        return flask.redirect(url_for('main.index'))
        
    professor = flask_login.current_user.professor_profile
    
    # Group by Class?
    # Dict: Class -> [Subjects]
    
    classes_map = {}
    for assignment in professor.assignments:
        c = assignment.enrolled_class
        # Robustness check: Ensure class exists and has teaching unit
        if not c or not c.teaching_unit:
            continue
            
        if c.id not in classes_map:
            classes_map[c.id] = {
                'id': c.id,
                'name': c.name,
                'school': c.teaching_unit.name,
                'subjects': []
            }
        
        if assignment.subject:
             classes_map[c.id]['subjects'].append(assignment.subject.name)
        
    return flask.render_template('professors/dashboard.html', classes=classes_map.values())

@professors_bp.route('/class/<int:class_id>/students')
@flask_login.login_required
def class_students(class_id):
    from flask import session
    if not flask_login.current_user.professor_profile or session.get('active_role') != 'professor':
        flask.flash('Acesso restrito a professores.', 'danger')
        return flask.redirect(url_for('main.index'))
        
    professor = flask_login.current_user.professor_profile
    
    # Verify access: Does this professor have ANY assignment in this class?
    has_access = False
    for a in professor.assignments:
        if a.class_id == class_id:
            has_access = True
            break
            
    if not has_access:
        flask.flash('Você não tem acesso a esta turma.', 'danger')
        return flask.redirect(url_for('professors.dashboard'))
        
    from app.models import Class
    class_query = Class.query.filter_by(id=class_id)
    class_query = filter_by_tenant(class_query, Class)
    klass = class_query.first_or_404()
    
    # Get active students through enrollment relationship
    page = request.args.get('page', 1, type=int)
    from app.models import Enrollment
    students_query = Student.query.join(Enrollment)\
        .filter(Enrollment.class_id == class_id, Enrollment.active == True)
    students_query = filter_by_tenant(students_query, Student)
    students_pagination = students_query.order_by(Student.name)\
        .paginate(page=page, per_page=30)
    
    return flask.render_template('professors/class_students.html', klass=klass, students=students_pagination)
