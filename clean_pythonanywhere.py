#!/usr/bin/env python
"""
Run this on PythonAnywhere to clean all test data from the database.
Usage on PythonAnywhere:
1. Upload this file to your project directory
2. Run: python clean_pythonanywhere.py
"""
import os
import sys

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db, Product, Supplier, Customer, Purchase, PurchaseItem, Sale, SaleItem, StockMovement, Expense, Capital, TierConfig

app = create_app()

with app.app_context():
    print("Cleaning PythonAnywhere database...")
    
    # Delete in correct order (children first due to FK constraints)
    deleted = {}
    
    deleted['sale_items'] = SaleItem.query.delete()
    deleted['sales'] = Sale.query.delete()
    deleted['purchase_items'] = PurchaseItem.query.delete()
    deleted['purchases'] = Purchase.query.delete()
    deleted['stock_movements'] = StockMovement.query.delete()
    deleted['expenses'] = Expense.query.delete()
    deleted['capital'] = Capital.query.delete()
    deleted['customers'] = Customer.query.delete()
    deleted['suppliers'] = Supplier.query.delete()
    deleted['products'] = Product.query.delete()
    # Keep users and tier_config
    
    db.session.commit()
    
    print("Deleted:")
    for table, count in deleted.items():
        print(f"  {table}: {count} rows")
    
    # Verify
    print("\nRemaining counts:")
    print(f"  products: {Product.query.count()}")
    print(f"  purchases: {Purchase.query.count()}")
    print(f"  sales: {Sale.query.count()}")
    print(f"  stock_movements: {StockMovement.query.count()}")
    print(f"  suppliers: {Supplier.query.count()}")
    print(f"  customers: {Customer.query.count()}")
    print(f"  users: {db.session.query(db.Model).filter(db.Model.__tablename__ == 'users').count()}")
    
    print("\nDone! Database cleaned.")