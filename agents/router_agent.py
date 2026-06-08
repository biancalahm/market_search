from pydantic import BaseModel, Field
from enum import Enum
from google import genai
from config import settings

class IntencaoEnum(str, Enum):
    CONSULTA = "consulta"
    CADASTRO_MANUAL = "cadastro_manual"
    EXCLUSAO = "exclusao"
    OUTRO = "outro"

class RoteamentoUsuario(BaseModel):
    intencao: IntencaoEnum
    entidade_foco: str = Field(description="O produto ou categoria que o usuário mencionou, ex: 'café', 'leite'")

class RouterAgent:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = "gemini-2.5-flash"

    def classificar_mensagem(self, texto_usuario: str) -> RoteamentoUsuario:
        prompt = f"Analise a seguinte mensagem enviada por um usuário em um bot de compras e classifique a intenção: '{texto_usuario}'"
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RoteamentoUsuario,
                temperature=0.0
            )
        )
        return RoteamentoUsuario.model_validate_json(response.text)