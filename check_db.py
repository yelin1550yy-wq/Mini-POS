import sqlite3
conn = sqlite3.connect('instance/minipos.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for t in tables:
    print(t[0])
    cursor.execute('SELECT COUNT(*) FROM ' + t[0])
    count = cursor.fetchone()[0]
    print('  Rows:', count)
conn.close()