import os
import shutil
import sqlite3

def prepare_db():
    basedir = os.path.abspath(os.path.join('.', ''))
    src = os.path.join(basedir, 'instance', 'idebmais.db')
    dest_dir = os.path.join(basedir, 'app', 'static', 'data')
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, 'idebmais_test.db')

    print('Copiando banco de dados SQLite local...')
    shutil.copy2(src, dest)

    print('Otimizando tamanho do banco copiado (VACUUM)...')
    conn = sqlite3.connect(dest)
    conn.execute('VACUUM')
    conn.close()

    print('Compactando banco (GZIP)...')
    import gzip
    dest_gz = dest + '.gz'
    with open(dest, 'rb') as f_in:
        with gzip.open(dest_gz, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
            
    # Remove uncompressed to avoid large git pushes
    os.remove(dest)

    print('Dividindo arquivo em partes (Chunking)...')
    chunk_size = 20 * 1024 * 1024 # 20 MB
    with open(dest_gz, 'rb') as f_in:
        part_num = 0
        while True:
            chunk = f_in.read(chunk_size)
            if not chunk:
                break
            part_name = f"{dest_gz}.part{part_num:02d}"
            with open(part_name, 'wb') as f_out:
                f_out.write(chunk)
            part_num += 1

    # Remove o gz único e grande
    os.remove(dest_gz)

    print(f'Banco de testes pronto! Dividido em {part_num} partes menores que 20MB.')

if __name__ == '__main__':
    prepare_db()
