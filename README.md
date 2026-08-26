# Cursos Online — Fullstack

Plataforma de cursos online com:
- Frontend HTML/CSS/JavaScript responsivo
- API REST com FastAPI
- Banco SQLite com SQLAlchemy
- Cadastro/login com JWT
- Cursos, aulas, matrículas e progresso
- Área do aluno
- Painel administrativo simples
- Documentação automática da API em /docs

## Rodar no Ubuntu/Termux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Abra: http://127.0.0.1:8000

Usuário admin inicial:
- e-mail: admin@cursos.local
- senha: admin123

Troque essa senha antes de usar em produção.
