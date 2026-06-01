import sys
import os

# Adiciona o diretório raiz ao path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Tenant, User, TeachingUnit, Class, Student, Exam, Evaluation

def run_tests():
    app = create_app()
    with app.app_context():
        print("=== INICIANDO VERIFICAÇÃO DE MULTI-TENANCY ===")
        
        # 1. Verificar se o Tenant 1 (SME Goiânia) existe
        t1 = Tenant.query.filter_by(name="SME Goiânia").first()
        if not t1:
            print("[ERRO] Tenant 'SME Goiânia' não encontrado. Rodou a migração inicial?")
            return
        print(f"[OK] Tenant 1 encontrado: {t1.name} (ID: {t1.id}, Tipo: {t1.type})")
        
        # 2. Criar um segundo Tenant para simular isolamento
        t2 = Tenant.query.filter_by(name="SME Aparecida").first()
        if not t2:
            t2 = Tenant(name="SME Aparecida", type="Municipal")
            db.session.add(t2)
            db.session.commit()
            print(f"[CRIADO] Tenant 2: {t2.name} (ID: {t2.id})")
        else:
            print(f"[OK] Tenant 2 já existe: {t2.name} (ID: {t2.id})")
            
        # 3. Criar usuários de teste para cada Tenant
        u1 = User.query.filter_by(username="user_goiania").first()
        if not u1:
            u1 = User(username="user_goiania", name="Gestor Goiânia", role="admin", roles="admin", active=True, tenant_id=t1.id)
            u1.set_password("senha123")
            db.session.add(u1)
            print("[CRIADO] Usuário Goiânia")
            
        u2 = User.query.filter_by(username="user_aparecida").first()
        if not u2:
            u2 = User(username="user_aparecida", name="Gestor Aparecida", role="admin", roles="admin", active=True, tenant_id=t2.id)
            u2.set_password("senha123")
            db.session.add(u2)
            print("[CRIADO] Usuário Aparecida")
            
        # 4. Criar Escolas em cada Tenant
        esc1 = TeachingUnit.query.filter_by(name="Escola Municipal Goiânia Sul", tenant_id=t1.id).first()
        if not esc1:
            esc1 = TeachingUnit(name="Escola Municipal Goiânia Sul", type="Escola", tenant_id=t1.id)
            db.session.add(esc1)
            print("[CRIADA] Escola no Tenant 1")
            
        esc2 = TeachingUnit.query.filter_by(name="Escola Municipal Aparecida Centro", tenant_id=t2.id).first()
        if not esc2:
            esc2 = TeachingUnit(name="Escola Municipal Aparecida Centro", type="Escola", tenant_id=t2.id)
            db.session.add(esc2)
            print("[CRIADA] Escola no Tenant 2")
            
        db.session.commit()
        
        # 5. Executar validação de queries simulando o contexto do usuário logado
        print("\n--- SIMULANDO ACESSO GESTOR GOIÂNIA (Tenant 1) ---")
        # Simular o login de u1 injetando-o como current_user na query
        # filter_by_tenant usa flask_login.current_user por padrão.
        # Podemos mockar o login_user ou simplesmente testar a função filter_by_tenant diretamente de forma determinística
        from app.utils.tenancy import filter_by_tenant
        
        # Para simular, vamos mockar temporariamente o flask_login.current_user
        # ou passar um contexto mockado.
        # Uma forma limpa de mockar current_user em scripts standalone é criar uma classe/objeto mockado
        class MockCurrentUser:
            def __init__(self, tenant_id, is_system_admin=False):
                self.tenant_id = tenant_id
                self.is_system_admin = is_system_admin
                self.is_authenticated = True
                
        # Mockar temporariamente em app.utils.tenancy
        import app.utils.tenancy
        original_current_user = app.utils.tenancy.current_user
        
        # Simular Gestor Goiânia
        app.utils.tenancy.current_user = MockCurrentUser(tenant_id=t1.id)
        
        # Buscar escolas
        q_goiania = TeachingUnit.query
        q_goiania = filter_by_tenant(q_goiania, TeachingUnit)
        escolas_goiania = q_goiania.all()
        
        print(f"Escolas visíveis para Goiânia: {[e.name for e in escolas_goiania]}")
        has_aparecida = any(e.name == "Escola Municipal Aparecida Centro" for e in escolas_goiania)
        if has_aparecida:
            print("[ERRO] Gestor Goiânia conseguiu visualizar escola de Aparecida!")
        else:
            print("[SUCESSO] Isolamento de escolas para Goiânia funcionou perfeitamente!")
            
        # Simular Gestor Aparecida
        app.utils.tenancy.current_user = MockCurrentUser(tenant_id=t2.id)
        
        q_aparecida = TeachingUnit.query
        q_aparecida = filter_by_tenant(q_aparecida, TeachingUnit)
        escolas_aparecida = q_aparecida.all()
        
        print(f"Escolas visíveis para Aparecida: {[e.name for e in escolas_aparecida]}")
        has_goiania = any(e.name == "Escola Municipal Goiânia Sul" for e in escolas_aparecida)
        if has_goiania:
            print("[ERRO] Gestor Aparecida conseguiu visualizar escola de Goiânia!")
        else:
            print("[SUCESSO] Isolamento de escolas para Aparecida funcionou perfeitamente!")
            
        # Simular Super Admin do Sistema
        app.utils.tenancy.current_user = MockCurrentUser(tenant_id=None, is_system_admin=True)
        
        q_system = TeachingUnit.query
        q_system = filter_by_tenant(q_system, TeachingUnit)
        escolas_system = q_system.all()
        print(f"Escolas visíveis para Super Admin: {len(escolas_system)} escolas no total.")
        has_both = any(e.name == "Escola Municipal Goiânia Sul" for e in escolas_system) and \
                   any(e.name == "Escola Municipal Aparecida Centro" for e in escolas_system)
        if has_both:
            print("[SUCESSO] Super Admin conseguiu visualizar todas as escolas de todos os tenants!")
        else:
            print("[ERRO] Super Admin não conseguiu visualizar escolas de todos os tenants!")
            
        # Restaurar original_current_user
        app.utils.tenancy.current_user = original_current_user
        
        # 6. Limpeza dos dados de teste
        print("\n--- LIMPANDO DADOS DE TESTE DE APARECIDA ---")
        # Vamos manter o Tenant 2 e os usuários/escolas de Goiânia, mas limpar Aparecida se desejado
        # Ou manter para fins de demonstração permanente. Vamos deletar apenas o tenant de teste Aparecida e suas relações
        # para garantir integridade perfeita.
        TeachingUnit.query.filter_by(tenant_id=t2.id).delete()
        User.query.filter_by(tenant_id=t2.id).delete()
        Tenant.query.filter_by(id=t2.id).delete()
        db.session.commit()
        print("[LIMPADO] Dados de teste de Aparecida excluídos com sucesso.")
        
        print("\n=== VERIFICAÇÃO CONCLUÍDA COM SUCESSO! ===")

if __name__ == "__main__":
    run_tests()
