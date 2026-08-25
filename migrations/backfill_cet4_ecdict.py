# -*- coding: utf-8 -*-
"""四级词库音标/例句回填脚本（ECDICT 数据源）

数据源: f:\\Dev\\JustWord-frontend\\scripts\\ecdict.csv (ECDICT 标准词库, 77 万词)
行为:
  1) 幂等: 检查 library_words 是否已有 example 列, 无则 ALTER 添加;
  2) 读取 ECDICT, 按 english 精确匹配四级库(id=1)全部词条;
  3) 回填 phonetic(音标) + example(英文释义充当例句, 截断 500)。
用法: python migrations/backfill_cet4_ecdict.py   (本脚本当前放在前端 scripts 目录)
"""
import csv
import io
import sys
import asyncio

sys.stdout.reconfigure(encoding="utf-8")
import aiomysql

ECDICT = r"f:\Dev\JustWord-frontend\scripts\ecdict.csv"
LIB_ID = 1


async def main():
    # 1) 读 ECDICT -> {word: (phonetic, definition)}
    ecdict = {}
    with io.open(ECDICT, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # 跳过表头
        for row in reader:
            if not row or not row[0]:
                continue
            word = row[0].strip().lower()
            phon = row[1].strip() if len(row) > 1 else ""
            defin = row[2].strip() if len(row) > 2 else ""
            ecdict[word] = (phon, defin)
    print("ecdict loaded:", len(ecdict))

    c = await aiomysql.connect(host="localhost", user="root", password="123456", db="justword")
    cur = await c.cursor()

    # 2) 幂等添加 example 列
    await cur.execute(
        "SELECT COUNT(*) FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA='justword' AND TABLE_NAME='library_words' AND COLUMN_NAME='example'"
    )
    if (await cur.fetchone())[0] == 0:
        await cur.execute("ALTER TABLE library_words ADD COLUMN example VARCHAR(500) NULL")
        print("column example added")
    else:
        print("column example exists")

    # 3) 读取四级库全部词
    await cur.execute(f"SELECT id, english FROM library_words WHERE library_id={LIB_ID}")
    rows = await cur.fetchall()
    print("library words:", len(rows))

    # 4) 回填 phonetic + example
    updated = 0
    no_phon = 0
    no_example = 0
    for wid, en in rows:
        info = ecdict.get(en.strip().lower())
        if not info:
            continue
        phon, defin = info
        if len(defin) > 500:
            defin = defin[:500]
        await cur.execute(
            "UPDATE library_words SET phonetic=%s, example=%s WHERE id=%s",
            (phon or None, defin or None, wid),
        )
        updated += 1
        if not phon:
            no_phon += 1
        if not defin:
            no_example += 1

    await c.commit()

    # 5) 统计
    await cur.execute("SELECT COUNT(*) FROM library_words WHERE phonetic IS NOT NULL")
    phon_total = (await cur.fetchone())[0]
    await cur.execute("SELECT COUNT(*) FROM library_words WHERE example IS NOT NULL")
    ex_total = (await cur.fetchone())[0]
    print(f"updated={updated} | no_phon={no_phon} | no_example={no_example}")
    print(f"total phonetic={phon_total} | total example={ex_total}")
    c.close()


if __name__ == "__main__":
    asyncio.run(main())
