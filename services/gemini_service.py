import json
from google import genai
from google.genai import types
import ollama  # Biblioteca para conectar com o Qwen local
from pydantic import BaseModel, Field
from typing import List, Optional
from config.settings import settings

# =====================================================================
# CONTRATOS DE DADOS (Pydantic)
# =====================================================================
class ItemNotaFiscal(BaseModel):
    nome_produto: str = Field(description="Nome genérico e limpo extraído da nota fiscal")
    marca: Optional[str] = Field(None, description="Marca do produto, se legível")
    categoria: str = Field(description="Categoria genérica mercadológica em português")
    quantidade: float = Field(description="Quantidade comprada do item")
    unidade_medida: str = Field(description="Unidade de medida simplificada. Ex: UN, KG, L")
    valor_unitario: float = Field(description="Preço pago por unidade")
    valor_total: float = Field(description="Preço total pago por este item")

class NotaFiscalEstruturada(BaseModel):
    mercado: str = Field(description="Nome do estabelecimento / supermercado")
    data_compra: str = Field(description="Data da compra extraída no formato ISO YYYY-MM-DD")
    valor_total_nota: float = Field(description="Valor total geral da nota fiscal")
    itens: List[ItemNotaFiscal] = Field(description="Lista contendo todos os produtos identificados")


