from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from .config import Config
from flask_mail import Mail
import simplejson as json

db = SQLAlchemy()
jwt = JWTManager()
mail = Mail()

revoked_tokens = set()

class CustomJSONEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        kwargs['ensure_ascii'] = False
        super().__init__(*args, **kwargs)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.json_encoder = CustomJSONEncoder

    db.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)

    # Инициализация CORS для всего приложения
    CORS(app, resources={r"/*": {"origins": "*"}})

    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(jwt_header, jwt_payload):
        jti = jwt_payload['jti']
        return jti in revoked_tokens

    with app.app_context():
        from .routes.auth import auth_bp
        from .routes.doctor import doctors_bp
        from .routes.hr import hr_bp
        from .routes.manager import managers_bp

        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(doctors_bp, url_prefix='/doctor')
        app.register_blueprint(hr_bp, url_prefix='/hr')
        app.register_blueprint(managers_bp, url_prefix='/manager')

        db.create_all()

    return app
