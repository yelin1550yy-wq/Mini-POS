from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models import db, Sale, SaleItem, Purchase, PurchaseItem, Product, Expense, Customer, Supplier, StockMovement, User
from sqlalchemy import func, and_, inspect
from datetime import date, datetime, timedelta
from decimal import Decimal
import io
import csv
import json
import os

bp = Blueprint('reports', __name__)

REPORT_TYPES = [
    ('sales', 'Sales Report'),
    ('purchases', 'Purchase Report'),
    ('stock', 'Current Stock Report'),
    ('stock_movement', 'Stock Movement Report'),
    ('product_sales', 'Product Sales Report'),
    ('top_selling', 'Top Selling Products'),
    ('gross_profit', 'Gross Profit Report'),
    ('net_profit', 'Net Profit Report'),
    ('adv_expense', 'Advertisement Expense Report'),
    ('other_expense', 'Other Expense Report'),
]

def get_date_range(period, date_from=None, date_to=None):
    if date_from and date_to:
        return datetime.strptime(date_from, '%Y-%m-%d').date(), datetime.strptime(date_to, '%Y-%m-%d').date()
    
    today = date.today()
    if period == 'today':
        return today, today
    elif period == 'week':
        start = today - timedelta(days=today.weekday())
        return start, today
    elif period == 'month':
        start = today.replace(day=1)
        return start, today
    elif period == 'year':
        start = today.replace(month=1, day=1)
        return start, today
    return today, today

@bp.route('/')
@login_required
def index():
    return render_template('reports/index.html', report_types=REPORT_TYPES)

@bp.route('/<report_type>')
@login_required
def view(report_type):
    period = request.args.get('period', 'month')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    product_filter = request.args.get('product', '', type=int)
    customer_filter = request.args.get('customer', '', type=int)
    supplier_filter = request.args.get('supplier', '', type=int)
    
    start_date, end_date = get_date_range(period, date_from, date_to)
    
    products = Product.query.filter_by(is_active=True).order_by(Product.product_code).all()
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    
    if report_type == 'sales':
        return sales_report(start_date, end_date, customer_filter, products, customers, suppliers, period, date_from, date_to)
    elif report_type == 'purchases':
        return purchases_report(start_date, end_date, supplier_filter, products, customers, suppliers, period, date_from, date_to)
    elif report_type == 'stock':
        return stock_report(products, customers, suppliers, period, date_from, date_to)
    elif report_type == 'stock_movement':
        return stock_movement_report(start_date, end_date, product_filter, products, customers, suppliers, period, date_from, date_to)
    elif report_type == 'product_sales':
        return product_sales_report(start_date, end_date, product_filter, products, customers, suppliers, period, date_from, date_to)
    elif report_type == 'top_selling':
        return top_selling_report(start_date, end_date, products, customers, suppliers, period, date_from, date_to)
    elif report_type == 'gross_profit':
        return gross_profit_report(start_date, end_date, products, customers, suppliers, period, date_from, date_to)
    elif report_type == 'net_profit':
        return net_profit_report(start_date, end_date, products, customers, suppliers, period, date_from, date_to)
    elif report_type == 'adv_expense':
        return adv_expense_report(start_date, end_date, products, customers, suppliers, period, date_from, date_to)
    elif report_type == 'other_expense':
        return other_expense_report(start_date, end_date, products, customers, suppliers, period, date_from, date_to)
    
    return redirect(url_for('reports.index'))

def sales_report(start_date, end_date, customer_filter, products, customers, suppliers, period, date_from, date_to):
    query = Sale.query.filter(Sale.date >= start_date, Sale.date <= end_date)
    if customer_filter:
        query = query.filter(Sale.customer_id == customer_filter)
    sales = query.order_by(Sale.date, Sale.id).all()
    
    rows = []
    total_qty = 0
    total_sales = 0
    total_cost = 0
    total_profit = 0
    
    for sale in sales:
        for item in sale.items:
            rows.append({
                'date': sale.date,
                'sale_no': sale.sale_no,
                'customer': sale.customer.name if sale.customer else 'Walk-in',
                'product_code': item.product.product_code,
                'item_name': item.product.item_name,
                'qty': item.quantity,
                'ref_price': item.reference_price,
                'actual_price': item.actual_price,
                'total': item.total_price,
                'cost': item.total_cost,
                'profit': item.gross_profit
            })
            total_qty += item.quantity
            total_sales += item.total_price
            total_cost += item.total_cost
            total_profit += item.gross_profit
    
    return render_template('reports/sales.html',
                           rows=rows,
                           total_qty=total_qty,
                           total_sales=total_sales,
                           total_cost=total_cost,
                           total_profit=total_profit,
                           period=period, date_from=date_from, date_to=date_to,
                           products=products, customers=customers, suppliers=suppliers,
                           customer_filter=customer_filter,
                           report_title='Sales Report')

