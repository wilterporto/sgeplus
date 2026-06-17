# Detalhamento de Funcionalidades e Requisitos Técnicos

Este documento detalha as regras de negócio, especificações técnicas, modelagem de dados esperada e requisitos de interface para as funcionalidades solicitadas. Deve ser seguido rigorosamente pela equipe de desenvolvimento.

## 1. Motivos de Ausência

Sistema para gerenciar os motivos pelos quais os alunos podem faltar, alimentando diretamente o diário de classe e os relatórios de evasão/absenteísmo.

*   **Campos e Dados do Cadastro:**
    *   **Descrição** <span style="color:red">*</span> (Ex: Atestado Médico, Atraso do Transporte).
    *   **Categoria** <span style="color:red">*</span> (Ex: Saúde, Familiar, Transporte, Injustificada).
    *   **Ativo/Inativo** <span style="color:red">*</span> (Toggle para habilitar o uso no diário).
    *   **Observação Interna** (Opcional - para regras da secretaria).
    *   **Data de Criação e Usuário Responsável** (Registrados sistemicamente e visíveis na listagem).
*   **Listagem e Filtros:**
    *   Filtros obrigatórios: Busca por Descrição, Categoria e Status (Ativo/Inativo).
    *   **Paginação:** Obrigatório o limite de **30 registros por página**.
*   **Regras de Exclusão:**
    *   Validação de Integridade: O registro só poderá ser excluído (DELETE) caso **não possua dependência** de dados em outras tabelas (ex: não esteja vinculado a nenhum registro de frequência do aluno). Caso haja vínculo, apenas a inativação será permitida.

## 2. Matrizes, Temas, Descritores/Habilidades

Gestão da estrutura curricular que embasará as avaliações (ex: BNCC, matrizes estaduais). 

*   **Matrizes de Referência:**
    *   **Nome da Matriz** <span style="color:red">*</span> (Ex: SAEB 2023).
    *   **Fonte / Origem** <span style="color:red">*</span> (Federal, Estadual, Municipal ou Própria).
    *   **Composição a partir de Documento Base:** O sistema deve permitir que a rede monte uma nova matriz referencial derivando ou importando a estrutura de um **Documento Curricular Existente** (ex: importar os descritores da BNCC como base para a matriz municipal).
    *   **Ano/Etapa** <span style="color:red">*</span> (Ex: 9º Ano do Ensino Fundamental).
    *   **Disciplina** <span style="color:red">*</span> (Ex: Língua Portuguesa).
    *   **Vigência** <span style="color:red">*</span> (Ano de início e término de validade da matriz).
*   **Temas / Tópicos:**
    *   Vinculação obrigatória à Matriz.
    *   **Descrição do Tema** <span style="color:red">*</span> (Ex: Práticas de Leitura).
*   **Descritores / Habilidades:**
    *   Vinculação obrigatória ao Tema.
    *   **Código do Descritor** <span style="color:red">*</span> (Ex: D01, EF01MA01).
    *   **Descrição da Habilidade** <span style="color:red">*</span> (Ex: Localizar informações explícitas em um texto).
*   **Regras de Interface e Importação:**
    *   **Listagem Paginada:** Todas as tabelas desta seção devem possuir paginação estrita de **30 registros por página**.
    *   **Importação via Excel (.xlsx / .csv):**
        *   Ao selecionar o arquivo e clicar em "Importar", o modal de envio deverá ser **fechado imediatamente**.
        *   A interface deverá exibir uma **barra de progresso** em tempo real, informando o percentual de importação, o total de registros já importados e o total a ser importado.
        *   No backend, o processamento deve ser otimizado utilizando inserções em massa (*Bulk Insert*) para máximo desempenho.
*   **Regras de Exclusão:**
    *   Matrizes não podem ser excluídas se possuírem Temas associados; Temas se tiverem Descritores; e Descritores se já tiverem Questões vinculadas.

## 3. Banco de Questões

Repositório centralizado, rico e tagueado de questões que servirão de base para a montagem de avaliações e simulados.

