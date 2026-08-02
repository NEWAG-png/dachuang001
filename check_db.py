import sqlite3
import os

# 你的数据库文件名
db_file = "spectrum_data.db"

if not os.path.exists(db_file):
    print(f"❌ 错误：找不到文件 {db_file}，请确保它和脚本在同一个文件夹！")
else:
    print(f"✅ 找到数据库: {db_file}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 1. 获取所有表名
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    if not tables:
        print("⚠️ 数据库是空的，没有表！")
    else:
        print(f"📂 发现表: {[t[0] for t in tables]}")
        
        # 2. 遍历每个表，查看列名和前几行数据
        for table in tables:
            table_name = table[0]
            print(f"\n--- 正在检查表: {table_name} ---")
            
            # 获取列名 (PRAGMA table_info 是查看表结构的命令)
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            col_names = [col[1] for col in columns] # 提取第二项作为列名
            print(f"📋 列名 (Columns): {col_names}")
            
            # 读取前 2 行数据看看样子
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 2")
            rows = cursor.fetchall()
            for row in rows:
                print(f"👀 数据示例: {row}")

    conn.close()
    print("\n🎉 检查完毕！请把上面的【列名】发给我，我立刻修改主程序！")