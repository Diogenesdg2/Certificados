import smtplib
import ssl
import threading
import schedule
import time
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config
import database
import crypto_utils

TEMPLATE_PADRAO = {
    "assunto": "[Certificado Digital] {nome} - vence em {dias} dia(s)",
    "corpo": """<html><body style="font-family:Arial,sans-serif;padding:20px">
<div style="border-left:6px solid {cor};padding:15px;background:#fafafa;border-radius:4px">
  <h2 style="color:{cor};margin:0 0 10px">Alerta de Certificado Digital</h2>
  <table style="border-collapse:collapse;width:100%">
    <tr><td style="padding:6px;font-weight:bold;width:160px">Nome/Titular:</td>
        <td style="padding:6px">{nome}</td></tr>
    <tr style="background:#f0f0f0">
        <td style="padding:6px;font-weight:bold">Tipo:</td>
        <td style="padding:6px">{tipo}</td></tr>
    <tr><td style="padding:6px;font-weight:bold">Responsavel:</td>
        <td style="padding:6px">{responsavel}</td></tr>
    <tr style="background:#f0f0f0">
        <td style="padding:6px;font-weight:bold">Vencimento:</td>
        <td style="padding:6px;color:{cor};font-weight:bold">{vencimento} - {situacao}</td></tr>
    <tr><td style="padding:6px;font-weight:bold">Observacao:</td>
        <td style="padding:6px">{obs}</td></tr>
  </table>
</div>
<p style="color:#777;font-size:12px;margin-top:20px">Mensagem automatica - Gerenciador de Certificados Digitais</p>
</body></html>"""
}

def carregar_config_email() -> dict:
    cfg = database.get_config("config_email", {})
    cfg = dict(cfg) if cfg else {}
    if cfg.get("senha"):
        cfg["senha"] = crypto_utils.descriptografar_senha(cfg["senha"])
    return cfg

def salvar_config_email(cfg: dict):
    cfg_para_salvar = dict(cfg)
    if cfg_para_salvar.get("senha"):
        cfg_para_salvar["senha"] = crypto_utils.criptografar_senha(cfg_para_salvar["senha"])
    database.set_config("config_email", cfg_para_salvar)

def carregar_template() -> dict:
    return database.get_config("template_email", TEMPLATE_PADRAO)

def salvar_template(t: dict):
    database.set_config("template_email", t)

def salvar_template_verificado(t: dict) -> tuple:
    try:
        database.set_config("template_email", t)
    except Exception as e:
        return False, f"Erro ao gravar no banco de dados:\n{e}"
    try:
        salvo = database.get_config("template_email", None)
    except Exception as e:
        return False, f"Nao foi possivel confirmar a gravacao:\n{e}"
    if not salvo or salvo.get("assunto") != t.get("assunto") or salvo.get("corpo") != t.get("corpo"):
        return False, "A gravacao nao foi confirmada no banco de dados."
    return True, "Template salvo com sucesso!"

def _cor_situacao(dias_restantes):
    if dias_restantes < 0:
        return "#c0392b", f"VENCIDO ha {abs(dias_restantes)} dia(s)"
    elif dias_restantes <= 7:
        return "#e74c3c", f"vence em {dias_restantes} dia(s) - CRITICO"
    elif dias_restantes <= 15:
        return "#e67e22", f"vence em {dias_restantes} dia(s)"
    else:
        return "#f39c12", f"vence em {dias_restantes} dia(s)"

def enviar_email(config_email, destinatarios, cert):
    if not config_email.get("smtp_host"):
        return False, "E-mail nao configurado."

    dias_restantes = (date.fromisoformat(cert["vencimento"]) - date.today()).days
    cor, situacao  = _cor_situacao(dias_restantes)
    template = carregar_template()

    variaveis = {
        "nome":        cert.get("nome", ""),
        "tipo":        cert.get("tipo", ""),
        "responsavel": cert.get("responsavel", "-"),
        "vencimento":  cert.get("vencimento", ""),
        "obs":         cert.get("obs", "-"),
        "dias":        str(dias_restantes),
        "situacao":    situacao,
        "cor":         cor,
    }

    try:
        assunto = template["assunto"].format(**variaveis)
        html    = template["corpo"].format(**variaveis)
    except KeyError as e:
        return False, f"Variavel invalida no template: {e}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"]    = config_email["usuario"]
    msg["To"]      = ", ".join(destinatarios)
    msg["Disposition-Notification-To"] = config_email["usuario"]
    msg["Return-Receipt-To"]           = config_email["usuario"]
    msg.attach(MIMEText(html, "html"))

    try:
        ctx   = ssl.create_default_context()
        porta = int(config_email.get("smtp_porta", 587))
        host  = config_email["smtp_host"]
        if porta == 465:
            with smtplib.SMTP_SSL(host, porta, context=ctx) as s:
                s.login(config_email["usuario"], config_email["senha"])
                s.sendmail(config_email["usuario"], destinatarios, msg.as_string())
        else:
            with smtplib.SMTP(host, porta, timeout=15) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
                s.login(config_email["usuario"], config_email["senha"])
                s.sendmail(config_email["usuario"], destinatarios, msg.as_string())
        return True, "E-mail enviado com sucesso."
    except Exception as e:
        return False, str(e)