*   **Campos de Classificação e Metadados:**
    *   **Matriz / Tema / Descritor** <span style="color:red">*</span> (Seleção dependente e aninhada).
    *   **Nível de Complexidade** <span style="color:red">*</span> (Fácil, Médio, Difícil).
    *   **Fonte / Origem** <span style="color:red">*</span> (Ex: ENEM, ENADE, Autoral, Prova Brasil).
    *   **Ano de Aplicação Origem** (Opcional - ano em que a questão foi criada/aplicada originalmente).
    *   **Tags / Palavras-chave** (Opcional - Múltiplas strings para facilitar a busca, ex: "Fração", "Regra de Três").
    *   **Status de Revisão** <span style="color:red">*</span> (Rascunho, Em Revisão, Aprovada, Arquivada).
*   **Fluxo de Criação e Aprovação (Permissões):**
    *   **Professores:** Têm permissão para criar e enviar novas questões para o banco. Ao serem salvas e finalizadas, essas questões assumem o status de "Em Revisão".
    *   **Secretaria/Gestores:** Possuem a permissão exclusiva de validar a qualidade pedagógica e alterar o status da questão para "Aprovada".
    *   **Uso nas Provas:** A Secretaria (e a rotina de geração automática) fará o uso **exclusivo** de questões com status "Aprovada" na montagem de provas e simulados oficiais.
*   **Conteúdo da Questão:**
    *   **Tipo da Questão** <span style="color:red">*</span> (Múltipla Escolha, Discursiva/Aberta).
    *   **Enunciado** <span style="color:red">*</span> (Campo *Rich Text* com suporte a equações matemáticas e formatação).
    *   **Imagens de Apoio** (Opcional).
    *   **Alternativas** <span style="color:red">*</span> (Para múltipla escolha, mínimo 2 opções de resposta).
    *   **Alternativa Correta** <span style="color:red">*</span> (Gabarito oficial do sistema).
    *   **Resolução Comentada** (Opcional - Texto explicativo do raciocínio para chegar à resposta).
*   **Interface e Ações:**
    *   **Listagem:** Limitada a **30 registros por página**.
    *   **Importação via Excel:** Segue a mesma regra da barra de progresso após fechamento do modal e *Bulk Insert* otimizado.
    *   **Exclusão:** Se a questão já constar em uma prova consolidada, a exclusão física é bloqueada. Deve-se alterar o status para "Arquivada".

## 4. Cadastro de Avaliações

Módulo estrutural para definir as diretrizes gerais das avaliações que serão aplicadas na rede ou escola, determinando sua composição.

*   **Parâmetros de Cadastro da Avaliação:**
    *   **Nome/Título da Avaliação** <span style="color:red">*</span> (Ex: 1º Simulado Bimestral, Avaliação Diagnóstica).
    *   **Período Letivo / Bimestre** <span style="color:red">*</span>.
    *   **Tipo de Avaliação** <span style="color:red">*</span> (Simulado, Prova Regular, Diagnóstica).
    *   **Composição Disciplinar (Estrutura):** <span style="color:red">*</span>
        *   **Único Componente (Monodisciplinar):** A avaliação será formada por questões de uma única disciplina (Ex: Apenas prova de Matemática).
        *   **Vários Componentes (Multidisciplinar):** A avaliação será um caderno único contendo questões de múltiplas disciplinas (Ex: Simulado da Rede com Português, Matemática e Ciências). O sistema deverá permitir a adição dinâmica das disciplinas que farão parte desta avaliação no ato do cadastro.
    *   **Público-Alvo (Série/Ano)** <span style="color:red">*</span>.
*   **Regras de Listagem e Exclusão:**
    *   Paginação padrão de 30 registros. Bloqueio de exclusão caso existam provas geradas para esta avaliação.

## 5. Provas (Montagem e Aplicação)

Módulo onde o usuário materializa o caderno de testes baseado na avaliação previamente cadastrada.

