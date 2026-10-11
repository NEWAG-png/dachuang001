import sqlite3
#1.连接到数据库
conn=sqlite3.connect('spectrum_data.db')
cursor=conn.cursor()
#2.定义
columns_to_add = [
    ('aging_condition', 'TEXT'),
    ('aging_degree', 'TEXT'),
    ('xrd_conclusion', 'TEXT')
]
#3.循环添加
for col_name, col_type in columns_to_add:
    try:
        sql = f"ALTER TABLE spectra ADD COLUMN {col_name} {col_type}"
        cursor.execute(sql)
        print(f"成功添加字段: {col_name}")
    except sqlite3.OperationalError:
        print(f"提示:字段 {col_name} 已经存在，跳过。")
conn.commit()
conn.close()
print("\n数据库修改完成")