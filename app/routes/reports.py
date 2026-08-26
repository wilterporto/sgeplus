from flask import render_template, flash, redirect, url_for, send_file, request, jsonify
from flask_login import login_required, current_user
from app.routes import reports_bp
from app.models import StudentResult, Question, Descriptor, Exam, db, ExamItem, AbsenceReason, Student, Enrollment, Class, SchoolYear
from sqlalchemy import func
import json
import random
from datetime import datetime
from io import BytesIO
from xhtml2pdf import pisa
from app.utils.analytics import get_exam_selectors, get_dashboard_data, get_rankings_data

@reports_bp.route('/')
@login_required
def dashboard():
    # Only Admin, Regional Manager or Secretary can see this dashboard
    if current_user.role not in ['admin', 'regional_manager', 'secretaria']:
        flash('Acesso restrito.', 'danger')
        return redirect(url_for('main.index'))
        
    from app.models import IndigenousPeople, QuilombolaCommunity
    from app.utils.tenancy import filter_by_tenant
    
    exams = get_exam_selectors()
    indigenous = filter_by_tenant(IndigenousPeople.query, IndigenousPeople).all()
    quilombolas = filter_by_tenant(QuilombolaCommunity.query, QuilombolaCommunity).all()
    
    return render_template('reports/dashboard.html', exams=exams, indigenous=indigenous, quilombolas=quilombolas)

@reports_bp.route('/data')
@login_required
def api_dashboard_data():
    exam_id = request.args.get('exam_id', type=int)
    if not exam_id:
        return jsonify({'error': 'Exam ID required'}), 400
        
    regional_ids = request.args.getlist('regional_id[]', type=int)
    unit_ids = request.args.getlist('unit_id[]', type=int)
    school_year_ids = request.args.getlist('school_year_id[]', type=int)
    class_ids = request.args.getlist('class_id[]', type=int)
    
    # Demographic filters (Multi-select)
    races = request.args.getlist('races[]')
    nationalities = request.args.getlist('nationalities[]')
    incomes = request.args.getlist('incomes[]')
    
    # Novos Filtros Avançados
    zones = request.args.getlist('zones[]')
    locations = request.args.getlist('locations[]')
    deficiency = request.args.getlist('deficiency[]')
    bolsa = request.args.getlist('bolsa[]')
    dietary = request.args.getlist('dietary[]')
    indigenous = request.args.getlist('indigenous[]', type=int)
    quilombola = request.args.getlist('quilombola[]')
    quilombola_community = request.args.getlist('quilombolaCommunity[]', type=int)
    
    data = get_dashboard_data(
        exam_id=exam_id, 
        regional_ids=regional_ids, 
        unit_ids=unit_ids, 
        class_ids=class_ids, 
        school_year_ids=school_year_ids, 
        races=races, 
        nationalities=nationalities, 
        incomes=incomes,
        zones=zones,
        locations=locations,
        deficiency=deficiency,
        bolsa=bolsa,
        dietary=dietary,
        indigenous=indigenous,
        quilombola=quilombola,
        quilombola_community=quilombola_community
    )
    return jsonify(data)

