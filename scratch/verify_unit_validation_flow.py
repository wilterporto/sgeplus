import sys
import os

# Adiciona o diretório da aplicação ao PYTHONPATH
sys.path.append(r'c:\Users\pc\source\sgeplus')

from app import create_app
from app.models import Question, TeachingUnit, db
from app.routes.exams import Exam

def main():
    print("====================================================")
    print(" INICIANDO TESTE FIM-A-FIM: VALIDAÇÃO POR UNIDADE    ")
    print("====================================================")

    app = create_app()
    with app.app_context():
        # 1. Obter uma escola ativa para o teste
        school = TeachingUnit.query.filter_by(type='Escola').first()
        if not school:
            print("  [ERROR] Nenhuma escola encontrada no banco para rodar o teste.")
            sys.exit(1)
        print(f"[*] Escola Selecionada para o Teste: ID {school.id} ({school.name})")

        # 2. Obter uma segunda escola para testar o isolamento
        other_school = TeachingUnit.query.filter(TeachingUnit.type == 'Escola', TeachingUnit.id != school.id).first()
        if not other_school:
            print("  [ERROR] Segunda escola não encontrada para testar isolamento.")
            sys.exit(1)
        print(f"[*] Escola Secundária para Isolamento: ID {other_school.id} ({other_school.name})")

        # 3. Criar uma questão temporária de teste
        print("\n[*] Criando questão de teste temporária...")
        test_question = Question(
            statement="Questão de Teste - Validação por Unidade Escolar",
            type="MULTIPLA_ESCOLHA",
            difficulty="Medio",
            correct_alternative="A",
            status="aprovada",
            alternatives='{"A": "Opção A", "B": "Opção B"}'
        )
        db.session.add(test_question)
        db.session.commit()
        print(f"  [OK] Questão criada com sucesso! ID: {test_question.id}")

        try:
            # 4. Validar que a questão inicialmente NÃO está validada por nenhuma das escolas
            print("\n[*] Verificando estado inicial da questão...")
            if school in test_question.validated_units or other_school in test_question.validated_units:
                print("  [ERROR] A questão já possui validações ativas de forma inesperada.")
                sys.exit(1)
            print("  [OK] Questão livre de validações.")

            # 5. Simular a query do sorteador de provas para a Escola 1 (deve dar Vazio)
            print("\n[*] Teste 1: Buscando questões no sorteador para Escola 1 (Sem validar ainda)...")
            query = Question.query.join(Question.validated_units).filter(TeachingUnit.id == school.id)
            available = query.distinct().all()
            if any(q.id == test_question.id for q in available):
                print("  [ERROR] A questão de teste apareceu no escopo da Escola 1 sem estar validada!")
                sys.exit(1)
            print(f"  [OK] Sucesso! A questão de teste não foi listada (Disponíveis sob validação da escola: {len(available)}).")

            # 6. Validar a questão para a Escola 1
            print(f"\n[*] Validando a questão ID {test_question.id} para a Escola 1 ({school.name})...")
            test_question.validated_units.append(school)
            db.session.commit()
            print("  [OK] Transação gravada com sucesso no SQLite.")

            # 7. Verificar se a questão agora está listada como validada pela Escola 1
            print("\n[*] Verificando relacionamento de validações na questão...")
            if school not in test_question.validated_units:
                print("  [ERROR] A Escola 1 não consta na lista de validações da questão!")
                sys.exit(1)
            if other_school in test_question.validated_units:
                print("  [ERROR] A Escola 2 consta na lista de validações incorretamente!")
                sys.exit(1)
            print("  [OK] Apenas a Escola 1 possui a validação desta questão.")

            # 8. Simular a query do sorteador para a Escola 1 (DEVE CONTER A QUESTÃO)
            print("\n[*] Teste 2: Buscando questões no sorteador para Escola 1 (Agora Validada)...")
            query = Question.query.join(Question.validated_units).filter(TeachingUnit.id == school.id)
            available = query.distinct().all()
            if not any(q.id == test_question.id for q in available):
                print("  [ERROR] A questão de teste validada NÃO apareceu no sorteador da Escola 1!")
                sys.exit(1)
            print(f"  [OK] Sucesso! A questão validada está no escopo (Disponíveis: {len(available)}).")

            # 9. Simular a query do sorteador para a Escola 2 (Isolamento - DEVE DAR VAZIO)
            print("\n[*] Teste 3: Buscando questões no sorteador para Escola 2 (Isolamento)...")
            query = Question.query.join(Question.validated_units).filter(TeachingUnit.id == other_school.id)
            available_other = query.distinct().all()
            if any(q.id == test_question.id for q in available_other):
                print("  [ERROR] Falha de Isolamento: Questão validada pela Escola 1 vazou para a Escola 2!")
                sys.exit(1)
            print(f"  [OK] Sucesso! A questão de teste está isolada e não vazou para a Escola 2 (Disponíveis: {len(available_other)}).")

            # 10. Remover a validação da Escola 1 (Desvalidação)
            print(f"\n[*] Removendo validação da Escola 1 para a questão ID {test_question.id}...")
            test_question.validated_units.remove(school)
            db.session.commit()
            print("  [OK] Transação gravada com sucesso.")

            # 11. Simular a query do sorteador para a Escola 1 de novo (deve dar Vazio)
            print("\n[*] Teste 4: Buscando questões no sorteador para Escola 1 (Após remover validação)...")
            query = Question.query.join(Question.validated_units).filter(TeachingUnit.id == school.id)
            available = query.distinct().all()
            if any(q.id == test_question.id for q in available):
                print("  [ERROR] A questão de teste apareceu no escopo após a remoção da validação!")
                sys.exit(1)
            print("  [OK] Sucesso! A questão deixou o escopo da Escola 1 perfeitamente.")

        finally:
            # Limpeza definitiva da questão temporária
            print("\n[*] Realizando limpeza da questão temporária de teste...")
            db.session.delete(test_question)
            db.session.commit()
            print("  [OK] Limpeza concluída.")

    print("\n====================================================")
    print(" TODOS OS TESTES DE VALIDAÇÃO CONCLUÍDOS COM SUCESSO!")
    print("====================================================")

if __name__ == '__main__':
    main()
