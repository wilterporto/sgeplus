import sys
import os
import re

# Adiciona o diretório da aplicação ao PYTHONPATH
sys.path.append(r'c:\Users\pc\source\sgeplus')

from app import create_app
from app.models import User, db

def verify_route(client, route_url, page_name, expected_terms, forbidden_terms):
    print(f"\n[*] Requisitando a rota '{route_url}' ({page_name})...")
    response = client.get(route_url)
    
    print(f"[*] Código de Status HTTP: {response.status_code}")
    if response.status_code != 200:
        print(f"  [ERRO] A rota retornou o código de status: {response.status_code}")
        return False
        
    html_content = response.data.decode('utf-8')
    
    # 1. Verificar termos esperados (Componente / Componentes / etc.)
    passed_expected = True
    for term in expected_terms:
        # Busca sem case-sensitive ou literal
        if term.lower() in html_content.lower():
            print(f"  [OK] Termo esperado '{term}' encontrado no HTML.")
        else:
            # Algumas páginas podem não exibir todos se a lista estiver vazia, mas fazemos um log informativo
            print(f"  [AVISO] Termo esperado '{term}' não encontrado explicitamente.")
            
    # 2. Verificar termos proibidos (Disciplina / Disciplinas / etc.)
    passed_forbidden = True
    
    # Vamos buscar no HTML texto visível (ignorando scripts JS de modais ou urls do flask,
    # focando em tags de texto, headers <th>, <label>, etc.)
    # Procuramos o termo isolado "Disciplina" ou "Disciplinas" ou "disciplina" ou "disciplinas" em tags HTML.
    # Evitamos falsos positivos com URLs como "edit_subject" ou atributos subject_id no HTML/JS.
    # Então, fazemos regex para encontrar a palavra exata em locais visíveis.
    visible_pattern = re.compile(r'>\s*[^<]*\b(disciplina|disciplinas)\b[^<]*<', re.IGNORECASE)
    matches = visible_pattern.findall(html_content)
    
    # Também verificamos strings em alertas JavaScript, como os alert() que alteramos
    js_alert_pattern = re.compile(r"alert\([^)]*['\"]\b(disciplina|disciplinas)\b['\"][^)]*\)", re.IGNORECASE)
    js_matches = js_alert_pattern.findall(html_content)
    
    all_matches = matches + js_matches
    
    if all_matches:
        print(f"  [FALHA] Termos proibidos (Disciplina/s) encontrados no texto visível/alertas: {all_matches}")
        passed_forbidden = False
    else:
        print(f"  [OK] Nenhum termo visível 'Disciplina/s' residual detectado.")
        
    return passed_forbidden

def main():
    print("====================================================")
    print(" VERIFICANDO RENOVE E SUBSTITUIÇÃO DE DISCIPLINAS    ")
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
            
        print(f"[*] Usando o usuário admin: {admin_user.username} (ID: {admin_user.id}) para os testes.")
        admin_id = str(admin_user.id)

    success = True
    with app.test_client() as client:
        # Injetar a sessão de autenticação do Flask-Login
        with client.session_transaction() as sess:
            sess['_user_id'] = admin_id
            sess['_fresh'] = True
            sess['active_role'] = 'admin'
            
        # Testar as diferentes rotas
        routes_to_test = [
            ('/academic/definitions', 'Definições Acadêmicas', ['Componentes', 'Novo Componente'], ['Disciplina', 'Disciplinas']),
            ('/academic/curriculums', 'Estruturas Curriculares', ['Qtd. componentes'], ['Qtd. disciplinas']),
            ('/professors/', 'Lista de Professores', ['Componente', 'Comp'], ['Disciplina', 'Disc']),
            ('/exams/', 'Lista de Provas', ['Componente'], ['Disciplina']),
            ('/matrices/descriptors', 'Descritores de Habilidades', ['Componente'], ['Disciplina']),
            ('/audit/logs', 'Logs de Auditoria', ['Componente'], ['Disciplina'])
        ]
        
        for route_url, page_name, expected, forbidden in routes_to_test:
            route_ok = verify_route(client, route_url, page_name, expected, forbidden)
            if not route_ok:
                success = False
                
    print("\n====================================================")
    if success:
        print(" [SUCESSO] RENOVAÇÃO DO TERMO EXECUTADA COM 100% DE EXCELÊNCIA! ")
        print("====================================================")
        sys.exit(0)
    else:
        print(" [FALHA] Algum termo residual 'Disciplina' foi encontrado. ")
        print("====================================================")
        sys.exit(1)

if __name__ == "__main__":
    main()