@reports_bp.route('/seed-absence')
@login_required
def seed_absence_reasons():
    """
    Atribui motivos de ausência (com pesos) a 5% dos alunos do 5º ANO
    que não fizeram provas de Língua Portuguesa e Matemática.
    Distribuição: 60% Atestado médico | 30% Transporte | 10% Família em viagem.
    """
    # Buscar os 3 motivos cadastrados
    reason_med = AbsenceReason.query.filter(AbsenceReason.name.ilike('%atestado%')).first()
    reason_transp = AbsenceReason.query.filter(AbsenceReason.name.ilike('%transporte%')).first()
    reason_viagem = AbsenceReason.query.filter(AbsenceReason.name.ilike('%viagem%')).first()

    missing = []
    if not reason_med:    missing.append('Atestado médico')
    if not reason_transp: missing.append('Ausência de transporte escolar')
    if not reason_viagem: missing.append('Família em viagem')
    if missing:
        flash(f'Motivos de ausência não encontrados: {", ".join(missing)}. Cadastre-os primeiro.', 'danger')
        return redirect(url_for('reports.dashboard'))

    # Distribuição ponderada
    weighted_reasons = (
        [reason_med.id]    * 60 +
        [reason_transp.id] * 30 +
        [reason_viagem.id] * 10
    )

    # Localizar provas do 5º ANO de LP e Matemática
    year_5 = SchoolYear.query.filter(SchoolYear.name.ilike('%5%')).first()
    if not year_5:
        flash('Ano escolar "5º ANO" não encontrado na base.', 'danger')
        return redirect(url_for('reports.dashboard'))

    # Buscar provas via Subject direto (abordagem robusta)
    from app.models import Subject
    target_subjects = Subject.query.filter(
        db.or_(
            Subject.name.ilike('%língua portuguesa%'),
            Subject.name.ilike('%lingua portuguesa%'),
            Subject.name.ilike('%português%'),
            Subject.name.ilike('%matem%')
        )
    ).all()
    subject_ids = [s.id for s in target_subjects]

    if not subject_ids:
        flash('Nenhum componente curricular de Língua Portuguesa ou Matemática encontrado.', 'danger')
        return redirect(url_for('reports.dashboard'))

    target_exams = Exam.query.filter(
        Exam.school_year_id == year_5.id,
        Exam.subject_id.in_(subject_ids)
    ).all()

    if not target_exams:
        flash(f'Nenhuma prova do 5º ANO encontrada para os componentes selecionados (IDs: {subject_ids}).', 'warning')
        return redirect(url_for('reports.dashboard'))

    total_updated = 0

    for exam in target_exams:
        # Buscar todos os resultados da prova sem motivo de ausência já atribuído
        candidates = StudentResult.query.filter(
            StudentResult.exam_id == exam.id,
            StudentResult.absence_reason_id == None
        ).all()

        if not candidates:
            continue

        # 5% arredondado para cima (mínimo 1)
        n_to_assign = max(1, round(len(candidates) * 0.05))
        chosen = random.sample(candidates, min(n_to_assign, len(candidates)))

        for result in chosen:
            result.absence_reason_id = random.choice(weighted_reasons)
            total_updated += 1

    db.session.commit()

    if total_updated == 0:
        flash('Nenhum registro elegível encontrado. Verifique se há alunos sem resposta nas provas do 5º ANO.', 'warning')
    else:
        flash(
            f'✅ {total_updated} motivo(s) de ausência atribuído(s) com sucesso em '
            f'{len(target_exams)} prova(s) do 5º ANO (LP/Matemática). '
            f'Distribuição: 60% Atestado médico | 30% Transporte | 10% Família em viagem.',
            'success'
        )
    return redirect(url_for('reports.dashboard'))

@reports_bp.route('/export/students-by-level')
@login_required
def export_students_by_level():
    exam_id = request.args.get('exam_id', type=int)
    level = request.args.get('level', type=int)
    if not exam_id or not level:
        return "Exam ID e Nível são obrigatórios", 400

    regional_ids = request.args.getlist('regional_id[]', type=int)
    unit_ids = request.args.getlist('unit_id[]', type=int)
    school_year_ids = request.args.getlist('school_year_id[]', type=int)
    class_ids = request.args.getlist('class_id[]', type=int)
    races = request.args.getlist('races[]')
    nationalities = request.args.getlist('nationalities[]')
    incomes = request.args.getlist('incomes[]')
    zones = request.args.getlist('zones[]')
    locations = request.args.getlist('locations[]')
    deficiency = request.args.getlist('deficiency[]')
    bolsa = request.args.getlist('bolsa[]')
    dietary = request.args.getlist('dietary[]')

    rankings = get_rankings_data(
        exam_id, regional_ids, unit_ids, class_ids, school_year_ids,
        races, nationalities, incomes, zones, locations, deficiency, bolsa, dietary
    )

    filtered_students = []
    for s in rankings.get('students', []):
        score = s['score']
        if score < 25: s_level = 1
        elif score < 50: s_level = 2
        elif score < 75: s_level = 3
        else: s_level = 4
        
        if s_level == level:
            filtered_students.append(s)

    # Order alphabetically by school and then by student
    filtered_students.sort(key=lambda x: (x['sub'] or '', x['name'] or ''))

    level_names = {
        1: 'Abaixo do básico',
        2: 'Básico',
        3: 'Proficiente',
        4: 'Avançado'
    }
    level_name = level_names.get(level, str(level))

    exam = Exam.query.get_or_404(exam_id)
    html = render_template('reports/pdf_students_by_level.html', 
                           students=filtered_students, 
                           level_name=level_name, 
                           exam=exam,
                           now=datetime.now())
    
    dest = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=dest)
    if pisa_status.err:
        return "Erro ao gerar PDF", 500
    
    dest.seek(0)
    return send_file(dest, download_name=f"alunos_nivel_{level}.pdf", as_attachment=True, mimetype='application/pdf')

