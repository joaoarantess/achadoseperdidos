import os
import sqlite3
from datetime import datetime

from flask import Flask, flash, g, redirect, render_template, request, url_for

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "achados.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "troque-esta-chave")

# valor guardado no banco -> texto exibido
TIPOS = {"perdido": "Perdido", "encontrado": "Encontrado"}

# valor da URL (?filtro=...) -> tipo no banco (None = sem filtro)
FILTROS = {"todos": None, "perdidos": "perdido", "encontrados": "encontrado"}

# limites de tamanho dos campos
LIMITES = {"nome": 80, "descricao": 500, "local": 100, "contato": 100}


# ---------------------------------------------------------------- banco ----
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def fechar_db(_erro):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DATABASE) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS itens (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo        TEXT    NOT NULL CHECK (tipo IN ('perdido', 'encontrado')),
                nome        TEXT    NOT NULL,
                descricao   TEXT    NOT NULL,
                local       TEXT    NOT NULL,
                contato     TEXT    NOT NULL,
                resolvido   INTEGER NOT NULL DEFAULT 0,
                criado_em   TEXT    NOT NULL,
                resolvido_em TEXT
            )
            """
        )


# ------------------------------------------------------------- utilidades ----
@app.template_filter("data_br")
def data_br(valor):
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return ""


def filtro_valido(valor):
    return valor if valor in FILTROS else "todos"


def validar(form):
    """Devolve (dados_limpos, erros)."""
    dados = {"tipo": form.get("tipo", "").strip()}
    erros = []

    if dados["tipo"] not in TIPOS:
        erros.append("Escolha se o item foi perdido ou encontrado.")

    rotulos = {
        "nome": "o nome do item",
        "descricao": "a descrição",
        "local": "o local",
        "contato": "um contato",
    }
    for campo, limite in LIMITES.items():
        valor = form.get(campo, "").strip()
        dados[campo] = valor
        if not valor:
            erros.append(f"Informe {rotulos[campo]}.")
        elif len(valor) > limite:
            erros.append(f"O campo '{campo}' aceita no máximo {limite} caracteres.")

    return dados, erros


# ------------------------------------------------------------------ rotas ----
@app.route("/")
def index():
    filtro = filtro_valido(request.args.get("filtro", "todos"))
    tipo = FILTROS[filtro]
    db = get_db()

    sql = "SELECT * FROM itens"
    params = ()
    if tipo:
        sql += " WHERE tipo = ?"
        params = (tipo,)
    sql += " ORDER BY resolvido ASC, id DESC"  # abertos primeiro, mais novos antes
    itens = db.execute(sql, params).fetchall()

    # contagem de itens ainda em aberto, para mostrar nas abas
    linhas = db.execute(
        "SELECT tipo, COUNT(*) AS total FROM itens WHERE resolvido = 0 GROUP BY tipo"
    ).fetchall()
    abertos = {linha["tipo"]: linha["total"] for linha in linhas}
    contagem = {
        "todos": sum(abertos.values()),
        "perdidos": abertos.get("perdido", 0),
        "encontrados": abertos.get("encontrado", 0),
    }

    return render_template("index.html", itens=itens, filtro=filtro, contagem=contagem)


@app.route("/novo", methods=["GET", "POST"])
def novo():
    if request.method == "POST":
        dados, erros = validar(request.form)
        if erros:
            for erro in erros:
                flash(erro, "erro")
            return render_template("novo.html", form=dados), 400

        db = get_db()
        db.execute(
            "INSERT INTO itens (tipo, nome, descricao, local, contato, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                dados["tipo"],
                dados["nome"],
                dados["descricao"],
                dados["local"],
                dados["contato"],
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        db.commit()
        flash("Item publicado no mural.", "ok")
        return redirect(url_for("index"))

    return render_template("novo.html", form={})


@app.route("/item/<int:item_id>/resolver", methods=["POST"])
def resolver(item_id):
    db = get_db()
    db.execute(
        "UPDATE itens SET resolvido = 1, resolvido_em = ? WHERE id = ?",
        (datetime.now().isoformat(timespec="seconds"), item_id),
    )
    db.commit()
    flash("Item marcado como resolvido.", "ok")
    return redirect(url_for("index", filtro=filtro_valido(request.form.get("filtro"))))


@app.route("/item/<int:item_id>/reabrir", methods=["POST"])
def reabrir(item_id):
    db = get_db()
    db.execute(
        "UPDATE itens SET resolvido = 0, resolvido_em = NULL WHERE id = ?", (item_id,)
    )
    db.commit()
    flash("Item reaberto.", "ok")
    return redirect(url_for("index", filtro=filtro_valido(request.form.get("filtro"))))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
