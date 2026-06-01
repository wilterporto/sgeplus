import sys
import os

# Adiciona o diretório da aplicação ao PYTHONPATH
sys.path.append(r'c:\Users\pc\source\sgeplus')

from app import create_app
from app.models import Student, db
from app.audit_utils import log_audit

def main():
    print("====================================================")
    # Sempre me entregue as respostas em português do Brasil (RULE)
    print(" INICIANDO ATUALIZAÇÃO DA ZONA RESIDENCIAL EM LOTE ")
    print("====================================================")

    app = create_app()
    with app.app_context():
        # Buscar todos os alunos de forma ordenada por ID para determinismo
        students = Student.query.order_by(Student.id).all()
        total_students = len(students)
        
        if total_students == 0:
            print("[ERRO] Nenhum aluno encontrado na base de dados!")
            sys.exit(1)
            
        # Calcular os 85% para Urbana e 15% para Rural
        num_urban = int(round(total_students * 0.85))
        num_rural = total_students - num_urban
        
        print(f"[*] Total de alunos encontrados: {total_students}")
        print(f"[*] Meta de distribuição: 85% Urbana ({num_urban} alunos) | 15% Rural ({num_rural} alunos)")
        
        # Atualizar cada aluno na transação
        for idx, student in enumerate(students):
            if idx < num_urban:
                student.residential_zone = 'Urbana'
            else:
                student.residential_zone = 'Rural'
                
        # Gravar alterações física no SQLite
        db.session.commit()
        print("[OK] Transação de banco gravada com sucesso no SQLite!")
        
        # Gravar log de auditoria corporativo em lote
        log_audit(
            'UPDATE', 
            'Student', 
            0, 
            f"Atualizacao em lote da Zona Residencial dos alunos: {num_urban} Urbana (85%) e {num_rural} Rural (15%) de um total de {total_students} registros."
        )
        print("[OK] Log de auditoria consolidado gravado com sucesso!")
        
        # Verificar o resultado fisicamente
        total_real_urban = Student.query.filter_by(residential_zone='Urbana').count()
        total_real_rural = Student.query.filter_by(residential_zone='Rural').count()
        
        print("\n================ VERIFICAÇÃO PÓS-MIGRAÇÃO ================")
        print(f"[*] Total real Urbana no banco: {total_real_urban} ({round(total_real_urban / total_students * 100, 2)}%)")
        print(f"[*] Total real Rural no banco: {total_real_rural} ({round(total_real_rural / total_students * 100, 2)}%)")
        print("==========================================================")
        
        if total_real_urban == num_urban and total_real_rural == num_rural:
            print("[SUCESSO] Distribuição perfeita atingida!")
        else:
            print("[AVISO] Distribuição concluída, mas com pequenas variações de arredondamento.")

if __name__ == "__main__":
    main()