# =====================================================================
# SERVIÇO DE INTERFACE COM MÚLTIPLOS PROVEDORES DE IA
# =====================================================================
class GeminiService:
    def __init__(self):
        # Define qual IA usar baseado no .env (Opções: "gemini" ou "ollama")
        # Se não configurado, o padrão assume o "gemini" para manter retrocompatibilidade
        self.provider = getattr(settings, "PROVEDOR_IA").lower()
        
        # Inicializa o cliente correspondente
        if self.provider == "gemini":
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self.model_name = "gemini-2.5-flash"
        else:
            # Para o Ollama, o modelo será o Qwen configurado
            self.model_name = getattr(settings, "OLLAMA_MODEL", "qwen2.5:latest")

    def _obter_prompt_extracao(self) -> str:
        """Centraliza o prompt de auditoria para garantir consistência entre modelos"""
        categorias_sistema = [
            "HORTIFRUTI", "LATICINIOS_FRIOS", "ACOUGUE_PEIXARIA", "MERCEARIA", 
            "PADARIA", "BEBIDAS", "LIMPEZA", "HIGIENE_PERFUMARIA", "CONGELADOS", 
            "PET_SHOP", "UTILIDADES_DOMESTICAS"
        ]
        
        return f"""
        Você é um auditor de dados multimodal e sua missão é extrair com 100% de precisão os itens desta nota fiscal de supermercado.

        Regras de Integridade de Dados (CRUCIAIS):
        1. PRECISÃO ABSOLUTA: Extraia apenas o texto que você tem certeza absoluta que está impresso. É PROIBIDO inventar, completar com base em adivinhação ou trocar nomes de produtos com base em probabilidade (ex: nunca troque um borrão por 'arroz').
        2. TRATAMENTO DE AMBIGUIDADE (Regra Anti-Carvão): Se um item for impossível de ler com clareza total, você DEVE retornar o campo 'nome_produto' exatamente como 'ITEM_NAO_IDENTIFICADO'. Eu prefiro ter um dado vazio a ter um dado mentiroso no banco de dados.
        
        Extração de Campos:
        1. nome_produto: Deve ser o nome GENÉRICO e LIMPO do produto, sem marca e peso (ex: 'Creme de Leite').
        2. marca: Apenas o nome da marca, se estiver 100% legível. Caso contrário, null.
        3. categoria: Classifique o item OBRIGATORIAMENTE em uma destas strings exatas, baseando-se estritamente na descrição do nome_produto que você extraiu com precisão:
           {categorias_sistema}

           Guia de Apoio para Classificação:
           - Brócolis, frutas -> HORTIFRUTI
           - Carvão para churrasco, fósforos, velas -> BAZAR_ELETRO # <- Regra explícita adicionada
           - Creme de leite, queijo -> LATICINIOS_FRIOS
           - Arroz, feijão -> MERCEARIA"""

    def extrair_nota_fiscal(self, imagem_bytes: bytes, mime_type: str = "image/jpeg") -> NotaFiscalEstruturada:
        """
        Executa a extração usando a inteligência configurada no ecossistema (.env).
        Se for Qwen (Ollama), assume que a imagem já foi pré-processada/convertida em string de texto.
        """
        prompt = self._obter_prompt_extracao()

        # 🟢 PROVEDOR A: GEMINI (Multimodal Nativo)
        if self.provider == "gemini":
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[
                        types.Part.from_bytes(data=imagem_bytes, mime_type=mime_type),
                        prompt
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=NotaFiscalEstruturada,
                        temperature=0.0,
                    )
                )
                return NotaFiscalEstruturada.model_validate_json(response.text)
            except Exception as e:
                print(f"Erro crítico na extração com Gemini: {e}")
                raise e

        # 🔵 PROVEDOR B: OLLAMA / QWEN (Processamento de Texto Estruturado)
        else:
            try:
                # Nota Sênior: Como o Qwen padrão não possui visão, decodificamos os bytes tratados 
                # assumindo que a camada anterior de OCR enviou a string textual da nota no parâmetro.
                texto_da_nota = imagem_bytes.decode('utf-8', errors='ignore')
                
                conteudo_input = f"\nTexto Bruto Extraído da Nota Fiscal:\n{texto_da_nota}\n{prompt}\n"
                
                # Chamada utilizando a feature de Structured Outputs do Ollama (disponível nas versões recentes)
                response = ollama.chat(
                    model=self.model_name,
                    messages=[{'role': 'user', 'content': conteudo_input}],
                    options={'temperature': 0.1},
                    format=NotaFiscalEstruturada.model_json_schema() # Força o Qwen a seguir o schema Pydantic
                )
                
                json_puro = response['message']['content']
                return NotaFiscalEstruturada.model_validate_json(json_puro)
                
            except Exception as e:
                print(f"Erro crítico na extração com Ollama/Qwen: {e}")
                raise e
  
    

    def responder_consulta_historica(self, pergunta_usuario: str, historico_contexto_txt: str) -> str:
        """Responde às consultas analíticas do usuário usando o provedor ativo."""
        prompt = f"""
        Você é o cérebro analítico do assistente inteligente de compras.
        Sua missão é responder à pergunta do usuário baseando-se estritamente no histórico de compras fornecido abaixo.

        Histórico do Grupo (Dados Reais do Banco de Dados):
        {historico_contexto_txt}

        Regras de Negócio Cruciais:
        1. Se o histórico estiver vazio ou não contiver dados suficientes, responda exatamente: "Não há histórico suficiente para responder essa consulta."
        2. Seja direto, claro e formate a resposta com tópicos amigáveis para leitura no Telegram.

        Pergunta do Usuário: {pergunta_usuario}
        Resposta:
        """
        
        if self.provider == "gemini":
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.2)
                )
                return response.text
            except Exception as e:
                return f"Erro ao processar consulta no Gemini: {e}"
        else:
            try:
                response = ollama.chat(
                    model=self.model_name,
                    messages=[{'role': 'user', 'content': prompt}],
                    options={'temperature': 0.2}
                )
                return response['message']['content']
            except Exception as e:
                return f"Erro ao processar consulta no Ollama/Qwen: {e}"
            
    def extrair_produto_etiqueta(self, imagem_bytes: bytes) -> str:
        """Extrai apenas o nome limpo e normalizado do produto a partir da foto de uma etiqueta."""
        prompt = """
        Você é um scanner especialista em gôndolas de supermercado.
        Olhe para a foto desta etiqueta de preço e extraia APENAS o nome do produto  Deve ser o nome GENÉRICO e LIMPO  sem marca e peso limpo e genérico do produto principal e o valor de Varejo.
        
        Regras:
        - Remova pesos, volumes e marcas se poluírem o nome base (Ex: 'SABÃO EM PÓ OMO HYPER 1KG' vira 'Sabão em Pó').
        - Retorne única e exclusivamente uma string com o nome limpo. Não responda com frases ou JSON.
        """
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[types.Part.from_bytes(data=imagem_bytes, mime_type="image/jpeg"), prompt]
        )
        return response.text.strip()