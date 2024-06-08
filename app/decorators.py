from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required, get_jwt
from app.models import Users
from app import revoked_tokens

def role_and_approval_required(required_role):
    def decorator(f):
        @wraps(f)
        @jwt_required()
        @check_token_not_revoked
        def decorated_function(*args, **kwargs):
            current_user = get_jwt_identity()
            user = Users.query.filter_by(email=current_user['email']).first()
            if user.role != required_role or not user.approved:
                return jsonify({'message': 'Access denied'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def check_token_not_revoked(f):
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        jti = get_jwt()['jti']
        if jti in revoked_tokens:
            return jsonify({'message': 'Token has been revoked'}), 401
        return f(*args, **kwargs)
    return decorated_function

def hr_required(f):
    @wraps(f)
    @jwt_required()
    @check_token_not_revoked
    def decorated_function(*args, **kwargs):
        current_user = get_jwt_identity()
        user = Users.query.filter_by(email=current_user['email']).first()
        if user.role != 'HR':
            return jsonify({'message': 'Access denied'}), 403
        return f(*args, **kwargs)
    return decorated_function
