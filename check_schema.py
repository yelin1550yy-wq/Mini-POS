import sqlite3
conn = sqlite3.connect('instance/minipos.db')
cursor = conn.cursor()

cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='products'")
print('products:', cursor.fetchone()[0])

cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='purchase_items'")
print('purchase_items:', cursor.fetchone()[0])

cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sale_items'")
print('sale_items:', cursor.fetchone()[0])

cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='stock_movements'")
print('stock_movements:', cursor.fetchone()[0])

conn.close()