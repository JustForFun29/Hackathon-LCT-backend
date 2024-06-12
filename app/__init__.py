from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from .config import Config

db = SQLAlchemy()
jwt = JWTManager()

revoked_tokens = set()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    jwt.init_app(app)

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
