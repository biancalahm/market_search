from sqlalchemy.orm import Session
from database.models import Produto, HistoricoPreco, Grupo, Usuario, GrupoUsuario, EstadoConversa
from services.gemini_service import ItemNotaFiscal, NotaFiscalEstruturada
from datetime import datetime

class ComprasService:
    def __init__(self, db_session: Session):
        self.db = db_session

    def obter_ou_criar_produto(self, nome_limpo: str, categoria: str) -> Produto:
        """Garante a normalização do produto (RF06), evitando duplicidade na tabela de produtos"""
        nome_upper = nome_limpo.strip().upper()
        
        produto = self.db.query(Produto).filter(Produto.nome_normalizado == nome_upper).first()
        
        if not produto:
            produto = Produto(nome_normalizado=nome_upper, categoria=categoria)
            self.db.add(produto)
            self.db.flush() 
            
        return produto

    def salvar_nota_fiscal(self, dados_nota: NotaFiscalEstruturada, grupo_id: int, usuario_id: int):
        """
        Persiste os dados da nota fiscal extraídos pela IA no banco,
        vinculando o registro tanto ao grupo (casa) quanto ao usuário que realizou o envio.
        """
        itens_salvos = 0
        itens_salvos_list: list[dict] = []
        try:
            data_formatada = datetime.strptime(dados_nota.data_compra, "%Y-%m-%d")
            
            for item in dados_nota.itens:
                produto_db = self.obter_ou_criar_produto(item.nome_produto, item.categoria)
                
                # Inclusão do parâmetro usuario_id para diferenciar os gastos do casal
                novo_historico = HistoricoPreco(
                    produto_id=produto_db.id,
                    grupo_id=grupo_id,
                    usuario_id=usuario_id,  # Vincula o criador do registro
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
            
            self.db.commit()
            return {"count": itens_salvos, "itens": itens_salvos_list}
            
        except Exception as e:
            self.db.rollback()
            print(f"Erro crítico ao persistir nota fiscal: {e}")
            raise e
        
    def buscar_top3_precos(self, nome_produto: str, grupo_id: int):
        """
        Busca as 3 compras mais baratas registradas para este produto.
        Isolado por grupo_id para impedir que uma casa veja os dados de outra.
        """
        query_produtos = self.db.query(Produto.id).filter(Produto.nome_normalizado.ilike(f"%{nome_produto.upper()}%"))
        
        #Adicionado filtro de isolamento por grupo_id
        top3 = (self.db.query(HistoricoPreco)
                .filter(HistoricoPreco.grupo_id == grupo_id)
                .filter(HistoricoPreco.produto_id.in_(query_produtos))
                .order_by(HistoricoPreco.valor_unitario.asc())
                .limit(3)
                .all())
        return top3

    def analisar_tendencia_local(self, produto_id: int, mercado_atual: str, grupo_id: int) -> str:
        """
        Busca compras anteriores daquele mesmo produto naquele mercado específico 
        dentro do histórico do próprio grupo para calcular a tendência local.
        """
        # Adicionado filtro de isolamento por grupo_id
        historico_local = (self.db.query(HistoricoPreco)
                           .filter(HistoricoPreco.grupo_id == grupo_id)
                           .filter(HistoricoPreco.produto_id == produto_id)
                           .filter(HistoricoPreco.mercado.ilike(f"%{mercado_atual.strip()}%"))
                           .order_by(HistoricoPreco.data_compra.desc())
                           .first())
        
        if not historico_local:
            return f"🔍 Não encontrei registros anteriores de compras deste produto no estabelecimento *{mercado_atual}*."
            
        data_fmt = historico_local.data_compra.strftime('%d/%m/%Y')
        return (f" *Tendência local para este mercado:*\n"
                f"No dia {data_fmt}, você comprou esse mesmo produto no *{historico_local.mercado}* "
                f"por *R$ {historico_local.valor_unitario:.2f}* (Quantidade: {historico_local.quantidade}).")
    
    def obter_estado_conversa(self, chat_id: int):
        """Busca se o chat possui alguma pendência de resposta"""
        return self.db.query(EstadoConversa).filter(EstadoConversa.chat_id == chat_id).first()

    def salvar_estado_conversa(self, chat_id: int, estado: str, produto_id: int):
        """Grava ou atualiza o estado atual da conversa no banco"""
        registro = self.obter_estado_conversa(chat_id)
        if registro:
            registro.estado = estado
            registro.produto_contexto_id = produto_id
        else:
            nuevo_estado = EstadoConversa(chat_id=chat_id, estado=estado, produto_contexto_id=produto_id)
            self.db.add(nuevo_estado)
        self.db.commit()

    def limpar_estado_conversa(self, chat_id: int):
        """Deleta o estado após o ciclo ser concluído com sucesso"""
        self.db.query(EstadoConversa).filter(EstadoConversa.chat_id == chat_id).delete()
        self.db.commit()