import sqlite3
import threading
import json
from datetime import datetime, date
import config

_db_lock = threading.Lock()

def _conectar():
    conn = sqlite3.connect(config.DB_FILE, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def _executar_com_retry(func, tentativas=5, espera=0.5):
    import time
    ultimo_erro = None
    for i in range(tentativas):
        try:
            return func()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                ultimo_erro = e
                time.sleep(espera * (i + 1))
            else:
                raise
    raise ultimo_erro

def init_db():
    def _fazer():
        with _conectar() as conn:
            return conn
    _executar_com_retry(_fazer)
    with _db_lock, _conectar() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS certificados (
                id            TEXT PRIMARY KEY,
                tipo          TEXT NOT NULL DEFAULT 'A1',
                nome          TEXT NOT NULL,
                responsavel   TEXT DEFAULT '',
                vencimento    TEXT NOT NULL,
                obs           TEXT DEFAULT '',
                emails        TEXT DEFAULT '',
                arquivo_nome  TEXT DEFAULT '',
                arquivo_b64   TEXT DEFAULT '',
                arquivo_ext   TEXT DEFAULT 'pfx',
                senha_enc     TEXT DEFAULT '',
                ultimo_alerta TEXT DEFAULT '',
                dias_alerta   INTEGER DEFAULT 30,
                enviar_alerta INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS historico (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                cert_id   TEXT NOT NULL,
                data      TEXT NOT NULL,
                hora      TEXT NOT NULL,
                acao      TEXT NOT NULL,
                info_json TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS configuracoes (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS senha_mestre (
                id   INTEGER PRIMARY KEY CHECK (id = 1),
                hash TEXT NOT NULL,
                salt TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS log_emails (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora     TEXT NOT NULL,
                cert_id       TEXT NOT NULL,
                cert_nome     TEXT NOT NULL,
                cert_tipo     TEXT NOT NULL,
                destinatarios TEXT NOT NULL,
                assunto       TEXT NOT NULL,
                status        TEXT NOT NULL,
                erro          TEXT DEFAULT '',
                origem        TEXT NOT NULL DEFAULT 'automatico',
                lido          TEXT DEFAULT 'Pendente',
                data_leitura  TEXT DEFAULT ''
            );
            PRAGMA user_version;
        """)

def migrar_colunas_log():
    try:
        with _db_lock, _conectar() as conn:
            colunas_log = [row[1] for row in conn.execute("PRAGMA table_info(log_emails)").fetchall()]
            if "lido" not in colunas_log:
                conn.execute("ALTER TABLE log_emails ADD COLUMN lido TEXT DEFAULT 'Pendente'")
            if "data_leitura" not in colunas_log:
                conn.execute("ALTER TABLE log_emails ADD COLUMN data_leitura TEXT DEFAULT ''")
            colunas_cert = [row[1] for row in conn.execute("PRAGMA table_info(certificados)").fetchall()]
            if "dias_alerta" not in colunas_cert:
                conn.execute("ALTER TABLE certificados ADD COLUMN dias_alerta INTEGER DEFAULT 30")
            if "enviar_alerta" not in colunas_cert:
                conn.execute("ALTER TABLE certificados ADD COLUMN enviar_alerta INTEGER DEFAULT 1")
            colunas_mestre = [row[1] for row in conn.execute("PRAGMA table_info(senha_mestre)").fetchall()]
            if colunas_mestre and "salt" not in colunas_mestre:
                conn.execute("ALTER TABLE senha_mestre ADD COLUMN salt TEXT DEFAULT ''")
                conn.execute("DELETE FROM senha_mestre")
    except Exception as e:
        print(f"[aviso] Falha ao migrar colunas do banco: {e}")

def _row_to_cert(row) -> dict:
    c = dict(row)
    c["historico"] = []
    return c

def carregar_certificados() -> list:
    def _fazer():
        with _db_lock, _conectar() as conn:
            rows = conn.execute("SELECT * FROM certificados ORDER BY vencimento").fetchall()
            certs = []
            for row in rows:
                c = _row_to_cert(row)
                hist_rows = conn.execute("SELECT * FROM historico WHERE cert_id=? ORDER BY id DESC LIMIT 90", (c["id"],)).fetchall()
                c["historico"] = [{**json.loads(h["info_json"]), "data": h["data"], "hora": h["hora"], "acao": h["acao"]} for h in reversed(hist_rows)]
                certs.append(c)
            return certs
    return _executar_com_retry(_fazer)

def salvar_certificado(cert: dict):
    def _fazer():
      with _db_lock, _conectar() as conn:
        conn.execute("""
            INSERT INTO certificados
                (id, tipo, nome, responsavel, vencimento, obs, emails,
                 arquivo_nome, arquivo_b64, arquivo_ext, senha_enc, ultimo_alerta,
                 dias_alerta, enviar_alerta)
            VALUES
                (:id,:tipo,:nome,:responsavel,:vencimento,:obs,:emails,
                 :arquivo_nome,:arquivo_b64,:arquivo_ext,:senha_enc,:ultimo_alerta,
                 :dias_alerta,:enviar_alerta)
            ON CONFLICT(id) DO UPDATE SET
                tipo=excluded.tipo, nome=excluded.nome, responsavel=excluded.responsavel,
                vencimento=excluded.vencimento, obs=excluded.obs, emails=excluded.emails,
                arquivo_nome=excluded.arquivo_nome, arquivo_b64=excluded.arquivo_b64,
                arquivo_ext=excluded.arquivo_ext, senha_enc=excluded.senha_enc,
                ultimo_alerta=excluded.ultimo_alerta, dias_alerta=excluded.dias_alerta,
                enviar_alerta=excluded.enviar_alerta
        """, {
            "id": cert.get("id", ""), "tipo": cert.get("tipo", "A1"), "nome": cert.get("nome", ""),
            "responsavel": cert.get("responsavel", ""), "vencimento": cert.get("vencimento", ""),
            "obs": cert.get("obs", ""), "emails": cert.get("emails", ""),
            "arquivo_nome": cert.get("arquivo_nome", ""), "arquivo_b64": cert.get("arquivo_b64", ""),
            "arquivo_ext": cert.get("arquivo_ext", "pfx"), "senha_enc": cert.get("senha_enc", ""),
            "ultimo_alerta": cert.get("ultimo_alerta", ""), "dias_alerta": int(cert.get("dias_alerta", 30)),
            "enviar_alerta": 1 if cert.get("enviar_alerta", True) else 0,
          })
    _executar_com_retry(_fazer)

def excluir_certificado_db(cert_id: str):
    def _fazer():
        with _db_lock, _conectar() as conn:
            conn.execute("DELETE FROM historico WHERE cert_id=?", (cert_id,))
            conn.execute("DELETE FROM certificados WHERE id=?", (cert_id,))
    _executar_com_retry(_fazer)

def registrar_historico_db(cert_id: str, acao: str, **extras):
    info = json.dumps(extras, ensure_ascii=False)
    def _fazer():
        with _db_lock, _conectar() as conn:
            conn.execute("INSERT INTO historico (cert_id, data, hora, acao, info_json) VALUES (?,?,?,?,?)",
                (cert_id, str(date.today()), datetime.now().strftime("%H:%M:%S"), acao, info))
            conn.execute("DELETE FROM historico WHERE cert_id=? AND id NOT IN (SELECT id FROM historico WHERE cert_id=? ORDER BY id DESC LIMIT 90)", (cert_id, cert_id))
    _executar_com_retry(_fazer)

def registrar_log_email(cert: dict, destinatarios: list, assunto: str, status: str, erro: str = "", origem: str = "automatico"):
    def _fazer():
        with _db_lock, _conectar() as conn:
            conn.execute(
                "INSERT INTO log_emails (data_hora, cert_id, cert_nome, cert_tipo, destinatarios, assunto, status, erro, origem, lido, data_leitura) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cert.get("id", ""), cert.get("nome", ""), cert.get("tipo", ""), ", ".join(destinatarios), assunto, status, erro, origem, "Pendente", "")
            )
    _executar_com_retry(_fazer)

def marcar_log_lido(log_id: int, lido: bool):
    def _fazer():
        with _db_lock, _conectar() as conn:
            row = conn.execute("SELECT cert_id FROM log_emails WHERE id=?", (log_id,)).fetchone()
            cert_id = row["cert_id"] if row else None
            if lido:
                conn.execute("UPDATE log_emails SET lido='Lido', data_leitura=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), log_id))
                if cert_id: conn.execute("UPDATE certificados SET enviar_alerta=0 WHERE id=?", (cert_id,))
            else:
                conn.execute("UPDATE log_emails SET lido='Pendente', data_leitura='' WHERE id=?", (log_id,))
                if cert_id: conn.execute("UPDATE certificados SET enviar_alerta=1 WHERE id=?", (cert_id,))
    _executar_com_retry(_fazer)

def carregar_log_emails(filtro_data_ini="", filtro_data_fim="", filtro_cert="", filtro_status="", filtro_origem="", filtro_lido="") -> list:
    def _fazer():
        with _db_lock, _conectar() as conn:
            query = "SELECT * FROM log_emails WHERE 1=1"
            params = []
            if filtro_data_ini: query += " AND data_hora >= ?"; params.append(filtro_data_ini + " 00:00:00")
            if filtro_data_fim: query += " AND data_hora <= ?"; params.append(filtro_data_fim + " 23:59:59")
            if filtro_cert: query += " AND cert_nome LIKE ?"; params.append(f"%{filtro_cert}%")
            if filtro_status and filtro_status != "Todos": query += " AND status = ?"; params.append(filtro_status)
            if filtro_origem and filtro_origem != "Todos": query += " AND origem = ?"; params.append(filtro_origem)
            if filtro_lido and filtro_lido != "Todos": query += " AND lido = ?"; params.append(filtro_lido)
            query += " ORDER BY id DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
    return _executar_com_retry(_fazer)

def atualizar_ultimo_alerta(cert_id: str, data: str):
    def _fazer():
        with _db_lock, _conectar() as conn:
            conn.execute("UPDATE certificados SET ultimo_alerta=? WHERE id=?", (data, cert_id))
    _executar_com_retry(_fazer)

def get_config(chave: str, default=None):
    def _fazer():
        with _db_lock, _conectar() as conn:
            row = conn.execute("SELECT valor FROM configuracoes WHERE chave=?", (chave,)).fetchone()
            if row:
                try: return json.loads(row["valor"])
                except: return row["valor"]
            return default
    return _executar_com_retry(_fazer)

def set_config(chave: str, valor):
    def _fazer():
      with _db_lock, _conectar() as conn:
        conn.execute("INSERT INTO configuracoes (chave, valor) VALUES (?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, json.dumps(valor, ensure_ascii=False)))
    _executar_com_retry(_fazer)

def get_senha_mestre_db():
    with _db_lock, _conectar() as conn:
        return conn.execute("SELECT hash, salt FROM senha_mestre WHERE id=1").fetchone()

def set_senha_mestre_db(hash_senha, salt_hex):
    with _db_lock, _conectar() as conn:
        conn.execute("INSERT INTO senha_mestre (id, hash, salt) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET hash=excluded.hash, salt=excluded.salt", (hash_senha, salt_hex))