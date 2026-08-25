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
    achievements = relationship("Achievement", back_populates="user")

class Word(Base):
    __tablename__ = "words"

    id = Column(String(36), primary_key=True)
    english = Column(String(255), nullable=False)
    chinese = Column(String(255), nullable=False)
    phonetic = Column(String(64), nullable=True)         # 音标，可空
    part_of_speech = Column(String(32), nullable=True)   # 词性缩写，如 v./n./adj.
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
    phonetic = Column(String(64), nullable=True)         # 音标，可空
    part_of_speech = Column(String(32), nullable=True)   # 词性缩写，如 v./n./adj.
    example = Column(String(500), nullable=True)         # 例句，可空（ECDICT 英文释义）
    created_at = Column(DateTime, default=datetime.utcnow)

    library = relationship("WordLibrary", back_populates="words")


class UserLibrarySubscription(Base):
    """用户订阅的词库（服务端为准，账号级、跨设备一致，替代前端本地存储）"""
    __tablename__ = "user_library_subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "library_id", name="uq_user_library"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    library_id = Column(Integer, ForeignKey("word_libraries.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="library_subscriptions")
    library = relationship("WordLibrary")


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
    response_ms = Column(Integer, nullable=True)  # 该次判定反应耗时（毫秒）
    is_new = Column(Integer, nullable=True)       # 判定时该词是否为新学(1)/复习(0)（懒聚合按此分桶）
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


class Achievement(Base):
    """已解锁的成就/徽章（一用户一成就一条，解锁时间落库）"""
    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("user_id", "akey", name="uq_achievement_user_key"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    akey = Column(String(64), nullable=False)   # 成就标识
    unlocked_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="achievements")

class RefreshToken(Base):
    """登录刷新令牌（服务端存储，支持撤销与轮换）"""
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(128), unique=True, nullable=False)  # refresh token 的 SHA-256 摘要
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)     # 撤销时间（登出/轮换/失效）
    replaced_by_id = Column(String(36), nullable=True)  # 轮换后的新 refresh token id

    user = relationship("User", backref="refresh_tokens")

class UserPreference(Base):
    """账户级学习偏好（服务端持久化，跨设备一致）"""
    __tablename__ = "user_preferences"

    user_id = Column(String(36), ForeignKey("users.id"), primary_key=True)
    recitation_rule = Column(String(20), nullable=False, default="judge")  # 上次选择的背诵模式
    daily_target = Column(Integer, nullable=False, default=20)             # 每日目标（单词数）
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="preference")


class DailyStat(Base):
    """每日聚合学习统计（学习日 02:00 边界归日；懒聚合 upsert）"""
    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("user_id", "learning_date", name="uq_daily_user_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    learning_date = Column(Date, nullable=False)   # 学习日（02:00 边界归日）
    distinct_words = Column(Integer, default=0)     # 学词数（去重）
    attempts = Column(Integer, default=0)           # 判定数
    correct_count = Column(Integer, default=0)      # 答对数（correct + partial）
    partial_count = Column(Integer, default=0)      # 部分正确数
    wrong_count = Column(Integer, default=0)        # 错误数
    duration_seconds = Column(Integer, default=0)   # 学习时长
    avg_response_ms = Column(Integer, default=0)    # 平均判定反应耗时
    new_learned = Column(Integer, default=0)        # 新学答对数
    review_learned = Column(Integer, default=0)     # 复习答对数

    user = relationship("User", backref="daily_stats")


class WordSnapshot(Base):
    """单词 SM-2 调度历史快照（支撑记忆曲线真实演变）"""
    __tablename__ = "word_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    word_id = Column(String(36), ForeignKey("words.id", ondelete="CASCADE"), nullable=False)
    repetitions = Column(Integer, default=0)
    interval_days = Column(Integer, default=0)
    ef = Column(Float, default=2.5)
    next_review_at = Column(DateTime, nullable=True)
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)  # 快照时间

    user = relationship("User", backref="word_snapshots")
    word = relationship("Word", backref="snapshots")