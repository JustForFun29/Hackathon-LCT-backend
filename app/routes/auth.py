from flask import Blueprint, jsonify, request
from app import db, revoked_tokens
from app.decorators import check_token_not_revoked
from app.models import Users
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from datetime import timedelta
from sqlalchemy.exc import IntegrityError

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    try:
        new_user = Users(
            full_name=data['full_name'],
            email=data['email'],
            role=data['role'],
            approved=False
        )
        new_user.set_password(data['password'])
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({'message': 'User with this email already exists'}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = Users.query.filter_by(email=data['email']).first()
    if user is None or not user.check_password(data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
    try:
        access_token = create_access_token(
            identity={'email': user.email, 'role': user.role},
            expires_delta=timedelta(hours=1)
        )
        return jsonify(access_token=access_token)
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()['jti']
    revoked_tokens.add(jti)
    return jsonify({'message': 'Successfully logged out'}), 200

@auth_bp.route('/protected', methods=['GET'])
@check_token_not_revoked
def protected():
    current_user = get_jwt_identity()
    print("Decoded JWT:", current_user)
    return jsonify(logged_in_as=current_user), 200

@auth_bp.route('/current_user', methods=['GET'])
@check_token_not_revoked
def current_user():
    current_user = get_jwt_identity()
    return jsonify(current_user=current_user), 200

@auth_bp.route('/token_status', methods=['GET'])
@check_token_not_revoked
def token_status():
    jti = get_jwt()['jti']
    if jti in revoked_tokens:
        return jsonify({'message': 'Token has been revoked'}), 401
    return jsonify({'message': 'Token is active'}), 200

@auth_bp.route('/user_name', methods=['GET'])
@jwt_required()
@check_token_not_revoked
def user_name():
    current_user = get_jwt_identity()
    user = Users.query.filter_by(email=current_user['email']).first()
    if user:
        full_name_parts = user.full_name.split()
        if len(full_name_parts) >= 2:
            first_name = full_name_parts[0]
            middle_name = full_name_parts[2] if len(full_name_parts) > 2 else ""
            return jsonify({
                'first_name': first_name,
                'father_name': middle_name
            }), 200
        else:
            return jsonify({'message': 'Invalid full name format'}), 400
    return jsonify({'message': 'User not found'}), 404
