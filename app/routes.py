import uuid
from flask import Blueprint, jsonify, request
from app import db, revoked_tokens
from app.models import Users, Doctors, Modality, DoctorAdditionalModalities, DoctorSchedule
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
    decode_token
)
from app.decorators import role_and_approval_required, check_token_not_revoked
from datetime import datetime, date, time, timedelta
from sqlalchemy.exc import IntegrityError

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    try:
        new_user = Users(
            full_name=data['full_name'],
            email=data['email'],
            role=data['role'],
            approved=False  # Устанавливаем значение approved равным False
        )
        new_user.set_password(data['password'])
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({'message': 'User with this email already exists'}), 400

@bp.route('/login', methods=['POST'])
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

@bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    jti = get_jwt()['jti']
    revoked_tokens.add(jti)
    return jsonify({'message': 'Successfully logged out'}), 200

@bp.route('/protected', methods=['GET'])
@check_token_not_revoked
def protected():
    current_user = get_jwt_identity()
    print("Decoded JWT:", current_user)  # Вывод расшифровки JWT в консоль
    return jsonify(logged_in_as=current_user), 200

@bp.route('/current_user', methods=['GET'])
@check_token_not_revoked
def current_user():
    current_user = get_jwt_identity()
    return jsonify(current_user=current_user), 200

@bp.route('/admin_only', methods=['GET'])
@check_token_not_revoked
@role_and_approval_required('manager')
def admin_only():
    return jsonify({'message': 'Welcome, approved manager!'}), 200

@bp.route('/token_status', methods=['GET'])
@check_token_not_revoked
def token_status():
    jti = get_jwt()['jti']
    if jti in revoked_tokens:
        return jsonify({'message': 'Token has been revoked'}), 401
    return jsonify({'message': 'Token is active'}), 200

