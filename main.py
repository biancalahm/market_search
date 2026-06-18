from fastapi import FastAPI, Request, BackgroundTasks, status
from contextlib import asynccontextmanager
import uvicorn

from config.settings import settings
from database.models import inicializar_banco, SessionLocal, Grupo
from services.telegram_service import TelegramService
from services.gemini_service import GeminiService
from services.compras_service import ComprasService
from services.image_service import ImageService 

# Inicialização dos serviços globais
telegram_service = TelegramService()
gemini_service = GeminiService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa as tabelas do banco ao ligar o app (incluindo estados_conversa)
    inicializar_banco()
    yield

app = FastAPI(title="Smart Compras Bot", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ready", "bot": "@First_user_supermarket_bot"}

async def processar_evento_telegram(payload: dict):
    """Mecanismo assíncrono modificado para gerenciar máquina de estados (Notas vs Etiquetas)"""
    if "message" not in payload:
        return

    message = payload["message"]
    chat_id = message["chat"]["id"]
    db = SessionLocal()
    compras_service = ComprasService(db)

    try:
        # 1. Garante que o grupo/chat existe no banco
        grupo = db.query(Grupo).filter(Grupo.id == chat_id).first()
        if not grupo:
            grupo = Grupo(id=chat_id, nome=f"Grupo Chat {chat_id}")
            db.add(grupo)
            db.commit()

        # =====================================================================
        # O Usuário enviou uma FOTO (Nota Fiscal OU Etiqueta)
        # =====================================================================
        if "photo" in message:
            legenda = message.get("caption", "").strip().lower()
            
            foto = message["photo"][-1]
            file_id = foto["file_id"]
            
            # Download e otimização de imagem
            imagem_bytes_original = await telegram_service.baixar_foto(file_id)
            imagem_bytes_tratada = ImageService.otimizar_imagem_nota(imagem_bytes_original)
            
            # 🔍 SUB-CASO A.1: É uma Etiqueta de Preço para Cotação (/cotar)
            if "/cotar" in legenda or "cotar" in legenda:
                await telegram_service.enviar_mensagem(chat_id, "*Etiqueta recebida!* Identificando produto e buscando histórico...")
                
                # Extrai apenas o nome limpo do produto usando o Gemini
                nome_produto_limpo = gemini_service.extrair_produto_etiqueta(imagem_bytes_tratada)
                
                # Busca os 3 menores preços registrados na tabela fato HistoricoPreco
                top3_resultados = compras_service.buscar_top3_precos(nome_produto_limpo)
                
                if not top3_resultados:
                    resposta = f"Não encontrei nenhum histórico de preço para *'{nome_produto_limpo}'* no banco do grupo.\n\n*Qual o nome do mercado* onde você está agora para iniciarmos o histórico dele?"
                    # Puxa ou cria o produto na categoria padrão para capturar o ID
                    produto_db = compras_service.obter_ou_criar_produto(nome_produto_limpo, "MERCEARIA")
                    produto_id = produto_db.id
                else:
                    resposta = f"*Produto:* {nome_produto_limpo}\n\n *Melhores preços encontrados:*\n"
                    for idx, historico in enumerate(top3_resultados, 1):
                        data_fmt = historico.data_compra.strftime('%d/%m/%Y')
                        resposta += f"{idx}. *R$ {historico.valor_unitario:.2f}* no {historico.mercado} ({data_fmt})\n"
                    
                    resposta += "\n*Em qual mercado você está agora* para eu analisar a tendência de preço local?"
                    produto_id = top3_resultados[0].produto_id

                await telegram_service.enviar_mensagem(chat_id, resposta)
                
                # Ativa o Estado no banco: Próxima mensagem de texto será tratada como o mercado
                compras_service.salvar_estado_conversa(chat_id, "AGUARDANDO_MERCADO", produto_id)
                return

            # Fluxo padrão de Nota Fiscal
            else:
                await telegram_service.enviar_mensagem(chat_id, "*Nota recebida!* Otimizando imagem e extraindo itens com IA... Aguarde.")
                dados_nota = gemini_service.extrair_nota_fiscal(imagem_bytes_tratada)

                resultado_salvamento = compras_service.salvar_nota_fiscal(dados_nota, grupo_id=grupo.id)
                total_salvo = resultado_salvamento.get("count", 0)
                itens_salvos = resultado_salvamento.get("itens", [])

                resposta = f"*Sucesso!* {total_salvo} itens salvos no histórico do grupo.\n\n"
                resposta += f" *Mercado:* {dados_nota.mercado}\n"
                resposta += f" *Total Geral:* R$ {dados_nota.valor_total_nota:.2f}\n\n*Produtos Adicionados:*\n"
                for item in itens_salvos:
                    resposta += f"- {item['nome_produto']}: R$ {item['valor_unitario']:.2f}\n"

                await telegram_service.enviar_mensagem(chat_id, resposta)

        # =====================================================================
        #  O Usuário enviou um TEXTO (Comandos ou Resposta de Estado)
        # =====================================================================
        elif "text" in message:
            texto = message["text"].strip()
            
          
            estado_atual = compras_service.obter_estado_conversa(chat_id)
            if estado_atual and estado_atual.estado == "AGUARDANDO_MERCADO":
                produto_id = estado_atual.produto_contexto_id
                
                # Executa a query analítica de tendência
                insight_tendencia = compras_service.analisar_tendencia_local(produto_id, texto)
                await telegram_service.enviar_mensagem(chat_id, insight_tendencia)
                
                # Ciclo finalizado! Remove o estado do banco
                compras_service.limpar_estado_conversa(chat_id)
                return

          
            if texto.startswith("/start"):
                await telegram_service.enviar_mensagem(
                    chat_id, 
                    "*Sou seu Assistente  de Compras.*\n\n"
                    "- Envie a *foto de uma nota fiscal* para registrar.\n"
                    "- Envie a *foto de uma etiqueta de preço* com a legenda `/cotar` para ver históricos e tendências!"
                )
            else:
                await telegram_service.enviar_mensagem(chat_id, f"Você disse: '{texto}'. Em breve te trago o resultado!!")

    except Exception as e:
        print(f"Erro ao processar mensagem do Telegram: {e}")
        await telegram_service.enviar_mensagem(chat_id, "Desculpe, ocorreu um erro interno ao processar sua solicitação.")
    finally:
        db.close()

@app.post("/webhook")
async def receber_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(processar_evento_telegram, payload)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)