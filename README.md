🔐 Gerenciador de Certificados Digitais
Sistema desktop para gestão, monitoramento e alerta automático de vencimento de certificados digitais (A1 e A3), desenvolvido para eliminar o risco de certificados vencidos e automatizar a comunicação com clientes.

Python
Tkinter
SQLite
License

📋 Sobre o projeto
O Gerenciador de Certificados Digitais é uma aplicação desktop em Python que centraliza o controle de certificados digitais A1 (.pfx/.pem) e A3 de clientes, enviando alertas automáticos de vencimento por e-mail e mantendo um histórico completo e auditável de todas as comunicações.

O sistema roda simultaneamente em dois ambientes:

Servidor — sempre ativo, verificando vencimentos e disparando e-mails automaticamente
Estação de manutenção — acesso via área de trabalho remota para cadastro e consulta
O banco de dados e os arquivos de certificado ficam armazenados em uma pasta de rede compartilhada, permitindo uso simultâneo por múltiplos usuários.

✨ Funcionalidades
Gestão de certificados
Cadastro de certificados A1 (upload de .pfx/.pem com leitura automática dos dados) e A3 (cadastro manual)
Armazenamento seguro do arquivo do certificado dentro do próprio banco de dados
Exportação do arquivo original a qualquer momento
Histórico de alterações por certificado
Segurança
Senha mestre de acesso ao sistema, protegida com hash SHA-256
Senhas de certificados armazenadas com criptografia Fernet
Visualização de senha em janela temporária (auto-fechamento em 30s) com opção de cópia
Alertas automáticos por e-mail
Verificação periódica de vencimentos com envio automático de lembretes
Dias de antecedência configuráveis por certificado (padrão: 15 dias)
Opção de desativar o lembrete individualmente por certificado
Reativação automática do ciclo de alerta ao renovar um certificado (nova data de vencimento)
Editor de template de e-mail com variáveis dinâmicas ({nome}, {tipo}, {vencimento}, {dias}, etc.) e pré-visualização
Solicitação de confirmação de leitura nos e-mails enviados
Log e auditoria
Registro completo de todos os e-mails enviados (data, certificado, destinatário, status, origem)
Marcação manual de e-mails como Lido/Pendente, sincronizada automaticamente com a flag de envio de lembrete do certificado
Filtros por período, certificado, status e situação de leitura
Exportação para Excel (ou CSV, como fallback automático)
Usabilidade
Ícone na bandeja do sistema — minimiza ao fechar, com menu de acesso rápido (Abrir, Verificar Agora, Iniciar com Windows, Sair)
Inicialização automática com o Windows (configurável)
Atualização automática da tabela a cada 30 segundos + botão de atualização manual
🛠️ Tecnologias utilizadas
Python 3
Tkinter — interface gráfica
SQLite3 — banco de dados local (modo DELETE + synchronous=FULL, otimizado para uso em rede compartilhada)
Cryptography (Fernet) — criptografia de senhas
pystray + Pillow — ícone e menu na bandeja do sistema
openpyxl — exportação de relatórios para Excel
smtplib — envio de e-mails via SMTP com STARTTLS
PyInstaller — geração do executável .exe



📦 Instalação
pip install pystray pillow cryptography openpyxl


Execute o sistema com:
python certific.py

Gerando o executável
pyinstaller --onefile --windowed --name "Certificados" certific.py




⚙️ Configuração
O sistema utiliza um banco SQLite (certificados.db) e um arquivo de chave (chave.key), criados automaticamente na primeira execução, no mesmo diretório do executável.

As configurações de envio de e-mail (servidor SMTP, porta, usuário) são definidas diretamente na interface do sistema.



📄 Licença
Projeto de uso interno / privado. Todos os direitos reservados.

Desenvolvido para automatizar e trazer mais segurança ao processo de gestão de certificados digitais.
