import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import os
import sys
import threading
import time
from datetime import datetime, date
import winreg

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_DISPONIVEL = True
except ImportError:
    TRAY_DISPONIVEL = False

try:
    from tkcalendar import DateEntry
    TKCALENDAR_DISPONIVEL = True
except ImportError:
    TKCALENDAR_DISPONIVEL = False

# Importação para os Gráficos do Dashboard
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    from matplotlib.gridspec import GridSpec
    MATPLOTLIB_DISPONIVEL = True
except ImportError:
    MATPLOTLIB_DISPONIVEL = False

# Importando nossos modulos refatorados
import config
import database
import crypto_utils
import email_service

STARTUP_REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_APP_NAME = "GerenciadorCertificados"

def _startup_habilitado() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, STARTUP_APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False

def _habilitar_startup():
    caminho = os.path.abspath(sys.argv[0])
    if caminho.endswith(".py"):
        exe = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(exe):
            exe = sys.executable
        valor = f'"{exe}" "{caminho}"'
    else:
        valor = f'"{caminho}"'
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, STARTUP_APP_NAME, 0, winreg.REG_SZ, valor)
    winreg.CloseKey(key)

def _desabilitar_startup():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, STARTUP_APP_NAME)
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass

def pedir_senha_mestre(parent=None) -> bool:
    if not crypto_utils.senha_mestre_definida():
        win = tk.Toplevel(parent)
        win.title("Definir Senha Mestre")
        win.resizable(False, False)
        win.grab_set()
        win.geometry("360x220")

        hdr = tk.Frame(win, bg=config.COR_PRIMARIA, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Definir Senha Mestre", bg=config.COR_PRIMARIA, fg="#ffffff", font=("Segoe UI", 10, "bold")).pack(side="left", padx=12, pady=10)
        ttk.Label(win, text="Crie uma senha mestre para proteger\na visualizacao das senhas dos certificados.", font=("Segoe UI", 9), justify="center").pack(pady=(14, 6))

        f = ttk.Frame(win)
        f.pack(pady=4)
        ttk.Label(f, text="Nova senha:").grid(row=0, column=0, sticky="e", padx=6, pady=4)
        v1 = tk.StringVar()
        ttk.Entry(f, textvariable=v1, show="*", width=22).grid(row=0, column=1, pady=4)
        ttk.Label(f, text="Confirmar:").grid(row=1, column=0, sticky="e", padx=6, pady=4)
        v2 = tk.StringVar()
        ttk.Entry(f, textvariable=v2, show="*", width=22).grid(row=1, column=1, pady=4)

        resultado = [False]
        def _confirmar():
            s1, s2 = v1.get().strip(), v2.get().strip()
            if not s1:
                messagebox.showwarning("Atencao", "Digite uma senha.", parent=win)
                return
            if s1 != s2:
                messagebox.showerror("Erro", "As senhas nao conferem.", parent=win)
                return
            crypto_utils.definir_senha_mestre(s1)
            resultado[0] = True
            win.destroy()

        bf = ttk.Frame(win)
        bf.pack(pady=8)
        ttk.Button(bf, text="Definir", command=_confirmar).pack(side="left", padx=5)
        ttk.Button(bf, text="Cancelar", command=win.destroy).pack(side="left", padx=5)
        win.wait_window()
        return resultado[0]
    else:
        senha = simpledialog.askstring("Senha Mestre", "Digite a senha mestre:", show="*", parent=parent)
        if senha is None:
            return False
        if not crypto_utils.verificar_senha_mestre(senha):
            messagebox.showerror("Erro", "Senha mestre incorreta.", parent=parent)
            return False
        return True


class JanelaConfigEmail(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Configuracao de E-mail")
        self.resizable(False, False)
        self.grab_set()
        self._build()
        self._carregar()

    def _build(self):
        hdr = tk.Frame(self, bg=config.COR_PRIMARIA, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Configuracao de E-mail SMTP", bg=config.COR_PRIMARIA, fg="#ffffff", font=("Segoe UI", 10, "bold")).pack(side="left", padx=12, pady=10)
        pad = {"padx": 10, "pady": 5}
        frame = ttk.LabelFrame(self, text="Parametros SMTP", padding=15)
        frame.pack(padx=20, pady=15, fill="x")

        campos = [
            ("Servidor SMTP:",    "smtp_host",  False),
            ("Porta SMTP:",       "smtp_porta", False),
            ("Usuario (e-mail):", "usuario",    False),
            ("Senha:",            "senha",      True),
            ("E-mails Contab. (separar por ;):", "emails_contabilidade", False),
            ("E-mails Novo Cert. (separar por ;):", "emails_novo_cert", False),
        ]
        self.vars = {}
        for i, (label, key, pwd) in enumerate(campos):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w", **pad)
            v = tk.StringVar()
            show = "*" if pwd else ""
            ttk.Entry(frame, textvariable=v, width=35, show=show).grid(row=i, column=1, **pad)
            self.vars[key] = v

        ttk.Label(frame, text="Gmail: smtp.gmail.com  |  Porta: 465  |  Use App Password", foreground="#888", font=("Arial", 8)).grid(row=len(campos), column=0, columnspan=2, pady=(0, 5))

        bf = ttk.Frame(self)
        bf.pack(pady=(0, 15))
        ttk.Button(bf, text="Salvar",   command=self._salvar).pack(side="left", padx=5)
        ttk.Button(bf, text="Testar",   command=self._testar).pack(side="left", padx=5)
        ttk.Button(bf, text="Cancelar", command=self.destroy).pack(side="left", padx=5)

    def _carregar(self):
        cfg = email_service.carregar_config_email()
        for k, v in self.vars.items():
            v.set(cfg.get(k, ""))

    def _salvar(self):
        cfg = {k: v.get().strip() for k, v in self.vars.items()}
        email_service.salvar_config_email(cfg)
        messagebox.showinfo("Salvo", "Configuracao salva com sucesso!", parent=self)

    def _testar(self):
        cfg = {k: v.get().strip() for k, v in self.vars.items()}
        cert_teste = {"id": "teste", "nome": "Certificado de Teste", "tipo": "A1", "responsavel": "Teste", "vencimento": str(date.today()), "obs": "E-mail de teste do sistema"}
        ok, msg = email_service.enviar_email(cfg, [cfg.get("usuario", "")], cert_teste)
        if ok: messagebox.showinfo("Sucesso", "E-mail de teste enviado!", parent=self)
        else: messagebox.showerror("Erro", f"Falha ao enviar:\n{msg}", parent=self)


class JanelaCertificado(tk.Toplevel):
    def __init__(self, parent, cert=None, callback=None):
        super().__init__(parent)
        self.cert = cert
        self.callback = callback
        self.title("Editar Certificado" if cert else "Novo Certificado")
        self.resizable(False, False)
        self.grab_set()
        self._build()
        if cert: self._preencher()

    def _build(self):
        pad = {"padx": 10, "pady": 6}
        nb = ttk.Notebook(self)
        nb.pack(padx=15, pady=10, fill="both")

        f_geral = ttk.Frame(nb, padding=10)
        nb.add(f_geral, text=" Dados Gerais ")
        ttk.Label(f_geral, text="Tipo:").grid(row=0, column=0, sticky="w", **pad)
        self.var_tipo = tk.StringVar(value="A1")
        ttk.Combobox(f_geral, textvariable=self.var_tipo, values=["A1", "A3"], state="readonly", width=10).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(f_geral, text="Nome / Razao Social:").grid(row=1, column=0, sticky="w", **pad)
        self.var_nome = tk.StringVar()
        ttk.Entry(f_geral, textvariable=self.var_nome, width=38).grid(row=1, column=1, **pad)
        ttk.Label(f_geral, text="Responsavel:").grid(row=2, column=0, sticky="w", **pad)
        self.var_resp = tk.StringVar()
        ttk.Entry(f_geral, textvariable=self.var_resp, width=38).grid(row=2, column=1, **pad)
        ttk.Label(f_geral, text="Vencimento (AAAA-MM-DD):").grid(row=3, column=0, sticky="w", **pad)
        self.var_venc = tk.StringVar()
        ttk.Entry(f_geral, textvariable=self.var_venc, width=20).grid(row=3, column=1, sticky="w", **pad)
        ttk.Label(f_geral, text="Observacao:").grid(row=4, column=0, sticky="w", **pad)
        self.var_obs = tk.StringVar()
        ttk.Entry(f_geral, textvariable=self.var_obs, width=38).grid(row=4, column=1, **pad)
        ttk.Label(f_geral, text="E-mails p/ alerta\n(separe por virgula):").grid(row=5, column=0, sticky="w", **pad)
        self.var_emails = tk.StringVar()
        ttk.Entry(f_geral, textvariable=self.var_emails, width=38).grid(row=5, column=1, **pad)

        f_alerta = ttk.LabelFrame(f_geral, text="Configurações de Lembrete", padding=(10, 6))
        f_alerta.grid(row=6, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 2))
        self.var_enviar_alerta = tk.BooleanVar(value=True)
        chk = ttk.Checkbutton(f_alerta, text="Enviar lembrete de vencimento por e-mail", variable=self.var_enviar_alerta, command=self._toggle_alerta)
        chk.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.lbl_dias_alerta = ttk.Label(f_alerta, text="Iniciar envio (dias antes):")
        self.lbl_dias_alerta.grid(row=1, column=0, sticky="w", padx=(0, 6))
        self.var_dias_alerta = tk.StringVar(value="30")
        self.spin_dias_alerta = ttk.Spinbox(f_alerta, textvariable=self.var_dias_alerta, from_=1, to=365, width=6, state="normal")
        self.spin_dias_alerta.grid(row=1, column=1, sticky="w")
        ttk.Label(f_alerta, text="dia(s) antes do vencimento", foreground="#64748b").grid(row=1, column=2, sticky="w", padx=6)

        self.f_a1 = ttk.Frame(nb, padding=10)
        nb.add(self.f_a1, text=" Arquivo A1 ")
        ttk.Label(self.f_a1, text="Arquivo (.pfx / .pem):").grid(row=0, column=0, sticky="w", **pad)
        self.var_arquivo = tk.StringVar()
        ttk.Entry(self.f_a1, textvariable=self.var_arquivo, width=32).grid(row=0, column=1, **pad)
        ttk.Button(self.f_a1, text="...", command=self._browse).grid(row=0, column=2, padx=2)
        ttk.Label(self.f_a1, text="Senha do arquivo:").grid(row=1, column=0, sticky="w", **pad)
        self.var_senha = tk.StringVar()
        f_senha = ttk.Frame(self.f_a1)
        f_senha.grid(row=1, column=1, sticky="w", **pad)
        self.entry_senha = ttk.Entry(f_senha, textvariable=self.var_senha, show="*", width=26)
        self.entry_senha.pack(side="left")
        self._senha_visivel = False
        ttk.Button(f_senha, text="Ver", width=4, command=self._toggle_senha).pack(side="left", padx=2)
        ttk.Label(self.f_a1, text="A senha e armazenada de forma criptografada.\nO arquivo do certificado sera salvo internamente no banco de dados.", foreground="#888", font=("Arial", 8)).grid(row=2, column=0, columnspan=3, sticky="w", padx=10)

        f_btns_a1 = ttk.Frame(self.f_a1)
        f_btns_a1.grid(row=3, column=0, columnspan=3, pady=10)
        ttk.Button(f_btns_a1, text="Ler certificado automaticamente", command=self._ler_arquivo).pack(side="left", padx=4)
        self.btn_exportar = ttk.Button(f_btns_a1, text="Exportar arquivo salvo", command=self._exportar_arquivo)
        self.btn_exportar.pack(side="left", padx=4)
        self.lbl_arquivo_salvo = ttk.Label(self.f_a1, text="", foreground="#16a34a", font=("Segoe UI", 8, "italic"))
        self.lbl_arquivo_salvo.grid(row=4, column=0, columnspan=3, sticky="w", padx=10)

        bf = ttk.Frame(self)
        bf.pack(pady=(0, 12))
        ttk.Button(bf, text="Salvar",   command=self._salvar).pack(side="left", padx=6)
        ttk.Button(bf, text="Cancelar", command=self.destroy).pack(side="left", padx=6)

    def _toggle_alerta(self):
        estado = "normal" if self.var_enviar_alerta.get() else "disabled"
        self.spin_dias_alerta.config(state=estado)
        self.lbl_dias_alerta.config(foreground="" if self.var_enviar_alerta.get() else "#94a3b8")

    def _toggle_senha(self):
        if not pedir_senha_mestre(self): return
        self._senha_visivel = not self._senha_visivel
        self.entry_senha.config(show="" if self._senha_visivel else "*")

    def _exportar_arquivo(self):
        b64 = getattr(self, "_arquivo_b64", None) or (self.cert.get("arquivo_b64") if self.cert else None)
        if not b64:
            messagebox.showwarning("Atencao", "Nenhum arquivo armazenado neste certificado.", parent=self)
            return
        ext = ".pfx" if self.cert and "pfx" in self.cert.get("arquivo_ext", "pfx") else ".pem"
        dest = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[("Certificado", f"*{ext}"), ("Todos", "*.*")], initialfile=f"{self.cert.get('nome','certificado')}{ext}" if self.cert else f"certificado{ext}")
        if dest:
            try:
                crypto_utils.base64_para_arquivo(b64, dest)
                messagebox.showinfo("Sucesso", f"Arquivo exportado para:\n{dest}", parent=self)
            except Exception as e:
                messagebox.showerror("Erro", str(e), parent=self)

    def _browse(self):
        path = filedialog.askopenfilename(filetypes=[("Certificados", "*.pfx *.pem"), ("Todos", "*.*")])
        if path:
            self.var_arquivo.set(path)
            try:
                self._arquivo_b64 = crypto_utils.arquivo_para_base64(path)
                self._arquivo_ext = "pfx" if path.lower().endswith(".pfx") else "pem"
                self.lbl_arquivo_salvo.config(text="Arquivo carregado e sera salvo no banco ao confirmar.")
            except Exception as e:
                self._arquivo_b64 = None
                messagebox.showerror("Erro", f"Nao foi possivel ler o arquivo:\n{e}", parent=self)

    def _ler_arquivo(self):
        path = self.var_arquivo.get().strip()
        senha_raw = self.var_senha.get().strip()
        senha = crypto_utils.descriptografar_senha(senha_raw) or senha_raw
        if not path:
            messagebox.showwarning("Atencao", "Selecione um arquivo primeiro.", parent=self)
            return
        try:
            if path.lower().endswith(".pfx"):
                nome, venc = crypto_utils.ler_certificado_pfx(path, senha)
            else:
                nome, venc = crypto_utils.ler_certificado_pem(path)
            self.var_nome.set(nome)
            self.var_venc.set(venc)
            messagebox.showinfo("Sucesso", f"Certificado lido!\nNome: {nome}\nVencimento: {venc}", parent=self)
        except Exception as e:
            messagebox.showerror("Erro", f"Nao foi possivel ler o arquivo:\n{e}", parent=self)

    def _preencher(self):
        c = self.cert
        self.var_tipo.set(c.get("tipo", "A1"))
        self.var_nome.set(c.get("nome", ""))
        self.var_resp.set(c.get("responsavel", ""))
        self.var_venc.set(c.get("vencimento", ""))
        self.var_obs.set(c.get("obs", ""))
        self.var_emails.set(c.get("emails", ""))
        self.var_enviar_alerta.set(bool(c.get("enviar_alerta", 1)))
        self.var_dias_alerta.set(str(c.get("dias_alerta") or 30))
        self._toggle_alerta()
        self.var_arquivo.set(c.get("arquivo_nome", ""))
        self.var_senha.set("")
        self._arquivo_b64 = c.get("arquivo_b64", None)
        self._arquivo_ext = c.get("arquivo_ext", "pfx")
        if self._arquivo_b64:
            self.lbl_arquivo_salvo.config(text="Arquivo ja armazenado no banco. Use 'Exportar' para recuperar.")

    def _salvar(self):
        nome = self.var_nome.get().strip()
        venc = self.var_venc.get().strip()
        if not nome or not venc:
            messagebox.showwarning("Atencao", "Nome e Vencimento sao obrigatorios.", parent=self)
            return
        try:
            date.fromisoformat(venc)
        except ValueError:
            messagebox.showerror("Erro", "Data invalida. Use o formato AAAA-MM-DD.", parent=self)
            return

        # ---- INÍCIO DO BLOQUEIO DE DUPLICIDADE ----
        cert_id = self.cert["id"] if self.cert else str(int(time.time()))
        certs_existentes = database.carregar_certificados()
        for c in certs_existentes:
            if c["nome"].strip().lower() == nome.lower() and c["id"] != cert_id:
                messagebox.showwarning(
                    "Certificado Duplicado",
                    f"Já existe um certificado cadastrado para:\n\n'{nome}'\n\n"
                    "Para atualizar um certificado renovado, feche esta tela, selecione o cliente na lista principal e clique em 'Editar'.",
                    parent=self
                )
                return
        # ---- FIM DO BLOQUEIO DE DUPLICIDADE ----

        senha_digitada = self.var_senha.get().strip()
        if senha_digitada: senha_enc = crypto_utils.criptografar_senha(senha_digitada)
        elif self.cert: senha_enc = self.cert.get("senha_enc", "")
        else: senha_enc = ""

        cert_existente = self.cert or {}
        novo_b64 = getattr(self, "_arquivo_b64", None)
        novo_ext = getattr(self, "_arquivo_ext", "pfx")
        b64_final = novo_b64 or cert_existente.get("arquivo_b64", "")
        ext_final = novo_ext if novo_b64 else cert_existente.get("arquivo_ext", "pfx")
        nome_arq = os.path.basename(self.var_arquivo.get().strip()) if self.var_arquivo.get().strip() else cert_existente.get("arquivo_nome", "")

        is_novo = self.cert is None
        venc_anterior = cert_existente.get("vencimento", "")
        venc_mudou = (not is_novo) and venc_anterior and venc_anterior != venc
        if is_novo or venc_mudou: enviar_alerta_final = True
        else: enviar_alerta_final = self.var_enviar_alerta.get()

        dados = {
            "id": cert_id, "tipo": self.var_tipo.get(), "nome": nome,
            "responsavel": self.var_resp.get().strip(), "vencimento": venc,
            "obs": self.var_obs.get().strip(), "emails": self.var_emails.get().strip(),
            "arquivo_nome": nome_arq, "arquivo_b64": b64_final, "arquivo_ext": ext_final,
            "senha_enc": senha_enc, "ultimo_alerta": "" if venc_mudou else cert_existente.get("ultimo_alerta", ""),
            "dias_alerta": int(self.var_dias_alerta.get() or 30), "enviar_alerta": enviar_alerta_final,
        }

        database.salvar_certificado(dados)
        database.registrar_historico_db(cert_id, "cadastrado" if is_novo else "editado")

        if is_novo:
            def _enviar_boas_vindas():
                config_email = email_service.carregar_config_email()
                str_emails = config_email.get("emails_novo_cert", "").replace(";", ",")
                dest = [e.strip() for e in str_emails.split(",") if e.strip()]
                if dest:
                    ok, msg_erro = email_service.enviar_email_novo_certificado(config_email, dest, dados)
                    assunto_log = f"[Novo Certificado] {dados.get('nome', '')} - Disponível para uso"
                    if ok: database.registrar_log_email(dados, dest, assunto_log, "Enviado", origem="automatico")
                    else: database.registrar_log_email(dados, dest, assunto_log, "Erro", erro=msg_erro, origem="automatico")
            threading.Thread(target=_enviar_boas_vindas, daemon=True).start()

        if self.callback: self.callback()
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gerenciador de Certificados Digitais")
        self.geometry("1100x680")
        self.minsize(900, 520)
        self.configure(bg=config.COR_BG)
        self._tray_icon = None
        
        database.init_db()
        database.migrar_colunas_log()
        
        self._apply_style()
        self._build_header()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        self.tab_dash = tk.Frame(self.notebook, bg=config.COR_BG)
        self.notebook.add(self.tab_dash, text="   📊 Dashboard Geral   ")
        self._build_dashboard(self.tab_dash)

        self.tab_lista = tk.Frame(self.notebook, bg=config.COR_BG)
        self.notebook.add(self.tab_lista, text="   📋 Gestão de Certificados   ")
        self._build_toolbar(self.tab_lista)
        self._build_table(self.tab_lista)

        self._build_statusbar()
        self.atualizar_tabela()
        self._iniciar_auto_refresh()
        
        email_service.iniciar_scheduler(self)
        threading.Thread(target=email_service.verificar_certificados, args=(self,), daemon=True).start()
        
        if TRAY_DISPONIVEL:
            self.protocol("WM_DELETE_WINDOW", self._minimizar_tray)
            threading.Thread(target=self._iniciar_tray, daemon=True).start()
        else:
            self.protocol("WM_DELETE_WINDOW", self._confirmar_saida)

    def _criar_icone_tray(self):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 62, 62], fill=(26, 42, 74, 255))
        draw.ellipse([14, 14, 50, 50], fill=(37, 99, 235, 255))
        draw.ellipse([20, 20, 44, 44], fill=(26, 42, 74, 255))
        draw.ellipse([40, 40, 56, 56], fill=(22, 163, 74, 255))
        return img

    def _iniciar_tray(self):
        icone = self._criar_icone_tray()
        menu = pystray.Menu(
            pystray.MenuItem("Abrir", lambda: self.after(0, self._restaurar_janela), default=True),
            pystray.MenuItem("Verificar agora", lambda: self.after(0, self.verificar_agora)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Iniciar com o Windows", lambda: self.after(0, self.toggle_startup), checked=lambda item: _startup_habilitado()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", lambda: self.after(0, self._sair_completo)),
        )
        self._tray_icon = pystray.Icon("CertificadosDigitais", icone, "Gerenciador de Certificados", menu)
        self._tray_icon.run()

    def _minimizar_tray(self):
        self.withdraw()
        if self._tray_icon and TRAY_DISPONIVEL: self._tray_icon.visible = True

    def _restaurar_janela(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _sair_completo(self):
        if self._tray_icon: self._tray_icon.stop()
        self.destroy()

    def _confirmar_saida(self):
        if messagebox.askyesno("Sair", "Deseja encerrar o Gerenciador de Certificados?"):
            self.destroy()

    def _apply_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=config.COR_BG, foreground="#1e293b", font=("Segoe UI", 9))
        style.configure("Treeview", background=config.COR_BG_TABLE, fieldbackground=config.COR_BG_TABLE, foreground="#1e293b", rowheight=28, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background=config.COR_PRIMARIA, foreground=config.COR_TEXTO_CLR, font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", config.COR_SECUNDARIA)], foreground=[("selected", "#ffffff")])

    def _build_header(self):
        hdr = tk.Frame(self, bg=config.COR_PRIMARIA, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Gerenciador de Certificados Digitais", bg=config.COR_PRIMARIA, fg="#ffffff", font=("Segoe UI", 14, "bold")).pack(side="left", padx=18, pady=10)
        self.lbl_clock = tk.Label(hdr, bg=config.COR_PRIMARIA, fg="#94a3b8", font=("Segoe UI", 9))
        self.lbl_clock.pack(side="right", padx=16)
        self._tick()
        self._build_menu()

    def _tick(self):
        self.lbl_clock.config(text=datetime.now().strftime("%d/%m/%Y   %H:%M:%S"))
        self.after(1000, self._tick)

    def _build_menu(self):
        mb = tk.Menu(self, bg=config.COR_PRIMARIA, fg="#ffffff", activebackground=config.COR_SECUNDARIA, activeforeground="#ffffff", borderwidth=0)
        self.config(menu=mb)
        m_cert = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Certificados", menu=m_cert)
        m_cert.add_command(label="Novo certificado", command=self.novo_cert)
        m_cert.add_command(label="Editar selecionado", command=self.editar_cert)
        m_cert.add_command(label="Excluir selecionado", command=self.excluir_cert)
        m_cert.add_separator()
        m_cert.add_command(label="Sair", command=self.quit)
        m_conf = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Configuracoes", menu=m_conf)
        m_conf.add_command(label="Configurar e-mail", command=self.config_email)
        m_conf.add_command(label="Template do e-mail", command=self.config_template)
        m_conf.add_separator()
        m_conf.add_command(label="Iniciar com o Windows", command=self.toggle_startup)
        m_acao = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Ações", menu=m_acao)
        m_acao.add_command(label="Verificar agora", command=self.verificar_agora)
        m_acao.add_command(label="Atualizar lista", command=self.atualizar_tabela)
        m_acao.add_separator()
        m_acao.add_command(label="Log de E-mails", command=self.abrir_log_emails)

    def _build_dashboard(self, parent):
        if not MATPLOTLIB_DISPONIVEL:
            tk.Label(parent, text="Para visualizar o Dashboard, abra o terminal e instale o matplotlib:\n\npip install matplotlib",
                     bg=config.COR_BG, fg=config.COR_PRIMARIA, font=("Segoe UI", 12)).pack(expand=True)
            return
        self.f_cards = tk.Frame(parent, bg=config.COR_BG)
        self.f_cards.pack(fill="x", pady=15, padx=10)
        self.f_charts = tk.Frame(parent, bg=config.COR_BG)
        self.f_charts.pack(fill="both", expand=True, padx=10, pady=10)

    def atualizar_dashboard(self):
        if not MATPLOTLIB_DISPONIVEL:
            return

        certs = database.carregar_certificados()
        hoje = date.today()
        mes_atual = hoje.month
        ano_atual = hoje.year
        prox_mes = mes_atual + 1 if mes_atual < 12 else 1
        ano_prox = ano_atual if mes_atual < 12 else ano_atual + 1

        vence_neste_mes = 0
        vence_prox_mes = 0
        vencidos = 0
        ativos = 0

        status_counts = {"Vencidos": 0, "Até 30 dias": 0, "31 a 60 dias": 0, "Acima de 60 dias": 0}
        tipo_counts = {"A1": 0, "A3": 0}

        for c in certs:
            tipo = c.get("tipo", "A1")
            if tipo in tipo_counts:
                tipo_counts[tipo] += 1
            else:
                tipo_counts["A1"] += 1

            try:
                venc = date.fromisoformat(c["vencimento"])
                dias = (venc - hoje).days

                if dias < 0:
                    vencidos += 1
                    status_counts["Vencidos"] += 1
                else:
                    ativos += 1
                    if dias <= 30:
                        status_counts["Até 30 dias"] += 1
                    elif dias <= 60:
                        status_counts["31 a 60 dias"] += 1
                    else:
                        status_counts["Acima de 60 dias"] += 1

                    if venc.month == mes_atual and venc.year == ano_atual:
                        vence_neste_mes += 1
                    elif venc.month == prox_mes and venc.year == ano_prox:
                        vence_prox_mes += 1
            except Exception:
                pass

        for widget in self.f_cards.winfo_children():
            widget.destroy()

        def criar_card(parent, titulo, valor, cor_bg, cor_fg, filtro_alvo):
            f = tk.Frame(parent, bg=cor_bg, bd=0, relief="flat", highlightbackground="#cbd5e1", highlightthickness=1, cursor="hand2")
            f.pack(side="left", fill="both", expand=True, padx=8)
            lbl_tit = tk.Label(f, text=titulo, bg=cor_bg, fg=cor_fg, font=("Segoe UI", 10, "bold"), cursor="hand2")
            lbl_tit.pack(pady=(15, 5))
            lbl_val = tk.Label(f, text=str(valor), bg=cor_bg, fg=cor_fg, font=("Segoe UI", 26, "bold"), cursor="hand2")
            lbl_val.pack(pady=(0, 15))

            # Evento de duplo clique no cartão que muda o filtro e salta de aba
            def on_click(e):
                self.var_status_filtro.set(filtro_alvo)
                self.notebook.select(self.tab_lista) # Muda para a aba de gestão

            f.bind("<Double-1>", on_click)
            lbl_tit.bind("<Double-1>", on_click)
            lbl_val.bind("<Double-1>", on_click)

        criar_card(self.f_cards, "Vencem Este Mês", vence_neste_mes, "#fef3c7", "#d97706", "Vencem Este Mês")
        criar_card(self.f_cards, "Vencem Próximo Mês", vence_prox_mes, "#e0f2fe", "#0284c7", "Vencem Próx. Mês")
        criar_card(self.f_cards, "Certificados Ativos", ativos, "#dcfce7", "#166534", "Ativos")
        criar_card(self.f_cards, "Certificados Vencidos", vencidos, "#fee2e2", "#991b1b", "Vencidos")

        for widget in self.f_charts.winfo_children():
            widget.destroy()

        fig = Figure(figsize=(10, 5), dpi=100, facecolor=config.COR_BG)
        gs = GridSpec(2, 2, figure=fig, height_ratios=[1.2, 1])
        
        ax1 = fig.add_subplot(gs[:, 0])
        labels_pie = []
        sizes_pie = []
        colors_pie = []
        cores_map = {"Vencidos": "#ef4444", "Até 30 dias": "#f97316", "31 a 60 dias": "#eab308", "Acima de 60 dias": "#22c55e"}

        for k, v in status_counts.items():
            if v > 0:
                labels_pie.append(k)
                sizes_pie.append(v)
                colors_pie.append(cores_map[k])

        if sizes_pie:
            ax1.pie(sizes_pie, labels=labels_pie, colors=colors_pie, autopct='%1.1f%%', startangle=140, textprops={'fontsize': 9})
            ax1.set_title("Status de Validade", fontdict={'fontweight': 'bold', 'fontsize': 11})
        else:
            ax1.text(0.5, 0.5, "Sem dados registados", ha='center', va='center')
            ax1.axis('off')

        ax2 = fig.add_subplot(gs[0, 1])
        meses_pt = {1:"Jan", 2:"Fev", 3:"Mar", 4:"Abr", 5:"Mai", 6:"Jun", 7:"Jul", 8:"Ago", 9:"Set", 10:"Out", 11:"Nov", 12:"Dez"}
        meses_bar = []
        valores_bar = [0, 0, 0, 0, 0, 0]

        for i in range(6):
            m = hoje.month + i
            y = hoje.year
            if m > 12:
                m -= 12
                y += 1
            meses_bar.append(f"{meses_pt[m]}/{y}")

        for c in certs:
            try:
                venc = date.fromisoformat(c["vencimento"])
                if venc >= hoje:
                    for i in range(6):
                        m = hoje.month + i
                        y = hoje.year
                        if m > 12:
                            m -= 12
                            y += 1
                        if venc.month == m and venc.year == y:
                            valores_bar[i] += 1
                            break
            except:
                pass

        ax2.bar(meses_bar, valores_bar, color=config.COR_SECUNDARIA, width=0.5)
        ax2.set_title("Vencimentos (Próx. 6 Meses)", fontdict={'fontweight': 'bold', 'fontsize': 10})
        ax2.tick_params(axis='x', rotation=0, labelsize=8)
        from matplotlib.ticker import MaxNLocator
        ax2.yaxis.set_major_locator(MaxNLocator(integer=True))
        for i, v in enumerate(valores_bar):
            if v > 0:
                ax2.text(i, v + 0.1, str(v), color='black', ha='center', fontsize=8, fontweight='bold')

        ax3 = fig.add_subplot(gs[1, 1])
        labels_tipo = []
        sizes_tipo = []
        colors_tipo = []
        cores_tipo_map = {"A1": "#3b82f6", "A3": "#8b5cf6"}

        for k, v in tipo_counts.items():
            if v > 0:
                labels_tipo.append(k)
                sizes_tipo.append(v)
                colors_tipo.append(cores_tipo_map[k])

        if sizes_tipo:
            explode = [0.05 if i == 0 else 0 for i in range(len(sizes_tipo))]
            ax3.pie(sizes_tipo, labels=labels_tipo, colors=colors_tipo, autopct='%1.1f%%', startangle=90, textprops={'fontsize': 8}, explode=explode)
            ax3.set_title("Proporção A1 vs A3", fontdict={'fontweight': 'bold', 'fontsize': 10})
        else:
            ax3.axis('off')

        fig.tight_layout(pad=1.5)

        canvas_chart = FigureCanvasTkAgg(fig, master=self.f_charts)
        canvas_chart.draw()
        canvas_chart.get_tk_widget().pack(fill="both", expand=True)

    def _build_toolbar(self, parent):
        tb = tk.Frame(parent, bg="#223366", pady=6)
        tb.pack(fill="x")
        def btn(text, cmd, color=config.COR_SECUNDARIA):
            b = tk.Button(tb, text=text, command=cmd, bg=color, fg="#ffffff", activebackground="#1d4ed8", activeforeground="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=5, cursor="hand2", borderwidth=0)
            b.pack(side="left", padx=3)
            return b
        def sep(): tk.Frame(tb, bg="#445577", width=1).pack(side="left", fill="y", padx=6, pady=4)
        btn("+ Novo", self.novo_cert, "#16a34a")
        btn("Editar", self.editar_cert)
        btn("Excluir", self.excluir_cert, "#dc2626")
        btn("Historico", self.ver_historico)
        sep()
        btn("↻ Atualizar", self.atualizar_manual, "#0f766e")
        btn("Verificar agora", self.verificar_agora, "#0284c7")
        btn("Log E-mails", self.abrir_log_emails, "#b45309")
        btn("Config. E-mail", self.config_email)
        btn("Template", self.config_template)
        sep()
        btn("Exportar CSV", self.exportar_certificados_csv, "#16a34a")
        sep()
        
        # Filtro de Status (O NOVO COMBBOX PARA OS CARTOES)
        tk.Label(tb, text="Status:", bg="#223366", fg="#cbd5e1", font=("Segoe UI", 9)).pack(side="left")
        self.var_status_filtro = tk.StringVar(value="Todos")
        cb_status = ttk.Combobox(tb, textvariable=self.var_status_filtro, values=["Todos", "Vencem Este Mês", "Vencem Próx. Mês", "Ativos", "Vencidos"], state="readonly", width=16)
        cb_status.pack(side="left", padx=2)
        self.var_status_filtro.trace_add("write", lambda *_: self.atualizar_tabela())
        
        sep()
        
        # Filtro de Texto
        tk.Label(tb, text="Nome:", bg="#223366", fg="#cbd5e1", font=("Segoe UI", 9)).pack(side="left")
        self.var_filtro = tk.StringVar()
        self.var_filtro.trace_add("write", lambda *_: self.atualizar_tabela())
        tk.Entry(tb, textvariable=self.var_filtro, width=20, font=("Segoe UI", 9), relief="flat", bg="#334466", fg="#ffffff", insertbackground="#ffffff").pack(side="left", padx=(4, 2), ipady=3)
        
        # Filtro de Tipo
        self.var_tipo_filtro = tk.StringVar(value="Todos")
        cb = ttk.Combobox(tb, textvariable=self.var_tipo_filtro, values=["Todos", "A1", "A3"], state="readonly", width=6)
        cb.pack(side="left", padx=2)
        self.var_tipo_filtro.trace_add("write", lambda *_: self.atualizar_tabela())

    def _build_table(self, parent):
        cols = ("tipo", "nome", "responsavel", "vencimento", "dias", "situacao", "emails")
        headers = ("Tipo", "Nome / Razao Social", "Responsavel", "Vencimento", "Dias", "Situacao", "E-mails")
        frame = tk.Frame(parent, bg=config.COR_BG)
        frame.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        widths = [50, 180, 120, 100, 50, 80, 160]
        stretches = {"nome": True, "emails": True}
        
        # O comando lambda associado aos titulos já executa a ORDENAÇÃO
        for col, hdr, w in zip(cols, headers, widths):
            self.tree.heading(col, text=hdr, command=lambda c=col: self._ordenar(c))
            anchor = "center" if col in ("tipo", "dias", "situacao", "vencimento") else "w"
            self.tree.column(col, width=w, minwidth=w, anchor=anchor, stretch=stretches.get(col, False))

        sb_y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        sb_x = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb_y.grid(row=0, column=1, sticky="ns")
        sb_x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.tree.tag_configure("vencido", background=config.COR_VENCIDO, foreground=config.COR_VENCIDO_FG)
        self.tree.tag_configure("critico", background=config.COR_CRITICO, foreground=config.COR_CRITICO_FG)
        self.tree.tag_configure("atencao", background=config.COR_ATENCAO, foreground=config.COR_ATENCAO_FG)
        self.tree.tag_configure("ok", background=config.COR_OK, foreground=config.COR_OK_FG)
        self.tree.bind("<Double-1>", lambda _: self.editar_cert())

        self._btn_mail_widgets = {}
        self._btn_senha_widgets = {}
        self.tree.bind("<Configure>", lambda _: self.after(30, self._reposicionar_botoes))
        self.tree.bind("<MouseWheel>", lambda _: self.after(30, self._reposicionar_botoes))
        self.tree.bind("<Button-4>", lambda _: self.after(30, self._reposicionar_botoes))
        self.tree.bind("<Button-5>", lambda _: self.after(30, self._reposicionar_botoes))

    def _reposicionar_botoes(self):
        if self.notebook.index(self.notebook.select()) != 1:
            for btn in self._btn_mail_widgets.values(): btn.place_forget()
            for btn in self._btn_senha_widgets.values(): btn.place_forget()
            return

        total_w = sum(self.tree.column(c, "width") for c in self.tree["columns"])
        x_mail, x_senha = total_w - 95, total_w - 185
        for iid, btn in list(self._btn_mail_widgets.items()):
            try: bbox = self.tree.bbox(iid)
            except Exception: btn.place_forget(); continue
            if bbox: btn.place(in_=self.tree, x=x_mail + 4, y=bbox[1] + 2, width=84, height=bbox[3] - 4)
            else: btn.place_forget()
        for iid, btn in list(self._btn_senha_widgets.items()):
            try: bbox = self.tree.bbox(iid)
            except Exception: btn.place_forget(); continue
            if bbox: btn.place(in_=self.tree, x=x_senha + 4, y=bbox[1] + 2, width=82, height=bbox[3] - 4)
            else: btn.place_forget()

    def _build_statusbar(self):
        sb = tk.Frame(self, bg=config.COR_PRIMARIA, height=26)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self.status_bar = tk.Label(sb, text="  Pronto.", bg=config.COR_PRIMARIA, fg="#94a3b8", font=("Segoe UI", 8), anchor="w")
        self.status_bar.pack(fill="x", padx=4)

    def atualizar_tabela(self):
        for btn in self._btn_mail_widgets.values(): btn.destroy()
        self._btn_mail_widgets.clear()
        for btn in self._btn_senha_widgets.values(): btn.destroy()
        self._btn_senha_widgets.clear()
        for row in self.tree.get_children(): self.tree.delete(row)

        certs = database.carregar_certificados()
        filtro_texto = self.var_filtro.get().lower()
        tipo_f = self.var_tipo_filtro.get()
        status_f = self.var_status_filtro.get()
        
        hoje = date.today()
        mes_atual = hoje.month
        ano_atual = hoje.year
        prox_mes = mes_atual + 1 if mes_atual < 12 else 1
        ano_prox = ano_atual if mes_atual < 12 else ano_atual + 1

        for c in certs:
            if tipo_f != "Todos" and c.get("tipo") != tipo_f: continue
            if filtro_texto and filtro_texto not in c.get("nome", "").lower() and filtro_texto not in c.get("responsavel", "").lower(): continue
            
            try:
                venc = date.fromisoformat(c["vencimento"])
                dias = (venc - hoje).days
            except Exception:
                venc = None
                dias = 0

            # Filtro Lógico Baseado no clique do Cartão
            if status_f != "Todos":
                if status_f == "Vencidos" and dias >= 0: continue
                if status_f == "Ativos" and dias < 0: continue
                if status_f == "Vencem Este Mês" and not (venc and venc.month == mes_atual and venc.year == ano_atual): continue
                if status_f == "Vencem Próx. Mês" and not (venc and venc.month == prox_mes and venc.year == ano_prox): continue

            if dias < 0: sit, tag = "Vencido", "vencido"
            elif dias <= 7: sit, tag = "Critico", "critico"
            elif dias <= 30: sit, tag = "Atencao", "atencao"
            else: sit, tag = "OK", "ok"

            self.tree.insert("", "end", iid=c["id"], tags=(tag,), values=(c.get("tipo", ""), c.get("nome", ""), c.get("responsavel", ""), c.get("vencimento", ""), dias, sit, c.get("emails", "")))
            
            self._btn_mail_widgets[c["id"]] = tk.Button(self.tree, text="Enviar E-mail", font=("Segoe UI", 8, "bold"), bg="#2563eb", fg="#ffffff", activebackground="#1d4ed8", activeforeground="#ffffff", relief="flat", cursor="hand2", borderwidth=0, command=lambda id_=c["id"]: self._enviar_email_manual(id_))
            self._btn_senha_widgets[c["id"]] = tk.Button(self.tree, text="Ver Senha", font=("Segoe UI", 8, "bold"), bg="#7c3aed", fg="#ffffff", activebackground="#6d28d9", activeforeground="#ffffff", relief="flat", cursor="hand2", borderwidth=0, command=lambda id_=c["id"]: self._ver_senha(id_))

        self.after(50, self._reposicionar_botoes)
        self.status_bar.config(text=f"  {len(self.tree.get_children())} certificado(s) exibido(s).   |   Atualizado: {datetime.now().strftime('%H:%M:%S')}")
        
        # O Dashboard deve espelhar a base real sempre
        self.atualizar_dashboard()

    def _ordenar(self, col):
        # Esta é a função que ordena a coluna automaticamente ao ser clicada
        rows = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        rows.sort()
        for i, (_, k) in enumerate(rows): self.tree.move(k, "", i)
        self.after(50, self._reposicionar_botoes)

    def _cert_selecionado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Atencao", "Selecione um certificado na lista.")
            return None
        return next((c for c in database.carregar_certificados() if c["id"] == sel[0]), None)

    def _ver_senha(self, cert_id):
        cert = next((c for c in database.carregar_certificados() if c["id"] == cert_id), None)
        if not cert: return
        senha_enc = cert.get("senha_enc", "")
        if not senha_enc:
            messagebox.showinfo("Senha", "Nenhuma senha cadastrada para este certificado.", parent=self)
            return
        if not pedir_senha_mestre(self): return
        senha = crypto_utils.descriptografar_senha(senha_enc)
        if not senha:
            messagebox.showerror("Erro", "Nao foi possivel descriptografar a senha.", parent=self)
            return

        win = tk.Toplevel(self)
        win.title("Senha do Certificado")
        win.resizable(False, False)
        win.grab_set()
        win.configure(bg="#1e1b4b")

        hdr = tk.Frame(win, bg="#4c1d95", height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Senha do Certificado", bg="#4c1d95", fg="#ffffff", font=("Segoe UI", 11, "bold")).pack(side="left", padx=14, pady=12)
        tk.Label(win, text=cert.get("nome", ""), bg="#1e1b4b", fg="#c4b5fd", font=("Segoe UI", 10)).pack(pady=(14, 2))
        tk.Label(win, text=f"Tipo: {cert.get('tipo', '')}   |   Vencimento: {cert.get('vencimento', '')}", bg="#1e1b4b", fg="#7c3aed", font=("Segoe UI", 8)).pack(pady=(0, 10))

        f_senha = tk.Frame(win, bg="#2e1065", bd=0, pady=12, padx=20)
        f_senha.pack(fill="x", padx=30, pady=6)
        tk.Label(f_senha, text="Senha:", bg="#2e1065", fg="#a78bfa", font=("Segoe UI", 9)).pack(anchor="w")

        var_senha = tk.StringVar(value=senha)
        f_row = tk.Frame(f_senha, bg="#2e1065")
        f_row.pack(fill="x", pady=(4, 0))
        entry = tk.Entry(f_row, textvariable=var_senha, state="readonly", font=("Courier New", 14, "bold"), readonlybackground="#3b0764", fg="#f0abfc", relief="flat", bd=6, justify="center")
        entry.pack(side="left", fill="x", expand=True, ipady=6)

        def _limpar_clipboard():
            try:
                if win.clipboard_get() == senha: win.clipboard_clear()
            except Exception: pass

        def _copiar():
            win.clipboard_clear()
            win.clipboard_append(senha)
            btn_copiar.config(text="Copiado!", bg="#16a34a")
            win.after(1500, lambda: btn_copiar.config(text="Copiar", bg="#7c3aed"))
            win.after(30000, _limpar_clipboard)

        btn_copiar = tk.Button(f_row, text="Copiar", command=_copiar, bg="#7c3aed", fg="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), padx=10, cursor="hand2")
        btn_copiar.pack(side="left", padx=(6, 0))
        tk.Label(win, text="Esta janela fechara automaticamente em 30 segundos.", bg="#1e1b4b", fg="#6b7280", font=("Segoe UI", 8)).pack(pady=(10, 4))
        self._countdown_label = tk.Label(win, text="30", bg="#1e1b4b", fg="#f87171", font=("Segoe UI", 22, "bold"))
        self._countdown_label.pack()
        tk.Button(win, text="Fechar", command=lambda: [_limpar_clipboard(), win.destroy()], bg="#6d28d9", fg="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), padx=20, pady=6, cursor="hand2").pack(pady=14)
        win.geometry("380x320")

        def _tick(n):
            if not win.winfo_exists(): return
            self._countdown_label.config(text=str(n))
            if n <= 0: _limpar_clipboard(); win.destroy()
            else: win.after(1000, lambda: _tick(n - 1))
        _tick(30)

    def _enviar_email_manual(self, cert_id):
        cert = next((c for c in database.carregar_certificados() if c["id"] == cert_id), None)
        if not cert: return
        config_email = email_service.carregar_config_email()
        destinatarios = [e.strip() for e in cert.get("emails", "").split(",") if e.strip()]
        if not destinatarios: destinatarios = [config_email.get("usuario", "")]
        destinatarios = [d for d in destinatarios if d]
        if not destinatarios:
            messagebox.showwarning("Atencao", "Nenhum e-mail configurado para este certificado.")
            return

        self.status_bar.config(text=f"  Enviando e-mail para {', '.join(destinatarios)}...")
        self.update_idletasks()

        def _enviar():
            ok, msg = email_service.enviar_email(config_email, destinatarios, cert)
            _tmpl = email_service.carregar_template()
            try:
                _dias_r = (date.fromisoformat(cert["vencimento"]) - date.today()).days
                _assunto_log = _tmpl["assunto"].format(nome=cert.get("nome",""), tipo=cert.get("tipo",""), responsavel=cert.get("responsavel",""), vencimento=cert.get("vencimento",""), obs=cert.get("obs",""), dias=str(_dias_r), situacao="", cor="")
            except Exception:
                _assunto_log = _tmpl.get("assunto", "")
            if ok:
                database.registrar_historico_db(cert_id, "alerta_enviado", manual=True, destinatarios=destinatarios)
                database.registrar_log_email(cert, destinatarios, _assunto_log, "Enviado", origem="manual")
                self.after(0, lambda: [
                    messagebox.showinfo("Sucesso", "E-mail enviado para:\n" + "\n".join(destinatarios)),
                    self.status_bar.config(text=f"  E-mail enviado manualmente - {datetime.now().strftime('%H:%M:%S')}"),
                    self.atualizar_tabela()
                ])
            else:
                database.registrar_log_email(cert, destinatarios, _assunto_log, "Erro", erro=msg, origem="manual")
                self.after(0, lambda: [
                    messagebox.showerror("Erro", f"Falha ao enviar e-mail:\n{msg}"),
                    self.status_bar.config(text="  Erro ao enviar e-mail.")
                ])
        threading.Thread(target=_enviar, daemon=True).start()

    def novo_cert(self): JanelaCertificado(self, callback=self.atualizar_tabela)
    def editar_cert(self):
        cert = self._cert_selecionado()
        if cert: JanelaCertificado(self, cert=cert, callback=self.atualizar_tabela)
    def excluir_cert(self):
        cert = self._cert_selecionado()
        if cert and messagebox.askyesno("Confirmar", f"Excluir o certificado '{cert['nome']}'?"):
            database.excluir_certificado_db(cert["id"])
            self.atualizar_tabela()
    def ver_historico(self):
        cert = self._cert_selecionado()
        if cert: JanelaHistorico(self, cert)
    def config_email(self): JanelaConfigEmail(self)
    def config_template(self): JanelaTemplate(self)
    def abrir_log_emails(self): JanelaLogEmails(self)

    def exportar_certificados_csv(self):
        certs = database.carregar_certificados()
        if not certs:
            messagebox.showwarning("Atencao", "Nao ha certificados cadastrados para exportar.", parent=self)
            return
        destino = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("Todos", "*.*")], initialfile=f"certificados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        if not destino: return
        try:
            import csv
            with open(destino, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["ID", "Tipo", "Nome/Razao Social", "Responsavel", "Vencimento", "Dias Restantes", "Situacao", "E-mails", "Observacao", "Arquivo", "Dias Antes p/ Alerta", "Lembrete Ativo", "Ultimo Alerta Enviado"])
                for c in certs:
                    try: dias = (date.fromisoformat(c["vencimento"]) - date.today()).days
                    except Exception: dias = ""
                    if dias == "": situacao = ""
                    elif dias < 0: situacao = "Vencido"
                    elif dias <= 7: situacao = "Critico"
                    elif dias <= 30: situacao = "Atencao"
                    else: situacao = "OK"
                    writer.writerow([c.get("id", ""), c.get("tipo", ""), c.get("nome", ""), c.get("responsavel", ""), c.get("vencimento", ""), dias, situacao, c.get("emails", ""), c.get("obs", ""), c.get("arquivo_nome", ""), c.get("dias_alerta", ""), "Sim" if c.get("enviar_alerta", 1) else "Nao", c.get("ultimo_alerta", "")])
            messagebox.showinfo("Exportado", f"Listagem exportada com sucesso para:\n{destino}", parent=self)
        except Exception as e:
            messagebox.showerror("Erro", f"Nao foi possivel exportar:\n{e}", parent=self)

    def atualizar_manual(self):
        self.status_bar.config(text="  Atualizando lista...")
        self.update_idletasks()
        self.atualizar_tabela()

    def verificar_agora(self):
        self.status_bar.config(text="  Verificando certificados...")
        threading.Thread(target=email_service.verificar_certificados, args=(self,), daemon=True).start()

    def _iniciar_auto_refresh(self, intervalo_ms=30000):
        self._auto_refresh_intervalo = intervalo_ms
        self._agendar_refresh()

    def _agendar_refresh(self):
        self._auto_refresh_job = self.after(self._auto_refresh_intervalo, self._executar_refresh)

    def _executar_refresh(self):
        self.atualizar_tabela()
        self._agendar_refresh()

    def toggle_startup(self):
        if _startup_habilitado():
            _desabilitar_startup()
            messagebox.showinfo("Inicializacao", "O programa foi REMOVIDO da inicializacao automatica do Windows.")
        else:
            _habilitar_startup()
            messagebox.showinfo("Inicializacao", "O programa foi adicionado a inicializacao automatica do Windows.\nEle sera iniciado minimizado na bandeja ao ligar o PC.")

class JanelaHistorico(tk.Toplevel):
    ACOES = {"cadastrado": ("[+]", "Cadastrado"), "editado": ("[E]", "Editado"), "verificado": ("[V]", "Verificado"), "alerta_enviado": ("[@]", "Alerta enviado"), "erro_envio": ("[X]", "Erro no envio")}
    def __init__(self, parent, cert):
        super().__init__(parent)
        self.title(f"Historico - {cert['nome']}")
        self.geometry("720x420")
        self.grab_set()
        self._build(cert)

    def _build(self, cert):
        hdr = tk.Frame(self, bg=config.COR_PRIMARIA, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=f"  {cert['nome']}   |   Tipo: {cert['tipo']}", bg=config.COR_PRIMARIA, fg="#ffffff", font=("Segoe UI", 10, "bold")).pack(side="left", padx=12, pady=10)

        cols = ("data", "hora", "acao", "info")
        headers = ("Data", "Hora", "Acao", "Informacoes")
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=(8, 4))
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        widths = [90, 70, 160, 360]
        for col, hdr_txt, w in zip(cols, headers, widths):
            tree.heading(col, text=hdr_txt)
            tree.column(col, width=w)
        sb = ttk.Scrollbar(frame, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        historico = cert.get("historico", [])
        for entry in reversed(historico):
            icone, label = self.ACOES.get(entry.get("acao", ""), ("[?]", entry.get("acao", "")))
            extras = []
            if "dias_restantes" in entry: extras.append(f"{entry['dias_restantes']} dia(s) restante(s)")
            if entry.get("manual"): extras.append("Envio manual")
            if "destinatarios" in entry: extras.append(f"Para: {', '.join(entry['destinatarios'])}")
            if "erro" in entry: extras.append(f"Erro: {entry['erro']}")
            info = " | ".join(extras) if extras else "-"
            tree.insert("", "end", values=(entry.get("data", ""), entry.get("hora", ""), f"{icone} {label}", info))
        if not historico: tree.insert("", "end", values=("", "", "Nenhum registro ainda.", ""))
        tk.Button(self, text="Fechar", command=self.destroy, bg=config.COR_SECUNDARIA, fg="#ffffff", relief="flat", font=("Segoe UI", 9), padx=16, pady=5, cursor="hand2").pack(pady=8)


class JanelaTemplate(tk.Toplevel):
    VARIAVEIS = [("{nome}", "Nome / Razao Social"), ("{tipo}", "Tipo (A1 ou A3)"), ("{responsavel}", "Responsavel"), ("{vencimento}", "Data de vencimento"), ("{dias}", "Dias ate o vencimento"), ("{situacao}", "Texto da situacao"), ("{obs}", "Observacao"), ("{cor}", "Cor HTML conforme urgencia")]
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Template do E-mail")
        self.geometry("800x650")
        self.minsize(700, 480)
        self.resizable(True, True)
        self.grab_set()
        self._build()
        self._carregar()

    def _build(self):
        hdr = tk.Frame(self, bg=config.COR_PRIMARIA, height=44)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Editor de Template de E-mail", bg=config.COR_PRIMARIA, fg="#ffffff", font=("Segoe UI", 10, "bold")).pack(side="left", padx=12, pady=10)

        bf = tk.Frame(self, bg="#e2e8f0")
        bf.pack(fill="x", side="bottom", pady=10)
        btn_inner = tk.Frame(bf, bg="#e2e8f0")
        btn_inner.pack()
        tk.Button(btn_inner, text="Salvar", command=self._salvar, bg="#16a34a", fg="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), padx=14, pady=6, cursor="hand2").pack(side="left", padx=5)
        tk.Button(btn_inner, text="Pre-visualizar", command=self._preview, bg=config.COR_SECUNDARIA, fg="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), padx=14, pady=6, cursor="hand2").pack(side="left", padx=5)
        tk.Button(btn_inner, text="Restaurar padrao", command=self._restaurar, bg="#b45309", fg="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), padx=14, pady=6, cursor="hand2").pack(side="left", padx=5)
        tk.Button(btn_inner, text="Cancelar", command=self.destroy, bg="#64748b", fg="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), padx=14, pady=6, cursor="hand2").pack(side="left", padx=5)

        f_top = ttk.LabelFrame(self, text="Assunto", padding=8)
        f_top.pack(fill="x", padx=12, pady=(10, 4), side="top")
        self.var_assunto = tk.StringVar()
        ttk.Entry(f_top, textvariable=self.var_assunto, width=90).pack(fill="x")

        f_vars = ttk.LabelFrame(self, text="Variaveis - clique para inserir", padding=6)
        f_vars.pack(fill="x", padx=12, pady=4, side="bottom")
        for i, (var, desc) in enumerate(self.VARIAVEIS):
            col, row = i % 4, i // 4
            ttk.Button(f_vars, text=var, width=14, command=lambda v=var: self._inserir_variavel(v)).grid(row=row*2, column=col, padx=4, pady=2, sticky="w")
            ttk.Label(f_vars, text=desc, foreground="#666", font=("Arial", 7)).grid(row=row*2+1, column=col, padx=4, sticky="w")

        f_corpo = ttk.LabelFrame(self, text="Corpo do E-mail (HTML)", padding=8)
        f_corpo.pack(fill="both", expand=True, padx=12, pady=4, side="top")
        self.txt_corpo = tk.Text(f_corpo, wrap="word", font=("Courier New", 9), undo=True, height=12)
        sb = ttk.Scrollbar(f_corpo, command=self.txt_corpo.yview)
        self.txt_corpo.configure(yscrollcommand=sb.set)
        self.txt_corpo.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _carregar(self):
        t = email_service.carregar_template()
        self.var_assunto.set(t.get("assunto", email_service.TEMPLATE_PADRAO["assunto"]))
        self.txt_corpo.delete("1.0", "end")
        self.txt_corpo.insert("1.0", t.get("corpo", email_service.TEMPLATE_PADRAO["corpo"]))

    def _inserir_variavel(self, var):
        self.txt_corpo.insert(tk.INSERT, var)
        self.txt_corpo.focus()

    def _salvar(self):
        t = {"assunto": self.var_assunto.get().strip(), "corpo": self.txt_corpo.get("1.0", "end").strip()}
        if not t["assunto"] or not t["corpo"]:
            messagebox.showwarning("Atencao", "Assunto e corpo do e-mail nao podem ficar vazios.", parent=self)
            return
        ok, msg = email_service.salvar_template_verificado(t)
        if ok:
            messagebox.showinfo("Salvo", msg, parent=self)
            self._carregar()
        else: messagebox.showerror("Erro ao salvar", msg, parent=self)

    def _restaurar(self):
        if messagebox.askyesno("Confirmar", "Restaurar o template padrao?", parent=self):
            email_service.salvar_template(email_service.TEMPLATE_PADRAO)
            self._carregar()

    def _preview(self):
        corpo = self.txt_corpo.get("1.0", "end").strip()
        assunto = self.var_assunto.get()
        exemplo = {"nome": "Empresa Exemplo Ltda", "tipo": "A1", "responsavel": "Joao da Silva", "vencimento": str(date.today()), "dias": "10", "situacao": "vence em 10 dia(s)", "obs": "Renovar com urgencia", "cor": "#e74c3c"}
        try:
            for k, v in exemplo.items():
                corpo = corpo.replace("{" + k + "}", v)
                assunto = assunto.replace("{" + k + "}", v)
        except Exception as e:
            messagebox.showerror("Erro", str(e), parent=self)
            return

        win = tk.Toplevel(self)
        win.title("Pre-visualizacao")
        win.geometry("700x480")
        tk.Label(win, text=f"Assunto: {assunto}", font=("Segoe UI", 10, "bold"), fg="#1e293b").pack(anchor="w", padx=12, pady=(10, 2))
        ttk.Separator(win).pack(fill="x", padx=12, pady=4)
        txt = tk.Text(win, wrap="word", font=("Segoe UI", 9), state="normal", relief="flat")
        sb2 = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=sb2.set)
        txt.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(4, 12))
        sb2.pack(side="right", fill="y", pady=(4, 12), padx=(0, 4))
        txt.insert("1.0", corpo)
        txt.config(state="disabled")
        tk.Button(win, text="Fechar", command=win.destroy, bg=config.COR_SECUNDARIA, fg="#ffffff", relief="flat", font=("Segoe UI", 9), padx=14, pady=4, cursor="hand2").pack(pady=(0, 10))


class JanelaLogEmails(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Log de E-mails Enviados")
        self.geometry("1060x580")
        self.grab_set()
        self._registros_cache = []
        self._build()
        self.lbl_total.config(text="Utilize os filtros acima e clique em 'Filtrar' para procurar os registros.")

    def _build(self):
        hdr = tk.Frame(self, bg=config.COR_PRIMARIA, height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="  Log de E-mails Enviados", bg=config.COR_PRIMARIA, fg="#ffffff", font=("Segoe UI", 10, "bold")).pack(side="left", padx=12, pady=10)

        f_filtros = tk.Frame(self, bg="#f1f5f9", pady=8)
        f_filtros.pack(fill="x", padx=10, pady=(6, 0))

        tk.Label(f_filtros, text="De:", bg="#f1f5f9", font=("Segoe UI", 9)).grid(row=0, column=0, padx=(8,2), sticky="w")
        self.var_dt_ini = tk.StringVar()
        
        if TKCALENDAR_DISPONIVEL:
            self.cal_ini = DateEntry(f_filtros, textvariable=self.var_dt_ini, width=11, 
                                     date_pattern='y-mm-dd', background=config.COR_PRIMARIA, 
                                     foreground='white', borderwidth=2)
            self.cal_ini.grid(row=0, column=1, padx=2)
            self.cal_ini.delete(0, "end")
        else:
            self.cal_ini = ttk.Entry(f_filtros, textvariable=self.var_dt_ini, width=12)
            self.cal_ini.grid(row=0, column=1, padx=2)

        tk.Label(f_filtros, text="Ate:", bg="#f1f5f9", font=("Segoe UI", 9)).grid(row=0, column=2, padx=(8,2), sticky="w")
        self.var_dt_fim = tk.StringVar()
        
        if TKCALENDAR_DISPONIVEL:
            self.cal_fim = DateEntry(f_filtros, textvariable=self.var_dt_fim, width=11, 
                                     date_pattern='y-mm-dd', background=config.COR_PRIMARIA, 
                                     foreground='white', borderwidth=2)
            self.cal_fim.grid(row=0, column=3, padx=2)
            self.cal_fim.delete(0, "end")
        else:
            self.cal_fim = ttk.Entry(f_filtros, textvariable=self.var_dt_fim, width=12)
            self.cal_fim.grid(row=0, column=3, padx=2)

        tk.Label(f_filtros, text="Certificado:", bg="#f1f5f9", font=("Segoe UI", 9)).grid(row=0, column=4, padx=(12,2), sticky="w")
        self.var_cert = tk.StringVar()
        ttk.Entry(f_filtros, textvariable=self.var_cert, width=22).grid(row=0, column=5, padx=2)
        tk.Label(f_filtros, text="Status:", bg="#f1f5f9", font=("Segoe UI", 9)).grid(row=0, column=6, padx=(12,2), sticky="w")
        self.var_status = tk.StringVar(value="Todos")
        ttk.Combobox(f_filtros, textvariable=self.var_status, values=["Todos", "Enviado", "Erro"], state="readonly", width=10).grid(row=0, column=7, padx=2)
        tk.Label(f_filtros, text="Origem:", bg="#f1f5f9", font=("Segoe UI", 9)).grid(row=0, column=8, padx=(12,2), sticky="w")
        self.var_origem = tk.StringVar(value="Todos")
        ttk.Combobox(f_filtros, textvariable=self.var_origem, values=["Todos", "automatico", "manual"], state="readonly", width=12).grid(row=0, column=9, padx=2)
        tk.Label(f_filtros, text="Leitura:", bg="#f1f5f9", font=("Segoe UI", 9)).grid(row=0, column=10, padx=(12,2), sticky="w")
        self.var_lido = tk.StringVar(value="Todos")
        ttk.Combobox(f_filtros, textvariable=self.var_lido, values=["Todos", "Pendente", "Lido"], state="readonly", width=10).grid(row=0, column=11, padx=2)
        tk.Button(f_filtros, text="Filtrar", command=self._carregar, bg=config.COR_SECUNDARIA, fg="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=3, cursor="hand2").grid(row=0, column=10, padx=(10,2))
        tk.Button(f_filtros, text="Limpar", command=self._limpar_filtros, bg="#64748b", fg="#ffffff", relief="flat", font=("Segoe UI", 9), padx=8, pady=3, cursor="hand2").grid(row=0, column=13, padx=2)
        tk.Label(f_filtros, text="(formato: AAAA-MM-DD)", bg="#f1f5f9", fg="#94a3b8", font=("Segoe UI", 7)).grid(row=1, column=0, columnspan=4, sticky="w", padx=8)

        cols = ("data_hora", "cert_nome", "cert_tipo", "destinatarios", "assunto", "status", "origem", "lido", "data_leitura", "erro")
        headers = ("Data/Hora", "Certificado", "Tipo", "Destinatarios", "Assunto", "Status", "Origem", "Leitura", "Data Leitura", "Erro")
        widths = [130, 150, 45, 170, 200, 65, 75, 75, 110, 110]
        frame = tk.Frame(self, bg=config.COR_BG)
        frame.pack(fill="both", expand=True, padx=10, pady=(6, 0))
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for col, hdr_txt, w in zip(cols, headers, widths):
            self.tree.heading(col, text=hdr_txt)
            self.tree.column(col, width=w, minwidth=50)

        self.tree.tag_configure("enviado", foreground="#166534", background="#dcfce7")
        self.tree.tag_configure("erro", foreground="#991b1b", background="#fee2e2")
        self.tree.tag_configure("lido", foreground="#1e40af", background="#dbeafe")
        self.tree.bind("<Double-1>", self._duplo_clique)

        sb_y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        sb_x = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb_y.grid(row=0, column=1, sticky="ns")
        sb_x.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        f_bottom = tk.Frame(self, bg=config.COR_BG, pady=6)
        f_bottom.pack(fill="x", padx=10)
        self.lbl_total = tk.Label(f_bottom, text="", bg=config.COR_BG, fg="#64748b", font=("Segoe UI", 9))
        self.lbl_total.pack(side="left")
        tk.Button(f_bottom, text="✓ Marcar como Lido", command=self._marcar_lido, bg="#1d4ed8", fg="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), padx=10, pady=4, cursor="hand2").pack(side="right", padx=4)
        tk.Button(f_bottom, text="✗ Marcar como Pendente", command=self._marcar_pendente, bg="#64748b", fg="#ffffff", relief="flat", font=("Segoe UI", 9), padx=10, pady=4, cursor="hand2").pack(side="right", padx=4)
        tk.Button(f_bottom, text="Exportar para Excel (.xlsx)", command=self._exportar_excel, bg="#16a34a", fg="#ffffff", relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=4, cursor="hand2").pack(side="right", padx=4)
        tk.Button(f_bottom, text="Fechar", command=self.destroy, bg="#64748b", fg="#ffffff", relief="flat", font=("Segoe UI", 9), padx=12, pady=4, cursor="hand2").pack(side="right", padx=4)

    def _duplo_clique(self, event):
        sel = self.tree.selection()
        if not sel: return
        iid = sel[0]
        vals = self.tree.item(iid, "values")
        status_lido = vals[7] if len(vals) > 7 else "Pendente"
        log_id = self._id_do_iid(iid)
        if log_id is None: return
        database.marcar_log_lido(log_id, status_lido != "Lido")
        self._carregar()
        try:
            if hasattr(self.master, "atualizar_tabela"): self.master.atualizar_tabela()
        except Exception: pass

    def _id_do_iid(self, iid):
        idx = self.tree.index(iid)
        if 0 <= idx < len(self._registros_cache): return self._registros_cache[idx]["id"]
        return None

    def _marcar_lido(self):
        sel = self.tree.selection()
        if not sel: return messagebox.showwarning("Atencao", "Selecione um registro na lista.", parent=self)
        log_id = self._id_do_iid(sel[0])
        if log_id:
            database.marcar_log_lido(log_id, True)
            self._carregar()
            try:
                if hasattr(self.master, "atualizar_tabela"): self.master.atualizar_tabela()
            except Exception: pass

    def _marcar_pendente(self):
        sel = self.tree.selection()
        if not sel: return messagebox.showwarning("Atencao", "Selecione um registro na lista.", parent=self)
        log_id = self._id_do_iid(sel[0])
        if log_id:
            database.marcar_log_lido(log_id, False)
            self._carregar()
            try:
                if hasattr(self.master, "atualizar_tabela"): self.master.atualizar_tabela()
            except Exception: pass

    def _limpar_filtros(self):
        self.var_dt_ini.set("")
        self.var_dt_fim.set("")
        self.var_cert.set("")
        self.var_status.set("Todos")
        self.var_origem.set("Todos")
        self.var_lido.set("Todos")
        
        if hasattr(self, 'cal_ini'):
            self.cal_ini.delete(0, "end")
        if hasattr(self, 'cal_fim'):
            self.cal_fim.delete(0, "end")

        for row in self.tree.get_children(): self.tree.delete(row)
        self._registros_cache = []
        self.lbl_total.config(text="Utilize os filtros acima e clique em 'Filtrar' para procurar os registos.")

    def _carregar(self):
        for row in self.tree.get_children(): self.tree.delete(row)
        registros = database.carregar_log_emails(filtro_data_ini=self.var_dt_ini.get().strip(), filtro_data_fim=self.var_dt_fim.get().strip(), filtro_cert=self.var_cert.get().strip(), filtro_status=self.var_status.get(), filtro_origem=self.var_origem.get(), filtro_lido=self.var_lido.get())
        for r in registros:
            if r.get("lido") == "Lido": tag = "lido"
            elif r["status"] == "Enviado": tag = "enviado"
            else: tag = "erro"
            self.tree.insert("", "end", tags=(tag,), values=(r["data_hora"], r["cert_nome"], r["cert_tipo"], r["destinatarios"], r["assunto"], r["status"], r["origem"], r.get("lido") or "Pendente", r.get("data_leitura") or "", r.get("erro") or ""))
        self.lbl_total.config(text=f"{len(registros)} registro(s) encontrado(s)")
        self._registros_cache = registros

    def _exportar_excel(self):
        if not self._registros_cache:
            messagebox.showwarning("Atencao", "Nenhum registro para exportar.", parent=self)
            return
        destino = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")], initialfile=f"log_emails_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        if not destino: return
        try:
            try:
                import openpyxl
                from openpyxl.styles import Font, PatternFill, Alignment
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Log de E-mails"
                cabecalhos = ["Data/Hora", "Certificado", "Tipo", "Destinatarios", "Assunto", "Status", "Origem", "Leitura", "Data Leitura", "Erro"]
                chaves = ["data_hora", "cert_nome", "cert_tipo", "destinatarios", "assunto", "status", "origem", "lido", "data_leitura", "erro"]
                hdr_fill = PatternFill("solid", fgColor="1A2A4A")
                hdr_font = Font(bold=True, color="FFFFFF")
                for col_idx, cab in enumerate(cabecalhos, 1):
                    cell = ws.cell(row=1, column=col_idx, value=cab)
                    cell.fill, cell.font, cell.alignment = hdr_fill, hdr_font, Alignment(horizontal="center")
                for row_idx, r in enumerate(self._registros_cache, 2):
                    for col_idx, chave in enumerate(chaves, 1):
                        cell = ws.cell(row=row_idx, column=col_idx, value=r.get(chave, ""))
                        if r["status"] == "Erro": cell.fill = PatternFill("solid", fgColor="FEE2E2")
                        elif r["status"] == "Enviado": cell.fill = PatternFill("solid", fgColor="DCFCE7")
                for col in ws.columns:
                    max_len = max((len(str(c.value or "")) for c in col), default=0)
                    ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)
                wb.save(destino)
                messagebox.showinfo("Exportado", f"Arquivo Excel salvo em:\n{destino}", parent=self)
            except ImportError:
                import csv
                destino_csv = destino.replace(".xlsx", ".csv")
                with open(destino_csv, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.DictWriter(f, fieldnames=["data_hora","cert_nome","cert_tipo","destinatarios","assunto","status","origem","erro"])
                    writer.writeheader(); writer.writerows(self._registros_cache)
                messagebox.showinfo("Exportado", f"openpyxl nao instalado. Salvo como CSV:\n{destino_csv}\n\nPara Excel, instale: pip install openpyxl", parent=self)
        except Exception as e: messagebox.showerror("Erro", f"Nao foi possivel exportar:\n{e}", parent=self)

if __name__ == "__main__":
    app = App()
    app.mainloop()