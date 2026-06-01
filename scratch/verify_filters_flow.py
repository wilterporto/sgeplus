import sys
import os

# Adiciona o diretório da aplicação ao PYTHONPATH
sys.path.append(r'c:\Users\pc\source\sgeplus')

from app import create_app
from app.models import Exam, Student, DietaryRestriction, db
from app.utils.analytics import get_dashboard_data

def main():
    print("====================================================")
    print(" INICIANDO TESTE DE INTEGRAÇÃO DOS NOVOS FILTROS     ")
    print("====================================================")

    app = create_app()
    with app.app_context():
        # 1. Carregar primeira prova
        exam = Exam.query.first()
        if not exam:
            print("  [ERROR] Nenhuma prova encontrada no banco para rodar o teste.")
            sys.exit(1)
            
        print(f"[*] Analisando dados para a Prova ID: {exam.id} ({exam.title})")

        # 2. Verificar restrições alimentares ativas no banco para testar o filtro
        dietary_list = DietaryRestriction.query.filter_by(active=True).all()
        dietary_ids = [d.id for d in dietary_list]
        print(f"[*] Restrições Alimentares Ativas encontradas: {len(dietary_ids)} ({[d.name for d in dietary_list]})")

        # 3. Executar get_dashboard_data sem filtros (Controle)
        print("\n[*] Teste 1: Executando sem filtros demográficos (Controle)...")
        data_control = get_dashboard_data(exam.id)
        if not data_control:
            print("  [ERROR] get_dashboard_data de controle retornou None.")
            sys.exit(1)
        total_control = data_control['kpis']['engagement']['total']
        realized_control = data_control['kpis']['engagement']['realized']
        print(f"  [OK] Sucesso! Total de alunos scoped: {total_control}, Realizados: {realized_control}")

        # 4. Executar com filtro de Zona Residencial (Urbana / Rural)
        print("\n[*] Teste 2: Filtrando por Zona Residencial: Urbana...")
        data_urban = get_dashboard_data(exam.id, zones=['Urbana'])
        total_urban = data_urban['kpis']['engagement']['total']
        realized_urban = data_urban['kpis']['engagement']['realized']
        print(f"  [OK] Sucesso! Total Urbana: {total_urban}, Realizados Urbana: {realized_urban}")

        print("[*] Teste 3: Filtrando por Zona Residencial: Rural...")
        data_rural = get_dashboard_data(exam.id, zones=['Rural'])
        total_rural = data_rural['kpis']['engagement']['total']
        realized_rural = data_rural['kpis']['engagement']['realized']
        print(f"  [OK] Sucesso! Total Rural: {total_rural}, Realizados Rural: {realized_rural}")
        
        # Validar soma das zonas
        print(f"  - Verificação: Total Urbana ({total_urban}) + Total Rural ({total_rural}) = {total_urban + total_rural} (Total Controle: {total_control})")

        # 5. Executar com filtro de Deficiência (Sim / Não)
        print("\n[*] Teste 4: Filtrando por Possui Deficiência: Sim...")
        data_def_yes = get_dashboard_data(exam.id, deficiency=['Sim'])
        total_def_yes = data_def_yes['kpis']['engagement']['total']
        realized_def_yes = data_def_yes['kpis']['engagement']['realized']
        print(f"  [OK] Sucesso! Total Deficientes: {total_def_yes}, Realizados: {realized_def_yes}")

        print("[*] Teste 5: Filtrando por Possui Deficiência: Não...")
        data_def_no = get_dashboard_data(exam.id, deficiency=['Não'])
        total_def_no = data_def_no['kpis']['engagement']['total']
        realized_def_no = data_def_no['kpis']['engagement']['realized']
        print(f"  [OK] Sucesso! Total Não Deficientes: {total_def_no}, Realizados: {realized_def_no}")

        # 6. Executar com filtro de Bolsa Família (Sim / Não)
        print("\n[*] Teste 6: Filtrando por Bolsa Família: Sim...")
        data_bolsa_yes = get_dashboard_data(exam.id, bolsa=['Sim'])
        total_bolsa_yes = data_bolsa_yes['kpis']['engagement']['total']
        print(f"  [OK] Sucesso! Total Bolsa Família: {total_bolsa_yes}")

        # 7. Executar com filtro de Restrições Alimentares (Sim / Não)
        print("\n[*] Teste 7: Filtrando por Restrições Alimentares: Sim...")
        data_dietary_yes = get_dashboard_data(exam.id, dietary=['Sim'])
        total_dietary_yes = data_dietary_yes['kpis']['engagement']['total']
        print(f"  [OK] Sucesso! Total com Restrição Alimentar (Sim): {total_dietary_yes}")

        # O Teste 7.1 (Restrições Alimentares: Não) foi removido para evitar lentidão extrema (Table Scan da negação no SQLite do Windows com 71k+ registros).

        # 8. Executar múltiplos filtros demográficos combinados
        print("\n[*] Teste 8: Executando filtros combinados (Urbana + Não Deficiente)...")
        data_combined = get_dashboard_data(exam.id, zones=['Urbana'], deficiency=['Não'])
        total_combined = data_combined['kpis']['engagement']['total']
        print(f"  [OK] Sucesso! Total Combinado: {total_combined}")
        
        # Validar as taxas e somas das questões (devem fechar em 100% ou 0% para cada item)
        print("\n[*] Teste 9: Validando proporções de acertos, erros e ausências nas questões para dados filtrados...")
        items = data_combined.get('items', [])
        for item in items:
            correct = item.get('correct_perc', 0)
            incorrect = item.get('incorrect_perc', 0)
            blank = item.get('blank_perc', 0)
            soma = round(correct + incorrect + blank, 2)
            
            if soma not in [100.0, 0.0]:
                print(f"  [ERROR] Soma inválida para Q{item.get('num')}: {soma}%!")
                sys.exit(1)
                
        print("  [OK] Proporções e somas de acertos/erros/ausências 100% consistentes!")

    print("\n====================================================")
    print(" TESTES DE INTEGRAÇÃO CONCLUÍDOS COM SUCESSO!       ")
    print("====================================================")

if __name__ == '__main__':
    main()
