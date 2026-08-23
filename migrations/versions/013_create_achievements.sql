CREATE TABLE IF NOT EXISTS achievements (
    id INTEGER NOT NULL AUTO_INCREMENT,
    user_id VARCHAR(36) NOT NULL,
    akey VARCHAR(64) NOT NULL,
    unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_achievement_user_key (user_id, akey),
    CONSTRAINT fk_achievements_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);