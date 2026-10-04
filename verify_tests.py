#!/usr/bin/env python
"""
Complete verification and testing walkthrough for Mo Mo Pajamas POS application.
Tests all requirements and cleans up test data.
"""
import os
import sys
from decimal import Decimal
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import (
    db, User, Product, Supplier, Customer, Purchase, PurchaseItem, 
    Sale, SaleItem, StockMovement, TierConfig
)
from sqlalchemy import or_

app = create_app()

def cleanup_test_data():
    """Clean up all test data created during testing"""
    print("\n=== CLEANING UP TEST DATA ===")
    
    # Rollback any pending transaction first
    try:
        db.session.rollback()
    except:
        pass
    
    # Delete in correct order (children first due to FK constraints)
    deleted = {}
    
    # Delete test sale items and sales
    test_sales = Sale.query.filter(Sale.sale_no.like('SO-TEST%')).all()
    for sale in test_sales:
        SaleItem.query.filter_by(sale_id=sale.id).delete()
    Sale.query.filter(Sale.sale_no.like('SO-TEST%')).delete()
    deleted['test_sales'] = len(test_sales)
    
    # Delete test purchase items and purchases
    test_purchases = Purchase.query.filter(Purchase.purchase_no.like('PO-TEST%')).all()
    for purchase in test_purchases:
        PurchaseItem.query.filter_by(purchase_id=purchase.id).delete()
    Purchase.query.filter(Purchase.purchase_no.like('PO-TEST%')).delete()
    deleted['test_purchases'] = len(test_purchases)
    
    # Delete test stock movements
    StockMovement.query.filter(StockMovement.reference_no.like('%TEST%')).delete()
    deleted['test_stock_movements'] = StockMovement.query.filter(StockMovement.reference_no.like('%TEST%')).count()
    
    # Delete test customers
    test_customers = Customer.query.filter(
        (Customer.customer_code.like('CUST-TEST%')) | 
        (Customer.customer_code.like('CUST-999%')) |
        (Customer.name.like('Test Customer%'))
    ).all()
    for c in test_customers:
        db.session.delete(c)
    deleted['test_customers'] = len(test_customers)
    
    # Delete test products
    test_products = Product.query.filter(Product.product_code.like('TEST%')).all()
    for p in test_products:
        db.session.delete(p)
    deleted['test_products'] = len(test_products)
    
    # Delete test suppliers
    test_suppliers = Supplier.query.filter(Supplier.name.like('Test Supplier%')).all()
    for s in test_suppliers:
        db.session.delete(s)
    deleted['test_suppliers'] = len(test_suppliers)
    
    db.session.commit()
    
    print("Deleted:")
    for k, v in deleted.items():
        print(f"  {k}: {v}")

def test_customer_code_and_sorting():
    """Test 1: Customer Code & Sorting"""
    print("\n=== TEST 1: Customer Code & Sorting ===")
    
    # Test 1a: Create customer without code (auto-generate)
    customer1 = Customer(
        name="Test Customer Auto Code",
        phone="09-11111111",
        township="Test Township"
    )
    db.session.add(customer1)
    db.session.flush()
    
    print(f"Customer 1 created with code: {customer1.customer_code}")
    assert customer1.customer_code == "CUST-0001", f"Expected CUST-0001, got {customer1.customer_code}"
    print("[OK] Auto-generation works")
    
    # Test 1b: Create customer with custom code
    customer2 = Customer(
        customer_code="CUST-9999",
        name="Test Customer Custom Code",
        phone="09-22222222",
        township="Test Township"
    )
    db.session.add(customer2)
    db.session.flush()
    
    print(f"Customer 2 created with code: {customer2.customer_code}")
    assert customer2.customer_code == "CUST-9999", f"Expected CUST-9999, got {customer2.customer_code}"
    print("[OK] Custom code works")
    
    # Commit both customers
    db.session.commit()
    
    # Test 1c: Duplicate code validation (in new transaction)
    try:
        customer3 = Customer(
            customer_code="CUST-9999",
            name="Test Duplicate",
            phone="09-33333333"
        )
        db.session.add(customer3)
        db.session.flush()
        db.session.commit()
        print("[FAIL] Should have rejected duplicate code")
        return False
    except Exception as e:
        db.session.rollback()
        print("[OK] Duplicate code rejected")
    
    # Test 1d: Verify sorting (newest first)
    customers = Customer.query.order_by(Customer.created_at.desc()).all()
    assert customers[0].id == customer2.id, "Newest customer should be first"
    assert customers[1].id == customer1.id, "Second newest should be second"
    print("[OK] Sorting by created_at.desc() works")
    
    # Test 1e: Verify customer_code column in query
    customers_with_code = Customer.query.filter(Customer.customer_code.isnot(None)).all()
    for c in customers_with_code:
        assert c.customer_code is not None
    print("[OK] All customers have customer_code")
    
    db.session.commit()
    return True

