from flask import Flask

from config import Config
from extensions import mysql, bcrypt, sess, csrf
from routes.auth import auth_bp
from routes.admin import admin_bp
from routes.loja import loja_bp
from routes.produtos import produtos_bp

import logging
import re


class RedactTokenFilter(logging.Filter):

    def filter(self, record):
        mensagem = record.getMessage()

        mensagem = re.sub(
            r"([?&]token=)[^&\s]+",
            r"\1[REDACTED]",
            mensagem
        )

        record.msg = mensagem
        record.args = ()

        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logging.getLogger("werkzeug").addFilter(RedactTokenFilter())


def create_app():
    app = Flask(__name__)

    app.config.from_object(Config)

    mysql.init_app(app)
    bcrypt.init_app(app)
    sess.init_app(app)
    csrf.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(loja_bp)
    app.register_blueprint(produtos_bp)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)