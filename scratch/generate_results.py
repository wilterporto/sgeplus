import json
import random
import time
from app import create_app
from app.models import db, StudentResult, Exam, ExamItem, Enrollment, Class, SchoolYear, TeachingUnit, AbsenceReason

def generate_random_responses():
    app = create_app()
    with app.app_context():
        tenant_id = 1
        exam_id = 4
        
        # 1. Obter a Prova e os Itens (Questões)
        exam = db.session.query(Exam).get(exam_id)
        if not exam:
            print("Erro: Prova ID 3 não encontrada.")
            return
            
        items = exam.items.all()
        if not items:
            print("Erro: Nenhuma questão vinculada a esta prova.")
            return
            
        print(f"Prova: {exam.title} - {len(items)} questões.")
        
        # 2. Obter matrículas do 5º Ano do tenant 1
        enrollments = db.session.query(Enrollment).join(Class).join(TeachingUnit).join(SchoolYear).filter(
            TeachingUnit.tenant_id == tenant_id,
            SchoolYear.name.ilike('%5%')
        ).all()
        
        print(f"Total de Alunos (Matrículas) no 5º Ano: {len(enrollments)}")
        
        # Obter motivos de ausência
        absence_reasons = db.session.query(AbsenceReason).all()
        absence_reason_ids = [a.id for a in absence_reasons]
        
        if not absence_reason_ids:
            # Caso não tenha motivos cadastrados, criamos um dummy
            print("Nenhum motivo de ausência encontrado, pulando teste de ausência ou usando fallback...")
            absence_reason_ids = [None]
            
        # Remover resultados antigos desta prova e tenant para evitar duplicação (opcional, faremos apenas para os alunos que gerarmos)
        student_ids = [e.student_id for e in enrollments]
        deleted = db.session.query(StudentResult).filter(
            StudentResult.exam_id == exam_id,
            StudentResult.student_id.in_(student_ids)
        ).delete(synchronize_session=False)
        db.session.commit()
        print(f"Apagados {deleted} resultados anteriores.")
        
        # 3. Gerar Respostas
        results_to_insert = []
        
        absent_count = 0
        blank_count = 0
        perfect_count = 0
        normal_count = 0
        
        for e in enrollments:
            rand_val = random.random()
            
            if rand_val < 0.01:
                # 1% Ausente
                reason_id = random.choice(absence_reason_ids) if absence_reason_ids[0] is not None else None
                sr = StudentResult(
                    exam_id=exam_id,
                    student_id=e.student_id,
                    answers="{}",
                    score_percentage=0.0,
                    absence_reason_id=reason_id
                )
                absent_count += 1
                results_to_insert.append(sr)
                
            elif rand_val < 0.02:
                # 1% Presente, mas respostas em branco
                sr = StudentResult(
                    exam_id=exam_id,
                    student_id=e.student_id,
                    answers="{}",
                    score_percentage=0.0,
                    absence_reason_id=None
                )
                blank_count += 1
                results_to_insert.append(sr)
                
            else:
                # 98% Presente e respondeu
                # Destes 98%, vamos separar 10% para tirar nota máxima
                student_answers = {}
                correct_count = 0
                
                is_perfect = random.random() < 0.10 # 10% dos presentes
                
                if is_perfect:
                    perfect_count += 1
                    for item in items:
                        cor_alt = item.question.correct_alternative
                        student_answers[str(item.question.id)] = cor_alt
                        correct_count += 1
                else:
                    normal_count += 1
                    for item in items:
                        # 81.85% chance de acerto para compensar os 10% que tiram 100% e fechar a média em ~83.67% dos presentes
                        if random.random() < 0.8185:
                            cor_alt = item.question.correct_alternative
                            student_answers[str(item.question.id)] = cor_alt
                            correct_count += 1
                        else:
                            cor_alt = item.question.correct_alternative
                            # Escolhe um distrator que não seja o correto e nem vazio
                            try:
                                alts = json.loads(item.question.alternatives)
                                wrongs = [k for k in alts.keys() if k != cor_alt and k in ['A','B','C','D','E']]
                            except:
                                wrongs = ['A','B','C','D','E']
                                if cor_alt in wrongs:
                                    wrongs.remove(cor_alt)
                            
                            if wrongs:
                                student_answers[str(item.question.id)] = random.choice(wrongs)
                            else:
                                student_answers[str(item.question.id)] = None
                                
                score_percentage = (correct_count / len(items)) * 100 if items else 0.0
                
                sr = StudentResult(
                    exam_id=exam_id,
                    student_id=e.student_id,
                    answers=json.dumps(student_answers),
                    score_percentage=score_percentage,
                    absence_reason_id=None
                )
                results_to_insert.append(sr)
                
        # Insert all
        print(f"Inserindo {len(results_to_insert)} registros...")
        chunk_size = 500
        for i in range(0, len(results_to_insert), chunk_size):
            db.session.add_all(results_to_insert[i:i+chunk_size])
            db.session.commit()
            
        print("Finalizado!")
        print(f"Ausentes: {absent_count} | Em Branco: {blank_count} | 100% Acerto: {perfect_count} | Normal: {normal_count}")
        
if __name__ == '__main__':
    generate_random_responses()
