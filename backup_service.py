import os
import zipfile
import glob
from datetime import datetime

# Importamos o config para saber onde está a base de dados atual
import config

def realizar_backup_diario(dias_retencao=15, forcar=False):
    """
    Cria um ficheiro .zip com a base de dados e a chave de encriptação.
    Mantém apenas os últimos 'dias_retencao' ficheiros.
    """
    try:
        # A pasta principal onde o programa está a correr
        pasta_base = os.path.dirname(os.path.abspath(config.DB_FILE))
        
        # Cria uma subpasta chamada "Backups" (se não existir)
        pasta_backup = os.path.join(pasta_base, "Backups")
        if not os.path.exists(pasta_backup):
            os.makedirs(pasta_backup)
            
        hoje = datetime.now().strftime("%Y-%m-%d")
        hora = datetime.now().strftime("%H%M%S")
        
        # Se for manual (forçado), adicionamos a hora para não sobrepor o automático
        if forcar:
            nome_zip = f"backup_{hoje}_{hora}.zip"
        else:
            nome_zip = f"backup_{hoje}.zip"
            
        caminho_zip = os.path.join(pasta_backup, nome_zip)
        
        # Se já existe um backup automático para hoje e não estamos a forçar, ignoramos
        if os.path.exists(caminho_zip) and not forcar:
            return True, f"O backup de hoje já foi realizado."
            
        # Lista dos ficheiros mais vitais do sistema
        arquivos_para_salvar = [
            config.DB_FILE,                                 # certificados.db
            os.path.join(pasta_base, "chave.key")           # chave de encriptação
        ]
        
        # Cria o ficheiro ZIP e comprime os dados
        with zipfile.ZipFile(caminho_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for arq in arquivos_para_salvar:
                if os.path.exists(arq):
                    zipf.write(arq, os.path.basename(arq))
                    
        # --- Limpeza de Backups Antigos ---
        # Procura todos os zips de backup na pasta
        arquivos_antigos = glob.glob(os.path.join(pasta_backup, "backup_*.zip"))
        
        # Ordena do mais recente para o mais antigo
        arquivos_antigos.sort(key=os.path.getmtime, reverse=True)
        
        # Apaga todos os que passarem do limite de retenção (ex: 15 dias)
        for arq_antigo in arquivos_antigos[dias_retencao:]:
            try:
                os.remove(arq_antigo)
            except Exception:
                pass # Ignora se não conseguir apagar um ficheiro antigo (ex: em uso)
                
        return True, f"Backup criado com sucesso em:\n{caminho_zip}"
        
    except Exception as e:
        return False, str(e)