*   **Configuração e Agendamento da Aplicação:**
    *   **Vínculo com a Avaliação** <span style="color:red">*</span> (Ao selecionar, o sistema herda a estrutura, obrigando a prova a ser de um ou de vários componentes, filtrando as questões de acordo com a configuração da avaliação).
    *   **Modalidade** <span style="color:red">*</span> (Online via sistema, Impressa, ou Híbrida).
    *   **Data/Hora de Início** <span style="color:red">*</span> e **Data/Hora de Término** <span style="color:red">*</span> (Janela de aplicação).
    *   **Duração da Prova** (Opcional - Ex: Limite de 120 minutos após o aluno iniciar).
*   **Geração e Montagem da Prova (Regras de Negócio):**
    *   **Modo de Seleção Manual:** Abertura de modal listando o banco de questões (com filtros avançados e paginação estrita de 30 itens na busca). O usuário seleciona cada questão individualmente.
    *   **Modo de Geração Automática (Parametrizada):** O sistema sorteia as questões com base em critérios definidos pelo usuário:
        *   **Quantidade Total de Questões** e limite de questões **por Disciplina** <span style="color:red">*</span>.
        *   **Distribuição por Nível de Complexidade** <span style="color:red">*</span> (Ex: 30% Fáceis, 50% Médias, 20% Difíceis).
        *   **Distribuição por Descritor / Habilidade** (Ex: Solicitar que contenha exatamente 5 questões da habilidade D01 e 3 da D02).
        *   **Filtro por Fonte** (Ex: Gerar apenas com questões Autorais ou do ENEM).
        *   *Validação e Revisão:* O sistema sorteia as questões do banco (que estejam com status "Aprovada") e exibe um "Rascunho da Prova", permitindo ao autor revisar, remover e substituir qualquer questão sorteada antes do fechamento.
    *   **Configuração de Pontuação:**
        *   **Peso por Questão / Valor Total** <span style="color:red">*</span> (O sistema deve prever a soma dos pesos para compor a nota máxima da avaliação, validando contra o critério de aprovação da escola).
    *   **Regras de Aplicação (Modalidade Online):**
        *   Flag para **Embaralhamento Dinâmico** da ordem das questões e da ordem das alternativas (cada aluno visualizará a prova com ordem diferente).
        *   Restrição de Janela/Aba: Registrar no sistema se o aluno saiu da tela da prova para inibir colas (se tecnicamente viável).
    *   **Visibilidade de Resultados e Feedback:**
        *   Parametrizar se o aluno visualizará a nota final e a "Resolução Comentada" do gabarito imediatamente após enviar, ou apenas após a Data de Término limite da prova para a rede toda.
*   **Saída / Exportação (Modalidade Impressa):**
    *   Geração e download de PDF do "Caderno de Questões".
    *   **Provas e Cartões Customizados:** O sistema deve permitir a impressão de provas e cartões-resposta customizados, já contendo impresso o **Nome do Aluno**, sua **Turma** e um **QR Code** exclusivo em cada prova para identificação rápida e segura do estudante.
*   **Correção e Lançamento de Respostas:**
    *   **Resolução Online (Portal do Aluno):** O aluno poderá responder à prova de forma autônoma e direta por meio do seu Portal do Aluno, desde que a avaliação tenha sido gerada e parametrizada com essa possibilidade habilitada.
    *   **Correção Automatizada:** O sistema deverá permitir a leitura e correção automática da prova física utilizando a câmera de um dispositivo móvel ou através de imagem da prova escaneada (tecnologia OMR), utilizando o QR Code para vincular automaticamente o gabarito ao aluno.
    *   **Lançamento Manual:** O professor poderá registrar manualmente as respostas ou a nota final dos alunos no sistema, desde que possua a devida autorização/permissão.
*   **Listagem e Exclusão:**
    *   Listagem paginada (30 registros). Na grid de provas geradas, deverão ser exibidos em tempo real os indicadores daquela aplicação: **Percentual de Acertos, Percentual de Erros e Percentual de Ausências**.
    *   A exclusão é **bloqueada** integralmente caso exista qualquer resolução iniciada, resposta ou nota vinculada aos alunos.

