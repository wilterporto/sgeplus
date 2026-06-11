import sys
import os
import random
import json

sys.path.append(os.path.abspath(os.path.join('.', '')))

from app import create_app, db
from app.models import Exam, StudentResult, Enrollment, Class

app = create_app()

def generate_answers():
    with app.app_context():
        tenant_id = 7
        exam_ids = [6, 7] # 9º ANO and 3ª SÉRIE
        
        for exam_id in exam_ids:
            exam = Exam.query.get(exam_id)
            if not exam:
                print(f"Exam {exam_id} not found.")
                continue
                
            print(f"Gerando respostas para: {exam.title} ({exam.school_year.name if exam.school_year else ''})")
            
            # Clear existing results
            StudentResult.query.filter_by(exam_id=exam.id).delete()
            db.session.commit()
            
            # Find students. If exam is linked to classes, use them. Otherwise find all classes of that year
            classes = exam.classes.all()
            if not classes:
                classes = Class.query.filter_by(school_year_id=exam.school_year_id, tenant_id=tenant_id).all()
            
            enrollments = []
            for c in classes:
                enrollments.extend(c.enrollments.filter_by(active=True).all())
                
            print(f"Total de alunos encontrados: {len(enrollments)}")
            
            items = exam.items.all()
            if not items:
                print("Prova nao contem questoes!")
                continue
            
            results_batch = []
            inserted = 0
            for enr in enrollments:
                r = random.uniform(0, 100)
                
                answers_dict = {}
                is_absent = False
                absence_reason_id = None
                
                if r < 77:
                    # 77%: Acertar a maioria
                    for item in items:
                        if random.uniform(0, 100) < 85: # 85% chance of being correct
                            answers_dict[str(item.question.id)] = item.question.correct_alternative
                        else:
                            alts = list(item.question.get_alternatives().keys())
                            if item.question.correct_alternative in alts:
                                alts.remove(item.question.correct_alternative)
                            answers_dict[str(item.question.id)] = random.choice(alts) if alts else 'A'
                elif r < 94:
                    # 17%: Errar a maioria
                    for item in items:
                        if random.uniform(0, 100) < 20: # 20% chance of being correct
                            answers_dict[str(item.question.id)] = item.question.correct_alternative
                        else:
                            alts = list(item.question.get_alternatives().keys())
                            if item.question.correct_alternative in alts:
                                alts.remove(item.question.correct_alternative)
                            answers_dict[str(item.question.id)] = random.choice(alts) if alts else 'A'
                elif r < 97:
                    # 3%: Provas nao iniciadas (em branco)
                    pass
                else:
                    # 3%: Ausencias
                    is_absent = True
                    abs_r = random.uniform(0, 100)
                    if abs_r < 60:
                        absence_reason_id = 4 # Atestado medico
                    elif abs_r < 90:
                        absence_reason_id = 8 # Falta de transporte
                    else:
                        absence_reason_id = 11 # Motivo de viagem
                        
                # Calculate Score Percentage
                score_percentage = 0.0
                if not absence_reason_id and len(items) > 0 and answers_dict:
                    correct_count = 0
                    for item in items:
                        qid_str = str(item.question.id)
                        if answers_dict.get(qid_str) == item.question.correct_alternative:
                            correct_count += 1
                    score_percentage = (correct_count / len(items)) * 100

                res = StudentResult(
                    exam_id=exam.id,
                    student_id=enr.student_id,
                    absence_reason_id=absence_reason_id,
                    answers=json.dumps(answers_dict) if not absence_reason_id else None,
                    score_percentage=score_percentage
                )
                results_batch.append(res)
                inserted += 1
                
            db.session.bulk_save_objects(results_batch)
            db.session.commit()
            print(f"{inserted} resultados gerados com sucesso para o exame {exam.id}.\n")

generate_answers()
