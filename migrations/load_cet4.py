"""重建四级词库加载脚本

数据资产: migrations/data/cet4.tsv (english<TAB>chinese, 4543 条)
行为: 清空目标库旧词 -> 更新库名/描述 -> 批量插入 -> 回填 words_count。
用法: python migrations/load_cet4.py [library_id]
"""
import os
import sys
import asyncio
import aiomysql

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录
TSV = os.path.join(REPO, "migrations", "data", "cet4.tsv")
LIB_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
NEW_NAME = "大学英语四级完整词表"
NEW_DESC = "大学英语四级完整词表（4543 词，数据源 KyleBing/english-vocabulary）"


async def main():
    rows = []
    with open(TSV, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line or "\t" not in line:
                continue
            en, _, zh = line.partition("\t")
            rows.append((en.strip(), zh.strip()))
    print("to load:", len(rows))

    c = await aiomysql.connect(host="localhost", user="root", password="123456", db="justword")
    cur = await c.cursor()
    await cur.execute("DELETE FROM library_words WHERE library_id=%s", (LIB_ID,))
    await cur.execute("UPDATE word_libraries SET name=%s, description=%s WHERE id=%s",
                      (NEW_NAME, NEW_DESC, LIB_ID))
    sql = "INSERT INTO library_words (library_id, english, chinese) VALUES (%s,%s,%s)"
    for i in range(0, len(rows), 500):
        await cur.executemany(sql, [(LIB_ID, en, zh) for en, zh in rows[i:i + 500]])
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