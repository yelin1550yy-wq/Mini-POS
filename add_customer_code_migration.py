#!/usr/bin/env python
"""
Database migration script to add customer_code column and auto-generate codes for existing customers.
Run this on PythonAnywhere or local after deploying the new code.

Usage:
    python add_customer_code_migration.py
"""
import os
import sys

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, Customer

app = create_app()

with app.app_context():
    print("Running customer_code migration...")
    
    # Check if column exists (SQLite)
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('customers')]
    
    if 'customer_code' not in columns:
        print("Adding customer_code column...")
        # SQLite doesn't support ALTER TABLE ADD COLUMN with unique constraint directly
        # We'll use a workaround: create new table, copy data, drop old, rename
        
        with db.engine.connect() as conn:
            conn.execute(db.text("""
                CREATE TABLE customers_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    customer_code VARCHAR(20) NOT NULL UNIQUE,
                    name VARCHAR(200) NOT NULL,
                    account_name VARCHAR(200),
                    phone VARCHAR(50),
                    township VARCHAR(100),
                    address TEXT,
                    notes TEXT,
                    is_blacklisted BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME,
                    updated_at DATETIME,
                    tier VARCHAR(20) DEFAULT 'Silver'
                )
            """))
            
            # Get existing customers and generate codes
            existing = conn.execute(db.text("SELECT id, name, account_name, phone, township, address, notes, is_blacklisted, is_active, created_at, updated_at, tier FROM customers")).fetchall()
            
            for i, row in enumerate(existing, 1):
                code = f'CUST-{i:04d}'
                conn.execute(db.text("""
                    INSERT INTO customers_new (id, customer_code, name, account_name, phone, township, address, notes, is_blacklisted, is_active, created_at, updated_at, tier)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """), (row.id, code, row.name, row.account_name, row.phone, row.township, row.address, row.notes, row.is_blacklisted, row.is_active, row.created_at, row.updated_at, row.tier))
            
            conn.execute(db.text("DROP TABLE customers"))
            conn.execute(db.text("ALTER TABLE customers_new RENAME TO customers"))
            conn.commit()
        
        print(f"Migrated {len(existing)} existing customers with auto-generated codes.")
    else:
        print("customer_code column already exists, checking for nulls...")
        
        # Generate codes for any customers without one
        customers_without_code = Customer.query.filter(
            (Customer.customer_code.is_(None)) | (Customer.customer_code == '')
        ).all()
        
        if customers_without_code:
            for i, customer in enumerate(customers_without_code, 1):
                # Find next available number
                last = Customer.query.filter(Customer.customer_code.isnot(None)).order_by(Customer.id.desc()).first()
                if last and last.customer_code:
                    try:
                        last_num = int(last.customer_code.split('-')[-1])
                        next_num = last_num + i
                    except (ValueError, IndexError):
                        next_num = i
                else:
                    next_num = i
                customer.customer_code = f'CUST-{next_num:04d}'
            
            db.session.commit()
            print(f"Generated codes for {len(customers_without_code)} customers.")
        else:
            print("All customers already have codes.")
    
    # Recreate tier configs if missing
    from app.models import TierConfig
    TierConfig.initialize_default_tiers()
    print("Tier configs initialized.")
    
    # Verify
    total = Customer.query.count()
    with_code = Customer.query.filter(Customer.customer_code.isnot(None)).count()
    print(f"\nVerification: {total} total customers, {with_code} with customer_code")
    
    # Show sample
    for c in Customer.query.order_by(Customer.id).limit(5).all():
        print(f"  {c.customer_code} - {c.name}")
    
    print("\nMigration complete!")