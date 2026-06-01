import sys
import os
import json

# Adiciona o diretório da aplicação ao PYTHONPATH
sys.path.append(r'c:\Users\pc\source\sgeplus')

from app import create_app, db
from app.models import (
    User, Evaluation, SchoolYear, Subject, Descriptor, Question,
    Exam, ExamItem, Student, StudentResult, Class, TeachingUnit, Enrollment
)

def run_dashboard_multicomponents_test():
    print("====================================================")
    print(" INICIANDO TESTE DO DASHBOARD: MÚLTIPLOS COMPONENTES")
    print("====================================================")

    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        # 1. Obter usuário admin para a sessão
        admin_user = User.query.filter(User.role == 'admin').first()
        if not admin_user:
            admin_user = User.query.first()
        if not admin_user:
            print("[ERRO] Nenhum usuário encontrado no banco!")
            sys.exit(1)
            
        admin_id = str(admin_user.id)
        
        # 2. Localizar turma e alunos ativos e existentes no banco corporativo (Massa Real)
        from sqlalchemy import func
        class_with_students = db.session.query(Enrollment.class_id, func.count(Enrollment.id).label('cnt'))\
                                        .filter(Enrollment.active == True)\
                                        .group_by(Enrollment.class_id)\
                                        .having(func.count(Enrollment.id) >= 2)\
                                        .first()
                                        
        if not class_with_students:
            print("[ERRO] Nenhuma turma com pelo menos 2 alunos ativos encontrada!")
            sys.exit(1)
            
        test_class = Class.query.get(class_with_students.class_id)
        enrollments = Enrollment.query.filter_by(class_id=test_class.id, active=True).limit(2).all()
        student1 = enrollments[0].student
        student2 = enrollments[1].student
        year = test_class.school_year
        
        print(f"[*] Usando Turma Existente: '{test_class.name}' (ID: {test_class.id})")
        print(f"[*] Alunos Vinculados: '{student1.name}' (ID: {student1.id}) e '{student2.name}' (ID: {student2.id})")

        # 3. Mapear ou criar componentes/disciplinas
        sub_math = Subject.query.filter(Subject.name.like("%MATEMÁTICA%")).first()
        if not sub_math:
            sub_math = Subject(name="MATEMÁTICA")
            db.session.add(sub_math)
            
        sub_port = Subject.query.filter(Subject.name.like("%PORTUGUESA%")).first()
        if not sub_port:
            sub_port = Subject(name="LÍNGUA PORTUGUESA")
            db.session.add(sub_port)
        db.session.commit()
        
        # 4. Descritores temporários
        desc_math = Descriptor.query.filter_by(code="D_MATH_TEMP").first()
        if not desc_math:
            desc_math = Descriptor(code="D_MATH_TEMP", description="Habilidade Matemática", subject_id=sub_math.id, school_year_id=year.id)
            db.session.add(desc_math)
            
        desc_port = Descriptor.query.filter_by(code="D_PORT_TEMP").first()
        if not desc_port:
            desc_port = Descriptor(code="D_PORT_TEMP", description="Habilidade Português", subject_id=sub_port.id, school_year_id=year.id)
            db.session.add(desc_port)
        db.session.commit()

        # 5. Questões Temporárias (Aprovadas)
        q_math = Question(statement="Questão de Matemática Multi", alternatives='{"A": "Alt A", "B": "Alt B"}', correct_alternative="A", status="aprovada")
        q_math.descriptors.append(desc_math)
        db.session.add(q_math)
        
        q_port = Question(statement="Questão de Português Multi", alternatives='{"A": "Alt A", "B": "Alt B"}', correct_alternative="B", status="aprovada")
        q_port.descriptors.append(desc_port)
        db.session.add(q_port)
        db.session.commit()
        
        # 6. Avaliação e Prova Multidisciplinar
        eval_mult = Evaluation(name="Avaliação Multidisciplinar Integrada", type="Diagnostica", quantity=2, scoring_type="none", multiple_components=True)
        db.session.add(eval_mult)
        db.session.commit()
        
        exam = Exam(
            evaluation_id=eval_mult.id,
            title="Simulado Multidisciplinar Integrado",
            evaluation_type=eval_mult.type,
            academic_year="2026",
            application_date=db.func.current_date(),
            subject_id=None,
            school_year_id=year.id,
            status="Aprovado"
        )
        db.session.add(exam)
        db.session.flush()
        
        # Mapeamento físico de itens
        item_math = ExamItem(exam_id=exam.id, question_id=q_math.id, value=1.0)
        item_port = ExamItem(exam_id=exam.id, question_id=q_port.id, value=1.0)
        db.session.add(item_math)
        db.session.add(item_port)
        db.session.commit()

        # 7. Respostas dos Alunos no Simulado
        # Aluno 1: Acerta Matemática (A) e Erra Português (A)
        res1 = StudentResult(
            exam_id=exam.id,
            student_id=student1.id,
            answers=json.dumps({str(q_math.id): "A", str(q_port.id): "A"}),
            score_percentage=50.0
        )
        # Aluno 2: Acerta Matemática (A) e Acerta Português (B)
        res2 = StudentResult(
            exam_id=exam.id,
            student_id=student2.id,
            answers=json.dumps({str(q_math.id): "A", str(q_port.id): "B"}),
            score_percentage=100.0
        )
        db.session.add(res1)
        db.session.add(res2)
        db.session.commit()
        
        exam_id = exam.id
        sub_math_name = sub_math.name
        sub_port_name = sub_port.name
        student1_id = student1.id
        student2_id = student2.id

    # 8. Executar Requisição AJAX na Rota analítica
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['_user_id'] = admin_id
            sess['_fresh'] = True
            sess['active_role'] = 'admin'
            
        print(f"[*] Requisitando '/reports/data?exam_id={exam_id}'...")
        response = client.get(f'/reports/data?exam_id={exam_id}')
        
        print(f"[*] Código de Status HTTP: {response.status_code}")
        assert response.status_code == 200, "Deveria retornar 200 OK!"
        
        data = json.loads(response.data.decode('utf-8'))
        
        # Validar estrutura de componentes no JSON
        print("\n[*] Validando os desempenhos retornados por componente...")
        assert 'components_performance' in data, "Chave 'components_performance' ausente no JSON!"
        
        comp_perf = data['components_performance']
        print(f"[*] Componentes Calculados ({len(comp_perf)}):")
        for cp in comp_perf:
            print(f"  - Componente: {cp['name']} | Acertos: {cp['correct_count']}/{cp['total_count']} ({cp['correct_perc']}%)")
            
        # Esperado: 
        # Matemática -> 100.0% (2/2)
        # Língua Portuguesa -> 50.0% (1/2)
        math_data = next((c for c in comp_perf if c['name'] == sub_math_name), None)
        port_data = next((c for c in comp_perf if c['name'] == sub_port_name), None)
        
        assert math_data is not None, "Desempenho de Matemática ausente no retorno!"
        assert port_data is not None, "Desempenho de Língua Portuguesa ausente no retorno!"
        
        assert math_data['correct_perc'] == 100.0, f"Matemática deveria ter 100% de acertos, mas teve {math_data['correct_perc']}%"
        assert math_data['correct_count'] == 2, "Matemática deveria ter 2 acertos"
        assert math_data['total_count'] == 2, "Matemática deveria ter 2 respostas válidas"
        
        assert port_data['correct_perc'] == 50.0, f"Português deveria ter 50% de acertos, mas teve {port_data['correct_perc']}%"
        assert port_data['correct_count'] == 1, "Português deveria ter 1 acerto"
        assert port_data['total_count'] == 2, "Português deveria ter 2 respostas válidas"
        
        print("\n  [OK] Todos os cálculos e proporções de múltiplos componentes são 100% corretos!")

    # 9. Limpeza Determinística de registros temporários
    with app.app_context():
        print("\n[*] Iniciando limpeza dos registros temporários de teste...")
        db.session.delete(db.session.query(StudentResult).filter_by(exam_id=exam_id, student_id=student1_id).first())
        db.session.delete(db.session.query(StudentResult).filter_by(exam_id=exam_id, student_id=student2_id).first())
        db.session.delete(Exam.query.get(exam_id))
        db.session.delete(q_math)
        db.session.delete(q_port)
        db.session.delete(desc_math)
        db.session.delete(desc_port)
        db.session.delete(eval_mult)
        db.session.commit()
        print("  [OK] Limpeza de banco de dados concluída com sucesso!")
        print("====================================================")
        print(" [SUCESSO] TESTES DO DASHBOARD MULTIDISCIPLINAR OK! ")
        print("====================================================")

if __name__ == "__main__":
    run_dashboard_multicomponents_test()
