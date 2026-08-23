-- ============================================
-- 迁移脚本: 005_seed_default_words.sql
-- 描述: 添加默认示例单词
-- 作者: XuLin8
-- 日期: 2026-08-20
-- 版本: 005
-- ============================================

-- 执行迁移
INSERT INTO words (id, english, chinese, meta_data) VALUES
(UUID(), 'apple', '苹果', JSON_OBJECT(
    'phonetic', JSON_OBJECT('uk', '/ˈæpl/', 'us', '/ˈæpl/'),
    'wordType', 'noun',
    'difficulty', 1,
    'tags', JSON_ARRAY('fruit', 'food')
)),
(UUID(), 'book', '书本', JSON_OBJECT(
    'phonetic', JSON_OBJECT('uk', '/bʊk/', 'us', '/bʊk/'),
    'wordType', 'noun',
    'difficulty', 1,
    'tags', JSON_ARRAY('education')
)),
(UUID(), 'run', '跑步', JSON_OBJECT(
    'phonetic', JSON_OBJECT('uk', '/rʌn/', 'us', '/rʌn/'),
    'wordType', 'verb',
    'difficulty', 1,
    'conjugation', JSON_OBJECT(
        'present', 'run',
        'past', 'ran',
        'pastParticiple', 'run'
    )
));

-- ============================================
-- 回滚脚本
-- DELETE FROM words WHERE english IN ('apple', 'book', 'run');
-- ============================================