@reports_bp.route('/export/schools-by-proficiency')
@login_required
def export_schools_by_proficiency():
    exam_id = request.args.get('exam_id', type=int)
    prof_op = request.args.get('prof_op')
    prof_val = request.args.get('prof_val', type=float)
    if not exam_id or not prof_op or prof_val is None:
        return "Exam ID, Operador e Valor são obrigatórios", 400

    regional_ids = request.args.getlist('regional_id[]', type=int)
    unit_ids = request.args.getlist('unit_id[]', type=int)
    school_year_ids = request.args.getlist('school_year_id[]', type=int)
    class_ids = request.args.getlist('class_id[]', type=int)
    races = request.args.getlist('races[]')
    nationalities = request.args.getlist('nationalities[]')
    incomes = request.args.getlist('incomes[]')
    zones = request.args.getlist('zones[]')
    locations = request.args.getlist('locations[]')
    deficiency = request.args.getlist('deficiency[]')
    bolsa = request.args.getlist('bolsa[]')
    dietary = request.args.getlist('dietary[]')

    rankings = get_rankings_data(
        exam_id, regional_ids, unit_ids, class_ids, school_year_ids,
        races, nationalities, incomes, zones, locations, deficiency, bolsa, dietary
    )

    filtered_schools = []
    for s in rankings.get('schools', []):
        score = s['score']
        if score is None: continue
        if prof_op == '<' and score < prof_val:
            filtered_schools.append(s)
        elif prof_op == '>' and score > prof_val:
            filtered_schools.append(s)

    # Order alphabetically by school
    filtered_schools.sort(key=lambda x: x['name'] or '')

    exam = Exam.query.get_or_404(exam_id)
    html = render_template('reports/pdf_schools_by_proficiency.html', 
                           schools=filtered_schools, 
                           prof_op=prof_op, 
                           prof_val=prof_val, 
                           exam=exam,
                           now=datetime.now())
    
    dest = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=dest)
    if pisa_status.err:
        return "Erro ao gerar PDF", 500
    
    dest.seek(0)
    return send_file(dest, download_name=f"escolas_proficiencia.pdf", as_attachment=True, mimetype='application/pdf')

@reports_bp.route('/seed')
def seed_data():
    """Generates dummy data for demonstration"""
    # Create some descriptors if none
    if Descriptor.query.count() == 0:
        for i in range(1, 11):
            db.session.add(Descriptor(code=f'D{i}', description=f'Descriptor {i}', subject='Math'))
        db.session.commit()
        
    # Create some questions if none
    if Question.query.count() == 0:
        descriptors = Descriptor.query.all()
        for i in range(50):
            q = Question(
                statement=f"Questão Exemplo {i+1}",
                difficulty=random.choice(['Facil', 'Medio', 'Dificil']),
                descriptors=[random.choice(descriptors)],
                correct_alternative='A',
                alternatives=json.dumps({'A': 'Correta', 'B': 'Errada', 'C': 'Errada', 'D': 'Errada', 'E': 'Errada'})
            )
            db.session.add(q)
        db.session.commit()
        
    # Create some exams and results
    questions = Question.query.all()
    if not questions:
        flash('Sem questões para gerar dados.', 'warning')
        return redirect(url_for('reports.dashboard'))

    # Generate 20 students results
    for i in range(20):
        # Fake exam taking
        selected_qs = random.sample(questions, 10)
        answers = {}
        correct_count = 0
        
        # Simulate proficiency grouping
        # Student ability: 0.0 to 1.0
        ability = random.random() 
        
        for q in selected_qs:
            # Chance to correct depends on ability
            is_correct = random.random() < ability
            answers[str(q.id)] = is_correct
            if is_correct:
                correct_count += 1
                
        score = (correct_count / 10) * 100
        
        result = StudentResult(
            student_name=f"Aluno {i+1}",
            regional="Metropolitana",
            answers=json.dumps(answers),
            score_percentage=score
        )
        db.session.add(result)
        
    db.session.commit()
    flash('Dados de teste gerados com sucesso!', 'success')
    return redirect(url_for('reports.dashboard'))

