import sqlite3
#连接数据库
conn=sqlite3.connect('spectrum_data.db')
cursor=conn.cursor()
#一键清空
cursor.execute("DELETE FROM spectra")
conn.commit()
conn.close()
print("数据库清洗干净")