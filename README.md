# market_search

Projeto MVP para captura e registro de notas fiscais de supermercado via Telegram.

**Quick Start**
- **Python:** create and activate a virtualenv, then install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- **Config:** copie e edite o arquivo `.env` com suas chaves (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `DATABASE_URL`, `PORT`).

- **Inicializar o banco:**

```bash
python3 main_db.py
```

- **Executar a aplicação:**

```bash
python main.py
# ou
uvicorn main:app --reload --port 8000
```

**Arquivos principais**
- **`main.py`**: ponto de entrada da aplicação e webhook ([main.py](main.py)).
- **Config:** [config/settings.py](config/settings.py) (Pydantic Settings, carrega `.env`).
- **Modelos/DB:** [database/models.py](database/models.py) (SQLAlchemy models + inicialização), [database/connection.py](database/connection.py).
- **Serviços:** integrações em [services/telegram_service.py](services/telegram_service.py), [services/gemini_service.py](services/gemini_service.py), [services/compras_service.py](services/compras_service.py).

**Variáveis de ambiente importantes**
- `TELEGRAM_BOT_TOKEN`: token do bot Telegram.
- `GEMINI_API_KEY`: chave do serviço Gemini/GenAI.
- `DATABASE_URL`: URL do Postgres (ex: `postgresql://user:pass@host:5432/dbname`).
- `PORT`: porta do servidor (default 8000).

**Docker**
- Build e run (imagem básica):

```bash
docker build -t market_search:latest .
docker run -e DATABASE_URL="$DATABASE_URL" -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" -p 8000:8000 market_search:latest
```

**Testes / Execução local**
- Teste de fluxo de extração (manual): coloque uma imagem `img/nota2.jpeg` e execute:

```bash
python3 test/test_gemini.py
```

- Para rodar a suíte (se adicionada):

```bash
pytest -q
```

**Notas**
- Não comite o arquivo `.env` (está em `.gitignore`).
- `main_db.py` cria as tabelas com os modelos atuais — em desenvolvimento pode apagar dados.
- Abra issues ou peça ajuda caso tenha problemas com dependências (`pydantic`, `sqlalchemy`, `psycopg2-binary`).

---

Se quiser, eu posso adicionar um `Makefile` com comandos `setup`, `migrate` e `run`. 
