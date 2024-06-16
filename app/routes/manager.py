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
from app.ml.predictor import Predictor
import pandas as pd
from datetime import time, timedelta

from flask import request, jsonify, make_response
import pandas as pd
import io
from sqlalchemy.orm import joinedload

# Установим уровень логирования на DEBUG
logging.basicConfig(level=logging.DEBUG)

managers_bp = Blueprint('manager', __name__)
predictor = Predictor()

def send_email(to, subject, template):
    msg = Message(
        subject,
        recipients=[to],
        html=template,
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    mail.send(msg)

# def send_email(to, subject, template):
#     print(f'{to} {subject} {template}')


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


@managers_bp.route('/decline/<uuid:ticket_id>', methods=['PUT'])
@role_and_approval_required('manager')
def decline_ticket(ticket_id):
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({'message': 'Ticket not found'}), 404

    if ticket.status != 'Pending':
        return jsonify({'message': 'Only tickets with status "Pending" can be declined'}), 400

    try:
        ticket.status = 'Declined'
        db.session.commit()

        user = Users.query.get(ticket.user_id)
        subject = "Ваш запрос был отклонён"
        to = user.email
        template = f"""
        <p>Уважаемый {user.full_name},</p>
        <p>Ваш запрос с типом {ticket.type} был отклонён руководителем.</p>
        """
        send_email(to, subject, template)

        return jsonify({'message': 'Ticket declined successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400


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
                hours_worked=entry['hours_worked'],
                day_type=entry['day_type']
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
    data = request.get_json()
    start_date_str = data.get('start_date')

    if not start_date_str:
        return jsonify({'message': 'Start date is required'}), 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'message': 'Invalid date format, should be YYYY-MM-DD'}), 400

    end_date = start_date + timedelta(days=6)
    year = start_date.year

    start_week = start_date.isocalendar()[1]
    end_week = end_date.isocalendar()[1]

    study_types = [
        'densitometry', 'ct', 'ct_with_cu_1_zone', 'ct_with_cu_2_or_more_zones',
        'mmg', 'mrt', 'mrt_with_cu_1_zone', 'mrt_with_cu_2_or_more_zones',
        'rg', 'fluorography'
    ]

    study_counts = StudyCount.query.filter_by(year=year, week_number=start_week).all()

    if not study_counts:
        # If no data is found, call the prediction function
        predictions = {}
        for study_type in study_types:
            if study_type == 'mrt_with_cu_2_or_more_zones':
                predictions[study_type] = 155
            else:
                target = {
                    'densitometry': 'Денситометрия',
                    'ct': 'КТ',
                    'ct_with_cu_1_zone': 'КТ с КУ 1 зона',
                    'ct_with_cu_2_or_more_zones': 'КТ с КУ 2 и более зон',
                    'mmg': 'ММГ',
                    'mrt': 'МРТ',
                    'mrt_with_cu_1_zone': 'МРТ с КУ 1 зона',
                    'rg': 'РГ',
                    'fluorography': 'ФЛГ'
                }[study_type]

                data_for_ml = pd.DataFrame({
                    'Год': [year for _ in range(start_week, end_week + 1)],
                    'Номер недели': [i for i in range(start_week, end_week + 1)],
                })

                # Call the prediction function
                prediction = predictor.predict(target, data_for_ml)
                predictions[study_type] = sum(prediction)  # Summing the predictions over the week

        # Return the predictions
        return jsonify(predictions), 200

    result = {study_type: 0 for study_type in study_types}
    for study_count in study_counts:
        result[study_count.study_type] = study_count.study_count

    return jsonify(result), 200

@managers_bp.route('/export_study_counts', methods=['POST'])
@role_and_approval_required('manager')
def export_study_counts():
    data = request.get_json()
    start_date_str = data.get('start_date')
    export_format = data.get('format', 'csv')

    if not start_date_str:
        return jsonify({'message': 'Start date is required'}), 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'message': 'Invalid date format, should be YYYY-MM-DD'}), 400

    end_date = start_date + timedelta(days=6)
    year = start_date.year
    start_week = start_date.isocalendar()[1]
    end_week = end_date.isocalendar()[1]

    study_types = [
        'densitometry', 'ct', 'ct_with_cu_1_zone', 'ct_with_cu_2_or_more_zones',
        'mmg', 'mrt', 'mrt_with_cu_1_zone', 'mrt_with_cu_2_or_more_zones',
        'rg', 'fluorography'
    ]

    study_types_human_readable = {
        'densitometry': 'Денситометрия',
        'ct': 'КТ',
        'ct_with_cu_1_zone': 'КТ с КУ 1 зона',
        'ct_with_cu_2_or_more_zones': 'КТ с КУ 2 и более зон',
        'mmg': 'ММГ',
        'mrt': 'МРТ',
        'mrt_with_cu_1_zone': 'МРТ с КУ 1 зона',
        'mrt_with_cu_2_or_more_zones': 'МРТ с КУ 2 и более зон',
        'rg': 'РГ',
        'fluorography': 'Флюорография'
    }

    study_counts = StudyCount.query.filter_by(year=year, week_number=start_week).all()

    if not study_counts:
        predictions = {}
        for study_type in study_types:
            if study_type == 'mrt_with_cu_2_or_more_zones':
                predictions[study_type] = 155
            else:
                target = {
                    'densitometry': 'Денситометр',
                    'ct': 'КТ',
                    'ct_with_cu_1_zone': 'КТ с КУ 1 зона',
                    'ct_with_cu_2_or_more_zones': 'КТ с КУ 2 и более зон',
                    'mmg': 'ММГ',
                    'mrt': 'МРТ',
                    'mrt_with_cu_1_zone': 'МРТ с КУ 1 зона',
                    'rg': 'РГ',
                    'fluorography': 'Флюорограф'
                }[study_type]

                data_for_ml = pd.DataFrame({
                    'Год': [year for _ in range(start_week, end_week + 1)],
                    'Номер недели': [i for i in range(start_week, end_week + 1)],
                })

                prediction = predictor.predict(target, data_for_ml)
                predictions[study_type] = round(sum(prediction))

        result_data = {
            'Год': [year],
            'Неделя': [start_week],
        }
        for study_type, value in predictions.items():
            result_data[study_types_human_readable[study_type]] = [value]
    else:
        result_data = {
            'Год': [year],
            'Неделя': [start_week],
        }
        for study_count in study_counts:
            result_data[study_types_human_readable[study_count.study_type]] = [round(study_count.study_count)]

    df = pd.DataFrame(result_data)

    output = io.BytesIO()
    if export_format == 'excel':
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        response = make_response(output.read())
        response.headers['Content-Disposition'] = 'attachment; filename=study_counts.xlsx'
        response.headers['Content-type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:  # default to CSV
        df.to_csv(output, index=False)
        output.seek(0)
        response = make_response(output.read())
        response.headers['Content-Disposition'] = 'attachment; filename=study_counts.csv'
        response.headers['Content-type'] = 'text/csv'

    return response

import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)

