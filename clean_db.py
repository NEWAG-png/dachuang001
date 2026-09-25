import sqlite3

# 1. 连接数据库
conn = sqlite3.connect('spectrum_data.db')
cursor = conn.cursor()

# 2. 查出所有名字叫 "待测样品" 的记录
cursor.execute("SELECT id, material_name FROM spectra WHERE material_name LIKE ?", ('%待测样品%',))
rows = cursor.fetchall()

# 3. 删除它们
for row in rows:
    cursor.execute("DELETE FROM spectra WHERE id = ?", (row[0],))
    print(f"已删除 ID: {row[0]}, 名称: {row[1]}")

# 4. 提交并关闭
conn.commit()
conn.close()

# 5. 验证一下现在数据库里还剩多少条标准数据
conn2 = sqlite3.connect('spectrum_data.db')
cursor2 = conn2.cursor()
cursor2.execute("SELECT COUNT(*) FROM spectra WHERE source_tag = ?", ('Standard',))
print(f"\n🚀 数据库清洗完毕！目前 XRF 标准库剩余真实数据: {cursor2.fetchone()[0]} 条。")
conn2.close()