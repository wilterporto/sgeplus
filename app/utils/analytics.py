from app.models import db, StudentResult, Student, Enrollment, Class, TeachingUnit, Exam, ExamItem, Question, SchoolYear, Subject, Professor, TeachingAssignment, AbsenceReason
from sqlalchemy import func
import sqlalchemy as sa
import json
from app.utils.tenancy import get_tenant_id

def get_exam_selectors():
    """Returns list of exams formatted as 'Title - Year - School Year - Subject'"""
    from flask_login import current_user
    from app.utils.tenancy import filter_by_tenant
    query = Exam.query
    query = filter_by_tenant(query, Exam)
    exams = query.order_by(Exam.application_date.desc()).all()
    results = []
    for e in exams:
        # Use direct relationships if available, fallback to derivation if not
        school_year = e.school_year.name if e.school_year else None
        subject = e.subject.name if e.subject else None
        
        if not school_year or not subject:
            first_item = e.items.first()
            if first_item:
                descriptors = first_item.question.descriptors
                if descriptors and len(descriptors) > 0:
                    desc = descriptors[0]
                    if not school_year: school_year = desc.school_year.name if desc.school_year else "N/A"
                    if not subject: subject = desc.subject.name if desc.subject else "N/A"
        
        school_year = school_year or "N/A"
        subject = subject or "N/A"
        
        # Determine if it's a multiple components exam
        is_multiple = False
        if e.evaluation and getattr(e.evaluation, 'multiple_components', False):
            is_multiple = True
        elif e.subject_id is None:
            is_multiple = True
            
        display = f"{e.title} - {e.academic_year} - {school_year}"
        if not is_multiple and "multidisciplinar" not in e.title.lower():
            display += f" - {subject}"
            
        results.append({'id': e.id, 'display': display})
    return results

