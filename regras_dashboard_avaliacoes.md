# Dashboard de Avaliações Externas - Dicionário de Dados e Regras de Negócio

Este documento detalha as métricas, gráficos e as regras de negócio utilizadas para o cálculo dos dados apresentados no **Dashboard de Avaliações Externas** do sistema SGE Plus.

## 1. Filtros Globais
O dashboard permite o refinamento dos dados exibidos através dos seguintes filtros em cascata (Drilldown):
- **Avaliação (Obrigatório):** Define a avaliação externa base para a análise.
- **Regional:** Filtra os resultados por regionais de ensino.
- **Município:** Filtra os resultados por município (dependente da Regional).
- **Escola:** Filtra os resultados por unidade escolar (dependente do Município).
- **Disciplina:** Permite o filtro dos dados do dashboard para uma disciplina específica.

---

## 2. Indicadores Principais (Cards)

### 2.1. Total de Participantes
- **Descrição:** Número total de alunos vinculados à avaliação e que compõem o universo da análise, de acordo com os filtros aplicados.
- **Regra:** Soma total de todos os registros de alunos encontrados para a avaliação (independentemente de terem finalizado ou não).

### 2.2. Participação
- **Descrição:** Quantidade absoluta e o percentual de alunos que efetivamente realizaram e concluíram a avaliação.
- **Regra:** 
  - **Filtro base:** `ALT_FINALIZADO == 1` (ou status equivalente de conclusão).
  - **Cálculo Percentual:** `(Alunos Finalizados / Total de Participantes) * 100`.

### 2.3. Ausências Registradas
- **Descrição:** Quantidade absoluta e percentual de alunos que faltaram ou não realizaram a avaliação.
- **Regra:** 
  - **Filtro base:** `ALT_FINALIZADO == 0` (ou ausência de status de conclusão).
  - **Cálculo Percentual:** `(Alunos Não Finalizados / Total de Participantes) * 100`.

### 2.4. Proficiência Média
- **Descrição:** Percentual médio de acertos geral dos alunos que realizaram a avaliação.
- **Regra:** 
  - Considera apenas alunos participantes (`ALT_FINALIZADO == 1`).
  - **Cálculo:** Média das notas/percentuais de acerto individuais de todos os alunos filtrados.

### 2.5. Alunos em Alerta
- **Descrição:** Quantidade absoluta e percentual de alunos que obtiveram um desempenho considerado insatisfatório ou crítico (Abaixo do Básico).
- **Regra:** 
  - Alunos participantes cujo percentual de acerto individual seja **menor que 25%**.
  - **Cálculo Percentual:** `(Alunos Abaixo do Básico / Total de Participantes) * 100`.

### 2.6. Status Rede
- **Descrição:** Classifica o desempenho global da rede (ou do filtro selecionado) com base na **Proficiência Média**.
- **Regra (Níveis de Status):**
  - **Crítico:** Proficiência Média **abaixo de 50%**.
  - **Em evolução:** Proficiência Média **de 50% a 69,9%**.
  - **Excelente:** Proficiência Média **igual ou superior a 70%**.

---

## 3. Gráficos de Análise e Desempenho

### 3.1. Desempenho Geral (Gráfico Drilldown)
- **Descrição:** Gráfico de barras interativo que exibe a proficiência média. Permite a navegação em níveis hierárquicos: *Rede > Regional > Município > Escola > Aluno*.
- **Ordenação (Filtros disponíveis):**
  - **Ordem Alfabética:** Crescente pelo nome da localidade/escola/aluno.
  - **Maior Desempenho (Acertos):** Ordem decrescente de proficiência (Maiores notas primeiro).
  - **Menor Desempenho (Acertos):** Ordem crescente de proficiência (Menores notas primeiro).
  - **Maior / Menor % de Erros:** Ordena baseando-se na taxa de erros computada.
  - **Maior / Menor % Não Fizeram:** Ordena pela taxa de ausência/não realização em cada agrupamento.

### 3.2. Distribuição de Proficiência (Gráfico Donut)
- **Descrição:** Segmenta os alunos participantes em quatro faixas de desempenho.
- **Regras de Faixa:**
  - **Abaixo do Básico:** Desempenho < 25%.
  - **Básico:** Desempenho entre 25% e 49,9%.
  - **Proficiente:** Desempenho entre 50% e 74,9%.
  - **Avançado:** Desempenho >= 75%.

### 3.3. Desempenho por Cor/Raça e Sexo (Gráficos de Barras)
- **Descrição:** Exibe o comparativo de desempenho médio quebrando o público por informações demográficas (Cor/Raça e Gênero).
- **Regra Adicional:** Estes gráficos tabulam informações tanto da proficiência média quanto podem refletir índices de não participação (`ALT_FINALIZADO == 0`) por categoria populacional.

---

## 4. Análise de Competências

Esta seção divide as métricas em três colunas comparativas. Para garantia de dados limpos, a regra de negócio exclui registros corrompidos com o nome da competência "Não informado" ou vazia.

### 4.1. 10 Melhores Competências
- **Descrição:** Exibe as 10 habilidades/competências nas quais os alunos obtiveram as maiores médias de acerto.
- **Regra:** Ordenação decrescente pela taxa de acerto.

### 4.2. 10 Piores Competências
- **Descrição:** Exibe as 10 habilidades/competências com as piores taxas médias de acerto, independentemente de haver acertos ou não.
- **Regra:** Ordenação crescente pela taxa de acerto (piores médias no topo).

### 4.3. Competências sem acertos
- **Descrição:** Destaca criticamente as competências onde a rede/escola obteve exatamente 0% de acerto.
- **Regra:** 
  - Filtra rigorosamente por `Taxa de Acerto == 0`.
  - Exibe o limite das 10 primeiras ocorrências. 
  - Caso nenhuma competência possua 0% de acerto, o gráfico exibirá o rótulo "Nenhuma".

---

## 5. Justificativas de Ausência
- **Descrição:** Exibe o detalhamento dos motivos informados para os alunos que não realizaram a avaliação (`ALT_FINALIZADO == 0`).
- **Regra:** Agrupa e conta a frequência das justificativas registradas no banco de dados para a prova selecionada.
