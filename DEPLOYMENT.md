# Guia de Publicação Gratuita (Render + Neon.tech)

Este documento orienta o passo a passo para colocar o SGE Plus no ar sem custos iniciais, conectando a aplicação web (Flask) no **Render** e o banco de dados (PostgreSQL) no **Neon.tech**.

---

## 🐘 1. Configurando o Banco de Dados (Neon.tech)

O SGE Plus utiliza o banco de dados Neon.tech por oferecer um plano gratuito excelente para desenvolvimento e produção leve (Serverless Postgres).

1. Acesse [Neon.tech](https://neon.tech/) e crie sua conta.
2. No painel, clique em **"Create Project"**.
3. Defina um nome para o projeto (ex: `sgeplus-db`) e selecione a região mais próxima (ex: US East).
4. Ao concluir, o Neon irá mostrar a sua **Connection String** (URL de Conexão). Ela tem o seguinte formato:
   `postgresql://usuario:senha@ep-nome-xyz.us-east-2.aws.neon.tech/neondb?sslmode=require`
5. Copie e guarde essa URL em um local seguro. Ela será necessária para conectar o sistema ao banco.

---

## 🚀 2. Publicando o Aplicativo (Render)

A aplicação já está pré-configurada para o Render (Blueprint) graças ao arquivo `render.yaml` na raiz do projeto.

1. Acesse [Render.com](https://render.com/) e crie sua conta usando seu **GitHub**.
2. No painel inicial (Dashboard), clique em **"New"** e escolha **"Blueprint"**.
3. Conecte sua conta do GitHub e selecione o repositório do SGE Plus (`wilterporto/sgeplus`).
4. O Render vai ler o arquivo `render.yaml` e detectar que é um Web Service em Python.
5. Na tela seguinte, ele pedirá para preencher as **Variáveis de Ambiente** obrigatórias:
   - **`DATABASE_URL`**: Cole aqui a URL de conexão copiada do banco Neon.tech. *(Dica: Não se preocupe se estiver `postgres://` ou `postgresql://`, a aplicação já corrige isso automaticamente)*.
   - **`SECRET_KEY`**: Insira uma senha longa e aleatória (ex: `MinhaSenhaSuperSecreta!2026`). Isso é exigido pelo Flask para criptografia de cookies e sessões de segurança.
6. Role a tela até o final e clique em **"Apply"** (ou "Create").
7. O Render começará a compilar e instalar os pacotes (isso levará alguns minutos). Quando aparecer "Deploy Live", seu site estará no ar!

> [!TIP]
> No plano gratuito do Render, o sistema entra em "estado de sono" após 15 minutos sem acessos. O primeiro clique de um usuário fará o servidor "acordar", demorando de 30 a 50 segundos para abrir. Nos acessos subsequentes, ele será rápido.

---

## 📦 3. Povoando o Banco com os Dados de Teste

Assim que o Render concluir a instalação e o SGE Plus estiver online, seu banco de dados no Neon.tech estará completamente vazio (sem usuários, provas ou configurações).

Como nós já fatiamos e preparamos o banco SQLite de mais de 280 MB no código, nós precisamos instruir o SGE Plus na nuvem a migrá-lo:

1. Acesse a URL do seu sistema gerada pelo Render (ex: `https://sgeplus.onrender.com`).
2. Acesse a rota de administração (mesmo com o banco vazio, a tela de tenants possui o recurso de migração).
   Se não conseguir acesso direto pela interface devido a não ter usuários, acesse a URL direta:
   **`https://SEU_DOMINIO.onrender.com/admin/tenants`**
3. Clique no botão azul **"Migrar Dados de Teste"**.
4. Neste instante, em *background*, o servidor fará o seguinte:
   - Juntará as 5 fatias `.part` do seu banco em um único arquivo `.gz`.
   - Descompactará o `.gz` para recriar os 281 MB originais localmente no Render.
   - Lerá as tabelas do SQLite local e inserirá **todos** os mais de 35.000 resultados, usuários, descritores e avaliações diretamente no **PostgreSQL (Neon.tech)** de forma automatizada.
5. Esse processo pode demorar alguns minutos. Monitore pelo log do Render (na aba "Logs" no painel deles) para ver o andamento e quando ele avisar "Migração concluída com sucesso!".

Pronto! Seu ambiente SGE Plus de nuvem estará idêntico ao seu ambiente local, com todas as avaliações SAETO corrigidas e configuradas.
