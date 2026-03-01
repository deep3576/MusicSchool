import pymysql
from config import Config

conn = pymysql.connect(host=deep3576.mysql.pythonanywhere-services.com, port=3306,
                       user="deep3576", password="Gmsshn!43",
                       database="deep3576$ProductionDB", charset="utf8mb4")
with conn.cursor() as cur:
    cur.execute("SELECT NOW()")
    print(cur.fetchone())
conn.close()
