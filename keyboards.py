from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import config

engine = create_engine(config.DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.now)

class Appointment(Base):
    __tablename__ = 'appointments'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    service = Column(String(50))
    date = Column(String(20))
    time = Column(String(10))
    status = Column(String(20), default="pending")  # pending, approved, rejected, completed
    created_at = Column(DateTime, default=datetime.now)
    admin_comment = Column(Text, nullable=True)

class ServiceImage(Base):
    __tablename__ = 'service_images'
    id = Column(Integer, primary_key=True)
    service_type = Column(String(50))
    image_path = Column(String(255))
    uploaded_at = Column(DateTime, default=datetime.now)

def init_db():
    Base.metadata.create_all(engine)
