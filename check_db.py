import os
import sqlite3

DB_NAME = 'spectrum_data.db'

print("=" * 60)
print("【诊断工具】光谱系统健康检查")
print("=" * 60)

# 1. 检查数据库文件是否存在
print("\n[1] 检查数据库文件...")
if os.path.exists(DB_NAME):
    print(f"    OK: {DB_NAME} 存在，大小 {os.path.getsize(DB_NAME)} 字节")
else:
    print(f"    ERROR: {DB_NAME} 不存在！请先运行 python smart_import.py")
    exit(1)

# 2. 检查数据库表结构
print("\n[2] 检查数据库表结构...")
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print(f"    表列表: {tables}")

cursor.execute("PRAGMA table_info(spectra)")
columns = cursor.fetchall()
print(f"\n    spectra 表的列:")
for col in columns:
    print(f"      - {col[1]} (type: {col[2]})")

col_names = [col[1] for col in columns]
if 'spectrum_name' in col_names:
    print("    WARNING: 表中存在 spectrum_name 列！这是旧数据库！")
else:
    print("    OK: 表中不存在 spectrum_name 列")

# 3. 检查数据
print("\n[3] 检查数据内容...")
cursor.execute("SELECT COUNT(*) FROM spectra")
count = cursor.fetchone()[0]
print(f"    总记录数: {count}")

cursor.execute("SELECT spectrum_type, COUNT(*) FROM spectra GROUP BY spectrum_type")
type_counts = cursor.fetchall()
print(f"    各类型分布:")
for t, c in type_counts:
    print(f"      - {t}: {c} 条")

# 4. 打印示例
print("\n[4] 打印第一条示例数据...")
cursor.execute("SELECT name, spectrum_type, substr(data, 1, 80) FROM spectra LIMIT 1")
sample = cursor.fetchone()
if sample:
    print(f"    文件名: {sample[0]}")
    print(f"    类型: {sample[1]}")
    print(f"    数据: {sample[2]}")
else:
    print("    无数据！")

# 5. 检查 app.py
print("\n[5] 检查 app.py 文件内容...")
if os.path.exists('app.py'):
    with open('app.py', 'r', encoding='utf-8') as f:
        app_content = f.read()
    if 'spectrum_name' in app_content:
        print("    !!! 严重: app.py 中仍然包含 'spectrum_name' !!!")
        # 找出在哪一行
        for i, line in enumerate(app_content.split('\n'), 1):
            if 'spectrum_name' in line:
                print(f"       第 {i} 行: {line.strip()}")
    else:
        print("    OK: app.py 中不包含 'spectrum_name'")
    
    # 检查关键函数
    has_parse = 'def parse_csv' in app_content
    has_load = 'def load_database_spectra' in app_content
    has_streamlit = 'streamlit' in app_content or 'st.' in app_content
    print(f"    包含 parse_csv: {has_parse}")
    print(f"    包含 load_database_spectra: {has_load}")
    print(f"    包含 streamlit: {has_streamlit}")
    
    # 打印前30行看看是什么版本的app.py
    print("\n    app.py 前30行:")
    for i, line in enumerate(app_content.split('\n')[:30], 1):
        print(f"      {i:3d}: {line}")
else:
    print("    ERROR: app.py 文件不存在！")

conn.close()
print("\n" + "=" * 60)
print("诊断完成！")
print("=" * 60)