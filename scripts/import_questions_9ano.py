import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Question, Descriptor, User

app = create_app()

def get_descriptor(code):
    return Descriptor.query.filter_by(code=code, is_active=True).first()

def run_import():
    with app.app_context():
        # Pega o primeiro admin ou usuário válido para ser o autor das questões
        admin = User.query.filter_by(role='admin').first() or User.query.first()
        admin_id = admin.id if admin else None

        questions_data = [
            # MATEMÁTICA D1
            {
                "statement": "Observe o croqui abaixo que mostra o mapa de um bairro. A rua onde a escola está localizada é paralela à rua da padaria e transversal à rua do hospital. Sabendo que você está no hospital e vira à direita, qual o estabelecimento que você encontrará?",
                "alternatives": {"A": "Escola", "B": "Padaria", "C": "Supermercado", "D": "Farmácia"},
                "correct_alternative": "B",
                "difficulty": "Média",
                "type": "Múltipla Escolha",
                "descriptor_code": "D1"
            },
            # MATEMÁTICA D12
            {
                "statement": "Um terreno retangular tem 15 metros de comprimento por 10 metros de largura. Quantos metros de arame são necessários para cercar esse terreno com 3 voltas completas?",
                "alternatives": {"A": "50 metros", "B": "100 metros", "C": "150 metros", "D": "200 metros"},
                "correct_alternative": "C",
                "difficulty": "Fácil",
                "type": "Múltipla Escolha",
                "descriptor_code": "D12"
            },
            # PORTUGUÊS D1
            {
                "statement": "Leia o trecho: 'O menino acordou cedo, tomou seu café e correu para pegar o ônibus escolar antes das 7 horas.' De acordo com o texto, o que o menino fez logo após acordar?",
                "alternatives": {"A": "Correu para pegar o ônibus.", "B": "Foi dormir novamente.", "C": "Tomou seu café.", "D": "Brincou no quintal."},
                "correct_alternative": "C",
                "difficulty": "Fácil",
                "type": "Múltipla Escolha",
                "descriptor_code": "D1"
            },
            # PORTUGUÊS D4
            {
                "statement": "Leia a tirinha onde a personagem diz: 'Hoje o sol está rachando, preciso urgente de uma sombra e água fresca'. O que a personagem quer dizer implicitamente com essa frase?",
                "alternatives": {"A": "Que o sol está literalmente se quebrando no céu.", "B": "Que está sentindo muito frio.", "C": "Que está chovendo forte.", "D": "Que está sentindo muito calor e precisa se refrescar."},
                "correct_alternative": "D",
                "difficulty": "Média",
                "type": "Múltipla Escolha",
                "descriptor_code": "D4"
            },
            # HISTÓRIA EF09HI01
            {
                "statement": "A Proclamação da República no Brasil, ocorrida em 1889, foi o resultado de uma articulação política entre diferentes grupos. Qual foi o principal grupo social responsável por liderar o golpe que derrubou a Monarquia?",
                "alternatives": {"A": "Os trabalhadores urbanos.", "B": "O Exército brasileiro e cafeicultores paulistas.", "C": "Os escravizados recém-libertos.", "D": "Os comerciantes estrangeiros."},
                "correct_alternative": "B",
                "difficulty": "Média",
                "type": "Múltipla Escolha",
                "descriptor_code": "EF09HI01"
            },
            # GEOGRAFIA EF09GE01
            {
                "statement": "Durante o século XIX e início do XX, as potências europeias promoveram a divisão do continente africano e asiático. Qual o nome dado a esse processo de domínio e divisão territorial liderado pela hegemonia europeia?",
                "alternatives": {"A": "Globalização", "B": "Descolonização", "C": "Imperialismo (Neocolonialismo)", "D": "Guerra Fria"},
                "correct_alternative": "C",
                "difficulty": "Média",
                "type": "Múltipla Escolha",
                "descriptor_code": "EF09GE01"
            },
            # CIÊNCIAS EF09CI01
            {
                "statement": "A água pode ser encontrada em três estados físicos principais. Quando colocamos água líquida no congelador e ela se transforma em gelo, qual é o nome dessa mudança de estado físico?",
                "alternatives": {"A": "Fusão", "B": "Vaporização", "C": "Condensação", "D": "Solidificação"},
                "correct_alternative": "D",
                "difficulty": "Fácil",
                "type": "Múltipla Escolha",
                "descriptor_code": "EF09CI01"
            },
            # INGLÊS EF09LI01
            {
                "statement": "Read the sentence: 'The sudden loud noise frightened the little cat, causing it to run away quickly.' Based on the context, what does the word 'frightened' mean?",
                "alternatives": {"A": "Made happy", "B": "Made hungry", "C": "Scared", "D": "Slept"},
                "correct_alternative": "C",
                "difficulty": "Média",
                "type": "Múltipla Escolha",
                "descriptor_code": "EF09LI01"
            },
            # EDUCAÇÃO FÍSICA EF89EF01
            {
                "statement": "Nos esportes coletivos, além da figura do jogador, existem outras funções fundamentais para que a partida ocorra. Qual é a função do árbitro em um esporte de quadra?",
                "alternatives": {"A": "Marcar os gols.", "B": "Treinar a equipe.", "C": "Garantir o cumprimento das regras do jogo.", "D": "Vender ingressos."},
                "correct_alternative": "C",
                "difficulty": "Fácil",
                "type": "Múltipla Escolha",
                "descriptor_code": "EF89EF01"
            },
            # ARTE EF69AR01
            {
                "statement": "A arte contemporânea frequentemente rompe com os padrões tradicionais da pintura e da escultura. Uma característica comum de muitas obras contemporâneas é:",
                "alternatives": {"A": "O uso exclusivo de telas e tintas a óleo clássicas.", "B": "A representação estritamente realista da natureza.", "C": "A interação com o público e o uso de diferentes mídias e materiais inovadores.", "D": "A proibição do uso de tecnologia e fotografia."},
                "correct_alternative": "C",
                "difficulty": "Média",
                "type": "Múltipla Escolha",
                "descriptor_code": "EF69AR01"
            }
        ]

        inserted_count = 0
        skipped_count = 0

        for q_data in questions_data:
            # Verifica se já existe uma questão com esse mesmo enunciado no banco para evitar duplicatas
            existing_q = Question.query.filter(Question.statement == q_data["statement"]).first()
            if existing_q:
                skipped_count += 1
                continue
            
            # Obtém o descritor relacionado
            descriptor = get_descriptor(q_data["descriptor_code"])
            
            new_q = Question(
                statement=q_data["statement"],
                difficulty=q_data["difficulty"],
                correct_alternative=q_data["correct_alternative"],
                type=q_data["type"],
                status='Aprovada',
                created_by_id=admin_id,
                approved_by_secretaria=True
            )
            new_q.set_alternatives(q_data["alternatives"])
            
            if descriptor:
                new_q.descriptors.append(descriptor)
                
            db.session.add(new_q)
            inserted_count += 1

        db.session.commit()
        print(f"Processo de injeção de questões finalizado.")
        print(f"Novas questões importadas: {inserted_count}")
        print(f"Questões ignoradas (já existiam): {skipped_count}")

if __name__ == '__main__':
    run_import()
