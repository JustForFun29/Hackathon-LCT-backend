import uuid
import string
import random
from flask import Blueprint, jsonify, request, current_app
from app import db, mail
from app.models import Users, Doctors, Modality, DoctorAdditionalModalities, DoctorSchedule, Ticket
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.decorators import role_and_approval_required, check_token_not_revoked
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from flask_mail import Message
import logging
import simplejson as json
hr_bp = Blueprint('hr', __name__)

# Настраиваем логирование
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s:%(message)s')

def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    password = ''.join(random.choice(characters) for i in range(length))
    return password

#TODO: Поменять это на рабочий email

# def send_email(to, subject, template):
#     msg = Message(
#         subject,
#         recipients=[to],
#         html=template,
#         sender="hello@such.ae"
#     )
#     mail.send(msg)
def send_email(to, subject, template):
    print(f'{to} {subject} {template}')


@hr_bp.route('/email', methods=['POST'])
@role_and_approval_required('hr')
def email_test():
    data = request.get_json()
    try:
        # Отправляем уведомление по электронной почте
        subject = "Был создан запрос на создание аккаунта"
        to = 'dimashumbetzhan@gmail.com'
        template = f"""
                       <p>Дождитесь активации вашего аккаунта после утверждения руководителя!</p>
                       """
        send_email(to, subject, template)
        return jsonify({'message': 'success!'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@hr_bp.route('/create_doctor', methods=['POST'])
@role_and_approval_required('hr')
def hr_create_doctor():
    data = request.get_json()
    try:
        password = generate_random_password()
        new_user = Users(
            full_name=data['full_name'],
            email=data['email'],
            role='doctor',
            approved=False
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

        # Создаем тикет для подтверждения доктора
        new_ticket = Ticket(
            user_id=new_user.id,
            type='approve_doctor',
            data={},
            status='Pending'
        )
        db.session.add(new_ticket)
        db.session.commit()

        # Отправляем уведомление по электронной почте
        subject = "Был создан запрос на создание аккаунта"
        to = data['email']
        template = f"""
               <p>Уважаемый {data['full_name']},</p>
               <p>Сотрудник Кадрового Отдела создал запрос на активацию вашего аккаунта в системе</p>
               <p>Ваш логин {data['email']}</p>
               <p>Ваш пароль {password}<p>
               <p>Дождитесь активации вашего аккаунта после утверждения руководителя!</p>
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

@hr_bp.route('/doctor/<uuid:doctor_id>/delete', methods=['DELETE'])
@role_and_approval_required('hr')
def delete_doctor(doctor_id):
    try:
        doctor = Doctors.query.get(doctor_id)
        if not doctor:
            return jsonify({'message': 'Doctor not found'}), 404

        db.session.delete(doctor)
        db.session.commit()

        # Создаем тикет для удаления врача
        new_ticket = Ticket(
            user_id=doctor.user_id,
            type='delete_doctor',
            data={},
            status='Pending'
        )
        db.session.add(new_ticket)
        db.session.commit()

        return jsonify({'message': 'Doctor deleted successfully and deletion ticket generated'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400

@hr_bp.route('/doctor/<uuid:doctor_id>/update', methods=['PUT'])
@role_and_approval_required('hr')
def propose_doctor_update(doctor_id):
    data = request.get_json()
    try:
        # Получаем пользователя по doctor_id
        doctor = Doctors.query.get(doctor_id)
        if not doctor:
            return jsonify({'message': 'Doctor not found'}), 404

        user_id = doctor.user_id

        # Обрабатываем основную модальность
        if 'main_modality' in data:
            main_modality_name = data['main_modality']
            main_modality = Modality.query.filter_by(name=main_modality_name).first()
            if not main_modality:
                main_modality = Modality(name=main_modality_name)
                db.session.add(main_modality)
                db.session.commit()
            data['main_modality_id'] = main_modality.id
            del data['main_modality']  # Удаляем текстовое поле, так как мы добавили ID

        # Сериализуем данные в JSON строку
        data_json = json.dumps(data, ensure_ascii=False)

        # Создаем тикет для изменения данных врача
        new_ticket = Ticket(
            user_id=user_id,
            type='update_doctor',
            data=data_json,  # Сохраняем сериализованные данные
            status='Pending'
        )
        db.session.add(new_ticket)
        db.session.commit()

        return jsonify({'message': 'Doctor update ticket created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': str(e)}), 400


# @hr_bp.route('/doctor/<uuid:doctor_id>/schedule', methods=['POST'])
# @role_and_approval_required('hr')
# def create_schedule(doctor_id):
#     data = request.get_json()
#     try:
#         schedule_entries = data['schedule']
#         for entry in schedule_entries:
#             schedule = DoctorSchedule(
#                 doctor_id=doctor_id,
#                 date=datetime.strptime(entry['date'], '%Y-%m-%d').date(),
#                 start_time=datetime.strptime(entry['start_time'], '%H:%M').time(),
#                 end_time=datetime.strptime(entry['end_time'], '%H:%M').time(),
#                 break_minutes=entry['break_minutes'],
#                 hours_worked=entry['hours_worked']
#             )
#             db.session.add(schedule)
#         db.session.commit()
#         return jsonify({'message': 'Schedule created successfully'}), 201
#     except Exception as e:
#         db.session.rollback()
#         return jsonify({'message': str(e)}), 400


# @hr_bp.route('/doctor/<uuid:doctor_id>/schedule/<uuid:schedule_id>', methods=['DELETE'])
# @role_and_approval_required('hr')
# def delete_schedule(doctor_id, schedule_id):
#     try:
#         schedule = DoctorSchedule.query.get(schedule_id)
#         if not schedule or schedule.doctor_id != doctor_id:
#             return jsonify({'message': 'Schedule not found'}), 404
#
#         db.session.delete(schedule)
#         db.session.commit()
#         return jsonify({'message': 'Schedule deleted successfully'}), 200
#     except Exception as e:
#         db.session.rollback()
#         return jsonify({'message': str(e)}), 400
