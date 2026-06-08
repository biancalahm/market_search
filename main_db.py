import sys
import os
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.models import Base, engine, inicializar_banco

def limpar_e_reiniciar_banco():
    print("🔥 Forçando a queda de conexões ativas no Render...")
    
    with engine.connect() as conexao:
        # Abre uma transação isolada fora dos blocos padrões
        conexao.execute(text("COMMIT;")) 
        
        try:
            # 1. Terminando todas as outras conexões ativas no banco de dados para evitar o travamento (Deadlock)
            conexao.execute(text("""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = current_database()
                  AND pid <> pg_backend_pid();
            """))
            print("🔌 Conexões antigas derrubadas com sucesso!")
            
            # 2. Agora sim, passa o trator no schema sem travar
            print("🗑️ Deletando o schema antigo...")
            conexao.execute(text("DROP SCHEMA public CASCADE;"))
            conexao.execute(text("CREATE SCHEMA public;"))
            conexao.execute(text("GRANT ALL ON SCHEMA public TO public;"))
            
            print("✨ Banco de dados totalmente zerado e limpo!")
        except Exception as e:
            print(f"❌ Erro ao limpar banco: {e}")
            raise e

    # 3. Cria as tabelas do zero com a estrutura nova (BigInteger, etc.)
    inicializar_banco()

if __name__ == "__main__":
    limpar_e_reiniciar_banco()