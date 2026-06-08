#database/models.py
import enum
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    String,
    Float,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    Boolean,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
from config.settings import settings


Base = declarative_base()


class CategoriaEnum(str, enum.Enum):
    HORTIFRUTI = "HORTIFRUTI"
    LATICINIOS_FRIOS = "LATICINIOS_FRIOS"
    ACOUGUE_PEIXARIA = "ACOUGUE_PEIXARIA"
    MERCEARIA = "MERCEARIA"
    PADARIA = "PADARIA"
    BEBIDAS = "BEBIDAS"
    LIMPEZA = "LIMPEZA"
    HIGIENE_PERFUMARIA = "HIGIENE_PERFUMARIA"
    CONGELADOS = "CONGELADOS"
    PET_SHOP = "PET_SHOP"
    UTILIDADES_DOMESTICAS = "UTILIDADES_DOMESTICAS"


class Grupo(Base):
    __tablename__ = "grupos"
    # Telegram/group chat ids can exceed 32-bit; use BigInteger
    id = Column(BigInteger, primary_key=True, autoincrement=False)
    nome = Column(String(100), nullable=False)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    historicos = relationship("HistoricoPreco", back_populates="grupo", cascade="all, delete-orphan")
    usuarios = relationship("GrupoUsuario", back_populates="grupo", cascade="all, delete-orphan")


class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(BigInteger, primary_key=True, autoincrement=False)
    telegram_id = Column(String(50), unique=True, nullable=False, index=True)
    nome = Column(String(100), nullable=False)
    grupos = relationship("GrupoUsuario", back_populates="usuario", cascade="all, delete-orphan")


class GrupoUsuario(Base):
    __tablename__ = "grupo_usuarios"
    grupo_id = Column(BigInteger, ForeignKey("grupos.id", ondelete="CASCADE"), primary_key=True)
    usuario_id = Column(BigInteger, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    data_associacao = Column(DateTime, default=datetime.utcnow)
    grupo = relationship("Grupo", back_populates="usuarios")
    usuario = relationship("Usuario", back_populates="grupos")


class Produto(Base):
    __tablename__ = "produtos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome_normalizado = Column(String(150), unique=True, nullable=False, index=True)
    categoria = Column(SAEnum(CategoriaEnum, name="categoria_enum"), nullable=False, index=True)
    historicos = relationship("HistoricoPreco", back_populates="produto")


class HistoricoPreco(Base):
    __tablename__ = "historico_precos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    produto_id = Column(ForeignKey("produtos.id", ondelete="RESTRICT"), nullable=False)
    grupo_id = Column(BigInteger, ForeignKey("grupos.id", ondelete="CASCADE"), nullable=False, index=True)
    marca = Column(String(100), nullable=True)
    valor_unitario = Column(Float, nullable=False)
    quantidade = Column(Float, nullable=False)
    unidade_medida = Column(String(20), nullable=False)
    mercado = Column(String(100), nullable=False, index=True)
    data_compra = Column(DateTime, nullable=False, index=True)
    valor_total = Column(Float, nullable=False)
    produto = relationship("Produto", back_populates="historicos")
    grupo = relationship("Grupo", back_populates="historicos")


# ENGINE
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def inicializar_banco():
    """Cria fisicamente as tabelas no PostgreSQL caso não existam"""
    print("Conectando ao PostgreSQL do Render e verificando tabelas/enums...")
    Base.metadata.create_all(bind=engine)
    print("Banco de dados pronto e normalizado para o MVP!")