# Маппер для времени выполнения исследований в минутах
mapper = {
    'Денситометрия': 15,
    'КТ': 30,
    'КТ с КУ 1 зона': 40,
    'КТ с КУ 2 и более зон': 50,
    'ММГ': 20,
    'МРТ': 45,
    'МРТ с КУ 1 зона': 60,
    'МРТ с КУ 2 и более зон': 75,
    'РГ': 10,
    'ФЛГ': 5
}

def get_doctors_info():
    doctors = db.session.query(Doctors).options(
        joinedload(Doctors.user),
        joinedload(Doctors.additional_modalities)
    ).all()

    result = []
    for doctor in doctors:
        main_modality = db.session.query(Modality).filter_by(id=doctor.main_modality_id).first()
        doctor_info = {
            'id': str(doctor.id),
            'full_name': doctor.user.full_name,
            'email': doctor.user.email,
            'experience': doctor.experience,
            'main_modality': main_modality.name if main_modality else None,
            'additional_modalities': [modality.name for modality in doctor.additional_modalities],
            'gender': doctor.gender,
            'rate': doctor.rate,
            'status': doctor.status,
            'phone': doctor.phone,
            'hours_per_week': 40
        }
        result.append(doctor_info)
    return result

@managers_bp.route('/analyze_doctors', methods=['POST'])
@role_and_approval_required('manager')
def analyze_doctors():
    data = request.get_json()
    start_date_str = data.get('start_date')

    logging.debug(f"Received start_date: {start_date_str}")

    if not start_date_str:
        return jsonify({'message': 'Start date is required'}), 400

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        logging.debug(f"Parsed start_date: {start_date}")
    except ValueError:
        return jsonify({'message': 'Invalid date format, should be YYYY-MM-DD'}), 400

    end_date = start_date + timedelta(days=6)
    year = start_date.year
    start_week = start_date.isocalendar()[1]

    logging.debug(f"Year: {year}, Start Week: {start_week}")

    # Получаем данные о количестве исследований
    study_counts = StudyCount.query.filter_by(year=year, week_number=start_week).all()
    logging.debug(f"Study Counts: {study_counts}")

    if not study_counts:
        study_types = [
            'Денситометрия', 'КТ', 'КТ с КУ 1 зона', 'КТ с КУ 2 и более зон',
            'ММГ', 'МРТ', 'МРТ с КУ 1 зона', 'МРТ с КУ 2 и более зон',
            'РГ', 'ФЛГ'
        ]

        # Вызов ML модели для прогнозирования
        predictions = {}
        for study_type in study_types:
            if study_type == 'МРТ с КУ 2 и более зон':
                predictions[study_type] = 155  # Примерное значение для демонстрации
            else:
                target = {
                    'Денситометрия': 'Денситометр',
                    'КТ': 'КТ',
                    'КТ с КУ 1 зона': 'КТ с КУ 1 зона',
                    'КТ с КУ 2 и более зон': 'КТ с КУ 2 и более зон',
                    'ММГ': 'ММГ',
                    'МРТ': 'МРТ',
                    'МРТ с КУ 1 зона': 'МРТ с КУ 1 зона',
                    'РГ': 'РГ',
                    'ФЛГ': 'Флюорограф'
                }[study_type]

                data_for_ml = pd.DataFrame({
                    'Год': [year for _ in range(start_week, start_week + 1)],  # Прогноз только на текущую неделю
                    'Номер недели': [start_week for _ in range(start_week, start_week + 1)],
                })

                # Вызов функции предсказания
                prediction = predictor.predict(target, data_for_ml)
                predictions[study_type] = sum(prediction)  # Суммирование прогноза по неделе

        # Используем прогнозы для дальнейших вычислений
        study_counts = predictions

    # Получаем данные о докторах
    doctors_info = get_doctors_info()
    logging.debug(f"Doctors Info: {doctors_info}")

    # Анализируем данные о количестве необходимых докторов
    response = []

    for study in study_counts:
        modality = study.study_type if isinstance(study, StudyCount) else study
        study_count = study.study_count if isinstance(study, StudyCount) else study_counts[study]
        required_minutes = study_count * mapper[modality]
        available_doctors = [doc for doc in doctors_info if doc['main_modality'] == modality or modality in doc['additional_modalities']]
        total_available_minutes = sum([doc['hours_per_week'] * 60 for doc in available_doctors])

        if total_available_minutes >= required_minutes:
            response.append({
                "type": modality,
                "quantity": len(available_doctors),
                "isEnough": True,
                "lack": 0
            })
        else:
            doctors_needed = (required_minutes - total_available_minutes) / (40 * 60)  # 40 часов в неделю, 60 минут в час
            response.append({
                "type": modality,
                "quantity": len(available_doctors),
                "isEnough": False,
                "lack": max(0, round(doctors_needed))
            })

    logging.debug(f"Response: {response}")

    return jsonify(response), 200