@bp.route('/hr/create_doctor', methods=['POST'])
@role_and_approval_required('manager')
def hr_create_doctor():
    data = request.get_json()
    default_password = "123456"
    try:
        # Создаем пользователя
        new_user = Users(
            full_name=data['full_name'],
            email=data['email'],
            role='doctor',
            approved=False  # Дефолтное значение при создании доктора кадровиком
        )
        new_user.set_password(default_password)
        db.session.add(new_user)
        db.session.commit()

        # Найти или создать основную модальность
        main_modality = Modality.query.filter_by(name=data['main_modality']).first()
        if not main_modality:
            main_modality = Modality(name=data['main_modality'])
            db.session.add(main_modality)
            db.session.commit()

        # Создаем запись в таблице doctors
        new_doctor = Doctors(
            user_id=new_user.id,
            experience=data['experience'],
            main_modality_id=main_modality.id,
            gender=data['gender'],
            rate=data['rate'],
            status='Ожидает подтверждения',  # Устанавливаем статус по умолчанию
            phone=data['phone']
        )

        # Добавляем дополнительные модальности
        additional_modalities = data.get('additional_modality', [])
        for modality_name in additional_modalities:
            modality = Modality.query.filter_by(name=modality_name).first()
            if not modality:
                modality = Modality(name=modality_name)
                db.session.add(modality)
                db.session.commit()
            new_doctor.additional_modalities.append(modality)

        db.session.add(new_doctor)
        db.session.commit()

        return jsonify({'message': 'Doctor created successfully'}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({'message': 'User with this email already exists'}), 400

@bp.route('/manager/create_doctor', methods=['POST'])
@role_and_approval_required('manager')
def manager_create_doctor():
    data = request.get_json()
    default_password = "123456"
    try:
        # Создаем пользователя
        new_user = Users(
            full_name=data['full_name'],
            email=data['email'],
            role='doctor',
            approved=True  # Устанавливаем значение approved равным True для доктора
        )
        new_user.set_password(default_password)
        db.session.add(new_user)
        db.session.commit()

        # Найти или создать основную модальность
        main_modality = Modality.query.filter_by(name=data['main_modality']).first()
        if not main_modality:
            main_modality = Modality(name=data['main_modality'])
            db.session.add(main_modality)
            db.session.commit()

        # Создаем запись в таблице doctors
        new_doctor = Doctors(
            user_id=new_user.id,
            experience=data['experience'],
            main_modality_id=main_modality.id,
            gender=data['gender'],
            rate=data['rate'],
            status='Активный',  # При создании руководителем сразу делаем активным
            phone=data['phone']
        )

        # Добавляем дополнительные модальности
        additional_modalities = data.get('additional_modality', [])
        for modality_name in additional_modalities:
            modality = Modality.query.filter_by(name=modality_name).first()
            if not modality:
                modality = Modality(name=modality_name)
                db.session.add(modality)
                db.session.commit()
            new_doctor.additional_modalities.append(modality)

        db.session.add(new_doctor)
        db.session.commit()

        return jsonify({'message': 'Doctor created successfully'}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({'message': 'User with this email already exists'}), 400

@bp.route('/doctors', methods=['GET'])
@role_and_approval_required('manager', 'hr')
def get_all_doctors():
    doctors = Doctors.query.all()
    result = []
    for doctor in doctors:
        user = Users.query.get(doctor.user_id)
        main_modality = Modality.query.get(doctor.main_modality_id)
        doctor_data = {
            'id': doctor.id,
            'full_name': user.full_name,
            'email': user.email,
            'experience': doctor.experience,
            'main_modality': main_modality.name if main_modality else None,
            'additional_modalities': [modality.name for modality in doctor.additional_modalities],
            'rate': doctor.rate,
            'status': doctor.status,
            'phone': doctor.phone,
            'gender': doctor.gender
        }
        result.append(doctor_data)
    return jsonify(result), 200

@bp.route('/manager/doctor/<uuid:doctor_id>', methods=['DELETE'])
@role_and_approval_required('manager')
def delete_doctor(doctor_id):
    doctor = Doctors.query.get(doctor_id)
    if not doctor:
        return jsonify({'message': 'Doctor not found'}), 404
    user = Users.query.get(doctor.user_id)

    # Удаляем записи из таблицы doctor_additional_modalities
    DoctorAdditionalModalities.query.filter_by(doctor_id=doctor.id).delete()

    # Удаляем записи из таблицы doctor_schedule
    DoctorSchedule.query.filter_by(doctor_id=doctor.id).delete()

    # Удаляем записи из таблиц doctors и users
    db.session.delete(doctor)
    db.session.delete(user)
    db.session.commit()

    return jsonify({'message': 'Doctor deleted successfully'}), 200

@bp.route('/manager/doctor/approve/<uuid:doctor_id>', methods=['PUT'])
@role_and_approval_required('manager')
def approve_doctor(doctor_id):
    doctor = Doctors.query.get(doctor_id)
    if not doctor:
        return jsonify({'message': 'Doctor not found'}), 404
    user = Users.query.get(doctor.user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    user.approved = True
    doctor.status = 'Активный'
    db.session.commit()

    return jsonify({'message': 'Doctor approved successfully'}), 200

@bp.route('/user_name', methods=['GET'])
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


@bp.route('/doctor/<uuid:doctor_id>/schedule', methods=['POST'])
@role_and_approval_required('manager', 'hr')
def create_schedule(doctor_id):
    data = request.get_json()
    try:
        schedule_entries = data['schedule']
        for entry in schedule_entries:
            schedule = DoctorSchedule(
                doctor_id=doctor_id,
                date=datetime.strptime(entry['date'], '%Y-%m-%d').date(),
                start_time=datetime.strptime(entry['start_time'], '%H:%M').time(),
                end_time=datetime.strptime(entry['end_time'], '%H:%M').time(),
                break_minutes=entry['break_minutes'],
                hours_worked=entry['hours_worked']
            )
            db.session.add(schedule)
        db.session.commit()
        return jsonify({'message': 'Schedule created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@bp.route('/doctor/<uuid:doctor_id>/schedule', methods=['GET'])
@role_and_approval_required('manager', 'hr')
def get_schedule(doctor_id):
    schedules = DoctorSchedule.query.filter_by(doctor_id=doctor_id).all()
    result = []
    for schedule in schedules:
        schedule_data = {
            'date': schedule.date.strftime('%Y-%m-%d'),
            'start_time': schedule.start_time.strftime('%H:%M'),
            'end_time': schedule.end_time.strftime('%H:%M'),
            'break_minutes': schedule.break_minutes,
            'hours_worked': schedule.hours_worked
        }
        result.append(schedule_data)
    return jsonify(result), 200

@bp.route('/doctor/<uuid:doctor_id>/schedule/<uuid:schedule_id>', methods=['PUT'])
@role_and_approval_required('manager')
def update_schedule(doctor_id, schedule_id):
    data = request.get_json()
    try:
        schedule = DoctorSchedule.query.get(schedule_id)
        if not schedule or schedule.doctor_id != doctor_id:
            return jsonify({'message': 'Schedule not found'}), 404

        schedule.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        schedule.start_time = datetime.strptime(data['start_time'], '%H:%M').time()
        schedule.end_time = datetime.strptime(data['end_time'], '%H:%M').time()
        schedule.break_minutes = data['break_minutes']
        schedule.hours_worked = data['hours_worked']
        db.session.commit()
        return jsonify({'message': 'Schedule updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@bp.route('/doctor/<uuid:doctor_id>/schedule/<uuid:schedule_id>', methods=['DELETE'])
@role_and_approval_required('manager', 'hr')
def delete_schedule(doctor_id, schedule_id):
    try:
        schedule = DoctorSchedule.query.get(schedule_id)
        if not schedule or schedule.doctor_id != doctor_id:
            return jsonify({'message': 'Schedule not found'}), 404

        db.session.delete(schedule)
        db.session.commit()
        return jsonify({'message': 'Schedule deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

# Новый endpoint для получения всех записей календаря для доктора
@bp.route('/doctor/schedule', methods=['GET'])
@jwt_required()
def get_doctor_schedule():
    current_user = get_jwt_identity()
    user = Users.query.filter_by(email=current_user['email']).first()
    if user.role != 'doctor':
        return jsonify({'message': 'Access denied'}), 403

    doctor = Doctors.query.filter_by(user_id=user.id).first()
    if not doctor:
        return jsonify({'message': 'Doctor not found'}), 404

    schedules = DoctorSchedule.query.filter_by(doctor_id=doctor.id).all()
    result = []
    for schedule in schedules:
        schedule_data = {
            'date': schedule.date.strftime('%Y-%m-%d'),
            'start_time': schedule.start_time.strftime('%H:%M'),
            'end_time': schedule.end_time.strftime('%H:%M'),
            'break_minutes': schedule.break_minutes,
            'hours_worked': schedule.hours_worked
        }
        result.append(schedule_data)
    return jsonify(result), 200