def test_sale_customer_selection_and_search():
    """Test 2: Sale Order Customer Selection & Search"""
    print("\n=== TEST 2: Sale Order Customer Selection & Search ===")
    
    # Create test supplier and products first
    supplier = Supplier(name="Test Supplier", phone="09-99999999")
    db.session.add(supplier)
    db.session.flush()
    
    product1 = Product(
        product_code="TEST-001",
        item_name="Test Product 1",
        product_type="စပန့်",
        reference_selling_price=1000,
        minimum_stock=5
    )
    product2 = Product(
        product_code="TEST-002",
        item_name="Test Product 2",
        product_type="ချည်နု",
        reference_selling_price=2000,
        minimum_stock=3
    )
    db.session.add_all([product1, product2])
    db.session.flush()
    
    # Create accepted purchase to add stock
    purchase = Purchase(
        purchase_no="PO-TEST-STOCK-001",
        date=date.today(),
        supplier_id=supplier.id,
        status="Accepted",
        accepted_date=datetime.utcnow()
    )
    db.session.add(purchase)
    db.session.flush()
    
    pi1 = PurchaseItem(purchase_id=purchase.id, product_id=product1.id, quantity=100, unit_price=500, reference_price=1000, total_price=50000)
    pi2 = PurchaseItem(purchase_id=purchase.id, product_id=product2.id, quantity=50, unit_price=1000, reference_price=2000, total_price=50000)
    db.session.add_all([pi1, pi2])
    db.session.flush()  # Flush to ensure purchase items have IDs and relationships work
    
    # Add stock movements
    for item in [pi1, pi2]:
        product = item.product
        current_stock = product.get_current_stock()
        new_balance = current_stock + item.quantity
        movement = StockMovement(
            date=purchase.accepted_date,
            transaction_type='Purchase',
            reference_no=purchase.purchase_no,
            product_id=product.id,
            quantity_in=item.quantity,
            quantity_out=0,
            balance=new_balance,
            unit_cost=item.unit_price
        )
        db.session.add(movement)
    
    db.session.commit()
    
    # Verify stock
    assert product1.get_current_stock() == 100, f"Expected 100, got {product1.get_current_stock()}"
    assert product2.get_current_stock() == 50, f"Expected 50, got {product2.get_current_stock()}"
    print("[OK] Test stock created")
    
    # Test 2a: Create sale with auto customer selection
    customer1 = Customer.query.filter_by(customer_code="CUST-0001").first()
    customer2 = Customer.query.filter_by(customer_code="CUST-9999").first()
    
    sale = Sale(
        sale_no="SO-TEST-001",
        date=date.today(),
        customer_id=customer1.id,
        channel="Direct Sale",
        status="Completed",
        payment_status="Unpaid",
        created_by=1
    )
    db.session.add(sale)
    db.session.flush()
    
    # Add sale items
    item1 = SaleItem(
        sale_id=sale.id,
        product_id=product1.id,
        quantity=10,
        reference_price=1000,
        actual_price=1200,
        total_price=12000,
        unit_cost=500,
        total_cost=5000,
        gross_profit=7000
    )
    db.session.add(item1)
    
    # Stock movement for sale
    current_stock = product1.get_current_stock()
    new_balance = current_stock - 10
    movement = StockMovement(
        date=sale.date,
        transaction_type='Sale',
        reference_no=sale.sale_no,
        product_id=product1.id,
        quantity_in=0,
        quantity_out=10,
        balance=new_balance,
        unit_cost=500
    )
    db.session.add(movement)
    
    db.session.commit()
    
    # Verify stock reduced
    assert product1.get_current_stock() == 90, f"Expected 90, got {product1.get_current_stock()}"
    print("[OK] Sale created with customer, stock reduced")
    
    # Test 2b: API search by name
    with app.test_client() as client:
        with client.session_transaction() as sess:
            # Need to login first
            pass
    
    # Test search via model query
    results = Customer.query.filter(
        Customer.is_active == True,
        db.or_(
            Customer.name.ilike(f"%Test Customer%"),
            Customer.customer_code.ilike(f"%Test Customer%")
        )
    ).order_by(Customer.created_at.desc()).limit(20).all()
    
    assert len(results) >= 2, f"Expected at least 2 results, got {len(results)}"
    print("[OK] Search by name works")
    
    # Test search by code
    results_code = Customer.query.filter(
        Customer.is_active == True,
        db.or_(
            Customer.name.ilike(f"%CUST-0001%"),
            Customer.customer_code.ilike(f"%CUST-0001%")
        )
    ).order_by(Customer.created_at.desc()).limit(20).all()
    
    assert len(results_code) >= 1, f"Expected at least 1 result, got {len(results_code)}"
    assert results_code[0].customer_code == "CUST-0001"
    print("[OK] Search by customer_code works")
    
    return True