def purchases_report(start_date, end_date, supplier_filter, products, customers, suppliers, period, date_from, date_to):
    query = Purchase.query.filter(Purchase.date >= start_date, Purchase.date <= end_date)
    if supplier_filter:
        query = query.filter(Purchase.supplier_id == supplier_filter)
    purchases = query.order_by(Purchase.date, Purchase.id).all()
    
    rows = []
    total_qty = 0
    total_amount = 0
    
    for pur in purchases:
        for item in pur.items:
            rows.append({
                'date': pur.date,
                'purchase_no': pur.purchase_no,
                'supplier': pur.supplier.name,
                'product_code': item.product.product_code,
                'item_name': item.product.item_name,
                'qty': item.quantity,
                'unit_price': item.unit_price,
                'total': item.total_price
            })
            total_qty += item.quantity
            total_amount += item.total_price
    
    return render_template('reports/purchases.html',
                           rows=rows,
                           total_qty=total_qty,
                           total_amount=total_amount,
                           period=period, date_from=date_from, date_to=date_to,
                           products=products, customers=customers, suppliers=suppliers,
                           supplier_filter=supplier_filter,
                           report_title='Purchase Report')

def stock_report(products, customers, suppliers, period, date_from, date_to):
    product_data = []
    total_value = 0
    
    for p in products:
        current_stock = p.get_current_stock()
        avg_cost = p.get_weighted_average_cost()
        stock_value = current_stock * avg_cost
        status = p.get_stock_status()
        
        product_data.append({
            'product': p,
            'current_stock': current_stock,
            'avg_cost': avg_cost,
            'stock_value': stock_value,
            'status': status
        })
        total_value += stock_value
    
    return render_template('reports/stock.html',
                           product_data=product_data,
                           total_value=total_value,
                           period=period, date_from=date_from, date_to=date_to,
                           products=products, customers=customers, suppliers=suppliers,
                           report_title='Current Stock Report')

def stock_movement_report(start_date, end_date, product_filter, products, customers, suppliers, period, date_from, date_to):
    query = StockMovement.query.join(Product).filter(
        StockMovement.date >= start_date, StockMovement.date <= end_date
    )
    if product_filter:
        query = query.filter(StockMovement.product_id == product_filter)
    movements = query.order_by(StockMovement.date, StockMovement.id).all()
    
    return render_template('reports/stock_movement.html',
                           movements=movements,
                           period=period, date_from=date_from, date_to=date_to,
                           products=products, customers=customers, suppliers=suppliers,
                           product_filter=product_filter,
                           report_title='Stock Movement Report')

def product_sales_report(start_date, end_date, product_filter, products, customers, suppliers, period, date_from, date_to):
    query = db.session.query(
        Product.product_code,
        Product.item_name,
        Product.product_type,
        func.sum(SaleItem.quantity).label('total_qty'),
        func.sum(SaleItem.total_price).label('total_revenue'),
        func.sum(SaleItem.total_cost).label('total_cost'),
        func.sum(SaleItem.gross_profit).label('total_profit')
    ).join(SaleItem).join(Sale).filter(
        Sale.date >= start_date, Sale.date <= end_date
    )
    if product_filter:
        query = query.filter(Product.id == product_filter)
    results = query.group_by(Product.id).order_by(func.sum(SaleItem.quantity).desc()).all()
    
    return render_template('reports/product_sales.html',
                           results=results,
                           period=period, date_from=date_from, date_to=date_to,
                           products=products, customers=customers, suppliers=suppliers,
                           product_filter=product_filter,
                           report_title='Product Sales Report')

