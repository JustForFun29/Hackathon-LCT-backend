import uuid
import string
import random
from flask import Blueprint, jsonify, request, current_app
from app import db
from app.models import Users, Doctors, Modality, DoctorAdditionalModalities, DoctorSchedule, Ticket, DayType, StudyCount
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.decorators import role_and_approval_required, check_token_not_revoked
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from flask_mail import Message
from app import mail
import logging
import json
from app.ml import Predictor
import pandas as pd
from datetime import time, timedelta



# Установим уровень логирования на DEBUG
logging.basicConfig(level=logging.DEBUG)

managers_bp = Blueprint('manager', __name__)
predictor = Predictor()


#TODO: Поменять это на рабочий email

# def send_email(to, subject, template):
#     msg = Message(
#         subject,
#         recipients=[to],
#         html=template,
#         sender=current_app.config['MAIL_DEFAULT_SENDER']
#     )
#     mail.send(msg)

def send_email(to, subject, template):
    print(f'{to} {subject} {template}')

def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    password = ''.join(random.choice(characters) for i in range(length))
    return password

@managers_bp.route('/tickets', methods=['GET'])
@role_and_approval_required('manager')
def get_tickets():
    tickets = Ticket.query.all()
    result = []
    for ticket in tickets:
        ticket_data = {
            'id': str(ticket.id),
            'type': ticket.type,
            'data': ticket.data,
            'status': ticket.status,
            'created_at': ticket.created_at,
            'full_name': ticket.user.full_name if ticket.user else None
        }
        result.append(ticket_data)
    return jsonify(result), 200



@managers_bp.route('/predict', methods=['POST'])
@role_and_approval_required('manager')
def predict():
    '''
    {
        'year': 2024,
        'start_week': 1,
        'end_week': 52,
        'target': 'МРТ с КУ 2 и более зон',

    }
    '''

    data = request.get_json()

    target = data['target']
    start_week = data['start_week']
    end_week = data['end_week']
    year = data['year']

    data_for_ml = pd.DataFrame({
        'Год': [2024 for _ in range(start_week, end_week + 1)],
        'Номер недели': [i for i in range(start_week, end_week + 1)],
    })

    return jsonify(
        {'predictions': predictor.predict(target, data_for_ml),
         'year': year, 'start_week': start_week, 'end_week': end_week, 'target': target}
    ), 200



