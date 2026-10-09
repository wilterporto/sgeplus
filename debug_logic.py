from app import create_app, db
from app.models import ExternalEvaluationResult, ExternalEvaluationStudent
import json

app = create_app()
with app.app_context():
    tenant_id = 1
    evaluation_id = 4
    year = '1º Ano EF'
    
    q = db.session.query(
        ExternalEvaluationResult.esc_inep,
        ExternalEvaluationResult.dis_nome,
        ExternalEvaluationStudent.tur_nome,
        ExternalEvaluationStudent.id.label('student_id'),
        db.func.sum(db.cast(ExternalEvaluationResult.atr_certo == '1', db.Integer)).label('correct_q'),
        db.func.count(ExternalEvaluationResult.id).label('total_q')
    ).join(
        ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id
    ).filter(
        ExternalEvaluationResult.evaluation_id == evaluation_id,
        ExternalEvaluationStudent.ser_nome == year,
        ExternalEvaluationResult.alt_finalizado == '1',
        ExternalEvaluationResult.nr_questao.isnot(None),
        ExternalEvaluationResult.nr_questao != ''
    ).group_by(
        ExternalEvaluationResult.esc_inep,
        ExternalEvaluationResult.dis_nome,
        ExternalEvaluationStudent.tur_nome,
        ExternalEvaluationStudent.id
    )
    
    student_results = q.all()
    print("Fetched", len(student_results), "rows")
    
    results_data = {}
    disciplines = []
    
    for esc_inep, dis_nome, tur_nome, std_id, correct_q, total_q in student_results:
        if not esc_inep: continue
        if not dis_nome: continue
        if not tur_nome: tur_nome = 'Turma Desconhecida'
        
        if dis_nome not in disciplines:
            disciplines.append(dis_nome)
            
        if esc_inep not in results_data:
            results_data[esc_inep] = {
                'inep': esc_inep,
                'name': 'Test School',
                'disciplines': {}
            }
            
        if dis_nome not in results_data[esc_inep]['disciplines']:
            results_data[esc_inep]['disciplines'][dis_nome] = {
                'total_correct': 0,
                'total_questions': 0,
                'students': [],
                'turmas': {}
            }
            
        stats = results_data[esc_inep]['disciplines'][dis_nome]
        stats['total_correct'] += int(correct_q or 0)
        stats['total_questions'] += int(total_q or 0)
        student_dict = {'correct': int(correct_q or 0), 'total': int(total_q or 0)}
        stats['students'].append(student_dict)
        
        if tur_nome not in stats['turmas']:
            stats['turmas'][tur_nome] = {
                'name': tur_nome,
                'total_correct': 0,
                'total_questions': 0,
                'students': []
            }
        t_stats = stats['turmas'][tur_nome]
        t_stats['total_correct'] += int(correct_q or 0)
        t_stats['total_questions'] += int(total_q or 0)
        t_stats['students'].append(student_dict)
        
    def process_stats(stats):
        if stats['total_questions'] > 0:
            avg_prof = (stats['total_correct'] / stats['total_questions']) * 100
        else:
            avg_prof = 0
            
        levels = {'Abaixo do básico': 0, 'Básico': 0, 'Proficiente': 0, 'Avançado': 0}
        total_students = len(stats['students'])
        
        for sinfo in stats['students']:
            if sinfo['total'] > 0:
                pct = (sinfo['correct'] / sinfo['total']) * 100
                if pct < 25: levels['Abaixo do básico'] += 1
                elif pct < 50: levels['Básico'] += 1
                elif pct < 75: levels['Proficiente'] += 1
                else: levels['Avançado'] += 1
                
        level_pcts = {k: (v / total_students * 100) if total_students > 0 else 0 for k, v in levels.items()}
        
        stats['avg_prof'] = avg_prof
        stats['levels'] = levels
        stats['level_pcts'] = level_pcts
        stats['total_students'] = total_students
        
        if 'students' in stats:
            del stats['students']
            
    for inep, sdata in results_data.items():
        for dis, stats in sdata['disciplines'].items():
            process_stats(stats)
            for t_name, t_stats in stats['turmas'].items():
                process_stats(t_stats)
                
    # Check the first school's first discipline
    if results_data:
        first_inep = list(results_data.keys())[0]
        first_dis = list(results_data[first_inep]['disciplines'].keys())[0]
        dis_stats = results_data[first_inep]['disciplines'][first_dis]
        print(f"School: {first_inep}, Discipline: {first_dis}")
        print("Turmas length:", len(dis_stats['turmas']))
        print("Turmas keys:", list(dis_stats['turmas'].keys()))
        first_turma = list(dis_stats['turmas'].keys())[0]
        print("First turma:", json.dumps(dis_stats['turmas'][first_turma], indent=2))
    else:
        print("No results")
