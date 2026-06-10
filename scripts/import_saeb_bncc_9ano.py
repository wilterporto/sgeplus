import sys
import os

# Adiciona o diretório raiz do projeto ao sys.path para importar o app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import ReferenceMatrix, Subject, Descriptor, Theme, SchoolYear

app = create_app()

def run_import():
    with app.app_context():
        # 1. Garantir que temos a matriz SAEB
        matrix = ReferenceMatrix.query.filter_by(name='SAEB').first()
        if not matrix:
            matrix = ReferenceMatrix(name='SAEB', description='Matriz de Referência SAEB e BNCC')
            db.session.add(matrix)
            db.session.commit()
            
        # 2. Obter ou criar o SchoolYear "9º Ano"
        school_year = SchoolYear.query.filter(SchoolYear.name.ilike('%9º Ano%')).first()
        if not school_year:
            school_year = SchoolYear(name='9º Ano')
            db.session.add(school_year)
            db.session.commit()

        # 3. Dicionário de Subjects para mapeamento
        subjects = Subject.query.all()
        subject_map = {s.name.upper(): s for s in subjects}

        def get_subject(name):
            if name.upper() in subject_map:
                return subject_map[name.upper()]
            # Se não existir, cria
            new_subject = Subject(name=name.upper())
            db.session.add(new_subject)
            db.session.commit()
            subject_map[name.upper()] = new_subject
            return new_subject

        # 4. Dados a serem importados
        data_to_import = [
            {
                "subject": "MATEMÁTICA",
                "theme": "Espaço e Forma",
                "descriptors": [
                    {"code": "D1", "description": "Identificar a localização/movimentação de objeto em mapas, croquis e outras representações gráficas."},
                    {"code": "D2", "description": "Identificar propriedades comuns e diferenças entre figuras bidimensionais e tridimensionais, relacionando-as com as suas planificações."},
                    {"code": "D3", "description": "Identificar propriedades de triângulos pela comparação de medidas de lados e ângulos."},
                    {"code": "D4", "description": "Identificar relação entre quadriláteros por meio de suas propriedades."},
                    {"code": "D5", "description": "Reconhecer a conservação ou modificação de medidas (lados, perímetro, área) em ampliação e/ou redução de figuras poligonais."}
                ]
            },
            {
                "subject": "MATEMÁTICA",
                "theme": "Grandezas e Medidas",
                "descriptors": [
                    {"code": "D12", "description": "Resolver problema envolvendo o cálculo de perímetro de figuras planas."},
                    {"code": "D13", "description": "Resolver problema envolvendo o cálculo de área de figuras planas."},
                    {"code": "D14", "description": "Resolver problema envolvendo noções de volume."},
                    {"code": "D15", "description": "Resolver problema envolvendo relações entre diferentes unidades de medida."}
                ]
            },
            {
                "subject": "LÍNGUA PORTUGUESA",
                "theme": "Procedimentos de Leitura",
                "descriptors": [
                    {"code": "D1", "description": "Localizar informações explícitas em um texto."},
                    {"code": "D3", "description": "Inferir o sentido de uma palavra ou expressão."},
                    {"code": "D4", "description": "Inferir uma informação implícita em um texto."},
                    {"code": "D6", "description": "Identificar o tema de um texto."},
                    {"code": "D14", "description": "Distinguir um fato da opinião relativa a esse fato."}
                ]
            },
            {
                "subject": "HISTÓRIA",
                "theme": "O nascimento da República no Brasil",
                "descriptors": [
                    {"code": "EF09HI01", "description": "Descrever e contextualizar os principais aspectos sociais, culturais, econômicos e políticos da emergência da República no Brasil."},
                    {"code": "EF09HI02", "description": "Caracterizar e compreender os ciclos da história republicana, identificando particularidades da história local e regional até 1954."},
                    {"code": "EF09HI03", "description": "Identificar os mecanismos de inserção dos negros na sociedade brasileira pós-abolição."}
                ]
            },
            {
                "subject": "GEOGRAFIA",
                "theme": "A hegemonia europeia na economia",
                "descriptors": [
                    {"code": "EF09GE01", "description": "Analisar criticamente de que forma a hegemonia europeia foi exercida em várias regiões do planeta, notadamente em situações de conflito."},
                    {"code": "EF09GE02", "description": "Analisar a atuação das corporações internacionais e das organizações econômicas mundiais na vida da população em relação ao consumo."},
                    {"code": "EF09GE03", "description": "Identificar diferentes manifestações culturais de minorias étnicas como forma de compreender a multiplicidade cultural."}
                ]
            },
            {
                "subject": "CIÊNCIAS",
                "theme": "Matéria e energia",
                "descriptors": [
                    {"code": "EF09CI01", "description": "Investigar as mudanças de estado físico da matéria e explicar essas transformações com base no modelo de constituição submicroscópica."},
                    {"code": "EF09CI02", "description": "Comparar quantidades de reagentes e produtos envolvidos em transformações químicas."},
                    {"code": "EF09CI03", "description": "Identificar modelos que descrevem a estrutura da matéria (constituição do átomo e composição de moléculas simples)."}
                ]
            },
            {
                "subject": "INGLÊS",
                "theme": "Estratégias de leitura",
                "descriptors": [
                    {"code": "EF09LI01", "description": "Fazer uso de conhecimentos prévios e explorar pistas para formular hipóteses sobre o significado do texto."},
                    {"code": "EF09LI02", "description": "Ler e compreender textos em língua inglesa com diferentes propósitos."},
                    {"code": "EF09LI03", "description": "Avaliar o posicionamento do autor em textos lidos ou ouvidos."}
                ]
            },
            {
                "subject": "EDUCAÇÃO FÍSICA",
                "theme": "Esportes",
                "descriptors": [
                    {"code": "EF89EF01", "description": "Experimentar diferentes papéis (jogador, árbitro e técnico) e fruir os esportes de rede/parede, campo e taco, invasão e combate."},
                    {"code": "EF89EF02", "description": "Praticar um ou mais esportes de rede/parede, campo e taco, invasão e combate."}
                ]
            },
            {
                "subject": "ARTE",
                "theme": "Artes visuais",
                "descriptors": [
                    {"code": "EF69AR01", "description": "Pesquisar, apreciar e analisar formas distintas das artes visuais tradicionais e contemporâneas."},
                    {"code": "EF69AR02", "description": "Pesquisar e analisar diferentes estilos visuais, contextualizando-os no tempo e no espaço."}
                ]
            }
        ]

        total_inserted = 0

        for item in data_to_import:
            subject = get_subject(item['subject'])
            
            # Buscar ou criar o Theme
            theme = Theme.query.filter_by(name=item['theme'], matrix_id=matrix.id).first()
            if not theme:
                theme = Theme(name=item['theme'], matrix_id=matrix.id)
                db.session.add(theme)
                db.session.commit()
            
            for desc in item['descriptors']:
                # Verifica se o descritor já existe para evitar duplicatas
                existing_desc = Descriptor.query.filter_by(
                    code=desc['code'],
                    matrix_id=matrix.id,
                    school_year_id=school_year.id,
                    subject_id=subject.id
                ).first()
                
                if not existing_desc:
                    descriptor = Descriptor(
                        code=desc['code'],
                        type='Descritor' if desc['code'].startswith('D') else 'Habilidade',
                        description=desc['description'],
                        matrix_id=matrix.id,
                        school_year_id=school_year.id,
                        subject_id=subject.id,
                        theme_id=theme.id,
                        is_active=True
                    )
                    db.session.add(descriptor)
                    total_inserted += 1

        db.session.commit()
        print(f"Sucesso! {total_inserted} descritores/habilidades foram importados/atualizados para o 9º Ano.")

if __name__ == '__main__':
    run_import()
