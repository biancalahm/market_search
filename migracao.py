import sys
import os
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.models import engine

def executar_migracao_bruta():
    print("⚡ Iniciando alteração estrutural forçada no banco do Render...")
    
    with engine.connect() as conexao:
        transacao = conexao.begin()
        try:
            # 1. Remove temporariamente as amarras (Chaves Estrangeiras) para não travar o banco
            print("🔗 Desvinculando chaves estrangeiras temporariamente...")
            conexao.execute(text("ALTER TABLE grupo_usuarios DROP CONSTRAINT IF EXISTS grupo_usuarios_grupo_id_fkey;"))
            conexao.execute(text("ALTER TABLE historico_precos DROP CONSTRAINT IF EXISTS historico_precos_grupo_id_fkey;"))
            
            # 2. Modifica o ID da tabela principal de Grupos para BIGINT (Suporta até 9 sextilhões)
            print("📐 Alterando a tabela 'grupos' para BigInteger...")
            conexao.execute(text("ALTER TABLE grupos ALTER COLUMN id TYPE BIGINT;"))
            
            # 3. Modifica as chaves estrangeiras nas tabelas filhas para BIGINT
            print("📐 Alterando as tabelas filhas para BigInteger...")
            conexao.execute(text("ALTER TABLE grupo_usuarios ALTER COLUMN grupo_id TYPE BIGINT;"))
            conexao.execute(text("ALTER TABLE historico_precos ALTER COLUMN grupo_id TYPE BIGINT;"))
            
            # 4. Reconstrói as amarras (Chaves Estrangeiras) com segurança
            print("🔒 Reconstruindo as chaves estrangeiras...")
            conexao.execute(text("""
                ALTER TABLE grupo_usuarios 
                ADD CONSTRAINT grupo_usuarios_grupo_id_fkey 
                FOREIGN KEY (grupo_id) REFERENCES grupos(id) ON DELETE CASCADE;
            """))
            conexao.execute(text("""
                ALTER TABLE historico_precos 
                ADD CONSTRAINT historico_precos_grupo_id_fkey 
                FOREIGN KEY (grupo_id) REFERENCES grupos(id) ON DELETE CASCADE;
            """))
            
            transacao.commit()
            print("✨ SUCESSO: O banco de dados do Render agora aceita IDs longos do Telegram!")
            
        except Exception as e:
            transacao.rollback()
            print(f"❌ Erro crítico na migração: {e}")
            raise e

if __name__ == "__main__":
    executar_migracao_bruta()