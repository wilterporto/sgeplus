# SGE Plus - Sistema de Gestão Escolar e Avaliações em Larga Escala

O **SGE Plus** é uma plataforma moderna e completa para gestão educacional, projetada para atender a múltiplas redes de ensino (Secretarias Estaduais e Municipais de Educação) em um ambiente único e seguro (arquitetura *Multi-Tenant*).

O sistema oferece um controle rigoroso sobre a estrutura escolar, matrículas, e o desempenho de professores e alunos, destacando-se como uma ferramenta robusta para aplicação e monitoramento de exames e simulados alinhados às maiores matrizes de referência do país (SAEB e ENEM).

## 🚀 Principais Funcionalidades

### 🏢 Arquitetura Multi-Tenant
- Isolamento completo de dados entre diferentes clientes (Redes Estaduais vs Redes Municipais).
- Super Administradores podem alternar facilmente entre as redes para prestar suporte e administrar dados globais.

### 📊 Avaliações e Provas Dinâmicas
- **Matrizes de Referência Oficiais**: Suporte nativo para matrizes do ENEM, SAEB e parâmetros curriculares estaduais, com gestão completa de Eixos, Temas, Descritores e Habilidades.
- **Banco de Questões Inteligente**: Injeção e gestão de milhares de questões classificadas por componente curricular, ano letivo e nível de dificuldade, todas validadas por secretarias.
- **Geração Automática de Provas**: Criação ágil de simulados e avaliações em massa, permitindo filtrar e selecionar questões pelo Ano Escolar com base nos descritores vinculados.

### 👨‍🎓 Gestão de Matrículas e Acompanhamento Estudantil
- Controle detalhado de estudantes, abrangendo desde dados demográficos e localização geográfica, até acompanhamentos sensíveis como restrições alimentares.
- Acompanhamento especializado com controle de medidas antropométricas e informações sobre perfis específicos (Quilombolas, Indígenas, etc.).

### 🏫 Estrutura Curricular e Lotação
- Gestão completa de Unidades de Ensino (Escolas e Regionais/DREs).
- Cadastro de Professores e sua carga horária (Lotações) conectada às turmas e componentes curriculares específicos.

### 📈 Dashboards e Relatórios
- Painéis em tempo real mostrando o nível de proficiência, porcentagem de acertos/erros (Radar e Heatmaps) dos estudantes.
- Visão panorâmica sobre índices de abstenção e motivos de falta dos estudantes.

### ⚙️ Alta Performance e Importações em Lote
- Módulos avançados para importação via planilhas (Excel/CSV) utilizando Threads em segundo plano e filas otimizadas (ex: `bulk_save_objects`) com barra de progresso em tempo real, suportando milhares de registros de forma assíncrona.

## 🛠️ Tecnologias Utilizadas
- **Backend:** Python com Flask e SQLAlchemy (ORM).
- **Frontend:** Jinja2, Bootstrap 5, JavaScript Vanilla (Módulos Dinâmicos).
- **Banco de Dados:** SQLite (Desenvolvimento) / Neon.tech PostgreSQL (Produção).
- **Infraestrutura / Nuvem:** Render (Gunicorn, Deploy Automático).
- **Segurança:** Proteção CSRF, Rate Limiting, Gestão de Permissões baseada em Funções (Role-Based Access Control).

## ☁️ Deploy no Render
A aplicação já conta com o arquivo `render.yaml` e as dependências necessárias para implantação. Possui também um utilitário exclusivo (`/admin/migrate-test-data`) de migração, permitindo importar dados locais (SQLite) integralmente para o banco PostgreSQL de produção num único clique.
