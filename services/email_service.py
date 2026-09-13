import smtplib
from email.message import EmailMessage

from flask import current_app


def enviar_email_verificacao(email, token):
    link = (
        f"{current_app.config['APP_BASE_URL']}"
        f"/verificar-email?token={token}"
    )

    mensagem = EmailMessage()

    mensagem["Subject"] = "Verificação de e-mail - S.A.N.E."
    mensagem["From"] = current_app.config["MAIL_FROM"]
    mensagem["To"] = email

    mensagem.set_content(
        f"""
Olá!

Recebemos um cadastro no S.A.N.E. utilizando este endereço de e-mail.

Para confirmar seu endereço, acesse o link abaixo:

{link}

Este link é válido por 24 horas e pode ser utilizado apenas uma vez.

Se você não realizou este cadastro, ignore este e-mail.

Atenciosamente,
Equipe S.A.N.E.
"""
    )

    with smtplib.SMTP(
        current_app.config["SMTP_HOST"],
        current_app.config["SMTP_PORT"]
    ) as servidor:

        servidor.starttls()

        servidor.login(
            current_app.config["SMTP_USER"],
            current_app.config["SMTP_PASSWORD"]
        )

        servidor.send_message(mensagem)