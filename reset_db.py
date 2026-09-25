import sqlite3
import os

db_path = 'spectrum_data.db'

if not os.path.exists(db_path):
    print("❌ 未找到数据库文件 spectrum_data.db")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🔄 正在格式化标准库数据库...")
    
    # 1. 统一把混乱的 '吸光度' 和 '透过率' 改成标准的 'FTIR'
    cursor.execute("UPDATE spectra SET spectrum_type = 'FTIR' WHERE spectrum_type IN ('吸光度', '透过率')")
    
    # 2. 把所有 source_tag 为 'Standard' 的数据统一归置
    cursor.execute("UPDATE spectra SET source_tag = 'Standard' WHERE source_tag = 'standard'")
    
    # 3. 删除所有非标准库的数据（待测样品和临时数据）
    cursor.execute("DELETE FROM spectra WHERE source_tag != 'Standard'")
    
    # 4. 重置 ID 计数器，让 ID 重新从 1 开始排列
    cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'spectra'")
    cursor.execute("DELETE FROM spectra") 
    
    conn.commit()
    conn.close()
    
    # 重新连接并验证
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT spectrum_type, COUNT(*) FROM spectra GROUP BY spectrum_type")
    rows = cursor.fetchall()
    conn.close()
    
    print("✅ 数据库标准库已彻底重置并格式化！")
    print(f"📊 当前数据库状态：{rows}")
    print("💡 请重新运行你的导入标准库脚本，将你的 52 条真实光谱重新导入。")