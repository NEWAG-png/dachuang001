import sqlite3

DB_PATH = 'spectrum_data.db'

def clean_database():
    """一键安全清洗数据库：删除光谱名称相同的重复数据，只保留ID最小的那一条"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 查找出所有有重复的 spectrum_name
    cursor.execute("""
        SELECT spectrum_name, COUNT(id) as count
        FROM spectra
        GROUP BY spectrum_name
        HAVING count > 1
    """)
    
    duplicate_names = cursor.fetchall()
    
    if not duplicate_names:
        print("✅ 数据库非常干净，没有发现任何重复数据！")
        return

    print(f"⚠️ 扫描到 {len(duplicate_names)} 组重复数据，正在开始智能清洗...")
    total_deleted = 0

    # 2. 遍历这些重复的数据组，执行删除
    for name, count in duplicate_names:
        print(f"  - 正在处理重复项: 【{name}】 (当前共有 {count} 条)")
        
        # 核心逻辑：删除除 id 最小(即最早录入)的那一条之外的所有记录
        cursor.execute("""
            DELETE FROM spectra
            WHERE spectrum_name = ?
            AND id NOT IN (
                SELECT MIN(id) FROM spectra WHERE spectrum_name = ?
            )
        """, (name, name))
        
        deleted_count = cursor.rowcount
        total_deleted += deleted_count
        print(f"    🗑️ 已清理 {deleted_count} 条多余记录，保留了最新/最早的一条。")

    # 3. 提交更改并关闭连接
    conn.commit()
    conn.close()

    print("\n" + "="*50)
    print(f"🎉 数据库清洗完毕！共清理出 {total_deleted} 条重复数据。")
    print("👉 现在你可以重新运行 Web 系统进行匹配测试了！")
    print("="*50)

if __name__ == "__main__":
    clean_database()