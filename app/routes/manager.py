import uuid
from flask import Blueprint, jsonify, request
from app import db
from app.models import Users, Doctors, Modality, DoctorAdditionalModalities, DoctorSchedule
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.decorators import role_and_approval_required, check_token_not_revoked
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

managers_bp = Blueprint('manager', __name__)

@managers_bp.route('/create_doctor', methods=['POST'])
@role_and_approval_required('manager')
def manager_create_doctor():
    data = request.get_json()
    #TODO: Добавить логику для создания рандомного пароля и отправки его по имейлу
    default_password = "123456"
    try:
        new_user = Users(
            full_name=data['full_name'],
            email=data['email'],
            role='doctor',
            approved=True
        )
        new_user.set_password(default_password)
        db.session.add(new_user)
        db.session.commit()

        main_modality = Modality.query.filter_by(name=data['main_modality']).first()
        if not main_modality:
            main_modality = Modality(name=data['main_modality'])
            db.session.add(main_modality)
            db.session.commit()

        new_doctor = Doctors(
            user_id=new_user.id,
            experience=data['experience'],
            main_modality_id=main_modality.id,
            gender=data['gender'],
            rate=data['rate'],
            status='Активный',
            phone=data['phone']
        )

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

@managers_bp.route('/doctors', methods=['GET'])
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

@managers_bp.route('/doctor/<uuid:doctor_id>', methods=['DELETE'])
@role_and_approval_required('manager')
def delete_doctor(doctor_id):
    doctor = Doctors.query.get(doctor_id)
    if not doctor:
        return jsonify({'message': 'Doctor not found'}), 404
    user = Users.query.get(doctor.user_id)

    DoctorAdditionalModalities.query.filter_by(doctor_id=doctor.id).delete()
    DoctorSchedule.query.filter_by(doctor_id=doctor.id).delete()
    db.session.delete(doctor)
    db.session.delete(user)
    db.session.commit()

    return jsonify({'message': 'Doctor deleted successfully'}), 200

@managers_bp.route('/doctor/approve/<uuid:doctor_id>', methods=['PUT'])
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

@managers_bp.route('/doctor/<uuid:doctor_id>/schedule/<uuid:schedule_id>', methods=['PUT'])
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

@managers_bp.route('/admin_only', methods=['GET'])
@check_token_not_revoked
@role_and_approval_required('manager')
def admin_only():
    return jsonify({'message': 'Welcome, approved manager!'}), 200
