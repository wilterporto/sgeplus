import json
import random
from app import create_app, db
from app.models import Exam, Class, Enrollment, Student, StudentResult, AbsenceReason

app = create_app()

def generate_answers(exam, mostly_correct=True):
    answers = {}
    correct_count = 0
    total = exam.items.count()
    if total == 0:
        return "{}", 0.0
        
    for item in exam.items:
        q = item.question
        correct_alt = q.correct_alternative
        alts = list(q.get_alternatives().keys())
        
        # Decide if student gets this question right
        if mostly_correct:
            is_correct = random.random() < 0.85 # 85% chance to get each right
        else:
            is_correct = random.random() < 0.25 # 25% chance to get each right
            
        if is_correct and correct_alt in alts:
            chosen = correct_alt
            correct_count += 1
        else:
            # pick random wrong answer
            wrong_alts = [a for a in alts if a != correct_alt]
            chosen = random.choice(wrong_alts) if wrong_alts else random.choice(alts)
            
        answers[str(q.id)] = chosen
        
    score_percentage = (correct_count / total) * 100.0 if total > 0 else 0.0
    return json.dumps(answers), score_percentage

with app.app_context():
    exam = Exam.query.get(5) # SAETO 2026 for 5th Grade
    if not exam:
        print("Exam not found!")
        exit(1)
        
    # Get all students enrolled in the classes of this exam
    class_ids = [c.id for c in exam.classes]
    
    # If exam is global/regional, it might not have specific classes linked.
    # In SGE Plus, Exams have `classes` if they are linked.
    if not class_ids:
        # If it's a global exam for 5th grade, get all 5th grade classes
        classes = Class.query.filter_by(school_year_id=exam.school_year_id).all()
        class_ids = [c.id for c in classes]
        
    enrollments = Enrollment.query.filter(Enrollment.class_id.in_(class_ids), Enrollment.active == True).all()
    student_ids = list(set([e.student_id for e in enrollments]))
    
    print(f"Found {len(student_ids)} students for exam {exam.title}")
    
    # Clean existing results
    StudentResult.query.filter_by(exam_id=exam.id).delete()
    db.session.commit()
    
    # Shuffle students
    random.shuffle(student_ids)
    
    total_students = len(student_ids)
    c_77 = int(total_students * 0.77)
    c_17 = int(total_students * 0.17)
    c_3_absent = int(total_students * 0.03)
    c_3_not_started = total_students - c_77 - c_17 - c_3_absent
    
    print(f"Distribution: 77%={c_77}, 17%={c_17}, 3% (Absent)={c_3_absent}, 3% (Not Started)={c_3_not_started}")
    
    absence_reasons = AbsenceReason.query.all()
    default_absence_id = absence_reasons[0].id if absence_reasons else None
    
    results = []
    
    # 77% mostly correct
    for sid in student_ids[:c_77]:
        answers, score = generate_answers(exam, mostly_correct=True)
        results.append(StudentResult(
            exam_id=exam.id,
            student_id=sid,
            answers=answers,
            score_percentage=score
        ))
        
    # 17% mostly wrong
    start = c_77
    end = c_77 + c_17
    for sid in student_ids[start:end]:
        answers, score = generate_answers(exam, mostly_correct=False)
        results.append(StudentResult(
            exam_id=exam.id,
            student_id=sid,
            answers=answers,
            score_percentage=score
        ))
        
    # 3% absent
    start = end
    end = start + c_3_absent
    for sid in student_ids[start:end]:
        reason_id = random.choice(absence_reasons).id if absence_reasons else default_absence_id
        results.append(StudentResult(
            exam_id=exam.id,
            student_id=sid,
            answers="{}",
            score_percentage=0.0,
            absence_reason_id=reason_id
        ))
        
    # the rest (c_3_not_started) gets no StudentResult
    
    db.session.bulk_save_objects(results)
    db.session.commit()
    print("Results simulated successfully!")
