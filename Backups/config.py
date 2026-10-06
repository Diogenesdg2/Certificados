import os
import sys

def _pasta_base() -> str:
    """Retorna sempre a pasta do executável/script, independente do diretório atual."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

DB_FILE    = os.path.join(_pasta_base(), "certificados.db")
CHAVE_FILE = os.path.join(_pasta_base(), "chave.key")

# Cores do Tema
COR_PRIMARIA   = "#1a2a4a"
COR_SECUNDARIA = "#2563eb"
COR_ACENTO     = "#38bdf8"
COR_BG         = "#f0f4f8"
COR_BG_TABLE   = "#ffffff"
COR_TEXTO_CLR  = "#ffffff"
COR_OK         = "#dcfce7"
COR_ATENCAO    = "#fef9c3"
COR_CRITICO    = "#ffedd5"
COR_VENCIDO    = "#fee2e2"
COR_OK_FG      = "#166534"
COR_ATENCAO_FG = "#854d0e"
COR_CRITICO_FG = "#9a3412"
COR_VENCIDO_FG = "#991b1b"