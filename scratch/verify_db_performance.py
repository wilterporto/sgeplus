import sys
import os
import time

# Adiciona o diretório da aplicação ao PYTHONPATH
sys.path.append(r'c:\Users\pc\source\sgeplus')

from app import create_app
from app.models import db, Exam, StudentResult
from app.utils.analytics import get_dashboard_data, _get_group_performance

def main():
    print("====================================================")
    print(" INICIANDO TESTE DE PERFORMANCE E INTEGRIDADE DE BD ")
    print("====================================================")

    app = create_app()
    with app.app_context():
        # Limpar qualquer transação anterior e habilitar WAL para concorrência
        from sqlalchemy import text
        try:
            db.session.rollback()
            db.session.execute(text("PRAGMA journal_mode=WAL;"))
            db.session.commit()
            print("[*] Habilitado modo WAL no SQLite com sucesso!")
        except Exception as e:
            db.session.rollback()
            print(f"[-] Aviso ao habilitar WAL: {e}")

        # Vamos pegar a primeira prova cadastrada no sistema
        exam = Exam.query.first()
        if not exam:
            print("  [ERROR] Nenhuma prova encontrada no banco para rodar o teste.")
            sys.exit(1)
            
        print(f"[*] Analisando performance para a Prova ID: {exam.id} ({exam.title})")
        
        # Teste 1: Medir tempo de execução de get_dashboard_data
        start_time = time.perf_counter()
        data = get_dashboard_data(exam.id)
        end_time = time.perf_counter()
        
        duration_ms = (end_time - start_time) * 1000
        print(f"\n[+] get_dashboard_data executado em {duration_ms:.2f} ms")
        
        if not data:
            print("  [ERROR] get_dashboard_data retornou None.")
            sys.exit(1)
            
        # Validar as chaves principais do dicionário retornado
        required_keys = ['kpis', 'ranking', 'items', 'components_performance', 'proficiency', 'difficulty_performance', 'rankings', 'current_exam_title']
        for key in required_keys:
            if key not in data:
                print(f"  [ERROR] Chave obrigatoria ausente no retorno: {key}")
                sys.exit(1)
            else:
                print(f"  [OK] Chave {key:<25} esta presente.")
                
        # Validar KPIs e Engajamento
        kpis = data.get('kpis')
        engagement = kpis.get('engagement', {})
        print(f"\n[*] Validacao de KPIs:")
        print(f"  - Nota Media Geral: {kpis.get('avg_score')}%")
        print(f"  - Taxa de Participacao: {kpis.get('participation')}%")
        print(f"  - Engajamento Total Scoped: {engagement.get('total')}")
        print(f"  - Presentes (Realized): {engagement.get('realized')}")
        print(f"  - Ausentes (Absent): {engagement.get('absent')}")
        print(f"  - Faltando (Missing): {engagement.get('missing')}")
        print(f"  - Respondido Integralmente: {engagement.get('fully_responded')}")
        
        # Teste 2: Medir performance e corretude do drill-down em _get_group_performance
        print("\n====================================================")
        print(" TESTANDO NIVEIS DE DRILL-DOWN (SEM N+1 QUERIES)    ")
        print("====================================================")
        
        levels = ['regional', 'unit', 'school_year', 'class']
        for lvl in levels:
            start_lvl = time.perf_counter()
            # Rodar a função com argumentos padrões vazios
            res = _get_group_performance(exam.id, lvl)
            end_lvl = time.perf_counter()
            lvl_dur = (end_lvl - start_lvl) * 1000
            
            print(f"\n[+] Nivel '{lvl:<11}' executado in {lvl_dur:.2f} ms | Retornou {len(res)} registros")
            
            if len(res) > 0:
                # Validar chaves e tipos
                first_item = res[0]
                for key in ['id', 'name', 'score']:
                    if key not in first_item:
                        print(f"  [ERROR] Item de ranking de '{lvl}' nao possui chave '{key}'!")
                        sys.exit(1)
                
                # Validar ordenacao decrescente
                scores = [item['score'] for item in res]
                is_sorted = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
                if not is_sorted:
                    print(f"  [ERROR] O ranking para o nivel '{lvl}' nao esta ordenado de forma decrescente por score!")
                    print(f"  Scores: {scores[:5]}...")
                    sys.exit(1)
                else:
                    print(f"  [OK] Ordenacao decrescente validada. Top score: {scores[0]} | Bottom score: {scores[-1]}")
                    
        print("\n====================================================")
        print(" TESTES DE PERFORMANCE E INTEGRIDADE APROVADOS!     ")
        print("====================================================")

if __name__ == '__main__':
    main()
