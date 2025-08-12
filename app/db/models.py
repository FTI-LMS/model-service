from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class VideoRecord(Base):
    __tablename__ = 'videos'
    id = Column(Integer, primary_key=True)
    job_id = Column(String(36), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    duration = Column(Float, nullable=False)
    instructor_name = Column(String(255))
    category = Column(String(100))
    training_content = Column(Text)
    transcript = Column(Text)
    confidence_score = Column(Float)
    extraction_method = Column(String(100))
    processing_status = Column(String(50), default='pending')  # pending|processing|completed|failed
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class ProcessingJob(Base):
    __tablename__ = 'jobs'
    id = Column(Integer, primary_key=True)
    job_id = Column(String(36), unique=True, nullable=False, index=True)
    status = Column(String(50), default='pending')
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    failed_files = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