def enviar_email_novo_certificado(config_email, destinatarios, cert):
    if not config_email.get("smtp_host"):
        return False, "E-mail não configurado."

    assunto = f"[Novo Certificado] {cert.get('nome', '')} - Disponível para uso"
    html = f"""<html><body style="font-family:Arial,sans-serif;padding:20px">
    <div style="border-left:6px solid #16a34a;padding:15px;background:#fafafa;border-radius:4px">
      <h2 style="color:#16a34a;margin:0 0 10px">Certificado Disponível</h2>
      <p>O certificado digital abaixo foi registado e já se encontra disponível para uso no sistema:</p>
      <table style="border-collapse:collapse;width:100%">
        <tr><td style="padding:6px;font-weight:bold;width:160px">Nome/Titular:</td>
            <td style="padding:6px">{cert.get("nome", "")}</td></tr>
        <tr style="background:#f0f0f0">
            <td style="padding:6px;font-weight:bold">Tipo:</td>
            <td style="padding:6px">{cert.get("tipo", "")}</td></tr>
        <tr><td style="padding:6px;font-weight:bold">Vencimento:</td>
            <td style="padding:6px">{cert.get("vencimento", "")}</td></tr>
        <tr style="background:#f0f0f0">
            <td style="padding:6px;font-weight:bold">Responsável:</td>
            <td style="padding:6px">{cert.get("responsavel", "-")}</td></tr>
      </table>
    </div>
    <p style="color:#777;font-size:12px;margin-top:20px">Mensagem automática - Gerenciador de Certificados</p>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"]    = config_email["usuario"]
    msg["To"]      = ", ".join(destinatarios)
    msg.attach(MIMEText(html, "html"))

    try:
        ctx   = ssl.create_default_context()
        porta = int(config_email.get("smtp_porta", 587))
        host  = config_email["smtp_host"]
        if porta == 465:
            with smtplib.SMTP_SSL(host, porta, context=ctx) as s:
                s.login(config_email["usuario"], config_email["senha"])
                s.sendmail(config_email["usuario"], destinatarios, msg.as_string())
        else:
            with smtplib.SMTP(host, porta, timeout=15) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
                s.login(config_email["usuario"], config_email["senha"])
                s.sendmail(config_email["usuario"], destinatarios, msg.as_string())
        return True, "E-mail enviado com sucesso."
    except Exception as e:
        return False, str(e)

def verificar_certificados(app=None):
    certs    = database.carregar_certificados()
    cfg_mail = carregar_config_email()
    hoje     = str(date.today())
    enviados = 0

    for cert in certs:
        try:
            dias = (date.fromisoformat(cert["vencimento"]) - date.today()).days
        except Exception:
            continue

        database.registrar_historico_db(cert["id"], "verificado", dias_restantes=dias)

        if not cert.get("enviar_alerta", 1):
            continue

        dias_inicio = int(cert.get("dias_alerta") or 30)
        enviar_para_cliente = (dias <= dias_inicio)
        enviar_para_escritorio = (dias in [15, 5, 1])
        
        if not (enviar_para_cliente or enviar_para_escritorio):
            continue
            
        if cert.get("ultimo_alerta") == hoje:
            continue

        destinatarios_final = []
        
        if enviar_para_cliente:
            dest_cliente = [e.strip() for e in cert.get("emails", "").split(",") if e.strip()]
            if not dest_cliente:
                dest_cliente = [cfg_mail.get("usuario", "")]
            destinatarios_final.extend(dest_cliente)
            
        if enviar_para_escritorio:
            str_emails_contab = cfg_mail.get("emails_contabilidade", "")
            str_emails_contab = str_emails_contab.replace(";", ",")
            lista_contabilidade = [e.strip() for e in str_emails_contab.split(",") if e.strip()]
            destinatarios_final.extend(lista_contabilidade)
            
        destinatarios = list(set([d for d in destinatarios_final if d]))

        if destinatarios:
            ok, msg = enviar_email(cfg_mail, destinatarios, cert)
            _tmpl = carregar_template()
            try:
                _assunto_log = _tmpl["assunto"].format(
                    nome=cert.get("nome",""), tipo=cert.get("tipo",""),
                    responsavel=cert.get("responsavel",""), vencimento=cert.get("vencimento",""),
                    obs=cert.get("obs",""), dias=str(dias), situacao="", cor=""
                )
            except Exception:
                _assunto_log = _tmpl.get("assunto", "")
            if ok:
                database.atualizar_ultimo_alerta(cert["id"], hoje)
                database.registrar_historico_db(cert["id"], "alerta_enviado", dias_restantes=dias, destinatarios=destinatarios)
                database.registrar_log_email(cert, destinatarios, _assunto_log, "Enviado", origem="automatico")
                enviados += 1
            else:
                database.registrar_historico_db(cert["id"], "erro_envio", dias_restantes=dias, erro=msg)
                database.registrar_log_email(cert, destinatarios, _assunto_log, "Erro", erro=msg, origem="automatico")

    if app:
        def _update():
            app.status_bar.config(text=f"  Ultima verificacao: {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  {enviados} alerta(s) enviado(s)")
            app.atualizar_tabela()
        app.after(0, _update)

def iniciar_scheduler(app):
    schedule.every().day.at("08:00").do(verificar_certificados, app=app)
    def loop():
        while True:
            schedule.run_pending()
            time.sleep(60)
    t = threading.Thread(target=loop, daemon=True)
    t.start()