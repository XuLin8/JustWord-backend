from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    words = relationship("Word", back_populates="user")

class Word(Base):
    __tablename__ = "words"
    
    id = Column(String(36), primary_key=True)
    english = Column(String(255), nullable=False)
    chinese = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(String(36), ForeignKey("users.id"))
    meta_data = Column(JSON, nullable=True, default={})
    
    # ✅ 关系定义
    user = relationship("User", back_populates="words")
    learning_records = relationship("LearningRecord", back_populates="word")

class LearningRecord(Base):
    __tablename__ = "learning_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    word_id = Column(String(36), ForeignKey("words.id"))
    mode = Column(String(20))  # 'en2zh' 或 'zh2en'
    user_answer = Column(Text)
    correct_answer = Column(Text)
    result = Column(String(20))  # 'correct', 'partial', 'wrong', 'close'
    score = Column(Float)
    feedback = Column(Text, nullable=True)    created_at = Column(DateTime, default=datetime.utcnow)
    
    # ✅ 关系定义
    word = relationship("Word", back_populates="learning_records")