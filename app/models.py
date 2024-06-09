from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
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
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
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
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), primary_key=True)
    modality_id = db.Column(db.Integer, db.ForeignKey('modality.id'), primary_key=True)
