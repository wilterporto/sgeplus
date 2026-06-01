import sys
import os

# Adiciona o diretório da aplicação ao PYTHONPATH
sys.path.append(r'c:\Users\pc\source\sgeplus')

from app import create_app
from app.models import User, db

def main():
    print("====================================================")
    print(" VERIFICANDO O DASHBOARD DE INDICADORES ACADÊMICOS  ")
    print("====================================================")

    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        # Buscar um usuário admin
        admin_user = User.query.filter(User.role == 'admin').first()
        if not admin_user:
            # Fallback para o primeiro usuário admin disponível
            admin_user = User.query.first()
            
        if not admin_user:
            print("[ERRO] Nenhum usuário administrador encontrado no banco!")
            sys.exit(1)
            
        print(f"[*] Usando o usuário admin: {admin_user.username} (ID: {admin_user.id}) para o teste.")
        admin_id = str(admin_user.id)

    with app.test_client() as client:
        # Injetar a sessão de autenticação do Flask-Login
        with client.session_transaction() as sess:
            sess['_user_id'] = admin_id
            sess['_fresh'] = True
            sess['active_role'] = 'admin'
            
        print("[*] Requisitando a rota '/academic/indicators'...")
        response = client.get('/academic/indicators')
        
        print(f"[*] Código de Status HTTP: {response.status_code}")
        
        if response.status_code != 200:
            print(f"  [ERRO] A rota retornou o código de status: {response.status_code}")
            sys.exit(1)
            
        print("  [OK] A rota carregou com absoluto sucesso!")
        
        html_content = response.data.decode('utf-8')
        
        # Validar a presença de novos termos no HTML
        print("\n[*] Validando os novos componentes de indicadores no HTML...")
        
        tests = {
            "Zona Residencial": "Zona Residencial",
            "Localização Diferenciada": "Localização Diferenciada de Residência",
            "Bolsa Família": "Bolsa Família",
            "Alunos com Deficiência": "Alunos com Deficiência (Sim)",
            "Sexo (Alunos)": "Distribuição por Sexo (Alunos)",
            "Sexo (Professores)": "Distribuição por Sexo (Professores)",
            "Regional com percentuais": "Escolas (%)",
        }
        
        all_passed = True
        for key, pattern in tests.items():
            if pattern in html_content:
                print(f"  [OK] Elemento '{key}' encontrado na interface!")
            else:
                print(f"  [FALHA] Elemento '{key}' ('{pattern}') ausente no HTML!")
                all_passed = False
                
        if all_passed:
            print("\n====================================================")
            print(" [SUCESSO] TODOS OS COMPONENTES ESTÃO OPERANDO 100% ")
            print("====================================================")
        else:
            print("\n====================================================")
            print(" [AVISO] Algum componente não foi detectado no HTML.")
            print("====================================================")
            sys.exit(1)

if __name__ == "__main__":
    main()