@reports_bp.route('/evaluation-summary', methods=['GET', 'POST'])
@login_required
def evaluation_summary():
    from app.models import Evaluation, SchoolYear, Exam, TeachingUnit, Class, Enrollment, Student, StudentResult, Subject, Region, SubRegion, Tenant
    from app.utils.tenancy import filter_by_tenant, get_tenant_id
    import json
    import io
    import pandas as pd
    from flask import send_file
    
    tenant_id = get_tenant_id()
    tenant_type = None
    if tenant_id:
        tenant = Tenant.query.get(tenant_id)
        tenant_type = tenant.type if tenant else None
        
    exam_query = filter_by_tenant(db.session.query(
        Exam.evaluation_id,
        Evaluation.name.label('eval_name'),
        Evaluation.type.label('eval_type'),
        Exam.school_year_id,
        SchoolYear.name.label('sy_name'),
        Exam.academic_year
    ).join(Evaluation, Exam.evaluation_id == Evaluation.id)\
     .join(SchoolYear, Exam.school_year_id == SchoolYear.id), Exam)
     
    combinations = exam_query.distinct().all()
    
    evaluation_group_options = []
    for row in combinations:
        val = f"{row.evaluation_id}_{row.school_year_id}_{row.academic_year}"
        display = f"{row.eval_name} ({row.eval_type}) - {row.sy_name} - {row.academic_year}"
        evaluation_group_options.append((val, display))
    
    evaluation_group_options.sort(key=lambda x: x[1])
    
    # Filter options
    tu_query = filter_by_tenant(TeachingUnit.query, TeachingUnit)
    residential_zones = [rz[0] for rz in tu_query.with_entities(TeachingUnit.residential_zone).distinct().filter(TeachingUnit.residential_zone != None).all()]
    diff_locations = [dl[0] for dl in tu_query.with_entities(TeachingUnit.differentiated_location).distinct().filter(TeachingUnit.differentiated_location != None).all()]
    
    regional_ids_in_use = [p[0] for p in tu_query.with_entities(TeachingUnit.parent_id).distinct().filter(TeachingUnit.parent_id != None).all()]
    regionals = TeachingUnit.query.filter(TeachingUnit.id.in_(regional_ids_in_use)).order_by(TeachingUnit.name).all()
    
    regions = Region.query.order_by(Region.name).all() if Region else []
    sub_regions = SubRegion.query.order_by(SubRegion.name).all() if SubRegion else []
    
    municipios = []
    if tenant_type and tenant_type.lower() == 'estadual':
        municipios = [m[0] for m in tu_query.with_entities(TeachingUnit.municipio).distinct().filter(TeachingUnit.municipio != None).order_by(TeachingUnit.municipio).all()]

    results_by_school = {}
    subjects_map = {}
    active_subject_ids = set()
    sorted_active_subjects = []
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 30
    
    evaluation_group = request.args.get('evaluation_group') or request.form.get('evaluation_group')
    
    evaluation_id = None
    school_year_id = None
    academic_year = None
    
    if evaluation_group:
        parts = evaluation_group.split('_')
        if len(parts) == 3:
            evaluation_id = int(parts[0])
            school_year_id = int(parts[1])
            academic_year = int(parts[2])
    
    # Advanced filters
    f_residential_zone = request.args.get('residential_zone') or request.form.get('residential_zone')
    f_differentiated_location = request.args.get('differentiated_location') or request.form.get('differentiated_location')
    f_regional_id = request.args.get('regional_id') or request.form.get('regional_id')
    f_region_id = request.args.get('region_id') or request.form.get('region_id')
    f_sub_region_id = request.args.get('sub_region_id') or request.form.get('sub_region_id')
    f_municipio = request.args.get('municipio') or request.form.get('municipio')
    export_format = request.args.get('export')
    
    total_pages = 0
    paginated_items = []
    
    if evaluation_id and school_year_id and academic_year:
        query = db.session.query(
            TeachingUnit, Exam, StudentResult
        ).join(Class, TeachingUnit.id == Class.teaching_unit_id)\
         .join(Enrollment, Class.id == Enrollment.class_id)\
         .join(Student, Enrollment.student_id == Student.id)\
         .join(StudentResult, Student.id == StudentResult.student_id)\
         .join(Exam, StudentResult.exam_id == Exam.id)\
         .filter(
            Exam.evaluation_id == evaluation_id,
            Exam.school_year_id == school_year_id,
            Exam.academic_year == academic_year,
            StudentResult.absence_reason_id == None,
            Enrollment.active == True
         )
         
        if tenant_id:
            query = query.filter(TeachingUnit.tenant_id == tenant_id)
            
        # Apply Advanced Filters
        if f_residential_zone:
            query = query.filter(TeachingUnit.residential_zone == f_residential_zone)
        if f_differentiated_location:
            query = query.filter(TeachingUnit.differentiated_location == f_differentiated_location)
        if f_regional_id:
            query = query.filter(TeachingUnit.parent_id == int(f_regional_id))
        if f_region_id:
            query = query.filter(TeachingUnit.region_id == int(f_region_id))
        if f_sub_region_id:
            query = query.filter(TeachingUnit.sub_region_id == int(f_sub_region_id))
        if f_municipio:
            query = query.filter(TeachingUnit.municipio == f_municipio)
            
        for s in Subject.query.all():
            subjects_map[str(s.id)] = s.name
            
        for unit, exam, result in query.all():
            unit_name = unit.name
            regional_name = unit.parent.name if unit.parent else 'N/A'
            if unit_name not in results_by_school:
                results_by_school[unit_name] = {
                    'unit': unit, 
                    'regional_name': regional_name,
                    'inep': unit.inep_code,
                    'municipio': unit.municipio,
                    'tenant_type': tenant_type,
                    'subjects': {},
                    'attendance_sum': 0,
                    'attendance_count': 0,
                    'overall_sum': 0,
                    'overall_count': 0
                }
            
            # Attendance
            if result.attendance_percentage is not None:
                results_by_school[unit_name]['attendance_sum'] += result.attendance_percentage
                results_by_school[unit_name]['attendance_count'] += 1
            
            if exam.subject_id:
                subj_id = str(exam.subject_id)
                active_subject_ids.add(subj_id)
                if subj_id not in results_by_school[unit_name]['subjects']:
                    results_by_school[unit_name]['subjects'][subj_id] = {'sum': 0, 'count': 0, 'att_sum': 0, 'att_count': 0}
                score = result.score_percentage or 0
                results_by_school[unit_name]['subjects'][subj_id]['sum'] += score
                results_by_school[unit_name]['subjects'][subj_id]['count'] += 1
                
                if result.attendance_percentage is not None:
                    results_by_school[unit_name]['subjects'][subj_id]['att_sum'] += result.attendance_percentage
                    results_by_school[unit_name]['subjects'][subj_id]['att_count'] += 1
                
                results_by_school[unit_name]['overall_sum'] += score
                results_by_school[unit_name]['overall_count'] += 1
            else:
                if result.subject_attendance:
                    try:
                        att_dict = json.loads(result.subject_attendance)
                        for s_id, score in att_dict.items():
                            active_subject_ids.add(s_id)
                            if s_id not in results_by_school[unit_name]['subjects']:
                                results_by_school[unit_name]['subjects'][s_id] = {'sum': 0, 'count': 0, 'att_sum': 0, 'att_count': 0}
                            score_val = float(score)
                            results_by_school[unit_name]['subjects'][s_id]['sum'] += score_val
                            results_by_school[unit_name]['subjects'][s_id]['count'] += 1
                            
                            if result.attendance_percentage is not None:
                                results_by_school[unit_name]['subjects'][s_id]['att_sum'] += result.attendance_percentage
                                results_by_school[unit_name]['subjects'][s_id]['att_count'] += 1
                            
                            results_by_school[unit_name]['overall_sum'] += score_val
                            results_by_school[unit_name]['overall_count'] += 1
                    except:
                        pass
        
        # Calculate averages
        for unit_name, data in results_by_school.items():
            for s_id, s_data in data['subjects'].items():
                s_data['avg'] = s_data['sum'] / s_data['count'] if s_data['count'] > 0 else 0
                s_data['att_avg'] = s_data['att_sum'] / s_data['att_count'] if s_data['att_count'] > 0 else 0
            
            data['attendance_avg'] = data['attendance_sum'] / data['attendance_count'] if data['attendance_count'] > 0 else 0
            data['overall_avg'] = data['overall_sum'] / data['overall_count'] if data['overall_count'] > 0 else 0
                
        # Prepare pagination
        sorted_items = sorted(results_by_school.items(), key=lambda x: x[1]['overall_avg'], reverse=True)
        total_items = len(sorted_items)
        sorted_active_subjects = sorted(list(active_subject_ids), key=lambda x: subjects_map.get(x, x))
        
        if export_format == 'excel':
            data = []
            for rank, (unit_name, r_data) in enumerate(sorted_items, 1):
                row = {
                    'Classificação': f"{rank}ª",
                    'Regional': r_data['regional_name'],
                    'Código INEP': r_data['inep'] or '',
                    'Escola': unit_name,
                    'Proficiência Média': f"{r_data['overall_avg']:.1f}%",
                    'Frequência Média': f"{r_data['attendance_avg']:.1f}%"
                }
                if tenant_type and tenant_type.lower() == 'estadual':
                    row['Município'] = r_data['municipio'] or ''
                    
                for subj_id in sorted_active_subjects:
                    subj_name = subjects_map.get(subj_id, f"Componente {subj_id}")
                    if subj_id in r_data['subjects']:
                        row[f"{subj_name} - Proficiência"] = f"{r_data['subjects'][subj_id]['avg']:.1f}%"
                        row[f"{subj_name} - Frequência"] = f"{r_data['subjects'][subj_id]['att_avg']:.1f}%"
                    else:
                        row[f"{subj_name} - Proficiência"] = "-"
                        row[f"{subj_name} - Frequência"] = "-"
                
                data.append(row)
                
            df = pd.DataFrame(data)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Resumo Avaliações')
            output.seek(0)
            return send_file(output, as_attachment=True, download_name='resumo_avaliacoes.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        import math
        total_pages = math.ceil(total_items / per_page)
        
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_items = sorted_items[start_idx:end_idx]

    return render_template('reports/evaluation_summary.html',
                           evaluation_group_options=evaluation_group_options,
                           residential_zones=residential_zones,
                           diff_locations=diff_locations,
                           regionals=regionals,
                           regions=regions,
                           sub_regions=sub_regions,
                           municipios=municipios,
                           tenant_type=tenant_type,
                           results_by_school=paginated_items,
                           subjects_map=subjects_map,
                           active_subject_ids=sorted_active_subjects,
                           page=page,
                           total_pages=total_pages,
                           evaluation_group=evaluation_group,
                           f_residential_zone=f_residential_zone,
                           f_differentiated_location=f_differentiated_location,
                           f_regional_id=int(f_regional_id) if f_regional_id else None,
                           f_region_id=int(f_region_id) if f_region_id else None,
                           f_sub_region_id=int(f_sub_region_id) if f_sub_region_id else None,
                           f_municipio=f_municipio)