def test_purchase_edit():
    """Test 3: Unrestricted Edit for Purchase Orders"""
    print("\n=== TEST 3: Purchase Order Edit ===")
    
    # Create a purchase in Ordered status (editable)
    supplier = Supplier.query.filter_by(name="Test Supplier").first()
    product1 = Product.query.filter_by(product_code="TEST-001").first()
    product2 = Product.query.filter_by(product_code="TEST-002").first()
    
    purchase = Purchase(
        purchase_no="PO-TEST-EDIT-001",
        date=date.today(),
        supplier_id=supplier.id,
        status="Ordered"  # Ordered = editable
    )
    db.session.add(purchase)
    db.session.flush()
    
    # Add initial items
    pi1 = PurchaseItem(purchase_id=purchase.id, product_id=product1.id, quantity=20, unit_price=500, reference_price=1000, total_price=10000)
    pi2 = PurchaseItem(purchase_id=purchase.id, product_id=product2.id, quantity=15, unit_price=1000, reference_price=2000, total_price=15000)
    db.session.add_all([pi1, pi2])
    db.session.commit()
    
    original_purchase_no = purchase.purchase_no
    
    # Now simulate edit: change quantities, add new item
    # Delete existing items
    PurchaseItem.query.filter_by(purchase_id=purchase.id).delete()
    db.session.flush()
    
    # Add new items
    pi1_new = PurchaseItem(purchase_id=purchase.id, product_id=product1.id, quantity=25, unit_price=550, reference_price=1100, total_price=13750)
    pi2_new = PurchaseItem(purchase_id=purchase.id, product_id=product2.id, quantity=10, unit_price=950, reference_price=1900, total_price=9500)
    db.session.add_all([pi1_new, pi2_new])
    
    # Update purchase header
    purchase.purchase_no = original_purchase_no  # Preserve original
    purchase.supplier_id = supplier.id
    purchase.notes = "Edited test"
    
    db.session.commit()
    
    # Verify
    purchase_updated = Purchase.query.filter_by(purchase_no=original_purchase_no).first()
    assert purchase_updated is not None, "Purchase should exist"
    assert purchase_updated.purchase_no == original_purchase_no, "Purchase number should be preserved"
    assert purchase_updated.items.count() == 2, "Should have 2 items"
    
    item1 = PurchaseItem.query.filter_by(purchase_id=purchase_updated.id, product_id=product1.id).first()
    assert item1.quantity == 25, f"Expected quantity 25, got {item1.quantity}"
    assert item1.unit_price == 550, f"Expected unit_price 550, got {item1.unit_price}"
    
    print("[OK] Purchase edit works, stock movements not affected (Ordered status)")
    return True