## 6. Dashboard Integrado

Painel gerencial focado em BI (Business Intelligence) Educacional para análise aprofundada.

*   **Filtros Globais:**
    *   Período Letivo / Bimestre.
    *   Escola / Turma / Disciplina.
    *   Nível de Complexidade da Questão.
*   **Métricas e KPIs Principais:**
    *   Total de Avaliações Aplicadas vs. Previstas.
    *   Média Geral de Notas (Consolidado por Turma/Escola/Rede).
    *   Taxa de Evasão/Absenteísmo nas Provas (integrado com o banco de "Motivos de Ausência").
*   **Gráficos e Análise Pedagógica:**
    *   **Desempenho por Descritor/Habilidade:** Gráfico indicando o percentual de acerto e erro em cada habilidade avaliada, crucial para indicar a necessidade de retomada de conteúdo (ex: Habilidade D01 teve apenas 30% de proficiência).
    *   **Análise de Complexidade:** Desempenho dos alunos distribuído por nível de questão (Fácil, Médio, Difícil).
    *   **Comparativo Institucional:** Visão lado a lado entre turmas de uma mesma escola, ou entre escolas da rede.
*   **Acesso e Autorização (Controle por Perfil e Contexto):**
    *   **Professor:** Visualiza estatísticas exclusivamente de suas turmas vinculadas.
    *   **Contexto de Unidade Escolar (Diretor/Coordenador):** Será possível analisar e extrair relatórios contendo estritamente os dados da própria unidade, suas turmas e alunos. Não haverá acesso aos dados de outras unidades escolares.
    *   **Contexto de Regional (Diretoria de Ensino/Superintendência):** Assim como ocorre em redes estaduais, os responsáveis pela regional poderão analisar somente os dados dos municípios e escolas vinculadas à sua regional jurisdicionada.
    *   **Contexto Global (Secretaria/Gestor da Rede):** Visualiza os dados gerais e compara todas as regionais, escolas e municípios que compõem a rede inteira.
*   **Requisitos Técnicos do Dashboard:**
    *   Exportação dos relatórios e gráficos em PDF e planilhas Excel estruturadas.

## 7. Tela de Diagnóstico da Turma

Uma interface dedicada e aprofundada, permitindo que o professor e a coordenação analisem minuciosamente o resultado de uma turma específica após a aplicação de uma prova.

*   **Informações e Visões Obrigatórias:**
    *   **Cabeçalho da Avaliação:** Total de alunos matriculados, total de alunos presentes na prova, ausentes e a média geral alcançada pela turma.
    *   **Desempenho Individual (Aluno a Aluno):** Tabela (paginada a 30) listando os alunos com sua nota absoluta, percentual de acerto, e um indicativo do nível de proficiência alcançado (Ex: Crítico, Básico, Adequado).
    *   **Mapa de Calor por Questão/Descritor:** Uma matriz visual cruzando os Alunos (linhas) x Questões ou Habilidades (colunas). As células recebem cores (ex: verde para acerto, vermelho para erro). Isso evidencia se uma habilidade específica não foi absorvida pela maioria da turma (erro sistêmico) ou se foi um erro isolado do aluno.
    *   **Alerta de Alunos em Risco:** Destaque para os estudantes que ficaram muito abaixo do esperado e que demandam nivelamento ou intervenção pedagógica urgente.
    *   **Plano de Intervenção Automático:** A partir dos resultados consolidados da avaliação, o sistema deverá formular e propor um plano de intervenção direcionado, focado especificamente nos descritores e habilidades com menor desempenho da turma.
    *   **Sugestão de Prova de Reforço:** Integrado ao plano de intervenção, o sistema deverá sugerir (e permitir a geração com um clique de) uma nova avaliação de reforço. Essa prova será montada automaticamente buscando no Banco de Questões itens associados aos descritores mapeados como deficientes na análise da turma.
    *   **Exportação do Diagnóstico:** Geração de um "Boletim da Turma" em PDF para reuniões de conselho de classe ou conselho de pais e mestres.
