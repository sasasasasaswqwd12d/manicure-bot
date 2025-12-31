from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, date
import config
import json

engine = create_engine(config.DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    birthday = Column(String(10), nullable=True)  # ДД.ММ.ГГГГ
    visits_count = Column(Integer, default=0)
    total_spent = Column(Integer, default=0)
    discount_percent = Column(Integer, default=0)
    referral_code = Column(String(10), unique=True)
    referred_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    last_visit = Column(DateTime, nullable=True)

    # Отношения
    appointments = relationship("Appointment", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="user", cascade="all, delete-orphan")
    discounts = relationship("UserDiscount", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")

class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    service = Column(String(50))
    service_name = Column(String(100))
    original_price = Column(Integer)
    final_price = Column(Integer)
    discount_applied = Column(Integer, default=0)
    date = Column(String(20))
    time = Column(String(10))
    status = Column(String(20), default="pending", index=True)  # pending, confirmed, completed, cancelled, noshow
    created_at = Column(DateTime, default=datetime.now)
    confirmed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    admin_comment = Column(Text, nullable=True)
    reminder_sent_24h = Column(Boolean, default=False)
    reminder_sent_3h = Column(Boolean, default=False)

    # Отношения
    user = relationship("User", back_populates="appointments")

class Review(Base):
    __tablename__ = 'reviews'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    rating = Column(Integer)  # 1-5
    text = Column(Text)
    photo_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    is_approved = Column(Boolean, default=True)

    # Отношения
    user = relationship("User", back_populates="reviews")

class ServiceImage(Base):
    __tablename__ = 'service_images'
    id = Column(Integer, primary_key=True)
    service_type = Column(String(50))
    image_path = Column(String(500))
    uploaded_at = Column(DateTime, default=datetime.now)

class UserDiscount(Base):
    __tablename__ = 'user_discounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    discount_type = Column(String(50))  # first_visit, referral, birthday, milestone
    discount_percent = Column(Integer)
    is_used = Column(Boolean, default=False)
    valid_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    # Отношения
    user = relationship("User", back_populates="discounts")

class Reminder(Base):
    __tablename__ = 'reminders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    appointment_id = Column(Integer, ForeignKey('appointments.id'), nullable=True)
    reminder_type = Column(String(50))  # 24h_before, 3h_before, after_visit, birthday
    scheduled_for = Column(DateTime)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    # Отношения
    user = relationship("User", back_populates="reminders")

class AdminMessage(Base):
    __tablename__ = 'admin_messages'
    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer)
    message_type = Column(String(50))  # broadcast, individual, targeted
    target_users = Column(JSON, nullable=True)  # Список ID пользователей или фильтры
    message_text = Column(Text)
    photo_path = Column(String(500), nullable=True)
    sent_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    sent_at = Column(DateTime, nullable=True)

def init_db():
    Base.metadata.create_all(engine)
    print("✅ База данных инициализирована")
