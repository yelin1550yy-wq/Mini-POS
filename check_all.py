import sqlite3
conn = sqlite3.connect('instance/minipos.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall()]

for table in tables:
    cursor.execute('SELECT COUNT(*) FROM ' + table)
    count = cursor.fetchone()[0]
    if count > 0:
        print(table + ': ' + str(count) + ' rows')
        cursor.execute('SELECT * FROM ' + table + ' LIMIT 5')
        rows = cursor.fetchall()
        for row in rows:
            print('  ' + str(row))
    else:
        print(table + ': 0 rows')
conn.close()