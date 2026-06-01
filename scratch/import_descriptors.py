import os
import sys

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Tenant, ReferenceMatrix, Subject, SchoolYear, Descriptor

bncc_data = {
    "Geografia": {
        "5º ANO": [
            ("EF05GE01", "Descrever e analisar dinâmicas populacionais na Unidade da Federação em que vive."),
            ("EF05GE02", "Identificar diferenças étnico-raciais e étnico-culturais e desigualdades sociais."),
            ("EF05GE03", "Identificar as formas e funções das cidades e analisar as mudanças sociais, econômicas e ambientais."),
            ("EF05GE04", "Reconhecer as características da cidade e analisar as interações entre a cidade e o campo."),
            ("EF05GE05", "Identificar e comparar as mudanças dos tipos de trabalho e desenvolvimento tecnológico na agropecuária.")
        ],
        "9º ANO": [
            ("EF09GE01", "Analisar criticamente de que forma a hegemonia europeia foi exercida em várias regiões do planeta."),
            ("EF09GE02", "Analisar a atuação das corporações internacionais e das organizações econômicas mundiais na vida da população."),
            ("EF09GE03", "Identificar diferentes manifestações culturais de minorias e grupos na defesa de direitos."),
            ("EF09GE04", "Relacionar diferenças de paisagens aos modos de viver de diferentes povos na Europa, Ásia e Oceania."),
            ("EF09GE05", "Analisar fatos e situações para compreender a integração mundial (econômica, política e cultural).")
        ]
    },
    "História": {
        "5º ANO": [
            ("EF05HI01", "Identificar os processos de formação das culturas e dos povos, relacionando-os com o espaço geográfico ocupado."),
            ("EF05HI02", "Identificar os mecanismos de organização do poder político com vistas à compreensão da ideia de Estado."),
            ("EF05HI03", "Analisar o papel das culturas e das religiões na composição identitária dos povos antigos."),
            ("EF05HI04", "Associar a noção de cidadania com os princípios de respeito à diversidade e à pluralidade."),
            ("EF05HI05", "Associar o conceito de cidadania à conquista de direitos dos povos e das sociedades.")
        ],
        "9º ANO": [
            ("EF09HI01", "Descrever e contextualizar os principais aspectos sociais, culturais, econômicos e políticos da Primeira República."),
            ("EF09HI02", "Caracterizar e compreender os ciclos da Guerra Fria e seus impactos nas sociedades."),
            ("EF09HI03", "Identificar os mecanismos de inserção dos negros na sociedade brasileira pós-abolição."),
            ("EF09HI04", "Discutir as motivações da adoção de políticas de cotas e ações afirmativas."),
            ("EF09HI05", "Identificar os processos de urbanização e modernização da sociedade brasileira e avaliar suas contradições.")
        ]
    },
    "Ciências": {
        "5º ANO": [
            ("EF05CI01", "Explorar fenômenos da vida cotidiana que evidenciem propriedades físicas dos materiais."),
            ("EF05CI02", "Aplicar os conhecimentos sobre as mudanças de estado físico da água para explicar o ciclo hidrológico."),
            ("EF05CI03", "Selecionar argumentos que justifiquem a importância da cobertura vegetal para a manutenção do ciclo da água."),
            ("EF05CI04", "Identificar os principais usos da água e outros materiais nas atividades cotidianas para discutir formas sustentáveis de utilização."),
            ("EF05CI05", "Construir propostas coletivas para um consumo mais consciente e criar soluções tecnológicas para o descarte adequado.")
        ],
        "9º ANO": [
            ("EF09CI01", "Investigar as mudanças de estado físico da matéria e explicar essas transformações com base no modelo de constituição submicroscópica."),
            ("EF09CI02", "Comparar quantidades de reagentes e produtos envolvidos em transformações químicas."),
            ("EF09CI03", "Identificar modelos que descrevem a estrutura da matéria (constituição do átomo e composição de moléculas simples)."),
            ("EF09CI04", "Planejar e executar experimentos que evidenciem que existem transformações químicas em que a massa se conserva."),
            ("EF09CI05", "Investigar os principais mecanismos de herança genética e aplicar as leis de Mendel.")
        ]
    }
}

def import_descriptors():
    app = create_app()
    with app.app_context():
        # Obter IDs necessários
        tenant = Tenant.query.filter(Tenant.name.ilike('%goiânia%')).first()
        if not tenant:
            print("Erro: Tenant SME Goiânia não encontrado!")
            return

        matrix = ReferenceMatrix.query.filter(ReferenceMatrix.name.ilike('%saeb%'), ReferenceMatrix.tenant_id == tenant.id).first()
        if not matrix:
            print("Matriz SAEB não encontrada para o tenant. Tentando matriz global...")
            matrix = ReferenceMatrix.query.filter(ReferenceMatrix.name.ilike('%saeb%'), ReferenceMatrix.tenant_id == None).first()
            if not matrix:
                print("Criando Matriz SAEB para o Tenant SME Goiânia.")
                matrix = ReferenceMatrix(name="SAEB", tenant_id=tenant.id)
                db.session.add(matrix)
                db.session.commit()

        # Mapear Subjects e SchoolYears
        subject_map = {}
        for s_name in bncc_data.keys():
            # Acentuação pode ser problema, buscar por partes do nome
            search_name = s_name.replace("ó", "o").replace("ê", "e")
            subj = Subject.query.filter(Subject.name.ilike(f"%{search_name}%")).first()
            if not subj and s_name == "Ciências":
                subj = Subject.query.filter(Subject.name.ilike("%ci_ncias%")).first()
            if not subj and s_name == "História":
                subj = Subject.query.filter(Subject.name.ilike("%hist_ria%")).first()
            
            if subj:
                subject_map[s_name] = subj.id
            else:
                print(f"Disciplina {s_name} não encontrada!")

        year_map = {}
        for y_name in ["5º ANO", "9º ANO"]:
            sy = SchoolYear.query.filter(SchoolYear.name.ilike(f"%{y_name[0]}%ano%")).first()
            if sy:
                year_map[y_name] = sy.id
            else:
                print(f"Ano Escolar {y_name} não encontrado!")

        descriptors_to_add = []
        count_added = 0
        count_existing = 0

        for subject_name, grades in bncc_data.items():
            subj_id = subject_map.get(subject_name)
            if not subj_id: continue

            for grade_name, desc_list in grades.items():
                year_id = year_map.get(grade_name)
                if not year_id: continue

                for code, description in desc_list:
                    # Verifica se já existe
                    existing = Descriptor.query.filter_by(
                        matrix_id=matrix.id,
                        subject_id=subj_id,
                        school_year_id=year_id,
                        code=code,
                        tenant_id=tenant.id
                    ).first()

                    if not existing:
                        desc = Descriptor(
                            matrix_id=matrix.id,
                            subject_id=subj_id,
                            school_year_id=year_id,
                            code=code,
                            description=description,
                            tenant_id=tenant.id
                        )
                        descriptors_to_add.append(desc)
                        count_added += 1
                    else:
                        count_existing += 1

        if descriptors_to_add:
            db.session.add_all(descriptors_to_add)
            db.session.commit()
            print(f"Sucesso: {count_added} descritores inseridos para a matriz {matrix.name} no tenant {tenant.name}.")
        else:
            print("Nenhum descritor novo a inserir.")
            
        print(f"Descritores já existentes ignorados: {count_existing}")

if __name__ == "__main__":
    import_descriptors()
