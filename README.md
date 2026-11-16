# EasyPlan — API de recorte de fundo (Render)

Nossa própria API de recorte. A edge function `sync-corretores` manda cada foto de
corretor para cá, recebe o PNG sem fundo e só então chama o Magnific para o personagem.
Não gasta crédito nenhum do Magnific.

- `GET /saude` mostra se está no ar e acorda o serviço.
- `POST /remover`: o corpo é a imagem (JPG ou PNG) e a resposta é o PNG sem fundo.
- Modelo: `silueta`, o mesmo do rembg (licença MIT). Roda direto no onnxruntime, sem as
  bibliotecas pesadas do rembg. O recorte sai idêntico ao do rembg, e o pico de memória
  ficou em ~425 MB no teste com uma foto real de corretor. Com o rembg completo seriam
  ~680 MB, mais que os 512 MB do plano grátis.

## Como publicar (uma vez só)

1. Crie um repositório no GitHub chamado `easyplan-remover-fundo` e envie os 3 arquivos
   desta pasta: `Dockerfile`, `app.py` e `requirements.txt`.
2. No render.com, vá em **New → Web Service** e escolha esse repositório.
3. Preencha assim:
   - **Name:** `easyplan-remover-fundo`
   - **Language:** Docker
   - **Instance Type:** Free
   - **Health Check Path** (em Advanced): `/saude`
4. Clique em **Deploy Web Service**. A primeira construção leva uns 5 a 10 minutos.
5. O endereço deve ficar `https://easyplan-remover-fundo.onrender.com`. Se o Render
   colocar um final diferente, avise, porque o endereço precisa ser trocado na `sync-corretores`.

## Limites do plano grátis

- O serviço dorme depois de 15 minutos sem uso, e acordar leva cerca de 1 minuto.
  A `sync-corretores` manda acordá-lo logo no começo. Se mesmo assim não der tempo,
  a foto fica salva com fundo (.jpg) e é recortada na próxima sincronização.
- Tem 512 MB de memória, por isso o serviço recorta uma foto por vez e reduz fotos
  maiores que 1600 px.
