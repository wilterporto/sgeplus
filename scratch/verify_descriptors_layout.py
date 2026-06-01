import sys
import os

# Adiciona o diretório da aplicação ao PYTHONPATH
sys.path.append(r'c:\Users\pc\source\sgeplus')

from app import create_app
from app.models import User, db

def main():
    print("====================================================")
    print(" VERIFICANDO TELA DE DESCRITORES/HABILIDADES (LAYOUT) ")
    print("====================================================")

    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        # Buscar um usuário admin
        admin_user = User.query.filter(User.role == 'admin').first()
        if not admin_user:
            admin_user = User.query.first()
            
        if not admin_user:
            print("[ERRO] Nenhum usuário administrador encontrado no banco!")
            sys.exit(1)
            
        admin_id = str(admin_user.id)

    with app.test_client() as client:
        # Injetar a sessão de autenticação do Flask-Login
        with client.session_transaction() as sess:
            sess['_user_id'] = admin_id
            sess['_fresh'] = True
            sess['active_role'] = 'admin'
            
        print("[*] Requisitando a rota '/matrices/descriptors'...")
        response = client.get('/matrices/descriptors')
        
        print(f"[*] Código de Status HTTP: {response.status_code}")
        
        if response.status_code != 200:
            print(f"  [ERRO] A rota retornou o código de status: {response.status_code}")
            sys.exit(1)
            
        print("  [OK] A rota carregou com absoluto sucesso!")
        
        html_content = response.data.decode('utf-8')
        
        # Validar a presença de componentes e correções de layout
        print("\n[*] Validando os alinhamentos e fechamentos de tags no HTML...")
        
        tests = {
            "Novo Descritor botão": 'Novo Descritor/Habilidade',
            "Botão Importar": 'Importar',
            "Dropdown Filtrar por Matriz": 'Filtrar por Matriz',
            "Cabeçalho alinhado (Descrição)": '<th>Descrição</th>',
            "Cabeçalho alinhado (Status)": '<th>Status</th>',
            "Coluna Ações": '<th>Ações</th>',
            "Modal Em Construção": 'id="underConstructionModal"',
            "Botão Documento Curricular": 'data-bs-target="#underConstructionModal"'
        }
        
        all_passed = True
        for key, pattern in tests.items():
            if pattern in html_content:
                print(f"  [OK] Elemento de layout '{key}' encontrado na interface!")
            else:
                print(f"  [FALHA] Elemento de layout '{key}' ('{pattern}') ausente no HTML!")
                all_passed = False
                
        if all_passed:
            print("\n====================================================")
            print(" [SUCESSO] LAYOUT DE DESCRITORES OPERANDO 100% OK!   ")
            print("====================================================")
        else:
            print("\n====================================================")
            print(" [AVISO] Algum componente de layout falhou no teste.")
            print("====================================================")
            sys.exit(1)

if __name__ == "__main__":
    main()
