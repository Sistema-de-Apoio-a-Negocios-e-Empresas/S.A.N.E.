
from flask import (
    Blueprint,
    flash,
    render_template,
    request,
    redirect,
    url_for,
    session,
    current_app
)

from extensions import mysql, bcrypt
from utils import validar_senha, validar_email, gerar_token_verificacao, hash_token_verificacao
from services.email_service import enviar_email_verificacao

import logging
logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    logger.info("Entrou na função login")

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '').strip()

        logger.info("Tentativa de login para %s", email)

        cur = mysql.connection.cursor()
        
        try:
            cur.execute("SELECT id, senha_hash FROM usuarios WHERE email = %s", (email,))
            user = cur.fetchone()

            logger.debug("Resultado da consulta: %s", user)

            if user and bcrypt.check_password_hash(user[1], senha):
                logger.info("Login realizado com sucesso para %s", email)
                
                current_app.session_interface.regenerate(session)
                
                session['usuario_id'] = user[0]

                # Busca a empresa vinculada ao usuário autenticado
                cur.execute("SELECT identificador_url FROM empresas WHERE usuario_id = %s", (user[0],))
                empresa = cur.fetchone()
                
                if empresa:
                    return redirect(f'/{empresa[0]}/admin')
                else:
                    flash("Empresa não vinculada ao usuário.", "danger")
                    return redirect(url_for("auth.login"))
            else:
                logger.warning("Falha de login para %s", email)
                flash("Login inválido.", "danger")
                return redirect(url_for("auth.login"))
        finally:
            cur.close()

    return render_template('auth/login.html')

@auth_bp.route('/cadastrar', methods=['POST'])
def cadastrar():
    
    nome = request.form.get('nome', '').strip()
    email = request.form.get('email', '').strip().lower()
    senha = request.form.get('senha', '')
    senha2 = request.form.get("senha2", "")
    identificador = request.form.get('identificador_url', '').strip().lower().replace(" ", "-")
    
    logger.info("Tentativa de cadastro para %s", email)

    if not nome or not email or not senha or not identificador:
        flash("Preencha todos os campos obrigatórios.", "warning")
        return redirect(url_for("auth.login"))
    
    email_valido, erro_email = validar_email(email)

    if not email_valido:
        flash(erro_email, "warning")
        logger.info("Erro: %s", erro_email)
        return redirect(url_for("auth.login"))
    
    senha_valida, erro_senha = validar_senha(senha)

    if not senha_valida:
        flash(erro_senha, "warning")
        logger.info("Erro: %s", erro_senha)
        return redirect(url_for("auth.login"))
    
    if senha != senha2:
        flash("As senhas não coincidem.", "warning")
        logger.info("Erro: As senhas não coincidem.")
        return redirect(url_for("auth.login"))

    cur = mysql.connection.cursor()
    
    try:
    
        cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
        
        if cur.fetchone():
            flash("E-mail já cadastrado.", "warning")
            return redirect(url_for("auth.login"))
        
        cur.execute(
            "SELECT id FROM empresas WHERE identificador_url = %s",
            (identificador,)
            )

        if cur.fetchone():
            flash("Identificador de URL já em uso.", "warning")
            return redirect(url_for("auth.login"))
    
        senha_hash = bcrypt.generate_password_hash(senha).decode('utf-8')
        
        cur.execute("INSERT INTO usuarios (email, senha_hash) VALUES (%s, %s)", (email, senha_hash))

        usuario_id = cur.lastrowid
        
        token, token_hash = gerar_token_verificacao()
        
        cur.execute(
            """
            INSERT INTO tokens_verificacao_email
                (usuario_id, token_hash, expira_em)
            VALUES
                (%s, %s, DATE_ADD(NOW(), INTERVAL 24 HOUR))
            """,
            (usuario_id, token_hash)
        )

        cur.execute("INSERT INTO empresas (usuario_id, nome, identificador_url) VALUES (%s, %s, %s)", (usuario_id, nome, identificador))
        mysql.connection.commit()
        
        enviar_email_verificacao(email, token)
        
        logger.info("Usuário %s cadastrou a empresa %s", email, identificador)
        
    except Exception:
        mysql.connection.rollback()
        logger.exception("Erro ao cadastrar empresa %s", identificador)
        raise
        
    finally:
        cur.close()
        
    flash("Cadastro realizado com sucesso!", "success")
    return redirect(url_for('auth.login'))

@auth_bp.route("/verificar-email", methods=["GET", "POST"])
def verificar_email():

    if request.method == "GET":
        token = request.args.get("token", "")

        if not token:
            flash("Link de verificação inválido.", "danger")
            return redirect(url_for("auth.login"))

        token_hash = hash_token_verificacao(token)

        cur = mysql.connection.cursor()

        try:
            cur.execute(
                """
                SELECT
                    t.id,
                    t.usuario_id
                FROM tokens_verificacao_email t
                WHERE t.token_hash = %s
                  AND t.usado_em IS NULL
                  AND t.expira_em > NOW()
                """,
                (token_hash,)
            )

            token_db = cur.fetchone()

        finally:
            cur.close()

        if not token_db:
            flash(
                "O link de verificação é inválido, expirou ou já foi utilizado.",
                "warning"
            )
            return redirect(url_for("auth.login"))

        return render_template(
            "auth/verificar_email.html",
            token=token
        )

    # POST

    token = request.form.get("token", "")

    if not token:
        flash("Link de verificação inválido.", "danger")
        return redirect(url_for("auth.login"))

    token_hash = hash_token_verificacao(token)

    cur = mysql.connection.cursor()

    try:
        cur.execute(
            """
            SELECT
                t.id,
                t.usuario_id
            FROM tokens_verificacao_email t
            WHERE t.token_hash = %s
              AND t.usado_em IS NULL
              AND t.expira_em > NOW()
            FOR UPDATE
            """,
            (token_hash,)
        )

        token_db = cur.fetchone()

        if not token_db:
            mysql.connection.rollback()

            flash(
                "O link de verificação é inválido, expirou ou já foi utilizado.",
                "warning"
            )
            return redirect(url_for("auth.login"))

        token_id, usuario_id = token_db

        cur.execute(
            """
            UPDATE usuarios
            SET email_verificado = TRUE
            WHERE id = %s
            """,
            (usuario_id,)
        )

        cur.execute(
            """
            UPDATE tokens_verificacao_email
            SET usado_em = NOW()
            WHERE id = %s
            """,
            (token_id,)
        )

        mysql.connection.commit()

    except Exception:
        mysql.connection.rollback()
        logger.exception(
            "Erro ao verificar e-mail do usuário %s",
            usuario_id if "usuario_id" in locals() else None
        )
        raise

    finally:
        cur.close()

    flash("E-mail verificado com sucesso!", "success")
    return redirect(url_for("auth.login"))

@auth_bp.route("/logout")
def logout():
    logger.info(
    "Usuário %s realizou logout",
    session.get("usuario_id")
)
    session.clear()
    return redirect(url_for("auth.login"))