@managers_bp.route('/approve/<uuid:ticket_id>', methods=['PUT'])
@role_and_approval_required('manager')
def approve_ticket(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'message': 'Ticket not found'}), 404

    if ticket.type == 'approve_doctor':
        user = Users.query.get(ticket.user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404

        user.approved = True
        ticket.status = 'Approved'
        db.session.commit()

        # Отправка email с уведомлением о подтверждении
        subject = "Ваш аккаунт был подтвержден!"
        to = user.email
        template = f"""
        <p>Уважаемый {user.full_name},</p>
        <p>Ваш аккаунт был подтвержден руководителем, вы можете использовать логин и пароль из предыдущего сообщения.</p>
        <p>Удачного пользования и будьте здоровы!</p>
        """
        send_email(to, subject, template)

        return jsonify({'message': 'Doctor approved successfully'}), 200

    elif ticket.type == 'update_doctor':

        doctor = Doctors.query.filter_by(user_id=ticket.user_id).first()

        if not doctor:
            return jsonify({'message': 'Doctor not found'}), 404

        # Десериализуем данные из JSON строки
        data = json.loads(ticket.data) if isinstance(ticket.data, str) else ticket.data

        # Обновляем данные врача
        if 'experience' in data:
            doctor.experience = data['experience']
        if 'main_modality_id' in data:
            doctor.main_modality_id = data['main_modality_id']
        if 'gender' in data:
            doctor.gender = data['gender']
        if 'rate' in data:
            doctor.rate = data['rate']
        if 'status' in data:
            doctor.status = data['status']
        if 'phone' in data:
            doctor.phone = data['phone']

        # Обновляем дополнительные модальности
        if 'additional_modality' in data:
            doctor.additional_modalities.clear()
            for modality_name in data['additional_modality']:
                modality = Modality.query.filter_by(name=modality_name).first()
                if not modality:
                    modality = Modality(name=modality_name)
                    db.session.add(modality)
                    db.session.commit()
                doctor.additional_modalities.append(modality)

        ticket.status = 'Approved'
        db.session.commit()

        # Отправляем уведомление по электронной почте
        subject = "Изменение данных врача одобрено"
        to = doctor.user.email
        template = f"""
                <p>Уважаемый {doctor.user.full_name},</p>
                <p>Ваши данные были успешно обновлены.</p>
                """
        send_email(to, subject, template)

        return jsonify({'message': 'Doctor update approved successfully'}), 200

    elif ticket.type == 'emergency_request':
        try:
            data = json.loads(ticket.data) if isinstance(ticket.data, str) else ticket.data
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
            doctor_id = Doctors.query.filter_by(user_id=ticket.user_id).first().id

            current_date = start_date
            while current_date <= end_date:
                # Проверяем, есть ли уже запись с типом "WORKING_DAY" на эту дату
                existing_schedule = DoctorSchedule.query.filter_by(doctor_id=doctor_id, date=current_date, day_type=DayType.WORKING_DAY).first()
                if existing_schedule:
                    db.session.delete(existing_schedule)

                # Создаем новую запись с типом "EMERGENCY"
                new_schedule = DoctorSchedule(
                    doctor_id=doctor_id,
                    date=current_date,
                    start_time=time(0, 0),
                    end_time=time(23, 59),
                    break_minutes=0,
                    hours_worked=0.0,
                    day_type=DayType.EMERGENCY
                )
                db.session.add(new_schedule)
                current_date += timedelta(days=1)

            ticket.status = 'Approved'
            db.session.commit()

            return jsonify({'message': 'Ticket approved successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': str(e)}), 400

    else:
        return jsonify({'message': 'Invalid ticket type'}), 400
@managers_bp.route('/ticket/<uuid:ticket_id>', methods=['DELETE'])
@role_and_approval_required('manager')
def delete_ticket(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'message': 'Ticket not found'}), 404

    db.session.delete(ticket)
    db.session.commit()
    return jsonify({'message': 'Ticket deleted successfully'}), 200