def get_dashboard_data(exam_id, regional_ids=None, unit_ids=None, class_ids=None, school_year_ids=None, races=None, nationalities=None, incomes=None, zones=None, locations=None, deficiency=None, bolsa=None, dietary=None, indigenous=None, quilombola=None, quilombola_community=None):
    """
    Aggregates performance data based on hierarchical and demographic filters.
    """
    from flask_login import current_user
    from app.utils.tenancy import filter_by_tenant
    
    exam_query = Exam.query.filter_by(id=exam_id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first()
    if not exam:
        return None

    # Base query for results of this exam
    query = db.session.query(StudentResult).filter(StudentResult.exam_id == exam_id)
    
    # Joins for filtering and grouping
    query = query.join(Student, StudentResult.student_id == Student.id)\
                 .join(Enrollment, Student.id == Enrollment.student_id)\
                 .filter(Enrollment.active == True)\
                 .join(Class, Enrollment.class_id == Class.id)\
                 .join(TeachingUnit, Class.teaching_unit_id == TeachingUnit.id)
                 
    if current_user.is_authenticated and get_tenant_id():
        query = query.filter(Student.tenant_id == get_tenant_id())

    # Apply hierarchical filters
    if class_ids:
        query = query.filter(Class.id.in_(class_ids))
    if unit_ids:
        query = query.filter(TeachingUnit.id.in_(unit_ids))
    if school_year_ids:
        query = query.filter(Class.school_year_id.in_(school_year_ids))
    if regional_ids:
        # Escolas nestas regionais
        query = query.filter(TeachingUnit.parent_id.in_(regional_ids))
        
    # RESTRIÇÃO: Garantir que todos os dados sejam do ano escolar da prova
    if exam.school_year_id:
        query = query.filter(Class.school_year_id == exam.school_year_id)

    # Apply demographic filters (Multi-select)
    if races and len(races) > 0:
        query = query.filter(Student.race.in_(races))
    if nationalities and len(nationalities) > 0:
        query = query.filter(Student.nationality.in_(nationalities))
    if incomes and len(incomes) > 0:
        query = query.filter(Student.family_income.in_(incomes))

    # Novos Filtros Avançados
    if zones and len(zones) > 0:
        query = query.filter(Student.residential_zone.in_(zones))
    if locations and len(locations) > 0:
        query = query.filter(Student.differentiated_location.in_(locations))
    if deficiency and len(deficiency) > 0:
        if 'Sim' in deficiency and 'Não' not in deficiency:
            query = query.filter(Student.special_needs == True)
        elif 'Não' in deficiency and 'Sim' not in deficiency:
            query = query.filter(Student.special_needs == False)
    if bolsa and len(bolsa) > 0:
        if 'Sim' in bolsa and 'Não' not in bolsa:
            query = query.filter(Student.bolsa_familia == True)
        elif 'Não' in bolsa and 'Sim' not in bolsa:
            query = query.filter(Student.bolsa_familia == False)
    if dietary and len(dietary) > 0:
        if 'Sim' in dietary and 'Não' not in dietary:
            query = query.filter(Student.dietary_restrictions.any())
        elif 'Não' in dietary and 'Sim' not in dietary:
            query = query.filter(~Student.dietary_restrictions.any())
    if indigenous and len(indigenous) > 0:
        query = query.filter(Student.indigenous_people_id.in_(indigenous))
    if quilombola and len(quilombola) > 0:
        if 'Sim' in quilombola and 'Não' not in quilombola and 'Nǐo' not in quilombola and 'Nào' not in quilombola:
            query = query.filter(Student.is_quilombola == True)
        elif ('Não' in quilombola or 'Nǐo' in quilombola or 'Nào' in quilombola) and 'Sim' not in quilombola:
            query = query.filter(Student.is_quilombola == False)
    if quilombola_community and len(quilombola_community) > 0:
        query = query.filter(Student.quilombola_community_id.in_(quilombola_community))


    query = query.with_entities(
        StudentResult.score_percentage,
        StudentResult.absence_reason_id,
        StudentResult.answers,
        StudentResult.finished_at,
        Student.id.label('student_id'),
        Student.name.label('student_name')
    )
    results = query.all()
    
    if not results:
        # Get identifying info even for empty results
        selectors = get_exam_selectors()
        current_display = next((s['display'] for s in selectors if s['id'] == exam_id), f"{exam.title} ({exam.academic_year})")
        
        return {
            'kpis': {'avg_score': 0, 'participation': 0, 'alerts': 0, 'engagement': {'total':0,'realized':0,'absent':0,'missing':0,'fully_responded':0,'partially_responded':0,'not_responded_present':0}},
            'ranking': [],
            'items': [],
            'details': [],
            'components_performance': [],
            'absence_reasons': [],
            'proficiency': {
                'level1': {'count': 0, 'perc': 0},
                'level2': {'count': 0, 'perc': 0},
                'level3': {'count': 0, 'perc': 0},
                'level4': {'count': 0, 'perc': 0}
            },
            'difficulty_performance': {
                'Facil': {'correct_perc': 0.0, 'total_answers': 0, 'correct_answers': 0},
                'Medio': {'correct_perc': 0.0, 'total_answers': 0, 'correct_answers': 0},
                'Dificil': {'correct_perc': 0.0, 'total_answers': 0, 'correct_answers': 0}
            },
            'radar_labels': [],
            'radar_data': [],
            'rankings': {
                'schools': [],
                'classes': [],
                'students': [],
                'professors': []
            },
            'map_data': {'schools': [], 'missing_coords_count': 0},
            'current_exam_title': current_display
        }

    # Pré-processamento dos resultados para uma lista leve de dicionários
    # Fazemos json.loads apenas uma única vez por aluno (O(N))
    processed_results = []
    for r in results:
        try:
            answers_dict = json.loads(r.answers) if r.answers else {}
        except Exception:
            answers_dict = {}
            
        processed_results.append({
            'score_percentage': r.score_percentage,
            'absence_reason_id': r.absence_reason_id,
            'finished_at': r.finished_at,
            'student_id': r.student_id,
            'student_name': r.student_name,
            'answers_dict': answers_dict
        })

    # 1. KPIs
    total_students_scoped = _get_total_students_count(
        exam, 
        regional_ids, 
        unit_ids, 
        class_ids, 
        school_year_ids,
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
    
    # Engagement and Completion logic - filter for finished exams for averages
    finished_results = [r for r in processed_results if r['absence_reason_id'] is None and r['finished_at'] is not None]
    realized_results = [r for r in processed_results if r['absence_reason_id'] is None]
    absent_results = [r for r in processed_results if r['absence_reason_id'] is not None]
    
    participation_rate = (len(realized_results) / total_students_scoped * 100) if total_students_scoped > 0 else 0
    avg_score = sum(r['score_percentage'] or 0 for r in finished_results) / len(finished_results) if finished_results else 0
    alerts = len([r for r in processed_results if r['absence_reason_id'] is None and (r['score_percentage'] or 0) < 50 and r['finished_at'] is not None])

    # Detailed Engagement
    total_items = exam.items.count()
    fully_responded = 0
    partially_responded = 0
    not_responded_present = 0
    
    for r in realized_results:
        ans_count = len(r['answers_dict'])
        if ans_count == total_items:
            fully_responded += 1
        elif ans_count > 0:
            partially_responded += 1
        else:
            not_responded_present += 1

    absent_count = len(absent_results)
    missing_count = total_students_scoped - len(processed_results) # Neither result nor absence recorded
    
    # Proficiency Levels
    prof_levels = {
        'level1': {'count': 0, 'perc': 0}, # < 25%
        'level2': {'count': 0, 'perc': 0}, # 25% - 49.9%
        'level3': {'count': 0, 'perc': 0}, # 50% - 74.99%
        'level4': {'count': 0, 'perc': 0}  # >= 75%
    }
    
    total_finished = len(finished_results)
    if total_finished > 0:
        for r in finished_results:
            score = r['score_percentage'] or 0
            if score < 25: prof_levels['level1']['count'] += 1
            elif score < 50: prof_levels['level2']['count'] += 1
            elif score < 75: prof_levels['level3']['count'] += 1
            else: prof_levels['level4']['count'] += 1
        
        for key in prof_levels:
            prof_levels[key]['perc'] = round((prof_levels[key]['count'] / total_finished) * 100, 1)

    # 2. Ranking / Drill-down
    # Determina qual nível estamos mostrando na lista de ranking
    ranking = []
    if not regional_ids and not unit_ids and not school_year_ids and not class_ids:
        # Mostrar Regionais
        ranking = _get_group_performance(exam_id, 'regional')
    elif regional_ids and not unit_ids:
        # Mostrar Escolas nestas Regionais
        ranking = _get_group_performance(exam_id, 'unit', regional_ids=regional_ids)
    elif unit_ids and not school_year_ids:
        # Show School Years in these Schools
        ranking = _get_group_performance(exam_id, 'school_year', unit_ids=unit_ids)
    elif school_year_ids and not class_ids:
        # Show Classes in these Grades & Schools
        ranking = _get_group_performance(exam_id, 'class', unit_ids=unit_ids, school_year_ids=school_year_ids)
    else:
        # Show Students in this Class
        ranking = [{"id": r['student_id'], "name": r['student_name'], "score": r['score_percentage'] or 0, "is_absent": r['absence_reason_id'] is not None} for r in processed_results]
        ranking.sort(key=lambda x: x['score'] or 0, reverse=True)

    # 3. Item Analysis & Difficulty Performance
    item_analysis = []
    difficulty_stats = {
        'Facil': {'correct': 0, 'total': 0},
        'Medio': {'correct': 0, 'total': 0},
        'Dificil': {'correct': 0, 'total': 0}
    }
    descriptor_stats = {} # {desc_id: {code, description, correct, total}}
    
    # --- TEMPORARY LOGGING ---
    try:
        with open('item_analysis_debug.log', 'a', encoding='utf-8') as f:
            f.write(f"\\n--- DEBUGGING EXAM {exam_id} --- \\n")
            f.write(f"Total processed_results: {len(processed_results)}\\n")
            f.write(f"Total exam.items: {exam.items.count()}\\n")
            if len(processed_results) > 0:
                f.write(f"Sample answers_dict for student 1: {processed_results[0].get('answers_dict')}\\n")
    except Exception as e:
        print("Log error:", e)
    # -------------------------

    def normalize_difficulty(diff_str):
        if not diff_str:
            return 'Medio'
        d = diff_str.lower()
        if 'fac' in d:
            return 'Facil'
        elif 'dif' in d:
            return 'Dificil'
        else:
            return 'Medio'

    for idx, item in enumerate(exam.items):
        if not item.question:
            continue
        diff = normalize_difficulty(item.question.difficulty)
        correct = 0
        incorrect = 0
        blank = 0
        total = len(processed_results) # Todos os alunos no escopo do filtro (presentes e ausentes)
        
        for res in processed_results:
            if res['absence_reason_id'] is not None:
                blank += 1
            else:
                ans = res['answers_dict'].get(str(item.question.id))
                if ans is not None and ans != '':
                    if ans == item.question.correct_alternative:
                        correct += 1
                    else:
                        incorrect += 1
                else:
                    blank += 1
                    
        correct_perc = round((correct / total * 100), 2) if total > 0 else 0.0
        incorrect_perc = round((incorrect / total * 100), 2) if total > 0 else 0.0
        blank_perc = round(100.0 - correct_perc - incorrect_perc, 2) if total > 0 else 0.0
        desc_codes = ", ".join([d.code for d in item.question.descriptors]) if item.question.descriptors else "N/A"
        desc_descriptions = "; ".join([d.description for d in item.question.descriptors]) if item.question.descriptors else ""
        
        # update descriptor_stats
        q_answered = correct + incorrect
        for d in item.question.descriptors:
            if d.id not in descriptor_stats:
                descriptor_stats[d.id] = {'code': d.code, 'description': d.description, 'correct': 0, 'total': 0}
            descriptor_stats[d.id]['correct'] += correct
            descriptor_stats[d.id]['total'] += q_answered
        
        # --- TEMPORARY LOGGING ---
        try:
            with open('item_analysis_debug.log', 'a', encoding='utf-8') as f:
                f.write(f"Item {idx+1} | Q_ID: {item.question.id} | Correct Alt: {item.question.correct_alternative} | Correct: {correct} | Incorrect: {incorrect} | Blank: {blank} | Correct Perc: {correct_perc}%\\n")
        except:
            pass
        # -------------------------
        
        item_analysis.append({
            'num': idx + 1,
            'question_id': item.question.id,
            'statement': item.question.statement,
            'desc_codes': desc_codes,
            'desc_descriptions': desc_descriptions,
            'correct_perc': correct_perc,
            'incorrect_perc': incorrect_perc,
            'blank_perc': blank_perc,
            'correct_count': correct,
            'incorrect_count': incorrect,
            'blank_count': blank,
            'total_count': total
        })
        
        if diff in difficulty_stats:
            difficulty_stats[diff]['correct'] += correct
            difficulty_stats[diff]['total'] += (correct + incorrect)

    difficulty_performance = {}
    for diff, stats in difficulty_stats.items():
        tot = stats['total']
        corr = stats['correct']
        difficulty_performance[diff] = {
            'correct_perc': round((corr / tot * 100), 1) if tot > 0 else 0.0,
            'total_answers': tot,
            'correct_answers': corr
        }
        
    radar_labels = []
    radar_data = []
    for d_id, stats in descriptor_stats.items():
        radar_labels.append(stats['code'])
        perc = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
        radar_data.append(round(perc, 1))

    # Get identifying info
    selectors = get_exam_selectors()
    current_display = next((s['display'] for s in selectors if s['id'] == exam_id), f"{exam.title} ({exam.academic_year})")

    # 4. Rankings (Global/Scoped Top and Bottom)
    rankings = get_rankings_data(
        exam_id, 
        regional_ids, 
        unit_ids, 
        class_ids, 
        school_year_ids, 
        races, 
        nationalities, 
        incomes,
        zones=zones,
        locations=locations,
        deficiency=deficiency,
        bolsa=bolsa,
        dietary=dietary,
        indigenous=indigenous,
        quilombola=quilombola,
        quilombola_community=quilombola_community
    )

    # 5. Desempenho por Componente (para provas de múltiplos componentes)
    components_performance = []
    if exam.evaluation and exam.evaluation.multiple_components:
        sub_map = {}
        for item in exam.items:
            if not item.question:
                continue
            sub = None
            for desc in item.question.descriptors:
                if desc.subject:
                    sub = desc.subject
                    break
            
            if not sub:
                continue
                
            if sub.id not in sub_map:
                sub_map[sub.id] = {'name': sub.name, 'correct': 0, 'total': 0}
                
            for res in realized_results:
                ans = res['answers_dict'].get(str(item.question.id))
                
                sub_map[sub.id]['total'] += 1
                if ans == item.question.correct_alternative:
                    sub_map[sub.id]['correct'] += 1
                    
        for sub_id, stats in sub_map.items():
            tot = stats['total']
            corr = stats['correct']
            perc = round((corr / tot * 100), 2) if tot > 0 else 0.0
            components_performance.append({
                'id': sub_id,
                'name': stats['name'],
                'correct_perc': perc,
                'correct_count': corr,
                'total_count': tot
            })
        components_performance.sort(key=lambda x: x['name'])

    # 6. Motivos de Ausência
    absence_reasons_data = get_absence_reasons_data(
        exam_id,
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

    # 7. Map Data
    map_data = {
        'schools': [],
        'missing_coords_count': 0
    }
    
    # Base query for target schools based on exam scope
    target_schools_query = TeachingUnit.query.filter_by(type='Escola', tenant_id=exam.tenant_id)
    
    # Restringe às escolas que efetivamente possuem alunos ativos no ano/série da prova
    target_schools_query = target_schools_query.join(Class, Class.teaching_unit_id == TeachingUnit.id)
    target_schools_query = target_schools_query.join(Enrollment, Enrollment.class_id == Class.id).filter(Enrollment.active == True)
    
    if exam.school_year_id:
        target_schools_query = target_schools_query.filter(Class.school_year_id == exam.school_year_id)
    
    # First, apply exam scope
    if exam.classes.count() > 0:
        target_schools_query = target_schools_query.filter(Class.id.in_([c.id for c in exam.classes]))
    elif exam.teaching_unit_id:
        target_schools_query = target_schools_query.filter(TeachingUnit.id == exam.teaching_unit_id)
    elif exam.regional_id:
        target_schools_query = target_schools_query.filter(TeachingUnit.parent_id == exam.regional_id)
        
    # Then, apply user filters
    if unit_ids:
        target_schools_query = target_schools_query.filter(TeachingUnit.id.in_(unit_ids))
    elif regional_ids:
        target_schools_query = target_schools_query.filter(TeachingUnit.parent_id.in_(regional_ids))
        
    target_schools = target_schools_query.distinct().all()
    
    # Get scores from ranking to color code
    school_scores = {s['name']: s['score'] for s in rankings['schools']}
    
    school_levels = {}
    for student in rankings['students']:
        school_name = student['sub']
        score = student['score']
        
        if score < 25: level = 1
        elif score < 50: level = 2
        elif score < 75: level = 3
        else: level = 4
        
        if school_name not in school_levels:
            school_levels[school_name] = set()
        school_levels[school_name].add(level)
        
    school_classes = {}
    for cls in rankings['classes']:
        school_id = cls['school_id']
        if school_id not in school_classes:
            school_classes[school_id] = []
        school_classes[school_id].append({
            'name': cls['name'],
            'score': cls['score']
        })
    
    for sch in target_schools:
        if sch.latitude and sch.longitude:
            try:
                lat = float(sch.latitude.replace(',', '.'))
                lng = float(sch.longitude.replace(',', '.'))
                map_data['schools'].append({
                    'id': sch.id,
                    'name': sch.name,
                    'lat': lat,
                    'lng': lng,
                    'score': school_scores.get(sch.name, None),
                    'levels': list(school_levels.get(sch.name, set())),
                    'classes': school_classes.get(sch.id, [])
                })
            except ValueError:
                map_data['missing_coords_count'] += 1
        else:
            map_data['missing_coords_count'] += 1

    return {
        'kpis': {
            'avg_score': round(avg_score, 1),
            'participation': round(participation_rate, 1),
            'alerts': alerts,
            'total_participation': len(realized_results),
            'engagement': {
                'total': total_students_scoped,
                'realized': len(realized_results),
                'absent': absent_count,
                'missing': missing_count,
                'fully_responded': fully_responded,
                'partially_responded': partially_responded,
                'not_responded_present': not_responded_present
            }
        },
        'ranking': ranking,
        'items': item_analysis,
        'components_performance': components_performance,
        'absence_reasons': absence_reasons_data,
        'proficiency': prof_levels,
        'difficulty_performance': difficulty_performance,
        'radar_labels': radar_labels,
        'radar_data': radar_data,
        'rankings': rankings,
        'map_data': map_data,
        'current_exam_title': current_display
    }

def get_rankings_data(exam_id, regional_ids=None, unit_ids=None, class_ids=None, school_year_ids=None, races=None, nationalities=None, incomes=None, zones=None, locations=None, deficiency=None, bolsa=None, dietary=None, indigenous=None, quilombola=None, quilombola_community=None):
    """
    Returns top and bottom performers for various categories.
    """
    from flask_login import current_user
    from app.utils.tenancy import filter_by_tenant
    
    exam_query = Exam.query.filter_by(id=exam_id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first()
    if not exam:
        return {}

    # Helper to get filtered result IDs
    base_query = db.session.query(StudentResult.id).filter(StudentResult.exam_id == exam_id)
    base_query = base_query.join(Student, StudentResult.student_id == Student.id)\
                           .join(Enrollment, Student.id == Enrollment.student_id)\
                           .filter(Enrollment.active == True)\
                           .join(Class, Enrollment.class_id == Class.id)\
                           .join(TeachingUnit, Class.teaching_unit_id == TeachingUnit.id)
                           
    if current_user.is_authenticated and get_tenant_id():
        base_query = base_query.filter(Student.tenant_id == get_tenant_id())

    if class_ids:
        base_query = base_query.filter(Class.id.in_(class_ids))
    if unit_ids:
        base_query = base_query.filter(TeachingUnit.id.in_(unit_ids))
    if school_year_ids:
        base_query = base_query.filter(Class.school_year_id.in_(school_year_ids))
    if regional_ids:
        base_query = base_query.filter(TeachingUnit.parent_id.in_(regional_ids))

    # RESTRIÇÃO: Garantir que todos os dados sejam do ano escolar da prova
    if exam.school_year_id:
        base_query = base_query.filter(Class.school_year_id == exam.school_year_id)

    if races: base_query = base_query.filter(Student.race.in_(races))
    if nationalities: base_query = base_query.filter(Student.nationality.in_(nationalities))
    if incomes: base_query = base_query.filter(Student.family_income.in_(incomes))

    # Novos Filtros Avançados
    if zones and len(zones) > 0:
        base_query = base_query.filter(Student.residential_zone.in_(zones))
    if locations and len(locations) > 0:
        base_query = base_query.filter(Student.differentiated_location.in_(locations))
    if deficiency and len(deficiency) > 0:
        if 'Sim' in deficiency and 'Não' not in deficiency:
            base_query = base_query.filter(Student.special_needs == True)
        elif 'Não' in deficiency and 'Sim' not in deficiency:
            base_query = base_query.filter(Student.special_needs == False)
    if bolsa and len(bolsa) > 0:
        if 'Sim' in bolsa and 'Não' not in bolsa:
            base_query = base_query.filter(Student.bolsa_familia == True)
        elif 'Não' in bolsa and 'Sim' not in bolsa:
            base_query = base_query.filter(Student.bolsa_familia == False)
    if dietary and len(dietary) > 0:
        if 'Sim' in dietary and 'Não' not in dietary:
            base_query = base_query.filter(Student.dietary_restrictions.any())
        elif 'Não' in dietary and 'Sim' not in dietary:
            base_query = base_query.filter(~Student.dietary_restrictions.any())

        # Schools Ranking
    schools_ranking = base_query.with_entities(TeachingUnit.name, db.func.avg(StudentResult.score_percentage).label('score'), TeachingUnit.municipio)\
        .group_by(TeachingUnit.name, TeachingUnit.municipio).order_by(db.desc('score')).all()

    # Classes Ranking
    classes_ranking = base_query.with_entities(
        Class.id, 
        Class.name, 
        TeachingUnit.name, 
        db.func.avg(StudentResult.score_percentage).label('score'),
        db.func.count(StudentResult.id).label('student_count'),
        db.func.sum(StudentResult.score_percentage).label('total_score'),
        TeachingUnit.id
    ).group_by(Class.id, TeachingUnit.name, TeachingUnit.id).order_by(db.desc('score')).all()

    # Students Ranking
    students_ranking = base_query.with_entities(Student.name, StudentResult.score_percentage.label('score'), TeachingUnit.name, Class.name)\
        .order_by(db.desc('score')).limit(50).all()

    # Professors Ranking
    class_ids = [r[0] for r in classes_ranking] if classes_ranking else []
    
    prof_assignments = []
    if class_ids:
        # Fetch chunked to avoid 999 limit if class_ids > 999 (though unlikely for one exam)
        chunk_size = 900
        for i in range(0, len(class_ids), chunk_size):
            chunk = class_ids[i:i+chunk_size]
            q = db.session.query(TeachingAssignment.class_id, Professor.name)\
                .join(Professor, Professor.id == TeachingAssignment.professor_id)\
                .filter(TeachingAssignment.class_id.in_(chunk))
            if exam.subject_id:
                q = q.filter(TeachingAssignment.subject_id == exam.subject_id)
            prof_assignments.extend(q.all())
            
    prof_scores = {}
    for class_id, prof_name in prof_assignments:
        if prof_name not in prof_scores:
            prof_scores[prof_name] = {'total': 0, 'count': 0}
            
        class_data = next((r for r in classes_ranking if r[0] == class_id), None)
        if class_data:
            prof_scores[prof_name]['total'] += (class_data[5] or 0)
            prof_scores[prof_name]['count'] += (class_data[4] or 0)
            
    professors_ranking = []
    for prof_name, stats in prof_scores.items():
        if stats['count'] > 0:
            avg_score = stats['total'] / stats['count']
            professors_ranking.append({'name': prof_name, 'score': round(avg_score, 2)})
            
    professors_ranking.sort(key=lambda x: x['score'], reverse=True)

    return {
        'schools': [{'name': r[0], 'score': round(r[1] or 0, 2), 'municipio': r[2]} for r in schools_ranking],
        'classes': [{'class_id': r[0], 'name': r[1], 'sub': r[2], 'score': round(r[3] or 0, 2), 'school_id': r[6]} for r in classes_ranking],
        'students': [{'name': r[0], 'sub': r[2], 'score': round(r[1] or 0, 2), 'class_name': r[3]} for r in students_ranking],
        'professors': professors_ranking
    }

def _get_total_students_count(exam, regional_ids=None, unit_ids=None, class_ids=None, school_year_ids=None, races=None, nationalities=None, incomes=None, zones=None, locations=None, deficiency=None, bolsa=None, dietary=None, indigenous=None, quilombola=None, quilombola_community=None):
    """Calculates potential participants based on exam scope and filters"""
    from flask_login import current_user
    from app.utils.tenancy import filter_by_tenant
    query = Student.query
    query = filter_by_tenant(query, Student)
    query = query.join(Enrollment).filter(Enrollment.active == True)
    
    # If any filters are applied, use them cumulatively. 
    # Otherwise, fallback to the exam's original scope.
    if class_ids or unit_ids or school_year_ids or regional_ids:
        if unit_ids or school_year_ids or regional_ids:
            query = query.join(Class, Enrollment.class_id == Class.id)
        if regional_ids:
            query = query.join(TeachingUnit, Class.teaching_unit_id == TeachingUnit.id)

        if class_ids:
            query = query.filter(Enrollment.class_id.in_(class_ids))
        if unit_ids:
            query = query.filter(Class.teaching_unit_id.in_(unit_ids))
        if school_year_ids:
            query = query.filter(Class.school_year_id.in_(school_year_ids))
        if regional_ids:
            query = query.filter(TeachingUnit.parent_id.in_(regional_ids))
            
        # RESTRIÇÃO: Garantir que todos os dados sejam do ano escolar da prova
        if exam.school_year_id:
            query = query.filter(Class.school_year_id == exam.school_year_id)
    else:
        # Global scope of the exam
        if exam.classes.count() > 0:
            query = query.filter(Enrollment.class_id.in_([c.id for c in exam.classes]))
        elif exam.teaching_unit_id:
            query = query.join(Class).filter(Class.teaching_unit_id == exam.teaching_unit_id)
        elif exam.regional_id:
            query = query.join(Class).join(TeachingUnit).filter(TeachingUnit.parent_id == exam.regional_id)
            
        # Mesmo no escopo global, respeitar o ano escolar se definido na prova
        if exam.school_year_id:
            # Join Class se ainda não foi joinado
            # Foi joinado nas condições 'elif exam.teaching_unit_id' e 'elif exam.regional_id'
            if exam.classes.count() > 0 or (not exam.teaching_unit_id and not exam.regional_id):
                query = query.join(Class, Enrollment.class_id == Class.id)
            query = query.filter(Class.school_year_id == exam.school_year_id)
            
    # NEW: Apply Exam Filters for Students
    if exam.target_nationality == 'Brasileiro':
        query = query.filter(Student.nationality == 'Brasileiro')
        
    if exam.target_special_needs == 'Somente Deficientes':
        query = query.filter(Student.special_needs == True)

    # Novos Filtros Avançados & Demográficos para Participação Consistente
    if races and len(races) > 0:
        query = query.filter(Student.race.in_(races))
    if nationalities and len(nationalities) > 0:
        query = query.filter(Student.nationality.in_(nationalities))
    if incomes and len(incomes) > 0:
        query = query.filter(Student.family_income.in_(incomes))

    if zones and len(zones) > 0:
        query = query.filter(Student.residential_zone.in_(zones))
    if locations and len(locations) > 0:
        query = query.filter(Student.differentiated_location.in_(locations))
    if deficiency and len(deficiency) > 0:
        if 'Sim' in deficiency and 'Não' not in deficiency:
            query = query.filter(Student.special_needs == True)
        elif 'Não' in deficiency and 'Sim' not in deficiency:
            query = query.filter(Student.special_needs == False)
    if bolsa and len(bolsa) > 0:
        if 'Sim' in bolsa and 'Não' not in bolsa:
            query = query.filter(Student.bolsa_familia == True)
        elif 'Não' in bolsa and 'Sim' not in bolsa:
            query = query.filter(Student.bolsa_familia == False)
    if dietary and len(dietary) > 0:
        if 'Sim' in dietary and 'Não' not in dietary:
            query = query.filter(Student.dietary_restrictions.any())
        elif 'Não' in dietary and 'Sim' not in dietary:
            query = query.filter(~Student.dietary_restrictions.any())
    if indigenous and len(indigenous) > 0:
        query = query.filter(Student.indigenous_people_id.in_(indigenous))
    if quilombola and len(quilombola) > 0:
        if 'Sim' in quilombola and 'Não' not in quilombola and 'Nǐo' not in quilombola and 'Nào' not in quilombola:
            query = query.filter(Student.is_quilombola == True)
        elif ('Não' in quilombola or 'Nǐo' in quilombola or 'Nào' in quilombola) and 'Sim' not in quilombola:
            query = query.filter(Student.is_quilombola == False)
    if quilombola_community and len(quilombola_community) > 0:
        query = query.filter(Student.quilombola_community_id.in_(quilombola_community))

            
    return query.count()

def _get_group_performance(exam_id, group_by, regional_ids=None, unit_ids=None, school_year_ids=None):
    """Helper to group averages by Regional, School, or Class"""
    from flask_login import current_user
    from app.utils.tenancy import filter_by_tenant
    if group_by == 'regional':
        # Buscar todas as regionais cadastradas
        reg_query = TeachingUnit.query.filter_by(type='Regional')
        reg_query = filter_by_tenant(reg_query, TeachingUnit)
        regionals = reg_query.all()
        
        # Buscar médias agrupadas por regional
        ParentUnit = sa.orm.aliased(TeachingUnit)
        avg_query = db.session.query(
            ParentUnit.id.label('reg_id'),
            func.avg(StudentResult.score_percentage).label('avg_score')
        ).select_from(StudentResult)\
         .join(Student, StudentResult.student_id == Student.id)\
         .join(Enrollment, Student.id == Enrollment.student_id)\
         .filter(Enrollment.active == True)\
         .join(Class, Enrollment.class_id == Class.id)\
         .join(TeachingUnit, Class.teaching_unit_id == TeachingUnit.id)\
         .join(ParentUnit, TeachingUnit.parent_id == ParentUnit.id)\
         .filter(StudentResult.exam_id == exam_id)\
         .filter(ParentUnit.type == 'Regional')
         
        if current_user.is_authenticated and get_tenant_id():
            avg_query = avg_query.filter(Student.tenant_id == get_tenant_id())
            
        avg_query = avg_query.group_by(ParentUnit.id)
         
        averages = {row.reg_id: row.avg_score for row in avg_query.all()}
        
        results = []
        for reg in regionals:
            avg = averages.get(reg.id)
            results.append({'id': reg.id, 'name': reg.name, 'score': round(avg, 2) if avg else 0})
        return sorted(results, key=lambda x: x['score'], reverse=True)

    elif group_by == 'unit':
        # Buscar escolas
        school_query = TeachingUnit.query.filter_by(type='Escola')
        school_query = filter_by_tenant(school_query, TeachingUnit)
        if regional_ids:
            school_query = school_query.filter(TeachingUnit.parent_id.in_(regional_ids))
        schools = school_query.all()
        
        # Buscar médias agrupadas por escola
        avg_query = db.session.query(
            Class.teaching_unit_id.label('unit_id'),
            func.avg(StudentResult.score_percentage).label('avg_score')
        ).select_from(StudentResult)\
         .join(Student, StudentResult.student_id == Student.id)\
         .join(Enrollment, Student.id == Enrollment.student_id)\
         .filter(Enrollment.active == True)\
         .join(Class, Enrollment.class_id == Class.id)\
         .filter(StudentResult.exam_id == exam_id)
         
        if regional_ids:
            avg_query = avg_query.join(TeachingUnit, Class.teaching_unit_id == TeachingUnit.id)\
                                 .filter(TeachingUnit.parent_id.in_(regional_ids))
                                 
        if current_user.is_authenticated and get_tenant_id():
            avg_query = avg_query.filter(Student.tenant_id == get_tenant_id())
            
        avg_query = avg_query.group_by(Class.teaching_unit_id)
        averages = {row.unit_id: row.avg_score for row in avg_query.all()}
        
        results = []
        for sch in schools:
            avg = averages.get(sch.id)
            results.append({'id': sch.id, 'name': sch.name, 'score': round(avg, 2) if avg else 0})
        return sorted(results, key=lambda x: x['score'], reverse=True)

    elif group_by == 'school_year':
        # Buscar anos escolares distinct no escopo
        year_query = db.session.query(SchoolYear.id, SchoolYear.name).join(Class)
        if unit_ids:
            year_query = year_query.filter(Class.teaching_unit_id.in_(unit_ids))
        if current_user.is_authenticated and get_tenant_id():
            year_query = year_query.filter(Class.tenant_id == get_tenant_id())
        years = year_query.distinct().all()
        
        # Buscar médias agrupadas por ano escolar
        avg_query = db.session.query(
            Class.school_year_id.label('school_year_id'),
            func.avg(StudentResult.score_percentage).label('avg_score')
        ).select_from(StudentResult)\
         .join(Student, StudentResult.student_id == Student.id)\
         .join(Enrollment, Student.id == Enrollment.student_id)\
         .filter(Enrollment.active == True)\
         .join(Class, Enrollment.class_id == Class.id)\
         .filter(StudentResult.exam_id == exam_id)
         
        if unit_ids:
            avg_query = avg_query.filter(Class.teaching_unit_id.in_(unit_ids))
            
        if current_user.is_authenticated and get_tenant_id():
            avg_query = avg_query.filter(Student.tenant_id == get_tenant_id())
            
        avg_query = avg_query.group_by(Class.school_year_id)
        averages = {row.school_year_id: row.avg_score for row in avg_query.all()}
        
        results = []
        for sy_id, sy_name in years:
            avg = averages.get(sy_id)
            results.append({'id': sy_id, 'name': sy_name, 'score': round(avg, 2) if avg else 0})
        return sorted(results, key=lambda x: x['score'], reverse=True)

    elif group_by == 'class':
        # Buscar turmas
        class_query = Class.query
        class_query = filter_by_tenant(class_query, Class)
        if unit_ids:
            class_query = class_query.filter(Class.teaching_unit_id.in_(unit_ids))
        if school_year_ids:
            class_query = class_query.filter(Class.school_year_id.in_(school_year_ids))
        classes = class_query.all()
        
        # Buscar médias agrupadas por turma
        avg_query = db.session.query(
            Enrollment.class_id.label('class_id'),
            func.avg(StudentResult.score_percentage).label('avg_score')
        ).select_from(StudentResult)\
         .join(Student, StudentResult.student_id == Student.id)\
         .join(Enrollment, Student.id == Enrollment.student_id)\
         .filter(Enrollment.active == True)\
         .filter(StudentResult.exam_id == exam_id)
         
        if unit_ids or school_year_ids:
            avg_query = avg_query.join(Class, Enrollment.class_id == Class.id)
            if unit_ids:
                avg_query = avg_query.filter(Class.teaching_unit_id.in_(unit_ids))
            if school_year_ids:
                avg_query = avg_query.filter(Class.school_year_id.in_(school_year_ids))
                
        if current_user.is_authenticated and get_tenant_id():
            avg_query = avg_query.filter(Student.tenant_id == get_tenant_id())
            
        avg_query = avg_query.group_by(Enrollment.class_id)
        averages = {row.class_id: row.avg_score for row in avg_query.all()}
        
        results = []
        for cls in classes:
            avg = averages.get(cls.id)
            results.append({'id': cls.id, 'name': cls.name, 'score': round(avg, 2) if avg else 0})
        return sorted(results, key=lambda x: x['score'], reverse=True)
    
    return []


def get_absence_reasons_data(exam_id, regional_ids=None, unit_ids=None, class_ids=None,
                             school_year_ids=None, races=None, nationalities=None,
                             incomes=None, zones=None, locations=None,
                             deficiency=None, bolsa=None, dietary=None, indigenous=None, quilombola=None, quilombola_community=None):
    """
    Agrega contagens e percentuais de motivos de ausência respeitando os filtros
    hierárquicos do dashboard.
    Retorna lista: [{id, name, count, perc}] ordenada por count desc.
    """
    from flask_login import current_user
    from app.utils.tenancy import filter_by_tenant

    exam_query = Exam.query.filter_by(id=exam_id)
    exam_query = filter_by_tenant(exam_query, Exam)
    exam = exam_query.first()
    if not exam:
        return []

    # Query base: apenas resultados COM motivo de ausência
    query = db.session.query(
        AbsenceReason.id.label('reason_id'),
        AbsenceReason.name.label('reason_name'),
        func.count(StudentResult.id).label('cnt')
    ).select_from(StudentResult)\
     .join(AbsenceReason, StudentResult.absence_reason_id == AbsenceReason.id)\
     .join(Student, StudentResult.student_id == Student.id)\
     .join(Enrollment, Student.id == Enrollment.student_id)\
     .filter(Enrollment.active == True)\
     .join(Class, Enrollment.class_id == Class.id)\
     .join(TeachingUnit, Class.teaching_unit_id == TeachingUnit.id)\
     .filter(StudentResult.exam_id == exam_id)

    if current_user.is_authenticated and get_tenant_id():
        query = query.filter(Student.tenant_id == get_tenant_id())

    # Filtros hierárquicos
    if class_ids:
        query = query.filter(Class.id.in_(class_ids))
    if unit_ids:
        query = query.filter(TeachingUnit.id.in_(unit_ids))
    if school_year_ids:
        query = query.filter(Class.school_year_id.in_(school_year_ids))
    if regional_ids:
        query = query.filter(TeachingUnit.parent_id.in_(regional_ids))
    if exam.school_year_id:
        query = query.filter(Class.school_year_id == exam.school_year_id)

    # Filtros demográficos
    if races:        query = query.filter(Student.race.in_(races))
    if nationalities: query = query.filter(Student.nationality.in_(nationalities))
    if incomes:      query = query.filter(Student.family_income.in_(incomes))
    if zones:        query = query.filter(Student.residential_zone.in_(zones))
    if locations:    query = query.filter(Student.differentiated_location.in_(locations))
    if deficiency:
        if 'Sim' in deficiency and 'Não' not in deficiency:
            query = query.filter(Student.special_needs == True)
        elif 'Não' in deficiency and 'Sim' not in deficiency:
            query = query.filter(Student.special_needs == False)
    if bolsa:
        if 'Sim' in bolsa and 'Não' not in bolsa:
            query = query.filter(Student.bolsa_familia == True)
        elif 'Não' in bolsa and 'Sim' not in bolsa:
            query = query.filter(Student.bolsa_familia == False)
    if dietary:
        if 'Sim' in dietary and 'Não' not in dietary:
            query = query.filter(Student.dietary_restrictions.any())
        elif 'Não' in dietary and 'Sim' not in dietary:
            query = query.filter(~Student.dietary_restrictions.any())
    if indigenous and len(indigenous) > 0:
        query = query.filter(Student.indigenous_people_id.in_(indigenous))
    if quilombola and len(quilombola) > 0:
        if 'Sim' in quilombola and 'Não' not in quilombola and 'Não' not in quilombola and 'No' not in quilombola:
            query = query.filter(Student.is_quilombola == True)
        elif ('Não' in quilombola or 'Não' in quilombola or 'No' in quilombola) and 'Sim' not in quilombola:
            query = query.filter(Student.is_quilombola == False)
    if quilombola_community and len(quilombola_community) > 0:
        query = query.filter(Student.quilombola_community_id.in_(quilombola_community))

    query = query.group_by(AbsenceReason.id, AbsenceReason.name)
    rows = query.all()

    if not rows:
        return []

    total_absent = sum(r.cnt for r in rows)
    result = []
    for r in rows:
        perc = round((r.cnt / total_absent * 100), 1) if total_absent > 0 else 0.0
        result.append({'id': r.reason_id, 'name': r.reason_name, 'count': r.cnt, 'perc': perc})

    return sorted(result, key=lambda x: x['count'], reverse=True)

def get_exam_stats(exam_id):
    """Returns average success, failure and absent percentages for an exam"""
    from flask_login import current_user
    if current_user.is_authenticated and get_tenant_id():
        exists = Exam.query.filter_by(id=exam_id, tenant_id=get_tenant_id()).first()
        if not exists:
            return {'success': 0.0, 'failure': 0.0, 'absent': 0.0}
            
    total_count = StudentResult.query.filter_by(exam_id=exam_id).count()
    if total_count == 0:
        return {'success': 0.0, 'failure': 0.0, 'absent': 0.0}
        
    absent_count = StudentResult.query.filter_by(exam_id=exam_id).filter(StudentResult.absence_reason_id.isnot(None)).count()
    absent_perc = round((absent_count / total_count * 100), 2)
    
    # Media de acertos apenas para os alunos que realizaram a prova (presenca ativa)
    avg = db.session.query(func.avg(StudentResult.score_percentage))\
        .filter(StudentResult.exam_id == exam_id, StudentResult.absence_reason_id.is_(None)).scalar()
        
    if avg is None:
        success_perc = 0.0
    else:
        success_perc = round(avg, 2)
        
    failure_perc = round(100.0 - success_perc, 2)
    
    return {'success': success_perc, 'failure': failure_perc, 'absent': absent_perc}
