FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    MODELO_ARQUIVO=/modelos/silueta.onnx

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baixa o modelo "silueta" (o mesmo do rembg, 44 MB) durante a construção e confere
# se o arquivo é o certo. Assim o serviço não precisa baixar nada quando acorda.
RUN python - <<'EOF'
import hashlib, os, urllib.request
url = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/silueta.onnx"
esperado = "75da6c8d2f8096ec743d071951be73b4a8bc7b3e51d9a6625d63644f90ffeedb"
os.makedirs("/modelos", exist_ok=True)
dados = urllib.request.urlopen(url, timeout=300).read()
assert hashlib.sha256(dados).hexdigest() == esperado, "modelo baixado não confere"
open("/modelos/silueta.onnx", "wb").write(dados)
EOF

COPY app.py .

# O Render informa a porta na variável PORT.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
