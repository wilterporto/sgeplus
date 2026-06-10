import sys
import os
import re

# Adiciona o diretório raiz do projeto ao sys.path para importar o app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Question

app = create_app()

def clean_html(text):
    if not text:
        return text
    # Converte quebras de linha HTML comuns para newline real,
    # para que na impressão não fique tudo numa linha só.
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    
    # Remove qualquer outra tag HTML
    text = re.sub(r'<[^>]+>', '', text)
    
    # Limpa quebras de linha excessivas e decodifica entidades básicas
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    
    # Remove espaços ou quebras extras no final e no começo
    return text.strip()

def run_cleaning():
    with app.app_context():
        questions = Question.query.all()
        updated_count = 0
        
        for q in questions:
            changed = False
            
            # Limpa o enunciado
            if q.statement:
                cleaned_stmt = clean_html(q.statement)
                if cleaned_stmt != q.statement:
                    q.statement = cleaned_stmt
                    changed = True
            
            # Limpa as alternativas
            alts = q.get_alternatives()
            if alts and isinstance(alts, dict):
                cleaned_alts = {}
                alts_changed = False
                for key, val in alts.items():
                    if isinstance(val, str):
                        cleaned_val = clean_html(val)
                        cleaned_alts[key] = cleaned_val
                        if cleaned_val != val:
                            alts_changed = True
                    else:
                        cleaned_alts[key] = val
                        
                if alts_changed:
                    q.set_alternatives(cleaned_alts)
                    changed = True
            
            if changed:
                updated_count += 1
                
        db.session.commit()
        print(f"Limpeza concluída! {updated_count} de {len(questions)} questões foram higienizadas e tiveram tags HTML removidas.")

if __name__ == '__main__':
    run_cleaning()
