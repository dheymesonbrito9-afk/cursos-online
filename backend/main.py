from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import hashlib
import secrets
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "cursos.db"
FRONTEND = BASE / "frontend"

app = Flask(__name__)

tokens = {}


def conectar():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def hash_senha(senha, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    senha_hash = hashlib.pbkdf2_hmac(
        "sha256",
        senha.encode(),
        salt.encode(),
        100_000
    ).hex()

    return salt + ":" + senha_hash


def verificar_senha(senha, armazenada):
    salt, senha_hash = armazenada.split(":")
    teste = hashlib.pbkdf2_hmac(
        "sha256",
        senha.encode(),
        salt.encode(),
        100_000
    ).hex()

    return secrets.compare_digest(teste, senha_hash)


def iniciar_banco():
    conn = conectar()

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        admin INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS cursos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        descricao TEXT,
        imagem TEXT,
        preco INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS aulas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        curso_id INTEGER NOT NULL,
        titulo TEXT NOT NULL,
        conteudo TEXT,
        video_url TEXT,
        posicao INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS matriculas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        curso_id INTEGER NOT NULL,
        UNIQUE(usuario_id, curso_id)
    );

    CREATE TABLE IF NOT EXISTS progresso (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER NOT NULL,
        aula_id INTEGER NOT NULL,
        concluida INTEGER DEFAULT 0,
        UNIQUE(usuario_id, aula_id)
    );
    """)

    admin = conn.execute(
        "SELECT id FROM usuarios WHERE email = ?",
        ("admin@cursos.local",)
    ).fetchone()

    if not admin:
        conn.execute(
            "INSERT INTO usuarios (nome,email,senha,admin) VALUES (?,?,?,1)",
            (
                "Administrador",
                "admin@cursos.local",
                hash_senha("admin123")
            )
        )

    quantidade = conn.execute(
        "SELECT COUNT(*) FROM cursos"
    ).fetchone()[0]

    if quantidade == 0:

        cursos = [
            (
                "Python do Zero ao Profissional",
                "Aprenda Python, lógica e automação na prática.",
                "https://images.unsplash.com/photo-1526379095098-d400fd0bf935?auto=format&fit=crop&w=900&q=80",
                0
            ),
            (
                "HTML, CSS e JavaScript",
                "Construa sites modernos e responsivos.",
                "https://images.unsplash.com/photo-1498050108023-c5249f4df085?auto=format&fit=crop&w=900&q=80",
                0
            )
        ]

        for curso in cursos:
            cursor = conn.execute(
                "INSERT INTO cursos (titulo,descricao,imagem,preco) VALUES (?,?,?,?)",
                curso
            )

            curso_id = cursor.lastrowid

            aulas = [
                ("Introdução", "Bem-vindo ao curso.", 1),
                ("Fundamentos", "Aprenda os conceitos fundamentais.", 2),
                ("Projeto prático", "Coloque o conhecimento em prática.", 3)
            ]

            for titulo, conteudo, posicao in aulas:
                conn.execute(
                    """
                    INSERT INTO aulas
                    (curso_id,titulo,conteudo,posicao)
                    VALUES (?,?,?,?)
                    """,
                    (curso_id, titulo, conteudo, posicao)
                )

    conn.commit()
    conn.close()


def usuario_atual():
    token = request.headers.get("Authorization", "")

    if not token.startswith("Bearer "):
        return None

    token = token.replace("Bearer ", "")
    usuario_id = tokens.get(token)

    if not usuario_id:
        return None

    conn = conectar()

    usuario = conn.execute(
        "SELECT * FROM usuarios WHERE id = ?",
        (usuario_id,)
    ).fetchone()

    conn.close()

    return usuario


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "backend": "Flask",
        "database": "SQLite"
    })


@app.route("/api/auth/register", methods=["POST"])
def registrar():

    dados = request.json

    nome = dados.get("name")
    email = dados.get("email")
    senha = dados.get("password")

    if not nome or not email or not senha:
        return jsonify({"detail": "Preencha todos os campos"}), 400

    if len(senha) < 6:
        return jsonify({
            "detail": "A senha precisa ter pelo menos 6 caracteres"
        }), 400

    conn = conectar()

    try:
        cursor = conn.execute(
            """
            INSERT INTO usuarios
            (nome,email,senha)
            VALUES (?,?,?)
            """,
            (nome, email, hash_senha(senha))
        )

        conn.commit()

        usuario = {
            "id": cursor.lastrowid,
            "name": nome,
            "email": email,
            "is_admin": False
        }

        return jsonify(usuario)

    except sqlite3.IntegrityError:
        return jsonify({
            "detail": "E-mail já cadastrado"
        }), 400

    finally:
        conn.close()


@app.route("/api/auth/login", methods=["POST"])
def login():

    dados = request.json

    email = dados.get("email")
    senha = dados.get("password")

    conn = conectar()

    usuario = conn.execute(
        "SELECT * FROM usuarios WHERE email = ?",
        (email,)
    ).fetchone()

    conn.close()

    if not usuario or not verificar_senha(
        senha,
        usuario["senha"]
    ):
        return jsonify({
            "detail": "E-mail ou senha inválidos"
        }), 401

    token = secrets.token_urlsafe(32)

    tokens[token] = usuario["id"]

    return jsonify({
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": usuario["id"],
            "name": usuario["nome"],
            "email": usuario["email"],
            "is_admin": bool(usuario["admin"])
        }
    })


@app.route("/api/me")
def me():

    usuario = usuario_atual()

    if not usuario:
        return jsonify({"detail": "Não autenticado"}), 401

    return jsonify({
        "id": usuario["id"],
        "name": usuario["nome"],
        "email": usuario["email"],
        "is_admin": bool(usuario["admin"])
    })


@app.route("/api/courses")
def cursos():

    conn = conectar()

    cursos = conn.execute("""
        SELECT
            c.id,
            c.titulo,
            c.descricao,
            c.imagem,
            c.preco,
            COUNT(a.id) AS aulas
        FROM cursos c
        LEFT JOIN aulas a
        ON a.curso_id = c.id
        GROUP BY c.id
    """).fetchall()

    conn.close()

    return jsonify([
        {
            "id": c["id"],
            "title": c["titulo"],
            "description": c["descricao"],
            "image": c["imagem"],
            "price": c["preco"],
            "lessons": c["aulas"]
        }
        for c in cursos
    ])


@app.route("/api/courses/<int:curso_id>")
def curso(curso_id):

    conn = conectar()

    curso = conn.execute(
        "SELECT * FROM cursos WHERE id = ?",
        (curso_id,)
    ).fetchone()

    if not curso:
        conn.close()
        return jsonify({"detail": "Curso não encontrado"}), 404

    aulas = conn.execute(
        """
        SELECT *
        FROM aulas
        WHERE curso_id = ?
        ORDER BY posicao
        """,
        (curso_id,)
    ).fetchall()

    conn.close()

    return jsonify({
        "id": curso["id"],
        "title": curso["titulo"],
        "description": curso["descricao"],
        "image": curso["imagem"],
        "price": curso["preco"],
        "lessons": [
            {
                "id": aula["id"],
                "title": aula["titulo"],
                "content": aula["conteudo"],
                "video_url": aula["video_url"],
                "position": aula["posicao"]
            }
            for aula in aulas
        ]
    })


@app.route("/api/courses/<int:curso_id>/enroll", methods=["POST"])
def matricular(curso_id):

    usuario = usuario_atual()

    if not usuario:
        return jsonify({"detail": "Faça login primeiro"}), 401

    conn = conectar()

    curso = conn.execute(
        "SELECT id FROM cursos WHERE id = ?",
        (curso_id,)
    ).fetchone()

    if not curso:
        conn.close()
        return jsonify({"detail": "Curso não encontrado"}), 404

    try:
        conn.execute(
            """
            INSERT INTO matriculas
            (usuario_id,curso_id)
            VALUES (?,?)
            """,
            (usuario["id"], curso_id)
        )

        conn.commit()

    except sqlite3.IntegrityError:
        pass

    conn.close()

    return jsonify({
        "message": "Matrícula realizada"
    })


@app.route("/api/my-courses")
def meus_cursos():

    usuario = usuario_atual()

    if not usuario:
        return jsonify({"detail": "Faça login primeiro"}), 401

    conn = conectar()

    cursos = conn.execute(
        """
        SELECT c.id,c.titulo
        FROM cursos c
        JOIN matriculas m
        ON m.curso_id = c.id
        WHERE m.usuario_id = ?
        """,
        (usuario["id"],)
    ).fetchall()

    conn.close()

    return jsonify([
        {
            "id": c["id"],
            "title": c["titulo"]
        }
        for c in cursos
    ])


@app.route("/api/lessons/<int:aula_id>/complete", methods=["POST"])
def concluir_aula(aula_id):

    usuario = usuario_atual()

    if not usuario:
        return jsonify({"detail": "Faça login primeiro"}), 401

    conn = conectar()

    aula = conn.execute(
        "SELECT * FROM aulas WHERE id = ?",
        (aula_id,)
    ).fetchone()

    if not aula:
        conn.close()
        return jsonify({"detail": "Aula não encontrada"}), 404

    matricula = conn.execute(
        """
        SELECT id
        FROM matriculas
        WHERE usuario_id = ?
        AND curso_id = ?
        """,
        (usuario["id"], aula["curso_id"])
    ).fetchone()

    if not matricula:
        conn.close()
        return jsonify({
            "detail": "Você não está matriculado"
        }), 403

    conn.execute(
        """
        INSERT INTO progresso
        (usuario_id,aula_id,concluida)
        VALUES (?,?,1)
        ON CONFLICT(usuario_id,aula_id)
        DO UPDATE SET concluida = 1
        """,
        (usuario["id"], aula_id)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "completed": True
    })


@app.route("/api/courses/<int:curso_id>/progress")
def progresso(curso_id):

    usuario = usuario_atual()

    if not usuario:
        return jsonify({"detail": "Faça login primeiro"}), 401

    conn = conectar()

    total = conn.execute(
        """
        SELECT COUNT(*)
        FROM aulas
        WHERE curso_id = ?
        """,
        (curso_id,)
    ).fetchone()[0]

    concluidas = conn.execute(
        """
        SELECT COUNT(*)
        FROM progresso p
        JOIN aulas a
        ON a.id = p.aula_id
        WHERE p.usuario_id = ?
        AND a.curso_id = ?
        AND p.concluida = 1
        """,
        (usuario["id"], curso_id)
    ).fetchone()[0]

    conn.close()

    porcentagem = 0

    if total:
        porcentagem = round(
            concluidas / total * 100
        )

    return jsonify({
        "completed": concluidas,
        "total": total,
        "percent": porcentagem
    })


@app.route("/")
def inicio():
    return send_from_directory(FRONTEND, "index.html")


@app.route("/<path:arquivo>")
def arquivos(arquivo):
    return send_from_directory(FRONTEND, arquivo)


iniciar_banco()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=True
    )
