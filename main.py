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
    """Mecanismo assíncrono capaz de diferenciar qual usuário enviou a mensagem dentro do grupo"""
    if "message" not in payload:
        return

    message = payload["message"]
    chat_id = message["chat"]["id"]  # ID do Grupo (Ex: Casa X)
    
    # 🌟 CAPTURA DO USUÁRIO FÍSICO (Quem enviou)
    user_info = message.get("from")
    if not user_info:
        return  # Ignora mensagens do próprio sistema/canais
        
    user_id = user_info["id"]
    user_name = user_info.get("first_name", f"Usuário {user_id}")

    db = SessionLocal()
    compras_service = ComprasService(db)

    try:
        # 1. Garante que o grupo/casa existe no banco
        grupo = db.query(Grupo).filter(Grupo.id == chat_id).first()
        if not grupo:
            grupo = Grupo(id=chat_id, nome=f"Grupo Chat {chat_id}")
            db.add(grupo)
            db.commit()

        # 2. 🌟 MULTITENANCY: Garante que o usuário existe no banco
        usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
        if not usuario:
            usuario = Usuario(id=user_id, telegram_id=str(user_id), nome=user_name)
            db.add(usuario)
            db.commit()

        # 3. 🌟 MULTITENANCY: Garante o vínculo do usuário com aquela casa específica (Tabela pivô)
        vinculo = db.query(GrupoUsuario).filter(
            GrupoUsuario.grupo_id == chat_id, 
            GrupoUsuario.usuario_id == user_id
        ).first()
        if not vinculo:
            vinculo = GrupoUsuario(grupo_id=chat_id, usuario_id=user_id)
            db.add(vinculo)
            db.commit()

        # =====================================================================
        # O Usuário enviou uma FOTO (Nota Fiscal OU Etiqueta)
        # =====================================================================
        if "photo" in message:
            legenda = message.get("caption", "").strip().lower()
            
            foto = message["photo"][-1]
            file_id = foto["file_id"]
            
            imagem_bytes_original = await telegram_service.baixar_foto(file_id)
            imagem_bytes_tratada = ImageService.otimizar_imagem_nota(imagem_bytes_original)
            
            # Fluxo específico para etiquetas de preço (com legenda /cotar)
            if "/cotar" in legenda or "cotar" in legenda:
                await telegram_service.enviar_mensagem(chat_id, f"🔍 *{user_name}*, sua etiqueta está sendo processada! Buscando histórico...")
                
                nome_produto_limpo = gemini_service.extrair_produto_etiqueta(imagem_bytes_tratada)
                top3_resultados = compras_service.buscar_top3_precos(nome_produto_limpo)
                
                if not top3_resultados:
                    resposta = f"Não encontrei nenhum histórico de preço para *'{nome_produto_limpo}'* no banco do grupo.\n\n📍 *{user_name}*, qual o nome do mercado onde você está agora?"
                    produto_db = compras_service.obter_ou_criar_produto(nome_produto_limpo, "MERCEARIA")
                    produto_id = produto_db.id
                else:
                    resposta = f"📦 *Produto:* {nome_produto_limpo}\n\n🏆 *Melhores preços encontrados:*\n"
                    for idx, historico in enumerate(top3_resultados, 1):
                        data_fmt = historico.data_compra.strftime('%d/%m/%Y')
                        resposta += f"{idx}. *R$ {historico.valor_unitario:.2f}* no {historico.mercado} ({data_fmt})\n"
                    
                    resposta += f"\n📍 *{user_name}*, em qual mercado você está agora para analisar a tendência?"
                    produto_id = top3_resultados[0].produto_id

                await telegram_service.enviar_mensagem(chat_id, resposta)
                compras_service.salvar_estado_conversa(chat_id, "AGUARDANDO_MERCADO", produto_id)
                return

            # Fluxo padrão de Nota Fiscal
            else:
                await telegram_service.enviar_mensagem(chat_id, f"🧾 *Nota recebida de {user_name}!* Extraindo itens com IA...")
                dados_nota = gemini_service.extrair_nota_fiscal(imagem_bytes_tratada)

                # 🌟 AGORA PASSAMOS O USER_ID PARA O SALVAMENTO
                resultado_salvamento = compras_service.salvar_nota_fiscal(dados_nota, grupo_id=grupo.id, usuario_id=usuario.id)
                total_salvo = resultado_salvamento.get("count", 0)
                itens_salvos = resultado_salvamento.get("itens", [])

                resposta = f"✅ *Sucesso!* {total_salvo} itens salvos no histórico da casa por *{user_name}*.\n\n"
                resposta += f" 🏪 *Mercado:* {dados_nota.mercado}\n"
                resposta += f" 💰 *Total Geral:* R$ {dados_nota.valor_total_nota:.2f}\n\n*Produtos Adicionados:*\n"
                for item in itens_salvos:
                    resposta += f"- {item['nome_produto']}: R$ {item['valor_unitario']:.2f}\n"

                await telegram_service.enviar_mensagem(chat_id, resposta)

        # =====================================================================
        # O Usuário enviou um TEXTO (Comandos ou Resposta de Estado)
        # =====================================================================
        elif "text" in message:
            texto = message["text"].strip()
            
            estado_atual = compras_service.obter_estado_conversa(chat_id)
            if estado_atual and estado_atual.estado == "AGUARDANDO_MERCADO":
                produto_id = estado_atual.produto_contexto_id
                
                insight_tendencia = compras_service.analisar_tendencia_local(produto_id, texto)
                await telegram_service.enviar_mensagem(chat_id, insight_tendencia)
                
                compras_service.limpar_estado_conversa(chat_id)
                return

            if texto.startswith("/start"):
                await telegram_service.enviar_mensagem(
                    chat_id, 
                    f"Olá, *{user_name}*! Sou o Assistente de Compras da sua casa.\n\n"
                    "- Envie a *foto de uma nota fiscal* para registrar os seus gastos.\n"
                    "- Envie a *foto de uma etiqueta* com a legenda `/cotar` para ver históricos!"
                )
            else:
                # O texto capturado aqui futuramente alimentará as queries do Agente Analítico
                await telegram_service.enviar_mensagem(chat_id, f"Registrado, {user_name}. Em breve farei análises completas das suas mensagens!")

    except Exception as e:
        import traceback
        print("\n" + "="*50)
        print(f"ERRO CRÍTICO NO WEBHOOK: {e}")
        traceback.print_exc()
        print("="*50 + "\n")
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