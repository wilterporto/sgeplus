# Dashboard de Nutrição Escolar

Este documento detalha o escopo e as funcionalidades reais implementadas na tela de "Dashboard - Nutrição Escolar", focada na análise avançada de dados antropométricos e estado nutricional dos estudantes. A equipe de desenvolvimento deve seguir rigorosamente as regras abaixo em qualquer manutenção desta tela.

## 1. Visão Geral
O dashboard oferece uma visão analítica abrangente sobre a saúde nutricional da rede educacional, cruzando dados antropométricos (IMC e Estatura) com critérios socioeconômicos e demográficos. A plataforma utiliza os padrões de crescimento da OMS (Z-Score) para diagnosticar o estado nutricional.

## 2. Indicadores Consolidados (Cards Superiores)
*   **Total de Alunos Aferidos e Não Aferidos** (com botões rápidos para exportação de alunos "Não Aferidos" e em "Risco Nutricional").
*   **Distribuição por Faixa Etária** (Comparativo absoluto e percentual entre "0 a 5 anos" e "5 a 19 anos").
*   **Distribuição por Sexo** (Comparativo entre Masculino e Feminino).

## 3. Filtros Avançados
A tela dispõe de um módulo colapsável para filtros detalhados, permitindo o cruzamento de dados:
*   **Demográficos:** Cor/Raça, Nacionalidade, Sexo, Faixa Etária.
*   **Socioeconômicos:** Renda Familiar, Bolsa Família.
*   **Geográficos e Contextuais:** Zona Residencial, Localização Diferenciada (Assentamento, Terra indígena, Quilombola), Região, Sub-Região, Classificação da Escola, Fonte de Energia.
*   **Saúde e Diversidade:** Possui Deficiência, Restrições Alimentares, Povo Indígena, Comunidade Quilombola.

## 4. Mapas e Gráficos Analíticos
*   **Mapa Interativo de Risco Nutricional:** Exibe o volume de alunos fora da faixa de Eutrofia distribuídos geograficamente pelas regionais.
*   **Detalhamento de Tabelas e Painéis Visuais:**
    *   **Quantitativo por Regional:** Apresentado em formato de **Tabela Dinâmica (Drill-Down)**. Permite que o usuário perfure os dados descendo os níveis de Regional -> Município -> Escola. A tabela deve conter subdivisões em abas e apresentar colunas de totais segmentadas por Faixa Etária (0 a 5 anos, 5 a 19 anos) e Sexo (Masculino, Feminino).
    *   **Quantitativo por Faixa Etária e Sexo:** Apresentado em formato de **Tabela Analítica Cruzada**. As linhas representam os diferentes Estados Nutricionais (Magreza, Eutrofia, Obesidade, etc). As colunas trazem os cruzamentos numéricos e percentuais por idades e gêneros, além da coluna de total geral.
    *   **Estado Nutricional (IMC/Idade):** Apresentado em **Gráfico de Rosca, Torta ou Barras Simples**. Demonstra visualmente a fatia populacional pertencente a cada classificação do IMC em relação ao total da rede.
    *   **Estatura/Idade:** Apresentado em **Gráfico de Rosca, Torta ou Barras Simples**. Demonstra o volume de alunos diagnosticados com Muito Baixa, Baixa ou Estatura Adequada.
    *   **Estado Nutricional Por Faixa Etária:** Apresentado em **Gráfico de Barras Empilhadas ou Agrupadas**. O eixo principal exibe as classificações nutricionais, enquanto as barras comparam lado a lado a incidência entre as idades (0-5 vs 5-19).
    *   **Estado Nutricional Por Sexo:** Apresentado em **Gráfico de Barras Empilhadas ou Agrupadas**. Similar ao anterior, porém colocando lado a lado o comparativo visual entre Masculino e Feminino para cada diagnóstico de IMC.
    *   **Estatura Por Faixa Etária:** Apresentado em **Gráfico de Barras Empilhadas ou Agrupadas**. Mostra a distribuição dos problemas de estatura cruzando com os recortes etários.
    *   **Estatura Por Sexo:** Apresentado em **Gráfico de Barras Empilhadas ou Agrupadas**. Demonstra como a adequação de estatura se divide entre meninos e meninas.
    *   **Comparativo Nutricional por Sexo (%):** Apresentado em formato de **Painel Lado a Lado com dois Gráficos do tipo Radar (Teia)**. O painel deve ter um gráfico exclusivo para o público Masculino e outro para o Feminino, plotando os pontos percentuais nos eixos da teia para facilitar o reconhecimento visual de padrões.
    *   **Comparativo Estatura por Sexo (%):** Apresentado também em **Painel com dois Gráficos Radar**. Utiliza a mesma lógica de teia para mapear as deficiências ou adequações de estatura isoladas por gênero.

## 5. Manual de Cálculos (Padrão OMS)
Modal acessível na tela com a metodologia científica (Escore-Z e Fórmula LMS) utilizada para classificar as faixas:
*   **IMC (0 a 5 anos):** Magreza Acentuada, Magreza, Eutrofia (Adequado), Risco de Sobrepeso, Sobrepeso, Obesidade.
*   **IMC (5 a 19 anos):** Magreza Acentuada, Magreza, Eutrofia (Adequado), Sobrepeso, Obesidade, Obesidade Grave.
*   **Estatura:** Muito Baixa Estatura, Baixa Estatura, Estatura Adequada.

## 6. Regras Gerais de Interface e Lançamento de Aferições
Caso haja telas satélites ligadas ao dashboard para inserção ou importação de novas avaliações antropométricas, aplicam-se as seguintes regras sistêmicas:
*   **Campos Obrigatórios:** Todo campo obrigatório de formulário deve ser assinalado com 1 único asterisco na cor vermelha (`<span style="color:red">*</span>`).
*   **Paginação:** Todas as tabelas de listagem (ex: histórico do aluno, listas nominais de risco) possuem o uso obrigatório de paginação com o limite de **30 registros por página**.
*   **Origem dos Dados:** O dashboard não requer rotina de importação externa; ele deve compilar os indicadores exclusivamente a partir dos registros de peso e altura já contidos no sistema, considerando sempre a última aferição (avaliação mais recente) de cada aluno.
*   **Exclusão de Registros:** A exclusão de qualquer dado cadastral só poderá ocorrer caso o registro **não possua dependência de dados** atrelada a ele em outras tabelas.
