from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, JSON, Float, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    username = Column(String(255), nullable=False)  # ✅ 确保有这个字段
    created_at = Column(DateTime, default=datetime.utcnow)
    words = relationship("Word", back_populates="user")
    learning_records = relationship("LearningRecord", back_populates="user")
    checkins = relationship("Checkin", back_populates="user")
    wrong_words = relationship("WrongWord", back_populates="user")
    wordbooks = relationship("Wordbook", back_populates="user")

class Word(Base):
    __tablename__ = "words"
    
    id = Column(String(36), primary_key=True)
    english = Column(String(255), nullable=False)
    chinese = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(String(36), ForeignKey("users.id"))
    meta_data = Column(JSON, nullable=True, default={})
    wordbook_id = Column(Integer, ForeignKey("wordbooks.id", ondelete="SET NULL"), nullable=True, default=None)  # 所属单词本

    # 间隔重复(SM-2)调度字段
    ef = Column(Float, default=2.5)                    # 易学度因子
    review_interval = Column(Integer, default=0)       # 间隔天数
    repetitions = Column(Integer, default=0)           # 连续答对次数
    next_review_at = Column(DateTime, nullable=True, default=datetime.utcnow)  # 下次复习时间
    last_reviewed_at = Column(DateTime, nullable=True) # 上次复习时间
    
    # ✅ 关系定义
    user = relationship("User", back_populates="words")
    learning_records = relationship("LearningRecord", back_populates="word")
    wordbook = relationship("Wordbook", back_populates="words")
    wrong_words = relationship("WrongWord", back_populates="word", cascade="all, delete-orphan")


class Wordbook(Base):
    __tablename__ = "wordbooks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="wordbooks")
    words = relationship("Word", back_populates="wordbook", order_by="Word.created_at.desc()")

class WordLibrary(Base):
    """公开词汇库（不属于单个用户，供用户导入）"""
    __tablename__ = "word_libraries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True, default="")
    words_count = Column(Integer, nullable=False, default=0)  # 词库内单词数
    created_at = Column(DateTime, default=datetime.utcnow)

    words = relationship("LibraryWord", back_populates="library", order_by="LibraryWord.english")

class LibraryWord(Base):
    """词库内的词（公开共享）"""
    __tablename__ = "library_words"

    id = Column(Integer, primary_key=True, autoincrement=True)
    library_id = Column(Integer, ForeignKey("word_libraries.id", ondelete="CASCADE"), nullable=False)
    english = Column(String(255), nullable=False)
    chinese = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    library = relationship("WordLibrary", back_populates="words")


class WrongWord(Base):
    """错题/薄弱词记录（一用户一词一条，复习答错自动累计）"""
    __tablename__ = "wrong_words"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    word_id = Column(String(36), ForeignKey("words.id", ondelete="CASCADE"), nullable=False)
    wrong_count = Column(Integer, nullable=False, default=1)   # 累计答错次数
    last_wrong_at = Column(DateTime, default=datetime.utcnow)  # 最近一次答错时间
    status = Column(String(20), nullable=False, default="open")  # open 待巩固 / resolved 已解决
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "word_id", name="uq_wrong_user_word"),)

    user = relationship("User", back_populates="wrong_words")
    word = relationship("Word", back_populates="wrong_words")

class LearningRecord(Base):
    __tablename__ = "learning_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    word_id = Column(String(36), ForeignKey("words.id"))
    user_id = Column(String(36), ForeignKey("users.id"))
    mode = Column(String(20))  # 'en2zh' 或 'zh2en'
    user_answer = Column(Text)
    correct_answer = Column(Text)
    result = Column(String(20))  # 'correct', 'partial', 'wrong', 'close'
    score = Column(Float)
    feedback = Column(Text, nullable=True)    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # ✅ 关系定义
    word = relationship("Word", back_populates="learning_records")
    user = relationship("User", back_populates="learning_records")


class Checkin(Base):
    __tablename__ = "checkins"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_checkin_user_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"))
    date = Column(Date, nullable=False)  # 打卡日期
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="checkins")