@managers_bp.route('/create_doctor', methods=['POST'])
@role_and_approval_required('manager')
def manager_create_doctor():
    data = request.get_json()
    try:
        password = generate_random_password()
        new_user = Users(
            full_name=data['full_name'],
            email=data['email'],
            role='doctor',
            approved=True
        )
        new_user.set_password(password)
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

        # Отправляем уведомление по электронной почте
        subject = "Был создан аккаунт"
        to = data['email']
        template = f"""
               <p>Уважаемый {data['full_name']},</p>
               <p>Руководитель медицинского центра создал аккаунта в системе</p>
               <p>Ваш логин {data['email']}</p>
               <p>Ваш пароль {password}<p>
               <p>Вы можете войти на наш сервис используя эти данные</p>
               """
        send_email(to, subject, template)

        return jsonify({'message': 'Doctor created successfully and approval ticket generated'}), 201
    except IntegrityError as e:
        db.session.rollback()
        if 'users_email_key' in str(e.orig):
            return jsonify({'message': 'User with this email already exists'}), 400
        logging.error(f"IntegrityError: {str(e)}")
        return jsonify({'message': 'Database integrity error occurred', 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error: {str(e)}")
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500

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

@managers_bp.route('/doctor/<uuid:doctor_id>', methods=['PUT'])
@role_and_approval_required('manager')
def update_doctor(doctor_id):
    data = request.get_json()
    try:
        # Получаем доктора по doctor_id
        doctor = Doctors.query.get(doctor_id)
        if not doctor:
            return jsonify({'message': 'Doctor not found'}), 404

        # Получаем пользователя по user_id
        user = Users.query.get(doctor.user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404

        # Обновляем данные пользователя
        if 'full_name' in data:
            user.full_name = data['full_name']

        # Обновляем данные доктора
        if 'experience' in data:
            doctor.experience = data['experience']
        if 'gender' in data:
            doctor.gender = data['gender']
        if 'rate' in data:
            doctor.rate = data['rate']
        if 'status' in data:
            doctor.status = data['status']
        if 'phone' in data:
            doctor.phone = data['phone']

        # Обновляем основную модальность
        if 'main_modality' in data:
            main_modality = Modality.query.filter_by(name=data['main_modality']).first()
            if not main_modality:
                main_modality = Modality(name=data['main_modality'])
                db.session.add(main_modality)
                db.session.commit()
            doctor.main_modality_id = main_modality.id

        # Обновляем дополнительные модальности
        if 'additional_modalities' in data:
            doctor.additional_modalities.clear()
            additional_modalities = data.get('additional_modalities', [])
            for modality_name in additional_modalities:
                modality = Modality.query.filter_by(name=modality_name).first()
                if not modality:
                    modality = Modality(name=modality_name)
                    db.session.add(modality)
                    db.session.commit()
                doctor.additional_modalities.append(modality)

        db.session.commit()
        return jsonify({'message': 'Doctor updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400


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

@managers_bp.route('/doctor/<uuid:doctor_id>/schedule', methods=['PUT'])
@role_and_approval_required('manager')
def update_or_create_schedule(doctor_id):
    data = request.get_json()
    try:
        # Парсим дату из строки
        date = datetime.strptime(data['date'], '%Y-%m-%d').date()

        # Проверяем, существует ли уже запись на эту дату
        existing_schedule = DoctorSchedule.query.filter_by(doctor_id=doctor_id, date=date).first()

        if existing_schedule:
            # Если запись существует, обновляем её
            existing_schedule.start_time = datetime.strptime(data['start_time'], '%H:%M').time()
            existing_schedule.end_time = datetime.strptime(data['end_time'], '%H:%M').time()
            existing_schedule.break_minutes = data['break_minutes']
            existing_schedule.hours_worked = data['hours_worked']
            existing_schedule.day_type = data['day_type']
            db.session.commit()
            return jsonify({'message': 'Schedule updated successfully'}), 200
        else:
            # Если записи нет, создаем новую
            new_schedule = DoctorSchedule(
                doctor_id=doctor_id,
                date=date,
                start_time=datetime.strptime(data['start_time'], '%H:%M').time(),
                end_time=datetime.strptime(data['end_time'], '%H:%M').time(),
                break_minutes=data['break_minutes'],
                hours_worked=data['hours_worked']
            )
            db.session.add(new_schedule)
            db.session.commit()
            return jsonify({'message': 'Schedule created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400


@managers_bp.route('/doctor/<uuid:doctor_id>/schedule', methods=['POST'])
@role_and_approval_required('manager')
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


@managers_bp.route('/doctor/<uuid:doctor_id>/schedule/<string:date>', methods=['DELETE'])
@role_and_approval_required('manager')
def delete_schedule(doctor_id, date):
    try:
        # Парсим дату из строки
        schedule_date = datetime.strptime(date, '%Y-%m-%d').date()

        # Находим запись в расписании доктора на указанную дату
        schedule = DoctorSchedule.query.filter_by(doctor_id=doctor_id, date=schedule_date).first()

        if not schedule:
            return jsonify({'message': 'Schedule not found for the specified date'}), 404

        # Удаляем запись из базы данных
        db.session.delete(schedule)
        db.session.commit()

        return jsonify({'message': 'Schedule deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error: {str(e)}")
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500

@managers_bp.route('/study_counts', methods=['GET'])
@role_and_approval_required('manager')
def get_study_counts():
    year = request.args.get('year', type=int)
    week_number = request.args.get('week_number', type=int)

    if not year or not week_number:
        return jsonify({'message': 'Year and week number are required'}), 400

    study_types = [
        'densitometry', 'ct', 'ct_with_cu_1_zone', 'ct_with_cu_2_or_more_zones',
        'mmg', 'mrt', 'mrt_with_cu_1_zone', 'mrt_with_cu_2_or_more_zones',
        'rg', 'fluorography'
    ]

    study_counts = StudyCount.query.filter_by(year=year, week_number=week_number).all()

    if not study_counts:
        return jsonify({'message': 'No data found for the specified week and year'}), 404

    result = {study_type: 0 for study_type in study_types}
    for study_count in study_counts:
        result[study_count.study_type] = study_count.study_count

    return jsonify(result), 200
