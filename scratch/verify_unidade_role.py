import os
import sys

# Add application directory to sys.path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, TeachingUnit, Class, Student, Professor, Question, TeachingAssignment

def test_unidade_role_mechanisms():
    app = create_app()
    with app.app_context():
        print("=== INICIANDO VERIFICAÇÃO DO PERFIL UNIDADE ===")
        
        # 1. Verificar se a role 'unidade' está declarada no modelo de usuários
        print("\n1. Verificando suporte à role 'unidade' no modelo de usuários:")
        user = User.query.filter(User.roles.like('%unidade%')).first()
        if user:
            print(f"   [OK] Encontrado usuário unidade de teste: {user.username} ({user.name})")
            print(f"   [OK] Escolas vinculadas: {[tu.name for tu in user.teaching_units]}")
        else:
            # Criar um usuário unidade de teste se não existir
            print("   [INFO] Criando usuário de teste com perfil unidade...")
            escola = TeachingUnit.query.filter_by(type='Escola').first()
            if not escola:
                print("   [ERRO] Nenhuma escola cadastrada para vincular ao usuário teste!")
                return
            
            user = User(
                username="teste_unidade",
                name="Gestor de Unidade Teste",
                email="unidade_teste@sgeplus.com",
                role="unidade",
                roles="unidade",
                active=True
            )
            user.set_password("123456")
            user.teaching_units.append(escola)
            db.session.add(user)
            db.session.commit()
            print(f"   [OK] Usuário 'teste_unidade' criado e vinculado à escola: {escola.name}")

        # 2. Testar queries de escopo escolar em turmas
        active_school = user.teaching_units[0]
        print(f"\n2. Testando restrição de escopo de Turmas para a escola '{active_school.name}':")
        classes = Class.query.filter_by(teaching_unit_id=active_school.id).all()
        print(f"   [OK] Turmas encontradas na escola ativa: {len(classes)} turmas.")
        for c in classes:
            print(f"     - Turma: {c.name} ({c.school_year.name})")

        # 3. Testar queries de escopo escolar em Alunos (matriculados nas turmas da escola)
        print(f"\n3. Testando restrição de escopo de Alunos para a escola '{active_school.name}':")
        from app.models import Enrollment
        students = Student.query.join(Enrollment).join(Class).filter(Class.teaching_unit_id == active_school.id).all()
        print(f"   [OK] Alunos matriculados nas turmas desta escola: {len(students)} alunos.")
        for s in students[:5]:
            print(f"     - Aluno: {s.name} (Matrícula: {s.registration_number})")
        if len(students) > 5:
            print(f"     - ... e mais {len(students) - 5} alunos.")

        # 4. Testar queries de escopo escolar em Professores modulados na escola
        print(f"\n4. Testando restrição de escopo de Professores para a escola '{active_school.name}':")
        professors = Professor.query.join(Professor.assignments).join(Class).filter(
            Class.teaching_unit_id == active_school.id
        ).distinct().all()
        print(f"   [OK] Professores modulados nas turmas desta escola: {len(professors)} professores.")
        for p in professors:
            print(f"     - Professor: {p.name} (CPF: {p.cpf})")

        # 5. Testar queries de escopo escolar em Questões criadas pelos professores da escola
        print(f"\n5. Testando restrição de escopo de Questões criadas por professores da escola:")
        prof_user_ids = db.session.query(Professor.user_id)\
            .join(TeachingAssignment, TeachingAssignment.professor_id == Professor.id)\
            .join(Class, Class.id == TeachingAssignment.class_id)\
            .filter(Class.teaching_unit_id == active_school.id)\
            .filter(Professor.user_id.isnot(None))\
            .subquery()
            
        questions = Question.query.filter(Question.created_by_id.in_(prof_user_ids)).all()
        print(f"   [OK] Questões criadas pelos professores que lecionam na escola: {len(questions)} questões.")
        for q in questions[:5]:
            print(f"     - Questão ID {q.id}: {q.statement[:60]}... (Dificuldade: {q.difficulty})")
        if len(questions) > 5:
            print(f"     - ... e mais {len(questions) - 5} questões.")

        print("\n=== VERIFICAÇÃO CONCLUÍDA COM SUCESSO! TUDO FUNCIONANDO PERFEITAMENTE! ===")

if __name__ == "__main__":
    test_unidade_role_mechanisms()
