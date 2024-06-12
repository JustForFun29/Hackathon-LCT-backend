import uuid
from sqlalchemy.dialects.postgresql import UUID
from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import JSON


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

    doctors = db.relationship('Doctors', backref='user', uselist=False)

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

class DoctorSchedule(db.Model):
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doctor_id = db.Column(UUID(as_uuid=True), db.ForeignKey('doctors.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    break_minutes = db.Column(db.Integer, nullable=False)
    hours_worked = db.Column(db.Float, nullable=False)

    doctor = db.relationship('Doctors', backref=db.backref('schedules', lazy=True))

class Ticket(db.Model):
    __tablename__ = 'ticket'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=True)
    type = db.Column(db.String(64), nullable=False)
    data = db.Column(JSON, nullable=False)
    status = db.Column(db.String(64), nullable=False, default='Pending')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())