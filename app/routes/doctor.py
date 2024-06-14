import uuid
from flask import Blueprint, jsonify, request
from app import db
from app.models import Users, Doctors, DoctorSchedule
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.decorators import role_and_approval_required, check_token_not_revoked
from datetime import datetime

doctors_bp = Blueprint('doctor', __name__)

@doctors_bp.route('/schedule', methods=['GET'])
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
            'hours_worked': schedule.hours_worked,
            'day_type': schedule.day_type.value  # Добавляем тип дня
        }
        result.append(schedule_data)
    return jsonify(result), 200


@doctors_bp.route('/<uuid:doctor_id>/schedule', methods=['GET'])
@role_and_approval_required('hr', 'manager')
def get_schedule(doctor_id):
    # Получаем параметры запроса для года и месяца
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    if not year or not month:
        return jsonify({'message': 'Year and month are required'}), 400

    # Фильтруем расписание по году и месяцу
    schedules = DoctorSchedule.query.filter(
        DoctorSchedule.doctor_id == doctor_id,
        db.extract('year', DoctorSchedule.date) == year,
        db.extract('month', DoctorSchedule.date) == month
    ).all()

    result = []
    half_month_hours = 0
    total_month_hours = 0

    for schedule in schedules:
        schedule_data = {
            'date': schedule.date.strftime('%Y-%m-%d'),
            'start_time': schedule.start_time.strftime('%H:%M'),
            'end_time': schedule.end_time.strftime('%H:%M'),
            'break_minutes': schedule.break_minutes,
            'hours_worked': schedule.hours_worked,
            'day_type': schedule.day_type.value  # Добавляем тип дня
        }
        result.append(schedule_data)
        total_month_hours += schedule.hours_worked
        if schedule.date.day <= 15:
            half_month_hours += schedule.hours_worked

    return jsonify({
        'schedule': result,
        'half_month_hours': half_month_hours,
        'total_month_hours': total_month_hours
    }), 200