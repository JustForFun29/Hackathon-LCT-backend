import uuid
from flask import Blueprint, jsonify, request
from app import db
from app.models import Users, Doctors, Modality, DoctorAdditionalModalities, DoctorSchedule
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.decorators import role_and_approval_required, check_token_not_revoked
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError

hr_bp = Blueprint('hr', __name__)

@hr_bp.route('/create_doctor', methods=['POST'])
@role_and_approval_required('hr')
def hr_create_doctor():
    data = request.get_json()
    default_password = "123456"
    try:
        new_user = Users(
            full_name=data['full_name'],
            email=data['email'],
            role='doctor',
            approved=False
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
            status='Ожидает подтверждения',
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

@hr_bp.route('/doctor/<uuid:doctor_id>/schedule', methods=['POST'])
@role_and_approval_required('hr')
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

@hr_bp.route('/doctor/<uuid:doctor_id>/schedule/<uuid:schedule_id>', methods=['DELETE'])
@role_and_approval_required('hr')
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
