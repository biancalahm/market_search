import sys
import os

raiz_projeto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if raiz_projeto not in sys.path:
    sys.path.insert(0, raiz_projeto)

from services.gemini_service import GeminiService
from services.compras_service import ComprasService
from database.models import SessionLocal, Grupo, inicializar_banco

def rodar_fluxo_completo():
    # 1. Garante que as tabelas existem
    inicializar_banco()
    
    db = SessionLocal()
    gemini = GeminiService()
    compras = ComprasService(db)
    
    try:
        # 2. Garante que temos pelo menos um grupo de teste no banco para vincular a nota
        grupo_teste = db.query(Grupo).first()
        if not grupo_teste:
            grupo_teste = Grupo(nome="Grupo Amostragem MVP")
            db.add(grupo_teste)
            db.commit()
            db.refresh(grupo_teste)
            print(f"🏠 Grupo de teste criado com ID: {grupo_teste.id}")
        
        # 3. Processa a nota fiscal física caso ela exista na raiz
        if os.path.exists("img/nota2.jpeg"):
            with open("img/nota2.jpeg", "rb") as f:
                foto_bytes = f.read()
            
            print("🧠 1/2: Enviando imagem para estruturação no Gemini...")
            dados_estruturados = gemini.extrair_nota_fiscal(foto_bytes)
            
            print("💾 2/2: Persistindo dados extraídos no PostgreSQL do Render...")
            total = compras.salvar_nota_fiscal(dados_estruturados, grupo_id=grupo_teste.id)
            
            print(f"\n🎉 SUCESSO ABSOLUTO! {total} itens foram extraídos e salvos no seu banco de dados.")
        else:
            print("\nColoque uma foto chamada 'nota2.jpeg' na raiz do projeto para ver a mágica acontecer de ponta a ponta!")
            
    finally:
        db.close()

if __name__ == "__main__":
    rodar_fluxo_completo()