import sqlite3

# 连接你的数据库
conn = sqlite3.connect('spectrum_data.db')
cursor = conn.cursor()

# ⚡ 执行一键清空（放心，只删数据不删文件）
cursor.execute("DELETE FROM spectra")
conn.commit()
conn.close()

print("🧹 数据库已彻底清洗干净！请继续执行下一步导入。")