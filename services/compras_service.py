#services/ComprasService.py
from sqlalchemy.orm import Session
from database.models import Produto, HistoricoPreco, Grupo, Usuario, GrupoUsuario
from services.gemini_service import NotaFiscalEstruturada
from datetime import datetime

class ComprasService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def obter_ou_criar_produto(self, nome_limpo: str, categoria: str) -> Produto:
        """Garante a normalização do produto (RF06), evitando duplicidade na tabela de produtos"""
        nome_upper = nome_limpo.strip().upper()
        
        # Tenta encontrar o produto já cadastrado pelo nome normalizado em caixa alta
        produto = self.db.query(Produto).filter(Produto.nome_normalizado == nome_upper).first()
        
        if not produto:
            # Se não existe, cria o registro do produto genérico
            produto = Produto(nome_normalizado=nome_upper, categoria=categoria)
            self.db.add(produto)
            self.db.flush()  # Executa o insert para gerar o ID sem comitar a transação inteira
            
        return produto

    def salvar_nota_fiscal(self, dados_nota: NotaFiscalEstruturada, grupo_id: int):
        """
        Recebe o objeto estruturado da IA e persiste os dados em massa no banco.
        Retorna a quantidade de itens salvos com sucesso.
        """
        itens_salvos = 0
        itens_salvos_list: list[dict] = []
        try:
            # Transforma a string de data da nota (YYYY-MM-DD) em objeto datetime do Python
            data_formatada = datetime.strptime(dados_nota.data_compra, "%Y-%m-%d")
            
            for item in dados_nota.itens:
                # 1. Resolve o ID do produto genérico/normalizado
                produto_db = self.obter_ou_criar_produto(item.nome_produto, item.categoria)
                
                # 2. Monta o registro histórico (A tabela fato)
                novo_historico = HistoricoPreco(
                    produto_id=produto_db.id,
                    grupo_id=grupo_id,
                    marca=item.marca,
                    valor_unitario=item.valor_unitario,
                    quantidade=item.quantidade,
                    unidade_medida=item.unidade_medida,
                    mercado=dados_nota.mercado,
                    data_compra=data_formatada,
                    valor_total=item.valor_total
                )
                self.db.add(novo_historico)
                itens_salvos += 1
                itens_salvos_list.append({
                    "nome_produto": item.nome_produto,
                    "valor_unitario": item.valor_unitario,
                    "quantidade": item.quantidade,
                    "valor_total": item.valor_total,
                })
            
            # Comita todas as operações de uma única vez (Garante atomicidade)
            self.db.commit()
            return {"count": itens_salvos, "itens": itens_salvos_list}
            
        except Exception as e:
            self.db.rollback() # Cancela tudo se der erro no meio do caminho para não quebrar o banco
            print(f"Erro crítico ao persistir nota fiscal: {e}")
            raise e