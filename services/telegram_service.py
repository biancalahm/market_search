#services/telegram_service.py
import httpx
from config.settings import settings

class TelegramService:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def enviar_mensagem(self, chat_id: int, texto: str) -> bool:
        """Envia uma resposta de texto para o usuário no Telegram"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": texto,
            "parse_mode": "Markdown"  # Permite negritos e itálicos amigáveis
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            return response.status_code == 200

    async def baixar_foto(self, file_id: str) -> bytes:
        """Obtém o arquivo de imagem enviado pelo usuário para passar ao Gemini"""
        url_get_file = f"{self.base_url}/getFile"
        async with httpx.AsyncClient() as client:
            # 1. Pede o caminho do arquivo para o Telegram
            res = await client.get(url_get_file, params={"file_id": file_id})
            file_path = res.json()["result"]["file_path"]
            
            # 2. Faz o download real dos bytes da imagem
            url_download = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            file_res = await client.get(url_download)
            return file_res.content