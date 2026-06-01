import sys
import os
import sqlite3

# Adiciona o diretório da aplicação ao PYTHONPATH
sys.path.append(r'c:\Users\pc\source\sgeplus')

def main():
    print("====================================================")
    print(" EXECUTANDO MIGRAÇÃO FÍSICA MULTI-TENANCY           ")
    print("====================================================")

    db_path = r'c:\Users\pc\source\sgeplus\instance\idebmais.db'
    if not os.path.exists(db_path):
        print(f"[ERROR] Banco de dados não encontrado em: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Criar a tabela 'tenant'
        print("[*] Criando tabela 'tenant'...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tenant (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) UNIQUE NOT NULL,
            type VARCHAR(50) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # 2. Adicionar is_system_admin no 'user'
        print("[*] Adicionando coluna 'is_system_admin' na tabela 'user'...")
        try:
            cursor.execute("ALTER TABLE user ADD COLUMN is_system_admin BOOLEAN NOT NULL DEFAULT 0;")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("  - Coluna 'is_system_admin' já existe na tabela 'user'.")
            else:
                raise e

        # 3. Adicionar tenant_id nas tabelas especificadas
        tab_columns = [
            ('user', 'tenant_id'),
            ('teaching_unit', 'tenant_id'),
            ('student', 'tenant_id'),
            ('class', 'tenant_id'),
            ('professor', 'tenant_id'),
            ('exam', 'tenant_id'),
            ('evaluation', 'tenant_id'),
            ('question', 'tenant_id')
        ]

        for tab, col in tab_columns:
            print(f"[*] Adicionando coluna '{col}' na tabela '{tab}'...")
            try:
                cursor.execute(f"ALTER TABLE {tab} ADD COLUMN {col} INTEGER REFERENCES tenant(id);")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"  - Coluna '{col}' já existe na tabela '{tab}'.")
                else:
                    raise e

        # 4. Inserir o primeiro cliente 'SME Goiânia'
        print("[*] Garantindo cliente 'SME Goiânia'...")
        cursor.execute("SELECT id FROM tenant WHERE name = 'SME Goiânia';")
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO tenant (name, type) VALUES ('SME Goiânia', 'Municipal');")
            tenant_id = cursor.lastrowid
            print(f"  - Cliente 'SME Goiânia' inserido com ID: {tenant_id}")
        else:
            tenant_id = row[0]
            print(f"  - Cliente 'SME Goiânia' já existe com ID: {tenant_id}")

        # 5. Atualizar o usuário administrador atual para ser super admin
        print("[*] Configurando usuário 'admin' como Administrador do Sistema (Super Admin)...")
        cursor.execute("UPDATE user SET is_system_admin = 1, tenant_id = NULL WHERE username = 'admin';")

        # 6. Atualizar todos os outros dados existentes para estarem vinculados ao cliente SME Goiânia (tenant_id = 1)
        tables_to_update = ['user', 'teaching_unit', 'student', 'class', 'professor', 'exam', 'evaluation', 'question']
        for tab in tables_to_update:
            if tab == 'user':
                # Não atualiza o super admin
                cursor.execute(f"UPDATE user SET tenant_id = ? WHERE username != 'admin';", (tenant_id,))
                print(f"  - Atualizados outros usuários para tenant_id = {tenant_id}")
            else:
                cursor.execute(f"UPDATE {tab} SET tenant_id = ? WHERE tenant_id IS NULL;", (tenant_id,))
                print(f"  - Atualizada tabela '{tab}' para tenant_id = {tenant_id}")

        # 7. Criar log de auditoria da migração
        print("[*] Gravando log de auditoria da transição Multi-Tenancy...")
        import json
        details = json.dumps({"description": "Migracao automatica da base corporativa para a arquitetura Multi-Tenancy. Cliente SME Goiania criado e todos os dados legados vinculados."})
        cursor.execute("""
        INSERT INTO audit_log (user_id, action, target_table, target_id, details, timestamp)
        VALUES (1, 'UPDATE', 'System', 0, ?, CURRENT_TIMESTAMP);
        """, (details,))

        conn.commit()
        print("\n[SUCCESS] Migração física e de dados concluída com sucesso absoluto!")

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Ocorreu um erro crítico durante a migração: {e}")
        sys.exit(1)
    finally:
        conn.close()

    print("====================================================")

if __name__ == '__main__':
    main()
