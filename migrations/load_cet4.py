"""重建四级词库加载脚本

数据资产: migrations/data/cet4.tsv (english<TAB>chinese, 4543 条)
行为: 清空目标库旧词 -> 更新库名/描述 -> 批量插入 -> 回填 words_count。
chinese 释义前缀含词性缩写（如 "v. 放弃"），解析后存入 part_of_speech 并自释义剥离。
用法: python migrations/load_cet4.py [library_id]
"""
import os
import sys
import asyncio
from typing import Optional
import aiomysql

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录
TSV = os.path.join(REPO, "migrations", "data", "cet4.tsv")
LIB_ID = int(sys.argv[1]) if sys.argv[1:] else 1
NEW_NAME = "大学英语四级完整词表"
NEW_DESC = "大学英语四级完整词表（4543 词，数据源 KyleBing/english-vocabulary）"


# 词性缩写 -> 全称（仅用于规整，保留缩写即可）
_POS_ABBR = {
    "n.", "v.", "vt.", "vi.", "adj.", "adv.", "art.", "pron.", "prep.",
    "conj.", "interj.", "num.", "aux.",
}


def parse_pos(chinese: str) -> tuple[Optional[str], str]:
    """从释义中提取词性前缀，返回 (part_of_speech, 剥离后的释义)。"""
    zh = chinese.strip()
    # 命中开头 "art." / "adj." / "vt." 等前缀（可追加空格）
    for abbr in sorted(_POS_ABBR, key=len, reverse=True):
        if zh.startswith(abbr):
            rest = zh[len(abbr):].strip()
            # 去掉“；/，/（）”等分隔符后紧跟的分隔
            rest = rest.lstrip("；;，,、 ")
            return abbr, rest
    return None, zh


async def main():
    rows = []
    no_pos = 0
    with open(TSV, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line or "\t" not in line:
                continue
            en, _, zh = line.partition("\t")
            pos, zh_clean = parse_pos(zh)
            rows.append((en.strip(), zh_clean, pos))
            if not pos:
                no_pos += 1
    print("to load:", len(rows), "| without pos:", no_pos)

    c = await aiomysql.connect(host="localhost", user="root", password="123456", db="justword")
    cur = await c.cursor()
    await cur.execute("DELETE FROM library_words WHERE library_id=%s", (LIB_ID,))
    await cur.execute("UPDATE word_libraries SET name=%s, description=%s WHERE id=%s",
                      (NEW_NAME, NEW_DESC, LIB_ID))
    sql = "INSERT INTO library_words (library_id, english, chinese, part_of_speech) VALUES (%s,%s,%s,%s)"
    for i in range(0, len(rows), 500):
        await cur.executemany(sql, [(LIB_ID, en, zh, pos) for en, zh, pos in rows[i:i + 500]])
    await cur.execute(
        "UPDATE word_libraries wl SET words_count=(SELECT COUNT(*) FROM library_words lw WHERE lw.library_id=wl.id)"
    )
    await c.commit()
    await cur.execute("SELECT id,name,words_count FROM word_libraries ORDER BY id")
    for r in await cur.fetchall():
        print(r)
    c.close()
    print("load cet4 ok")


if __name__ == "__main__":
    asyncio.run(main())