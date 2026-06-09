from app import create_app, db
from app.models import ReferenceMatrix, Subject, SchoolYear, Theme, Descriptor, Question, User

app = create_app()

with app.app_context():
    tenant_id = User.query.first().tenant_id
    
    matrix = ReferenceMatrix.query.filter_by(name='SAEB', tenant_id=tenant_id).first()
    subject = Subject.query.filter_by(name='LÍNGUA PORTUGUESA', tenant_id=tenant_id).first()
    year_5 = SchoolYear.query.filter_by(name='5º ANO', tenant_id=tenant_id).first()
    year_9 = SchoolYear.query.filter_by(name='9º ANO', tenant_id=tenant_id).first()
    
    user_id = User.query.first().id
    
    # Themes
    themes_map = {t.name: t.id for t in Theme.query.filter_by(matrix_id=matrix.id).all()}
    
    def get_or_create_theme(name):
        if name in themes_map:
            return themes_map[name]
        t = Theme(name=name, matrix_id=matrix.id, tenant_id=tenant_id)
        db.session.add(t)
        db.session.commit()
        themes_map[name] = t.id
        return t.id

    desc_data = [
        # 5º ANO
        (year_5, 'I - Procedimentos de Leitura', 'D1', 'Localizar informações explícitas em um texto.'),
        (year_5, 'I - Procedimentos de Leitura', 'D3', 'Inferir o sentido de uma palavra ou expressão.'),
        (year_5, 'I - Procedimentos de Leitura', 'D4', 'Inferir uma informação implícita em um texto.'),
        (year_5, 'I - Procedimentos de Leitura', 'D6', 'Identificar o tema de um texto.'),
        (year_5, 'I - Procedimentos de Leitura', 'D11', 'Distinguir um fato da opinião relativa a esse fato.'),
        (year_5, 'II - Implicações do Suporte, do Gênero e/ou do Enunciador na Compreensão do Texto', 'D5', 'Interpretar texto com auxílio de material gráfico (fotos, charges, etc.).'),
        (year_5, 'II - Implicações do Suporte, do Gênero e/ou do Enunciador na Compreensão do Texto', 'D9', 'Identificar a finalidade de textos de diferentes gêneros.'),
        (year_5, 'IV - Coerência e Coesão no Processamento do Texto', 'D2', 'Estabelecer relações entre partes do texto (substituições/repetições).'),
        (year_5, 'IV - Coerência e Coesão no Processamento do Texto', 'D7', 'Identificar o conflito gerador do enredo e os elementos que constroem a narrativa.'),
        (year_5, 'IV - Coerência e Coesão no Processamento do Texto', 'D8', 'Estabelecer relação causa/consequência.'),
        (year_5, 'IV - Coerência e Coesão no Processamento do Texto', 'D12', 'Estabelecer relações lógico-discursivas presentes no texto (conjunções, advérbios).'),
        (year_5, 'V - Relações entre Recursos Expressivos e Efeitos de Sentido', 'D13', 'Identificar efeitos de ironia ou humor em textos variados.'),
        (year_5, 'V - Relações entre Recursos Expressivos e Efeitos de Sentido', 'D14', 'Identificar efeito de sentido da pontuação.'),
        (year_5, 'VI - Variação Linguística', 'D10', 'Identificar marcas linguísticas que evidenciam o locutor/interlocutor.'),
        (year_5, 'III - Relação entre Textos', 'D15', 'Reconhecer diferentes formas de tratar a mesma informação ao comparar textos.'),
        
        # 9º ANO
        (year_9, 'I - Procedimentos de Leitura', 'D1', 'Localizar informações explícitas.'),
        (year_9, 'I - Procedimentos de Leitura', 'D3', 'Inferir o sentido de palavra ou expressão.'),
        (year_9, 'I - Procedimentos de Leitura', 'D4', 'Inferir informação implícita.'),
        (year_9, 'I - Procedimentos de Leitura', 'D6', 'Identificar o tema de um texto.'),
        (year_9, 'IV - Coerência e Coesão no Processamento do Texto', 'D7', 'Identificar a tese de um texto.'),
        (year_9, 'IV - Coerência e Coesão no Processamento do Texto', 'D8', 'Estabelecer relação entre a tese e os argumentos oferecidos para sustentá-la.'),
        (year_9, 'IV - Coerência e Coesão no Processamento do Texto', 'D9', 'Diferenciar as partes principais das secundárias em um texto.'),
        (year_9, 'IV - Coerência e Coesão no Processamento do Texto', 'D10', 'Identificar o conflito gerador do enredo e os elementos da narrativa.'),
        (year_9, 'III - Relação entre Textos', 'D20', 'Reconhecer diferentes formas de tratar uma informação na comparação de textos que tratam do mesmo tema.'),
        (year_9, 'III - Relação entre Textos', 'D21', 'Reconhecer posições distintas entre duas ou mais opiniões relativas ao mesmo fato ou tema.'),
        (year_9, 'V - Relações entre Recursos Expressivos e Efeitos de Sentido', 'D16', 'Identificar efeitos de ironia ou humor.'),
        (year_9, 'V - Relações entre Recursos Expressivos e Efeitos de Sentido', 'D17', 'Reconhecer efeito de sentido decorrente da escolha de pontuação.'),
        (year_9, 'V - Relações entre Recursos Expressivos e Efeitos de Sentido', 'D18', 'Reconhecer efeito de sentido decorrente da escolha de uma determinada palavra.'),
        (year_9, 'V - Relações entre Recursos Expressivos e Efeitos de Sentido', 'D19', 'Reconhecer efeito de sentido decorrente da exploração de recursos morfossintáticos.'),
        (year_9, 'VI - Variação Linguística', 'D13', 'Identificar as marcas linguísticas que evidenciam o locutor e o interlocutor de um texto.')
    ]
    
    desc_objects = []
    for y, theme_name, code, desc_text in desc_data:
        tid = get_or_create_theme(theme_name)
        d = Descriptor.query.filter_by(code=code, matrix_id=matrix.id, school_year_id=y.id, subject_id=subject.id).first()
        if not d:
            d = Descriptor(
                type='Descritor',
                code=code,
                description=desc_text,
                matrix_id=matrix.id,
                theme_id=tid,
                school_year_id=y.id,
                subject_id=subject.id,
                tenant_id=tenant_id,
                is_active=True
            )
            db.session.add(d)
            db.session.commit()
        desc_objects.append(d)

    print(f"Imported/Verified {len(desc_objects)} descriptors.")
    
    # Generate 2 questions for each descriptor
    q_count = 0
    for d in desc_objects:
        for i in range(2):
            q_stmt = f"<p>Leia o texto abaixo e responda:</p><p><em>Exemplo de texto base para a questão focando no descritor {d.code} ({d.description}) do {d.school_year.name}.</em></p><p>Qual é a resposta correta de acordo com a habilidade exigida?</p>"
            
            alts = {
                'A': 'Esta é uma alternativa incorreta para testar distratores.',
                'B': 'Esta é a alternativa correta baseada no texto.',
                'C': 'Outra alternativa incorreta que parece correta.',
                'D': 'Alternativa incorreta fora de contexto.',
                'E': 'Alternativa incorreta sem relação com o texto.'
            }
            
            q = Question(
                statement=q_stmt,
                difficulty='Medio',
                correct_alternative='B',
                type='MULTIPLA_ESCOLHA',
                status='aprovada',
                approved_by_secretaria=True,
                created_by_id=user_id,
                tenant_id=tenant_id
            )
            q.set_alternatives(alts)
            db.session.add(q)
            db.session.commit()
            
            # Link descriptor
            q.descriptors.append(d)
            db.session.commit()
            q_count += 1
            
    print(f"Created {q_count} questions.")
