# Guia de Implantação: Servidor Linux Ubuntu (SQLite)

Este documento detalha o passo a passo para hospedar o SGE Plus em um servidor virtual (VPS) ou máquina dedicada utilizando **Ubuntu Server**, **Nginx** (Proxy Reverso), **Gunicorn** (Servidor WSGI) e o banco de dados embutido **SQLite**.

---

## 🛠️ 1. Requisitos e Preparação Inicial

1. Acesse o seu servidor via SSH:
   ```bash
   ssh root@ip-do-seu-servidor
   ```
2. Atualize a lista de pacotes e o sistema:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
3. Instale as ferramentas e bibliotecas essenciais para o Python e o servidor web:
   ```bash
   sudo apt install python3 python3-venv python3-pip python3-dev build-essential nginx curl -y
   ```

---

## 📦 2. Configuração do Projeto e Ambiente Virtual

Recomendamos alocar a aplicação na pasta web padrão `/var/www/`.

1. Crie o diretório e ajuste as permissões no servidor:
   ```bash
   sudo mkdir -p /var/www/sgeplus
   sudo chown -R $USER:$USER /var/www/sgeplus
   ```
2. Transfira a pasta do seu projeto local para o servidor. Você pode utilizar um cliente SFTP (como WinSCP ou FileZilla) ou usar o comando SCP diretamente no terminal do seu Windows:
   ```powershell
   scp -r C:\Users\pc\source\sgeplus\* root@ip-do-seu-servidor:/var/www/sgeplus/
   ```
   *Dica: Você pode pular a cópia da pasta `.venv` local e da pasta `__pycache__`.*
   **Nota muito importante:** Como o sistema utilizará o SQLite, certifique-se de que a pasta `instance/` contendo o seu arquivo `.db` (banco de dados já alimentado) seja transferida corretamente para manter os seus dados.
3. Acesse a pasta no servidor e crie/ative o ambiente virtual (Virtual Environment):
   ```bash
   cd /var/www/sgeplus
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. Instale as dependências da aplicação, incluindo o servidor Gunicorn:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install gunicorn
   ```
5. Crie ou edite o arquivo de variáveis de ambiente:
   ```bash
   nano .env
   ```
   Adicione o seguinte conteúdo ao arquivo:
   ```env
   SECRET_KEY=sua_chave_secreta_aleatoria_e_longa_aqui
   FLASK_APP=run.py
   FLASK_ENV=production
   ```

---

## ⚙️ 3. Configurando o Gunicorn e o Systemd

O Gunicorn será o responsável por rodar a aplicação Python de forma contínua no background. Criaremos um serviço no sistema para ele iniciar automaticamente junto com o servidor.

1. Crie o arquivo de serviço do Systemd:
   ```bash
   sudo nano /etc/systemd/system/sgeplus.service
   ```
2. Insira as configurações abaixo (verifique se os caminhos estão corretos):
   ```ini
   [Unit]
   Description=Gunicorn instance to serve SGE Plus
   After=network.target

   [Service]
   User=www-data
   Group=www-data
   WorkingDirectory=/var/www/sgeplus
   Environment="PATH=/var/www/sgeplus/.venv/bin"
   EnvironmentFile=/var/www/sgeplus/.env
   ExecStart=/var/www/sgeplus/.venv/bin/gunicorn --workers 3 --bind unix:sgeplus.sock -m 007 wsgi:app

   [Install]
   WantedBy=multi-user.target
   ```
   *Nota: O usuário `www-data` precisará de permissão de escrita na pasta `instance/` para que o SQLite possa gravar e ler dados novos. Ajuste as permissões com:*
   ```bash
   sudo chown -R www-data:www-data /var/www/sgeplus/instance
   ```
3. Inicie e habilite o serviço:
   ```bash
   sudo systemctl start sgeplus
   sudo systemctl enable sgeplus
   sudo systemctl status sgeplus
   ```

---

## 🌐 4. Configurando o Proxy Reverso (Nginx)

O Nginx vai receber as requisições web na porta 80/443 e repassá-las para o Gunicorn (via Socket Unix).

1. Crie o arquivo de configuração do site:
   ```bash
   sudo nano /etc/nginx/sites-available/sgeplus
   ```
2. Adicione o bloco de servidor (substitua `seu_dominio.com.br` pelo IP do servidor ou domínio configurado):
   ```nginx
   server {
       listen 80;
       server_name seu_dominio.com.br www.seu_dominio.com.br;

       location / {
           include proxy_params;
           proxy_pass http://unix:/var/www/sgeplus/sgeplus.sock;
       }

       # Servir arquivos estáticos diretamente pelo Nginx para melhor performance
       location /static/ {
           alias /var/www/sgeplus/app/static/;
           expires 30d;
       }
   }
   ```
3. Habilite a configuração criando um link simbólico:
   ```bash
   sudo ln -s /etc/nginx/sites-available/sgeplus /etc/nginx/sites-enabled
   ```
4. Verifique se há erros de sintaxe e reinicie o Nginx:
   ```bash
   sudo nginx -t
   sudo systemctl restart nginx
   ```

---

## 🔒 5. Firewall e Certificado de Segurança (HTTPS)

1. Ajuste o firewall (UFW) para permitir tráfego HTTP, HTTPS e SSH:
   ```bash
   sudo ufw allow OpenSSH
   sudo ufw allow 'Nginx Full'
   sudo ufw enable
   ```
2. Para instalar o certificado SSL gratuito via Let's Encrypt (requer que o DNS do seu domínio já esteja apontando para o servidor):
   ```bash
   sudo apt install certbot python3-certbot-nginx -y
   sudo certbot --nginx -d seu_dominio.com.br -d www.seu_dominio.com.br
   ```
   Siga as instruções na tela e escolha a opção para redirecionar todo tráfego HTTP para HTTPS (Opção 2).

---

## 🔄 6. Manutenção Contínua

Sempre que você alterar o código localmente, transfira os arquivos que foram modificados (via SCP/WinSCP/FileZilla) substituindo os arquivos correspondentes na pasta `/var/www/sgeplus` do servidor. Após transferir as atualizações, execute os comandos abaixo no servidor para refletir as mudanças em produção:

```bash
cd /var/www/sgeplus
source .venv/bin/activate
pip install -r requirements.txt  # (Execute caso tenha adicionado novas dependências)
sudo systemctl restart sgeplus
```
