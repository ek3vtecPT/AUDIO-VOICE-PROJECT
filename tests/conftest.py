import os
import sys
import tempfile
from pathlib import Path

# dados de teste numa pasta temporária (antes de importar o pacote)
os.environ["ESTUDIO_VOZ_DADOS"] = tempfile.mkdtemp(prefix="estudio-voz-teste-")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
