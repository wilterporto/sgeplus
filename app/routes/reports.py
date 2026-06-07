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

    exam = Exam.query.get_or_404(exam_id)
    html = render_template('reports/pdf_students_by_level.html', 
                           students=filtered_students, 
                           level=level, 
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
