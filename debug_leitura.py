from app import create_app, db
from app.models import ExternalEvaluationResult

app = create_app()
with app.app_context():
    # check if 'Leitura' is in dis_nome
    results = db.session.query(
        ExternalEvaluationResult.dis_nome, 
        ExternalEvaluationResult.nr_questao, 
        ExternalEvaluationResult.atr_resposta
    ).filter(
        ExternalEvaluationResult.dis_nome.ilike('%Leitura%')
    ).limit(10).all()
    for r in results:
        print(f"dis_nome: {r.dis_nome}, nr_questao: {r.nr_questao}, atr_resposta: {r.atr_resposta}")
