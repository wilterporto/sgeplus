import sys
import os

# Adiciona o diretório da aplicação ao PYTHONPATH
sys.path.append(r'c:\Users\pc\source\sgeplus')

from app import create_app
from app.models import User, db

def main():
    print("====================================================")
    print(" VERIFICANDO INTEGRAÇÃO DO SOFTWARE PWA E TEMAS      ")
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
        # 1. Testar o Service Worker (sw.js)
        print("[*] Requisitando Service Worker em '/sw.js'...")
        res_sw = client.get('/sw.js')
        print(f"  - Status Code: {res_sw.status_code}")
        print(f"  - Content-Type: {res_sw.content_type}")
        
        if res_sw.status_code != 200 or 'javascript' not in res_sw.content_type:
            print("  [ERRO] Falha na validação técnica do Service Worker!")
            sys.exit(1)
        print("  [OK] Service Worker servido perfeitamente sob a raiz do domínio!")

        # 2. Testar o Manifesto PWA (manifest.json)
        print("\n[*] Requisitando Manifesto PWA em '/manifest.json'...")
        res_manifest = client.get('/manifest.json')
        print(f"  - Status Code: {res_manifest.status_code}")
        print(f"  - Content-Type: {res_manifest.content_type}")
        
        if res_manifest.status_code != 200 or 'json' not in res_manifest.content_type:
            print("  [ERRO] Falha na validação técnica do Manifesto PWA!")
            sys.exit(1)
        print("  [OK] Manifesto PWA servido perfeitamente sob a raiz do domínio!")

        # Injetar a sessão de autenticação do Flask-Login para acessar a página inicial
        with client.session_transaction() as sess:
            sess['_user_id'] = admin_id
            sess['_fresh'] = True
            sess['active_role'] = 'admin'

        # 3. Testar se o index contém o Manifesto e os scripts do alternador de tema
        print("\n[*] Requisitando a página inicial '/' para validar o template com admin...")
        res_index = client.get('/')
        print(f"  - Status Code: {res_index.status_code}")
        
        if res_index.status_code != 200:
            print("  [ERRO] Falha ao carregar a página inicial '/'!")
            sys.exit(1)
            
        html = res_index.data.decode('utf-8')
        
        tests = {
            "Manifest Link": '<link rel="manifest" href="/manifest.json">',
            "Apple Icon": '<link rel="apple-touch-icon" href="/static/images/icon-192.png">',
            "Evitar Flashing script": 'Evitar flashing de tema claro',
            "Atributo data-theme": 'data-bs-theme="light"',
            "Botão themeToggle": 'id="themeToggle"',
            "Ícone themeIcon": 'id="themeIcon"',
            "Registro SW JS": 'navigator.serviceWorker.register(\'/sw.js\')',
            "Persistência de Tema JS": 'localStorage.setItem(\'theme\''
        }
        
        all_passed = True
        for key, pattern in tests.items():
            if pattern in html:
                print(f"  [OK] Elemento PWA/Tema '{key}' encontrado no HTML!")
            else:
                print(f"  [FALHA] Elemento '{key}' ('{pattern}') ausente na página!")
                all_passed = False
                
        if all_passed:
            print("\n====================================================")
            print(" [SUCESSO] PWA E SELETOR DE TEMAS FUNCIONANDO 100%  ")
            print("====================================================")
        else:
            print("\n====================================================")
            print(" [FALHA] Algum recurso PWA ou de Tema está incompleto.")
            print("====================================================")
            sys.exit(1)

if __name__ == "__main__":
    main()
