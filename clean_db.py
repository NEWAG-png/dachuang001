import sqlite3

DB_NAME = 'spectrum_data.db'

def clean_duplicates():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. 查看当前总数
    cursor.execute("SELECT COUNT(*) FROM spectra")
    count_before = cursor.fetchone()[0]
    print(f"清理前数据总量: {count_before}")

    # 2. 删除重复数据
    # 逻辑：保留 ID 最小的那条，删除名字(file_name)和波数数据(data_json)都重复的后续记录
    # 注意：这里假设 file_name 唯一代表一个物质。如果不同物质名字一样，需要调整逻辑。
    # 更稳妥的方式是根据 material_name 去重
    
    cursor.execute('''
        DELETE FROM spectra
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM spectra
            GROUP BY material_name, spectrum_type
        )
    ''')
    
    deleted_count = cursor.rowcount
    conn.commit()
    
    # 3. 查看清理后总数
    cursor.execute("SELECT COUNT(*) FROM spectra")
    count_after = cursor.fetchone()[0]
    print(f"清理后数据总量: {count_after}")
    print(f"成功删除重复数据: {deleted_count} 条")
    
    conn.close()

if __name__ == '__main__':
    clean_duplicates()