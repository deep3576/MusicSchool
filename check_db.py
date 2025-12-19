import pymysql

conn = pymysql.connect(
    host="127.0.0.1",
    port=3306,
    user="deep3576",
    password="Gmsshn!43",
    database="deep3576$TheSpiritSchool_ProdDB",
    charset="utf8mb4",
    connect_timeout=10,
)

with conn.cursor() as cur:
    cur.execute("SELECT 1;")
    print(cur.fetchone())

conn.close()
print("✅ Connected")
