import sqlite3

# 1. 连接数据库
conn = sqlite3.connect('spectrum_data.db')
cursor = conn.cursor()

# 2. 找到所有 source_tag 为 'User_Upload' 的记录，把它们升级成 'Standard'
cursor.execute("SELECT COUNT(*) FROM spectra WHERE source_tag = ?", ('User_Upload',))
count_before = cursor.fetchone()[0]

cursor.execute("UPDATE spectra SET source_tag = ? WHERE source_tag = ?", ('Standard', 'User_Upload'))

# 3. 查看升级后的数量，确认修改成功
cursor.execute("SELECT COUNT(*) FROM spectra WHERE source_tag = ?", ('Standard',))
count_after = cursor.fetchone()[0]

conn.commit()
conn.close()

print("=" * 50)
print(f"🚀 升级完毕！")
print(f"📦 成功将 {count_before} 条数据从“待测样品”册封为“标准库”！")
print(f"🎯 现在你的标准库里一共有 {count_after} 条数据。")
print("=" * 50)
print("快去刷新网页，马上就能搜到 XRF 了！")