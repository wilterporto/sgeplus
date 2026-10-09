from app import create_app, db
from app.models import ExternalEvaluationResult, ExternalEvaluationStudent
import json

app = create_app()
with app.app_context():
    # Fetch first evaluation id and year
    res = db.session.query(ExternalEvaluationResult.evaluation_id, ExternalEvaluationStudent.ser_nome).join(ExternalEvaluationStudent, ExternalEvaluationResult.external_evaluation_student_id == ExternalEvaluationStudent.id).first()
    if not res:
        print("No results found")
        exit()
        
    evaluation_id, year = res
    print(f"Eval: {evaluation_id}, Year: {year}")
    
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
    print(f"Found {len(student_results)} student results.")
    
    # Check if tur_nome is being returned correctly
    if student_results:
        print("Sample row:", student_results[0])
