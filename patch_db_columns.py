import sqlite3
import os
import sys

def patch_database(db_path):
    print(f"Patching database at: {db_path}")
    if not os.path.exists(db_path):
        print(f"[WARN] Database file not found at: {db_path}")
        return False
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Purchases table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='purchases'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(purchases)")
        purchase_cols = [c[1] for c in cursor.fetchall()]
        print(f"Current purchases columns: {purchase_cols}")
        
        if 'payment_source' not in purchase_cols:
            cursor.execute("ALTER TABLE purchases ADD COLUMN payment_source VARCHAR(50) DEFAULT 'in_hand_cash'")
            print("-> Added purchases.payment_source")
        if 'paid_amount' not in purchase_cols:
            cursor.execute("ALTER TABLE purchases ADD COLUMN paid_amount NUMERIC(15, 2) DEFAULT 0")
            print("-> Added purchases.paid_amount")
        if 'balance_due' not in purchase_cols:
            cursor.execute("ALTER TABLE purchases ADD COLUMN balance_due NUMERIC(15, 2) DEFAULT 0")
            print("-> Added purchases.balance_due")
            
        cursor.execute("UPDATE purchases SET payment_source = 'in_hand_cash' WHERE payment_source IS NULL")
        cursor.execute("UPDATE purchases SET paid_amount = 0 WHERE paid_amount IS NULL")
        cursor.execute("UPDATE purchases SET balance_due = 0 WHERE balance_due IS NULL")
    
    # 2. Sales table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales'")
    if cursor.fetchone():
        cursor.execute("PRAGMA table_info(sales)")
        sales_cols = [c[1] for c in cursor.fetchall()]
        print(f"Current sales columns: {sales_cols}")
        
        if 'paid_amount' not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN paid_amount NUMERIC(15, 2) DEFAULT 0")
            print("-> Added sales.paid_amount")
        if 'balance_due' not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN balance_due NUMERIC(15, 2) DEFAULT 0")
            print("-> Added sales.balance_due")
        if 'payment_source' not in sales_cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN payment_source VARCHAR(50) DEFAULT 'in_hand_cash'")
            print("-> Added sales.payment_source")
            
        cursor.execute("UPDATE sales SET paid_amount = 0 WHERE paid_amount IS NULL")
        cursor.execute("UPDATE sales SET balance_due = 0 WHERE balance_due IS NULL")
        cursor.execute("UPDATE sales SET payment_source = 'in_hand_cash' WHERE payment_source IS NULL")
    
    # 3. Sale payments table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sale_payments'")
    if not cursor.fetchone():
        cursor.execute("""
        CREATE TABLE sale_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL REFERENCES sales(id),
            amount NUMERIC(15, 2) NOT NULL,
            payment_date DATETIME NOT NULL,
            payment_method VARCHAR(50) DEFAULT 'Cash',
            notes VARCHAR(200),
            created_by INTEGER REFERENCES users(id)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_sale_payments_sale_id ON sale_payments(sale_id)")
        print("-> Created table sale_payments")

    conn.commit()
    conn.close()
    print("[SUCCESS] Database schema patched and verified.")
    return True

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_db = os.path.join(base_dir, 'instance', 'minipos.db')
    
    # Check if DATABASE_URL or custom argument is provided
    if len(sys.argv) > 1:
        local_db = sys.argv[1]
    else:
        env_db = os.environ.get('DATABASE_URL')
        if env_db and env_db.startswith('sqlite:///'):
            path = env_db[len('sqlite:///'):]
            if os.path.exists(path):
                local_db = path

    patch_database(local_db)
