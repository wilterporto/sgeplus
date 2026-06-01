import json
import random
from app import create_app
from app.models import db, Descriptor, Question, Subject, SchoolYear

def generate_questions_for_descriptor(descriptor, num=3):
    if not descriptor.subject:
        return []
    subject_name = descriptor.subject.name.lower()
    school_year = descriptor.school_year.name.upper() if descriptor.school_year else "9º ANO"
    code = descriptor.code
    desc_text = descriptor.description[:50]
    
    questions = []
    for i in range(num):
        difficulty = random.choice(['Facil', 'Medio', 'Dificil'])
        
        if 'matem' in subject_name:
            if '5' in school_year:
                a, b = random.randint(100, 999), random.randint(10, 99)
                templates = [
                    (f"Uma fábrica produziu {a} cadernos pela manhã e {b} cadernos à tarde. Qual o total produzido no dia? (Habilidade: {code})", str(a+b), [str(a+b-10), str(a+b+10), str(a+b+100), str(a-b)]),
                    (f"João tinha R$ {a},00 e comprou um presente por R$ {b},00. Quanto sobrou para João? (Habilidade: {code})", str(a-b), [str(a-b-5), str(a-b+5), str(a+b), str(a-b+10)]),
                    (f"Em uma prateleira há {b} caixas, e cada caixa contém 12 lápis. Quantos lápis há no total? (Habilidade: {code})", str(b*12), [str(b*10), str(b*12+5), str(b+12), str(b*14)])
                ]
            else: # 9º ano
                x, y = random.randint(2, 10), random.randint(2, 10)
                templates = [
                    (f"Resolva a equação 2x + {x} = {x + 10}. O valor de x é: (Habilidade: {code})", "5", ["4", "6", "10", "2"]),
                    (f"A área de um retângulo é de {x * y * 2} cm² e sua base mede {x} cm. Qual é a altura? (Habilidade: {code})", str(y*2), [str(y), str(y*3), str(y+2), str(y*4)]),
                    (f"Qual o valor da expressão {x}² - {y}? (Habilidade: {code})", str(x**2 - y), [str((x**2 - y)+2), str(x**2 + y), str(x*2 - y), str(x**2 - y - 5)])
                ]
            stmt, ans, wrongs = random.choice(templates)
            cor_alt = 'A'
            alts = {'A': ans, 'B': wrongs[0], 'C': wrongs[1], 'D': wrongs[2], 'E': wrongs[3]}
            
        elif 'portugu' in subject_name:
            templates = [
                (f"Leia o trecho: 'A tecnologia avançou drasticamente nas últimas décadas, transformando como nos comunicamos.'\n\nSegundo o texto, a transformação ocorreu principalmente na forma como: (Habilidade: {code} - {desc_text}...)", "Nos comunicamos", ["Estudamos", "Trabalhamos", "Nos locomovemos", "Compramos"]),
                (f"Leia a tirinha e responda.\n\nNo segundo quadrinho, a expressão do personagem indica:\n(Habilidade: {code} - {desc_text}...)", "Surpresa", ["Alegria", "Tristeza", "Raiva", "Indiferença"]),
                (f"No verso 'O vento sussurrava segredos nas folhas', temos um exemplo da figura de linguagem:\n(Habilidade: {code} - {desc_text}...)", "Personificação (Prosopopeia)", ["Metáfora", "Hipérbole", "Eufemismo", "Pleonasmo"])
            ]
            stmt, ans, wrongs = random.choice(templates)
            cor_alt = 'C'
            alts = {'A': wrongs[0], 'B': wrongs[1], 'C': ans, 'D': wrongs[2], 'E': wrongs[3]}
            
        elif 'hist' in subject_name:
            templates = [
                (f"Sobre o período do Brasil Colônia, o principal produto de exportação no século XVI era:\n(Habilidade: {code} - {desc_text}...)", "O pau-brasil e a cana-de-açúcar", ["O ouro", "O café", "A borracha", "O algodão"]),
                (f"A Revolução Industrial trouxe mudanças drásticas na sociedade europeia. Uma delas foi:\n(Habilidade: {code} - {desc_text}...)", "O êxodo rural e o crescimento das cidades", ["O fortalecimento do feudalismo", "O fim do comércio marítimo", "O aumento das reservas indígenas", "A criação das capitanias hereditárias"]),
                (f"No contexto das Guerras Mundiais (século XX), uma consequência direta para a geopolítica foi:\n(Habilidade: {code} - {desc_text}...)", "O surgimento de novas superpotências", ["O fim da escravidão", "A descoberta das Américas", "A unificação da Itália e Alemanha", "O tratado de Tordesilhas"])
            ]
            stmt, ans, wrongs = random.choice(templates)
            cor_alt = 'B'
            alts = {'A': wrongs[0], 'B': ans, 'C': wrongs[1], 'D': wrongs[2], 'E': wrongs[3]}
            
        elif 'geogra' in subject_name:
            templates = [
                (f"O Brasil possui grande diversidade de biomas. O bioma caracterizado por vegetação rasteira e arbustos retorcidos no centro do país é o:\n(Habilidade: {code} - {desc_text}...)", "Cerrado", ["Mata Atlântica", "Caatinga", "Pampa", "Amazônia"]),
                (f"A globalização influencia diretamente a economia mundial através:\n(Habilidade: {code} - {desc_text}...)", "Do aumento das trocas comerciais e avanço nas comunicações", ["Do fechamento das fronteiras físicas", "Da limitação da internet", "Do fortalecimento dos mercados locais isolados", "Da extinção das empresas multinacionais"]),
                (f"Com o intenso processo de urbanização, surgem problemas estruturais nas grandes cidades, como:\n(Habilidade: {code} - {desc_text}...)", "A favelização e o trânsito intenso", ["O excesso de terras agricultáveis", "O fim da poluição", "A diminuição da densidade demográfica", "A ausência de indústrias"])
            ]
            stmt, ans, wrongs = random.choice(templates)
            cor_alt = 'D'
            alts = {'A': wrongs[0], 'B': wrongs[1], 'C': wrongs[2], 'D': ans, 'E': wrongs[3]}
            
        elif 'ci' in subject_name:
            templates = [
                (f"O processo pelo qual as plantas produzem seu próprio alimento utilizando a luz solar é chamado de:\n(Habilidade: {code} - {desc_text}...)", "Fotossíntese", ["Respiração celular", "Digestão", "Germinação", "Polinização"]),
                (f"Ao misturarmos água e óleo, observamos que as substâncias não se misturam completamente, formando uma mistura:\n(Habilidade: {code} - {desc_text}...)", "Heterogênea", ["Homogênea", "Saturada", "Concentrada", "Isotônica"]),
                (f"O sistema solar é composto por uma estrela e vários planetas. O planeta mais próximo do Sol é:\n(Habilidade: {code} - {desc_text}...)", "Mercúrio", ["Terra", "Marte", "Vênus", "Júpiter"])
            ]
            stmt, ans, wrongs = random.choice(templates)
            cor_alt = 'A'
            alts = {'A': ans, 'B': wrongs[0], 'C': wrongs[1], 'D': wrongs[2], 'E': wrongs[3]}
            
        else:
            stmt = f"Questão genérica para {subject_name.title()}, {school_year}, avaliando o descritor {code} ({desc_text}...)."
            ans = "Alternativa Correta"
            wrongs = ["Alternativa 1", "Alternativa 2", "Alternativa 3", "Alternativa 4"]
            cor_alt = 'E'
            alts = {'A': wrongs[0], 'B': wrongs[1], 'C': wrongs[2], 'D': wrongs[3], 'E': ans}
            
        q = Question(
            statement=stmt,
            difficulty=difficulty,
            correct_alternative=cor_alt,
            alternatives=json.dumps(alts),
            tenant_id=1
        )
        questions.append((q, descriptor))
        
    return questions

def main():
    app = create_app()
    with app.app_context():
        tenant_id = 1
        # Find descriptors for 5 and 9 years
        descs = db.session.query(Descriptor).join(SchoolYear).filter(
            Descriptor.tenant_id == tenant_id,
            db.or_(SchoolYear.name.ilike('%5%'), SchoolYear.name.ilike('%9%'))
        ).all()
        
        print(f'Encontrados {len(descs)} descritores.')
        
        new_questions_tuples = []
        for d in descs:
            new_questions_tuples.extend(generate_questions_for_descriptor(d, 3))
            
        if new_questions_tuples:
            for q, d in new_questions_tuples:
                q.descriptors.append(d)
                db.session.add(q)
            db.session.commit()
            print(f'{len(new_questions_tuples)} questões foram importadas com sucesso no banco de dados!')
        else:
            print('Nenhuma questão gerada.')

if __name__ == '__main__':
    main()
