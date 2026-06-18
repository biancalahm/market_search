#main.py
from fastapi import FastAPI, Request, BackgroundTasks, status
from contextlib import asynccontextmanager
import uvicorn

from config.settings import settings
from database.models import inicializar_banco, SessionLocal, Grupo
from services.telegram_service import TelegramService
from services.gemini_service import GeminiService
from services.compras_service import ComprasService


from services.image_service import ImageService # <- Adicione a importação aqui



# Inicialização dos serviços
telegram_service = TelegramService()
gemini_service = GeminiService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa as tabelas do banco ao ligar o app
    inicializar_banco()
    yield

app = FastAPI(title="Smart Compras Bot", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ready", "bot": "@First_user_supermarket_bot"}

async def processar_evento_telegram(payload: dict):
    """Mecanismo assíncrono para processar as mensagens sem travar o Telegram"""
    if "message" not in payload:
        return

    message = payload["message"]
    chat_id = message["chat"]["id"]
    db = SessionLocal()
    compras_service = ComprasService(db)

    try:
        # 1. Garante que o grupo/chat existe no nosso banco (Regra de Negócio: Dados pertencem ao Grupo)
        grupo = db.query(Grupo).filter(Grupo.id == chat_id).first()
        if not grupo:
            grupo = Grupo(id=chat_id, nome=f"Grupo Chat {chat_id}")
            db.add(grupo)
            db.commit()

        if "photo" in message:
            await telegram_service.enviar_mensagem(chat_id, "📸 *Nota recebida!* Otimizando imagem e extraindo itens com IA... Aguarde.")
            
            foto = message["photo"][-1]
            file_id = foto["file_id"]
            
            # Download dos bytes originais vindos do Telegram
            imagem_bytes_original = await telegram_service.baixar_foto(file_id)
            
            #  MÁGICA DE ENGENHARIA DE DADOS: Otimização da imagem com OpenCV antes do Gemini
            imagem_bytes_tratada = ImageService.otimizar_imagem_nota(imagem_bytes_original)
            
            # Passamos os bytes limpos para o Gemini extrair
            dados_nota = gemini_service.extrair_nota_fiscal(imagem_bytes_tratada)

            # Salva no banco de dados e recebe detalhes dos itens salvos
            resultado_salvamento = compras_service.salvar_nota_fiscal(dados_nota, grupo_id=grupo.id)
            total_salvo = resultado_salvamento.get("count", 0)
            itens_salvos = resultado_salvamento.get("itens", [])

            # Monta resposta amigável listando produtos e preços
            resposta = f"*Sucesso!* {total_salvo} itens salvos no histórico do grupo.\n\n"
            resposta += f" *Mercado:* {dados_nota.mercado}\n"
            resposta += f" *Total Geral:* R$ {dados_nota.valor_total_nota:.2f}\n\n*Produtos Adicionados:*\n"
            for item in itens_salvos:
                resposta += f"- {item['nome_produto']}: R$ {item['valor_unitario']:.2f}\n"

            await telegram_service.enviar_mensagem(chat_id, resposta)

        #  CENÁRIO B: O Usuário enviou um TEXTO (Consulta ou Comando)
        elif "text" in message:
            texto = message["text"]
            
            if texto.startswith("/start"):
                await telegram_service.enviar_mensagem(
                    chat_id, 
                    "*Olá! Sou seu Assistente Inteligente de Compras.*\n\n"
                    "Envie a *foto de uma nota fiscal* para eu cadastrar os produtos automaticamente, ou faça perguntas sobre seus gastos!"
                )
            else:
                # Aqui entra o RF07 e RF08: Buscar histórico e responder em linguagem natural
                # Como o agente de consultas será o próximo passo, vamos colocar uma resposta temporária:
                await telegram_service.enviar_mensagem(chat_id, f"Você disse: '{texto}'. Em breve responderei consultas analíticas aqui!")

    except Exception as e:
        print(f"Erro ao processar mensagem do Telegram: {e}")
        await telegram_service.enviar_mensagem(chat_id, "Desculpe, ocorreu um erro interno ao processar sua solicitação.")
    finally:
        db.close()

@app.post("/webhook")
async def receber_webhook(request: Request, background_tasks: BackgroundTasks):
    """Rota que receberá os dados enviados pelo Telegram"""
    payload = await request.json()
    # Executa o processamento pesado em segundo plano para responder o Telegram em < 2 segundos
    background_tasks.add_task(processar_evento_telegram, payload)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)