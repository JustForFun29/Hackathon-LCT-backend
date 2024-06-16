import json
from datetime import datetime, timedelta
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from werkzeug.security import generate_password_hash
from app.models import Users, Doctors, Modality, DoctorSchedule, db

# Путь к вашему файлу JSON
json_file_path = 'doctors.json'

# Создание подключения к базе данных
engine = create_engine('postgresql://postgres:123456@localhost/such')
Session = sessionmaker(bind=engine)
session = Session()

# Пароль по умолчанию для всех врачей
default_password = '123456'

# Функция для создания или получения модальности
def get_or_create_modality(name):
    modality = session.query(Modality).filter_by(name=name).first()
    if not modality:
        modality = Modality(name=name)
        session.add(modality)
        session.commit()
    return modality

# Загрузка данных из JSON файла
with open(json_file_path, 'r', encoding='utf-8') as file:
    doctors_data = json.load(file)

# Обработка данных
for doctor_data in doctors_data:
    # Проверка на существование пользователя с таким же email
    existing_user = session.query(Users).filter_by(email=doctor_data['email']).first()
    if existing_user:
        print(f"Пользователь с email {doctor_data['email']} уже существует. Пропуск.")
        continue

    # Создание пользователя
    user = Users(
        full_name=doctor_data['name'],
        email=doctor_data['email'],
        role='doctor',
        approved=True,
        password_hash=generate_password_hash(default_password)
    )
    session.add(user)
    session.commit()

    # Получение основной модальности
    main_modality = get_or_create_modality(doctor_data['main_modality'])

    # Создание врача
    doctor = Doctors(
        user_id=user.id,
        experience=str(doctor_data['experience']),
        main_modality_id=main_modality.id,
        gender=doctor_data['gender'],
        rate=doctor_data['rate'],
        phone=doctor_data['phone']
    )
    session.add(doctor)
    session.commit()

    # Добавление дополнительных модальностей
    for additional_modality_name in doctor_data['additional_modalities']:
        additional_modality = get_or_create_modality(additional_modality_name)
        doctor.additional_modalities.append(additional_modality)

    session.commit()

    # Добавление расписания
    for schedule_data in doctor_data['schedule']:
        schedule = DoctorSchedule(
            doctor_id=doctor.id,
            date=datetime.now() + timedelta(days=schedule_data['day_number']),  # Пример даты
            start_time=datetime.strptime(schedule_data['start'], '%H:%M').time(),
            end_time=datetime.strptime(schedule_data['end'], '%H:%M').time(),
            break_minutes=schedule_data['break'],
            hours_worked=schedule_data['hours'],
            day_type="WORKING_DAY"
        )
        session.add(schedule)

    session.commit()

print("Импорт данных завершен успешно.")

# Закрытие сессии
session.close()