def top_selling_report(start_date, end_date, products, customers, suppliers, period, date_from, date_to):
    # By quantity
    by_qty = db.session.query(
        Product.product_code,
        Product.item_name,
        func.sum(SaleItem.quantity).label('total_qty'),
        func.sum(SaleItem.total_price).label('total_revenue')
    ).join(SaleItem).join(Sale).filter(
        Sale.date >= start_date, Sale.date <= end_date
    ).group_by(Product.id).order_by(func.sum(SaleItem.quantity).desc()).limit(20).all()
    
    # By revenue
    by_rev = db.session.query(
        Product.product_code,
        Product.item_name,
        func.sum(SaleItem.quantity).label('total_qty'),
        func.sum(SaleItem.total_price).label('total_revenue')
    ).join(SaleItem).join(Sale).filter(
        Sale.date >= start_date, Sale.date <= end_date
    ).group_by(Product.id).order_by(func.sum(SaleItem.total_price).desc()).limit(20).all()
    
    return render_template('reports/top_selling.html',
                           by_qty=by_qty,
                           by_rev=by_rev,
                           period=period, date_from=date_from, date_to=date_to,
                           products=products, customers=customers, suppliers=suppliers,
                           report_title='Top Selling Products')

def gross_profit_report(start_date, end_date, products, customers, suppliers, period, date_from, date_to):
    sales = Sale.query.filter(Sale.date >= start_date, Sale.date <= end_date).all()
    
    daily = {}
    for sale in sales:
        day_key = sale.date.strftime('%Y-%m-%d')
        if day_key not in daily:
            daily[day_key] = {'sales': 0, 'cost': 0, 'profit': 0}
        for item in sale.items:
            daily[day_key]['sales'] += item.total_price
            daily[day_key]['cost'] += item.total_cost
            daily[day_key]['profit'] += item.gross_profit
    
    sorted_days = sorted(daily.items())
    
    total_sales = sum(v['sales'] for v in daily.values())
    total_cost = sum(v['cost'] for v in daily.values())
    total_profit = sum(v['profit'] for v in daily.values())
    
    return render_template('reports/gross_profit.html',
                           daily=sorted_days,
                           total_sales=total_sales,
                           total_cost=total_cost,
                           total_profit=total_profit,
                           period=period, date_from=date_from, date_to=date_to,
                           products=products, customers=customers, suppliers=suppliers,
                           report_title='Gross Profit Report')

def net_profit_report(start_date, end_date, products, customers, suppliers, period, date_from, date_to):
    # Sales
    sales = Sale.query.filter(Sale.date >= start_date, Sale.date <= end_date).all()
    total_sales = sum(sum(item.total_price for item in s.items) for s in sales)
    total_cogs = sum(sum(item.total_cost for item in s.items) for s in sales)
    gross_profit = total_sales - total_cogs
    
    # Expenses
    adv_expenses = Expense.query.filter(
        Expense.date >= start_date, Expense.date <= end_date,
        Expense.category == 'advertisement'
    ).all()
    other_expenses = Expense.query.filter(
        Expense.date >= start_date, Expense.date <= end_date,
        Expense.category == 'other'
    ).all()
    
    adv_by_cat = {}
    for e in adv_expenses:
        adv_by_cat[e.sub_category] = adv_by_cat.get(e.sub_category, 0) + e.amount
    
    other_by_cat = {}
    for e in other_expenses:
        other_by_cat[e.sub_category] = other_by_cat.get(e.sub_category, 0) + e.amount
    
    total_adv = sum(adv_by_cat.values())
    total_other = sum(other_by_cat.values())
    total_expenses = total_adv + total_other
    net_profit = gross_profit - total_expenses
    
    return render_template('reports/net_profit.html',
                           total_sales=total_sales,
                           total_cogs=total_cogs,
                           gross_profit=gross_profit,
                           adv_by_cat=adv_by_cat,
                           other_by_cat=other_by_cat,
                           total_adv=total_adv,
                           total_other=total_other,
                           total_expenses=total_expenses,
                           net_profit=net_profit,
                           period=period, date_from=date_from, date_to=date_to,
                           products=products, customers=customers, suppliers=suppliers,
                           report_title='Net Profit Report')

