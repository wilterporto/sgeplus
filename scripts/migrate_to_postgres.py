import os
import sys
import logging

basedir = os.path.abspath(os.path.join('.', ''))
sys.path.append(basedir)

from app import create_app, db
from app.models import SystemConfig
from sqlalchemy import create_engine, MetaData, text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    app = create_app()
    with app.app_context():
        # Verificando se o banco principal não é SQLite
        is_postgres = 'postgres' in app.config['SQLALCHEMY_DATABASE_URI']
        if not is_postgres:
            logger.warning("O banco de dados configurado nao parece ser o PostgreSQL/Neon. Migrando mesmo assim?")
            
        # Cria as tabelas no banco de destino caso não existam
        db.create_all()

        SystemConfig.set_value('migration_status', 'running')
        SystemConfig.set_value('migration_percent', '0')
        SystemConfig.set_value('migration_message', 'Preparando arquivos de banco de dados...')

        # Configura a conexão com o banco de origem (SQLite de teste)
        sqlite_db_path = os.path.join(basedir, 'app', 'static', 'data', 'idebmais_test.db')
        sqlite_gz_path = sqlite_db_path + '.gz'
        
        if not os.path.exists(sqlite_db_path):
            import glob
            import shutil
            import gzip
            
            # Se as partes existirem, juntá-las primeiro
            part_files = sorted(glob.glob(f"{sqlite_gz_path}.part*"))
            if part_files and not os.path.exists(sqlite_gz_path):
                logger.info(f"Juntando {len(part_files)} partes do banco de testes...")
                with open(sqlite_gz_path, 'wb') as dest_file:
                    for part_file in part_files:
                        with open(part_file, 'rb') as src_file:
                            dest_file.write(src_file.read())
                            
            if os.path.exists(sqlite_gz_path):
                logger.info("Descompactando banco de testes (GZIP -> DB)...")
                with gzip.open(sqlite_gz_path, 'rb') as f_in:
                    with open(sqlite_db_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                logger.error(f"Arquivo {sqlite_gz_path} e suas partes nao encontrados!")
                SystemConfig.set_value('migration_status', 'error')
                SystemConfig.set_value('migration_message', 'Arquivo de banco de dados não encontrado.')
                return
            
        SystemConfig.set_value('migration_percent', '10')
        SystemConfig.set_value('migration_message', 'Limpando dados antigos no PostgreSQL...')
        
        sqlite_uri = f'sqlite:///{sqlite_db_path}'
        sqlite_engine = create_engine(sqlite_uri)
        
        metadata = db.metadata
        tables = metadata.sorted_tables
        
        # Limpar banco de destino antes de importar
        logger.info("Limpando dados existentes no PostgreSQL (pode demorar)...")
        if is_postgres:
            for table in tables:
                if table.name != 'alembic_version':
                    try:
                        db.session.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
        else:
            for table in reversed(tables):
                try:
                    db.session.execute(table.delete())
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()

        SystemConfig.set_value('migration_percent', '20')
        logger.info("Iniciando migracao dos dados SQLite -> PostgreSQL")
        
        total_tables = len(tables)
        
        with sqlite_engine.connect() as sqlite_conn:
            for idx, table in enumerate(tables):
                logger.info(f"Processando tabela: {table.name}")
                percent = 20 + int((idx / total_tables) * 80)
                SystemConfig.set_value('migration_percent', str(percent))
                SystemConfig.set_value('migration_message', f'Migrando tabela {table.name} ({idx+1}/{total_tables})...')
                
                # Ler do SQLite
                try:
                    result = sqlite_conn.execute(table.select())
                    rows = result.fetchall()
                    keys = result.keys()
                except Exception as e:
                    logger.error(f"Erro ao ler tabela {table.name} do SQLite: {e}")
                    continue
                    
                if not rows:
                    continue
                    
                # Converter para lista de dicionarios e TRUNCAR STRINGS
                dicts = []
                for row in rows:
                    row_dict = dict(zip(keys, row))
                    for col in table.columns:
                        val = row_dict.get(col.name)
                        if isinstance(val, str) and hasattr(col.type, 'length') and col.type.length:
                            if len(val) > col.type.length:
                                row_dict[col.name] = val[:col.type.length]
                    dicts.append(row_dict)
                
                # Inserir no Postgres em lotes (chunks)
                chunk_size = 5000
                for i in range(0, len(dicts), chunk_size):
                    chunk = dicts[i:i + chunk_size]
                    try:
                        db.session.execute(table.insert(), chunk)
                        db.session.commit()
                        logger.info(f"  Inseridas {len(chunk)} linhas em {table.name} (Total: {min(i+chunk_size, len(dicts))}/{len(dicts)})")
                    except Exception as e:
                        db.session.rollback()
                        logger.error(f"  Erro ao inserir lote na tabela {table.name}, tentando linha por linha... Erro original: {e}")
                        # Fallback: tentar linha por linha
                        success_count = 0
                        for row in chunk:
                            try:
                                db.session.execute(table.insert(), [row])
                                db.session.commit()
                                success_count += 1
                            except Exception as row_err:
                                db.session.rollback()
                        logger.info(f"  Recuperadas {success_count} de {len(chunk)} linhas em {table.name} usando insercao individual.")
                
                # Sincronizar as sequencias no PostgreSQL (auto-incremento)
                if is_postgres:
                    # Tentar descobrir se existe uma coluna chamada 'id'
                    if 'id' in keys:
                        try:
                            seq_sql = text(f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), coalesce(max(id), 1), max(id) IS NOT null) FROM {table.name}")
                            db.session.execute(seq_sql)
                            db.session.commit()
                            logger.info(f"  Sequencia ID atualizada para {table.name}")
                        except Exception as e:
                            db.session.rollback()
                            logger.warning(f"  Aviso ao atualizar sequencia de {table.name} (talvez nao tenha auto-incremento): {e}")

        SystemConfig.set_value('migration_percent', '100')
        SystemConfig.set_value('migration_message', 'Migração concluída com sucesso!')
        SystemConfig.set_value('migration_status', 'completed')
        logger.info("Migracao concluida com sucesso!")


if __name__ == '__main__':
    run_migration()
