import uuid
from sqlalchemy.dialects.postgresql import UUID
from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import JSONB
import json


class Users(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.Column(db.String(64), nullable=False)
    approved = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Relationship with Doctors
    doctors = db.relationship('Doctors', backref='user', uselist=False)
    # Relationship with Tickets
    tickets = db.relationship('Ticket', backref='associated_user', lazy=True)


class Doctors(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    experience = db.Column(db.String(255), nullable=False)
    main_modality_id = db.Column(db.Integer, db.ForeignKey('modality.id'), nullable=False)
    gender = db.Column(db.String(255), nullable=False)
    rate = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(255), default='Ожидает подтверждения', nullable=False)
    phone = db.Column(db.String(255), nullable=False)
    additional_modalities = db.relationship('Modality', secondary='doctor_additional_modalities', backref=db.backref('doctors', lazy='dynamic'))


class Modality(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)

class DoctorAdditionalModalities(db.Model):
    __tablename__ = 'doctor_additional_modalities'
    doctor_id = db.Column(UUID(as_uuid=True), db.ForeignKey('doctors.id'), primary_key=True)
    modality_id = db.Column(db.Integer, db.ForeignKey('modality.id'), primary_key=True)


import enum
from sqlalchemy import Enum

class DayType(enum.Enum):
    WORKING_DAY = "Рабочий день"
    EMERGENCY = "Непредвиденная ситуация"
    VACATION = "Отпуск"

class DoctorSchedule(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id = db.Column(UUID(as_uuid=True), db.ForeignKey('doctors.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)
    break_minutes = db.Column(db.Integer, nullable=False)
    hours_worked = db.Column(db.Float, nullable=False)
    day_type = db.Column(Enum(DayType), nullable=False, default=DayType.WORKING_DAY)  # Добавляем поле для типа дня

    doctor = db.relationship('Doctors', backref=db.backref('schedules', lazy=True))


class Ticket(db.Model):
    __tablename__ = 'ticket'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=True)
    type = db.Column(db.String(64), nullable=False)
    data = db.Column(JSONB, nullable=False)
    status = db.Column(db.String(64), nullable=False, default='Pending')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    user = db.relationship('Users', backref=db.backref('associated_tickets', lazy=True))

    @property
    def data_dict(self):
        return json.loads(self.data)

    @data_dict.setter
    def data_dict(self, value):
        self.data = json.dumps(value, ensure_ascii=False)

class StudyCount(db.Model):
    __tablename__ = 'study_count'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    year = db.Column(db.Integer, nullable=False)
    week_number = db.Column(db.Integer, nullable=False)
    study_type = db.Column(db.String(255), nullable=False)
    study_count = db.Column(db.Float, nullable=False)