def adv_expense_report(start_date, end_date, products, customers, suppliers, period, date_from, date_to):
    expenses = Expense.query.filter(
        Expense.date >= start_date, Expense.date <= end_date,
        Expense.category == 'advertisement'
    ).order_by(Expense.date, Expense.id).all()
    
    by_sub = {}
    for e in expenses:
        by_sub[e.sub_category] = by_sub.get(e.sub_category, 0) + e.amount
    
    total = sum(e.amount for e in expenses)
    
    return render_template('reports/expense_detail.html',
                           expenses=expenses,
                           by_sub=by_sub,
                           total=total,
                           category='Advertisement',
                           period=period, date_from=date_from, date_to=date_to,
                           products=products, customers=customers, suppliers=suppliers,
                           report_title='Advertisement Expense Report')

def other_expense_report(start_date, end_date, products, customers, suppliers, period, date_from, date_to):
    expenses = Expense.query.filter(
        Expense.date >= start_date, Expense.date <= end_date,
        Expense.category == 'other'
    ).order_by(Expense.date, Expense.id).all()
    
    by_sub = {}
    for e in expenses:
        by_sub[e.sub_category] = by_sub.get(e.sub_category, 0) + e.amount
    
    total = sum(e.amount for e in expenses)
    
    return render_template('reports/expense_detail.html',
                           expenses=expenses,
                           by_sub=by_sub,
                           total=total,
                           category='Other Cost',
                           period=period, date_from=date_from, date_to=date_to,
                           products=products, customers=customers, suppliers=suppliers,
                           report_title='Other Expense Report')


@bp.route('/backup')
@login_required
def backup():
    if not current_user.is_admin():
        flash('Only administrators can backup data.', 'danger')
        return redirect(url_for('reports.index'))
    
    # Get all table data
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    backup_data = {}
    for table in tables:
        if table == 'alembic_version':
            continue
        columns = [c['name'] for c in inspector.get_columns(table)]
        rows = db.session.execute(db.text(f'SELECT * FROM {table}')).fetchall()
        backup_data[table] = {
            'columns': columns,
            'data': [dict(zip(columns, row)) for row in rows]
        }
    
    # Convert to JSON
    json_str = json.dumps(backup_data, default=str, indent=2)
    
    # Create response
    filename = f'minipos_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    return send_file(
        io.BytesIO(json_str.encode('utf-8')),
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )


@bp.route('/restore', methods=['GET', 'POST'])
@login_required
def restore():
    if not current_user.is_admin():
        flash('Only administrators can restore data.', 'danger')
        return redirect(url_for('reports.index'))
    
    if request.method == 'POST':
        if 'backup_file' not in request.files:
            flash('No file selected.', 'danger')
            return redirect(url_for('reports.restore'))
        
        file = request.files['backup_file']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(url_for('reports.restore'))
        
        if not file.filename.endswith('.json'):
            flash('Only JSON backup files are supported.', 'danger')
            return redirect(url_for('reports.restore'))
        
        try:
            content = file.read().decode('utf-8')
            backup_data = json.loads(content)
            
            # Get table order (respect foreign keys)
            table_order = [
                'users', 'products', 'suppliers', 'customers',
                'purchases', 'purchase_items', 'sales', 'sale_items',
                'stock_movements', 'expenses'
            ]
            
            # Clear existing data (in reverse order)
            for table in reversed(table_order):
                if table in backup_data:
                    db.session.execute(db.text(f'DELETE FROM {table}'))
            
            db.session.commit()
            
            # Restore data
            for table in table_order:
                if table not in backup_data:
                    continue
                
                columns = backup_data[table]['columns']
                rows = backup_data[table]['data']
                
                if not rows:
                    continue
                
                placeholders = ', '.join([':' + c for c in columns])
                cols_str = ', '.join(columns)
                
                for row in rows:
                    # Convert datetime strings back to datetime objects
                    for key, value in row.items():
                        if isinstance(value, str):
                            try:
                                if 'T' in value and len(value) > 10:
                                    row[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                                elif len(value) == 10 and value.count('-') == 2:
                                    row[key] = datetime.strptime(value, '%Y-%m-%d').date()
                            except:
                                pass
                    
                    sql = f'INSERT INTO {table} ({cols_str}) VALUES ({placeholders})'
                    db.session.execute(db.text(sql), row)
            
            db.session.commit()
            flash('Backup restored successfully!', 'success')
            return redirect(url_for('reports.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error restoring backup: {str(e)}', 'danger')
    
    return render_template('reports/restore.html')