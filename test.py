import sqlite3

conn = sqlite3.connect('spectrum_data.db')
cursor = conn.cursor()

# 1. 查看表结构
print("🔍 数据库表结构如下：")
cursor.execute("PRAGMA table_info(spectra)")
columns = cursor.fetchall()
for col in columns:
    print(col) 

# 2. 检查数据现状（看看有没有 Unknown）
print("\n👀 数据分类统计：")
cursor.execute("SELECT spectrum_type, COUNT(*) FROM spectra GROUP BY spectrum_type")
stats = cursor.fetchall()
for s in stats:
    print(f"   类型: {s[0]} | 数量: {s[1]}")

# 3. 【可选】一键修复：把 Unknown 批量改成 Standard
# 如果你的标准库里全是 Unknown，取消下面两行的注释来修复
# print("\n🛠️ 正在修复数据标签...")
# cursor.execute("UPDATE spectra SET spectrum_type = 'Standard' WHERE spectrum_type = 'Unknown' OR spectrum_type IS NULL")
# conn.commit()
# print("✅ 修复完成！请重新运行查看统计。")

conn.close()