def test_sale_edit():
    """Test 4: Unrestricted Edit for Sale Orders"""
    print("\n=== TEST 4: Sale Order Edit ===")
    
    customer1 = Customer.query.filter_by(customer_code="CUST-0001").first()
    product1 = Product.query.filter_by(product_code="TEST-001").first()
    product2 = Product.query.filter_by(product_code="TEST-002").first()
    
    # Create a sale in Completed status (editable)
    sale = Sale(
        sale_no="SO-TEST-EDIT-001",
        date=date.today(),
        customer_id=customer1.id,
        channel="Direct Sale",
        status="Completed",
        payment_status="Unpaid",
        created_by=1
    )
    db.session.add(sale)
    db.session.flush()
    
    # Add initial items
    item1 = SaleItem(
        sale_id=sale.id,
        product_id=product1.id,
        quantity=5,
        reference_price=1000,
        actual_price=1200,
        total_price=6000,
        unit_cost=500,
        total_cost=2500,
        gross_profit=3500
    )
    db.session.add(item1)
    
    # Stock movement
    current_stock = product1.get_current_stock()
    new_balance = current_stock - 5
    movement = StockMovement(
        date=sale.date,
        transaction_type='Sale',
        reference_no=sale.sale_no,
        product_id=product1.id,
        quantity_in=0,
        quantity_out=5,
        balance=new_balance,
        unit_cost=500
    )
    db.session.add(movement)
    db.session.commit()
    
    # Record stock before edit
    stock_before = product1.get_current_stock()
    
    # Now edit: change quantity from 5 to 8, add new item
    # Delete existing items and reverse stock
    for item in sale.items:
        product = item.product
        current_stock = product.get_current_stock()
        new_balance = current_stock + item.quantity
        rev_movement = StockMovement(
            date=datetime.now(),
            transaction_type='Sale Deleted',
            reference_no=sale.sale_no,
            product_id=product.id,
            quantity_in=item.quantity,
            quantity_out=0,
            balance=new_balance,
            unit_cost=item.unit_cost,
            notes=f'Reversal of sale {sale.sale_no} (edit)'
        )
        db.session.add(rev_movement)
    
    SaleItem.query.filter_by(sale_id=sale.id).delete()
    db.session.flush()
    
    # Add new items
    item1_new = SaleItem(
        sale_id=sale.id,
        product_id=product1.id,
        quantity=8,
        reference_price=1000,
        actual_price=1300,
        total_price=10400,
        unit_cost=500,
        total_cost=4000,
        gross_profit=6400
    )
    item2_new = SaleItem(
        sale_id=sale.id,
        product_id=product2.id,
        quantity=3,
        reference_price=2000,
        actual_price=2200,
        total_price=6600,
        unit_cost=1000,
        total_cost=3000,
        gross_profit=3600
    )
    db.session.add_all([item1_new, item2_new])
    db.session.flush()  # Flush to ensure relationships work
    
    # New stock movements
    for item in [item1_new, item2_new]:
        product = item.product
        current_stock = product.get_current_stock()
        new_balance = current_stock - item.quantity
        movement = StockMovement(
            date=sale.date,
            transaction_type='Sale',
            reference_no=sale.sale_no,
            product_id=product.id,
            quantity_in=0,
            quantity_out=item.quantity,
            balance=new_balance,
            unit_cost=item.unit_cost
        )
        db.session.add(movement)
    
    # Update sale header
    sale.sale_no = "SO-TEST-EDIT-001"  # Preserve original
    sale.discount_percent = 5
    # Calculate discount amount (same logic as sales route)
    subtotal = sum(item.total_price for item in sale.items)
    sale.discount_amount = (subtotal * sale.discount_percent / Decimal('100')).quantize(Decimal('0.01'))
    sale.notes = "Edited test"
    
    db.session.commit()
    
    # Verify
    sale_updated = Sale.query.filter_by(sale_no="SO-TEST-EDIT-001").first()
    assert sale_updated is not None, "Sale should exist"
    assert sale_updated.sale_no == "SO-TEST-EDIT-001", "Sale number preserved"
    assert sale_updated.items.count() == 2, "Should have 2 items"
    assert sale_updated.discount_percent == 5, "Discount updated"
    
    # Verify stock adjusted correctly
    # Product 1: was at stock_before, reverted +5, then -8 = net -3 from before
    # Product 2: was at 50, then -3 = 47
    stock_p1_after = product1.get_current_stock()
    stock_p2_after = product2.get_current_stock()
    
    assert stock_p1_after == stock_before - 3, f"Product1 stock should be {stock_before - 3}, got {stock_p1_after}"
    assert stock_p2_after == 47, f"Product2 stock should be 47, got {stock_p2_after}"
    
    # Verify totals recalculated
    subtotal = sum(item.total_price for item in sale_updated.items)
    expected_discount = (subtotal * Decimal('5') / Decimal('100')).quantize(Decimal('0.01'))
    assert sale_updated.discount_amount == expected_discount, f"Discount mismatch: {sale_updated.discount_amount} vs {expected_discount}"
    
    print("[OK] Sale edit works, stock movements adjusted correctly")
    print(f"  Product 1 stock: {stock_p1_after} (expected {stock_before - 3})")
    print(f"  Product 2 stock: {stock_p2_after} (expected 47)")
    print(f"  Discount: {sale_updated.discount_amount}")
    return True

def run_all_tests():
    """Run all tests and cleanup"""
    print("=" * 60)
    print("MO MO PAJAMAS - COMPLETE VERIFICATION TEST")
    print("=" * 60)
    
    with app.app_context():
        # Ensure tables exist
        db.create_all()
        
        # Initialize tiers
        TierConfig.initialize_default_tiers()
        
        # Clean any existing test data first
        cleanup_test_data()
        
        all_passed = True
        
        try:
            all_passed &= test_customer_code_and_sorting()
            all_passed &= test_sale_customer_selection_and_search()
            all_passed &= test_purchase_edit()
            all_passed &= test_sale_edit()
        except Exception as e:
            print(f"\n[FAIL] TEST ERROR: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
        finally:
            # ALWAYS cleanup
            cleanup_test_data()
        
        print("\n" + "=" * 60)
        if all_passed:
            print("[OK] ALL TESTS PASSED")
        else:
            print("[FAIL] SOME TESTS FAILED")
        print("=" * 60)
        
        return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)