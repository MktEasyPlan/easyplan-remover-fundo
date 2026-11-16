"""API de recorte de fundo do EasyPlan Studio (versão para o Render).

É a nossa própria API: recebe uma foto e devolve o PNG sem fundo.
Roda no plano grátis do Render (512 MB de memória, processador pequeno).

  GET  /saude    -> {"ok": true, "modelo": "silueta"}  (também usado para "acordar" o serviço)
  POST /remover  corpo = bytes da imagem (JPG ou PNG)  ->  resposta = PNG sem fundo

Se a variável REMOVER_FUNDO_KEY estiver definida no Render, o POST exige o
cabeçalho x-api-key com o mesmo valor. Sem ela, a rota fica aberta.

Modelo: "silueta" (o mesmo do rembg, licença MIT). O recorte é feito direto
com onnxruntime + numpy + Pillow, com o mesmo cálculo do rembg (resultado
idêntico), mas sem as bibliotecas pesadas dele. Assim o pico de memória fica
em ~400 MB, contra ~680 MB com o rembg completo, que não caberia nos 512 MB.
"""

import asyncio
import io
import os

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from PIL import Image, ImageOps

MODELO_ARQUIVO = os.environ.get("MODELO_ARQUIVO", "/modelos/silueta.onnx")
LADO_MAX = int(os.environ.get("LADO_MAX", "1600"))  # fotos maiores são reduzidas para caber na memória
LIMITE_BYTES = 15 * 1024 * 1024
CHAVE = os.environ.get("REMOVER_FUNDO_KEY", "").strip()

# Mesmo pré-processamento do rembg para o silueta / u2net.
LADO_MODELO = 320
MEDIA = np.array([0.485, 0.456, 0.406], dtype=np.float32)
DESVIO = np.array([0.229, 0.224, 0.225], dtype=np.float32)

opcoes = ort.SessionOptions()
opcoes.enable_cpu_mem_arena = False  # devolve a memória depois de cada foto
opcoes.enable_mem_pattern = False
opcoes.intra_op_num_threads = 1
opcoes.inter_op_num_threads = 1
sessao = ort.InferenceSession(MODELO_ARQUIVO, opcoes, providers=["CPUExecutionProvider"])
entrada_nome = sessao.get_inputs()[0].name

# Uma foto por vez: com 512 MB, dois recortes juntos podem estourar a memória.
fila = asyncio.Lock()

app = FastAPI()


def recortar(imagem: Image.Image) -> bytes:
    imagem = ImageOps.exif_transpose(imagem)  # corrige fotos de celular "deitadas"
    imagem = imagem.convert("RGBA") if imagem.mode in ("RGBA", "LA", "P") else imagem.convert("RGB")
    imagem.thumbnail((LADO_MAX, LADO_MAX))

    pequena = np.asarray(
        imagem.convert("RGB").resize((LADO_MODELO, LADO_MODELO), Image.Resampling.LANCZOS),
        dtype=np.float32,
    )
    pequena = pequena / max(float(pequena.max()), 1e-6)
    pequena = (pequena - MEDIA) / DESVIO
    x = np.expand_dims(pequena.transpose((2, 0, 1)), 0).astype(np.float32)

    saida = sessao.run(None, {entrada_nome: x})[0][:, 0, :, :]
    menor, maior = float(saida.min()), float(saida.max())
    saida = (saida - menor) / max(maior - menor, 1e-6)
    mascara = Image.fromarray((saida.squeeze() * 255).astype(np.uint8), mode="L").resize(
        imagem.size, Image.Resampling.LANCZOS
    )

    resultado = imagem.convert("RGBA")
    resultado.putalpha(mascara)
    buffer = io.BytesIO()
    # Sem optimize=True: no processador do plano grátis ele custava ~25% do tempo
    # para deixar o arquivo só ~5% menor.
    resultado.save(buffer, format="PNG", compress_level=6)
    return buffer.getvalue()


@app.get("/")
@app.get("/saude")
def saude():
    return {"ok": True, "modelo": os.path.basename(MODELO_ARQUIVO)}


@app.post("/remover")
async def remover_api(request: Request):
    if CHAVE and request.headers.get("x-api-key", "") != CHAVE:
        raise HTTPException(status_code=401, detail="Chave inválida")
    dados = await request.body()
    if not dados:
        raise HTTPException(status_code=400, detail="Envie a imagem no corpo da requisição")
    if len(dados) > LIMITE_BYTES:
        raise HTTPException(status_code=413, detail="Imagem maior que 15 MB")
    try:
        imagem = Image.open(io.BytesIO(dados))
        imagem.load()
    except Exception:
        raise HTTPException(status_code=400, detail="O arquivo não é uma imagem válida")
    async with fila:
        png = await asyncio.to_thread(recortar, imagem)
    return Response(content=png, media_type="image/png")
