"""标签体系迁移（幂等）

1) word_libraries / library_words 增加 tags(JSON) 列
2) 按词库名称回填词库标签（四级/六级/考研/托福/雅思/GRE/高考/专四/专八/商务英语）
3) 词库内词条继承词库标签
4) 回填已有用户单词：按英文匹配词库，把标签并入 meta_data.tags（不重复）

用法: python migrations/add_word_tags.py
"""
import asyncio
import json
import aiomysql

DB = dict(host="localhost", user="root", password="123456", db="justword")

_TAG_KWS = ("四级", "六级", "考研", "托福", "雅思", "GRE", "高考", "专四", "专八", "商务英语")


def derive(name: str):
    if not name:
        return None
    for kw in _TAG_KWS:
        if kw in name:
            return kw
    return None


async def main():
    c = await aiomysql.connect(**DB)
    cur = await c.cursor()

    # 1. 加列（MySQL 不支持 ADD COLUMN IF NOT EXISTS，先查 information_schema）
    for table, col, after in (
        ("word_libraries", "tags", "words_count"),
        ("library_words", "tags", "example"),
    ):
        await cur.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
            (DB["db"], table, col),
        )
        exists = (await cur.fetchone())[0]
        if not exists:
            await cur.execute(
                "ALTER TABLE `%s` ADD COLUMN `%s` JSON NULL AFTER `%s`" % (table, col, after)
            )
            print("add column:", table, col)

    # 2. 词库级标签
    await cur.execute("SELECT id, name FROM word_libraries ORDER BY id")
    libs = await cur.fetchall()
    tag_map: dict = {}
    for lid, name in libs:
        tag = derive(name)
        tags = [tag] if tag else []
        tag_map[lid] = tags
        await cur.execute(
            "UPDATE word_libraries SET tags=%s WHERE id=%s",
            (json.dumps(tags, ensure_ascii=False), lid),
        )

    # 3. 词库词条继承词库标签
    for lid, tags in tag_map.items():
        if not tags:
            continue
        await cur.execute(
            "UPDATE library_words SET tags=%s WHERE library_id=%s",
            (json.dumps(tags, ensure_ascii=False), lid),
        )

    # 4. 回填用户单词（按英文匹配，并入已有标签）
    await cur.execute(
        "SELECT english, tags FROM library_words WHERE tags IS NOT NULL AND tags != 'null'"
    )
    en_tags: dict = {}
    for en, raw in await cur.fetchall():
        if not en or not raw:
            continue
        try:
            tags = json.loads(raw)
        except Exception:
            continue
        if not tags:
            continue
        key = en.strip().lower()
        bucket = en_tags.setdefault(key, [])
        for tg in tags:
            if tg not in bucket:
                bucket.append(tg)

    await cur.execute("SELECT id, english, meta_data FROM words WHERE user_id IS NOT NULL")
    updated = 0
    for wid, en, meta in await cur.fetchall():
        if not en:
            continue
        key = en.strip().lower()
        if key not in en_tags:
            continue
        meta = meta if isinstance(meta, dict) else {}
        cur_tags = list(meta.get("tags") or [])
        changed = False
        for tg in en_tags[key]:
            if tg not in cur_tags:
                cur_tags.append(tg)
                changed = True
        if changed:
            meta["tags"] = cur_tags
            await cur.execute(
                "UPDATE words SET meta_data=%s WHERE id=%s",
                (json.dumps(meta, ensure_ascii=False), wid),
            )
            updated += 1

    await c.commit()
    print("libraries:", [(lid, tag_map.get(lid)) for lid, _ in libs])
    print("user words tagged:", updated)
    c.close()
    print("add_word_tags ok")


if __name__ == "__main__":
    asyncio.run(main())