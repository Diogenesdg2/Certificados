import os
import base64
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
from cryptography.x509 import load_pem_x509_certificate
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
import config
import database

_PBKDF2_ITERACOES = 200_000

def _obter_fernet():
    if os.path.exists(config.CHAVE_FILE):
        with open(config.CHAVE_FILE, "rb") as f:
            chave = f.read()
    else:
        chave = Fernet.generate_key()
        with open(config.CHAVE_FILE, "wb") as f:
            f.write(chave)
    return Fernet(chave)

def criptografar_senha(senha: str) -> str:
    if not senha: return ""
    return _obter_fernet().encrypt(senha.encode()).decode()

def descriptografar_senha(senha_enc: str) -> str:
    if not senha_enc: return ""
    try: return _obter_fernet().decrypt(senha_enc.encode()).decode()
    except: return ""

def _hash_senha(senha: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, _PBKDF2_ITERACOES)
    return dk.hex()

def senha_mestre_definida() -> bool:
    return database.get_senha_mestre_db() is not None

def verificar_senha_mestre(senha: str) -> bool:
    row = database.get_senha_mestre_db()
    if not row: return False
    salt = bytes.fromhex(row["salt"])
    return row["hash"] == _hash_senha(senha, salt)

def definir_senha_mestre(senha: str):
    salt = os.urandom(16)
    hash_senha = _hash_senha(senha, salt)
    database.set_senha_mestre_db(hash_senha, salt.hex())

def arquivo_para_base64(caminho: str) -> str:
    with open(caminho, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def base64_para_arquivo(b64: str, destino: str):
    with open(destino, "wb") as f:
        f.write(base64.b64decode(b64))

def ler_certificado_pfx(caminho, senha):
    with open(caminho, "rb") as f: dados = f.read()
    _, cert, _ = load_key_and_certificates(dados, senha.encode() if senha else None, default_backend())
    nome = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    vencimento = cert.not_valid_after_utc.date() if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after.date()
    return nome, str(vencimento)

def ler_certificado_pem(caminho):
    with open(caminho, "rb") as f: dados = f.read()
    cert = load_pem_x509_certificate(dados, default_backend())
    nome = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    vencimento = cert.not_valid_after_utc.date() if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after.date()
    return nome, str(vencimento)