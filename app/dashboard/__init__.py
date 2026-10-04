from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import db, Sale, SaleItem, Purchase, PurchaseItem, Product, Expense, Customer, StockMovement, Capital, TierConfig
from sqlalchemy import func, and_
from datetime import date, datetime, timedelta
from decimal import Decimal

bp = Blueprint('dashboard', __name__)

def get_date_range(period):
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
    period = request.args.get('period', 'today')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    if date_from and date_to:
        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    else:
        start_date, end_date = get_date_range(period)
    
    # Sales in period
    sales_query = Sale.query.filter(Sale.date >= start_date, Sale.date <= end_date)
    sales = sales_query.all()
    
    total_sales = sum(sum(item.total_price for item in s.items) for s in sales)
    total_cogs = sum(sum(item.total_cost for item in s.items) for s in sales)
    gross_profit = total_sales - total_cogs
    
    # Return calculations
    returned_sales = [s for s in sales if s.status == 'Returned']
    total_returns_qty = sum(sum(item.quantity for item in s.items) for s in returned_sales)
    total_returns_amount = sum(sum(item.total_price for item in s.items) for s in returned_sales)
    completed_sales = [s for s in sales if s.status == 'Completed']
    total_items_sold = sum(sum(item.quantity for item in s.items) for s in completed_sales)
    return_ratio = (total_returns_qty / (total_items_sold + total_returns_qty) * 100) if (total_items_sold + total_returns_qty) > 0 else 0
    
    # Sales Summary (all time)
    all_completed_sales = Sale.query.filter(Sale.status == 'Completed').all()
    all_total_sales = sum(sum(item.total_price for item in s.items) for s in all_completed_sales)
    all_outstanding = sum(s.outstanding_amount for s in all_completed_sales)
    all_paid = sum(s.total_amount - s.outstanding_amount for s in all_completed_sales)
    
    # Purchases in period
    purchases_query = Purchase.query.filter(Purchase.date >= start_date, Purchase.date <= end_date)
    purchases = purchases_query.all()
    total_purchases = sum(sum(item.total_price for item in p.items) for p in purchases)
    
    # Expenses in period
    adv_expenses = Expense.query.filter(
        Expense.date >= start_date, Expense.date <= end_date,
        Expense.category == 'advertisement'
    ).all()
    other_expenses = Expense.query.filter(
        Expense.date >= start_date, Expense.date <= end_date,
        Expense.category == 'other'
    ).all()
    
    total_adv_expense = sum(e.amount for e in adv_expenses)
    total_other_expense = sum(e.amount for e in other_expenses)
    total_expenses = total_adv_expense + total_other_expense
    
    net_profit = gross_profit - total_expenses
    
    # Current stock
    products = Product.query.filter_by(is_active=True).all()
    total_stock_value = sum(p.get_current_stock() * p.get_weighted_average_cost() for p in products)
    low_stock_items = [p for p in products if p.get_stock_status() == 'Low Stock']
    out_of_stock_items = [p for p in products if p.get_stock_status() == 'Out of Stock']
    
    # Capital
    total_capital = Capital.get_total_capital()
    total_injections = Capital.get_total_injections()
    total_withdrawals = Capital.get_total_withdrawals()
    
    # Current Business Value calculation
    # Purchase Item Value = Total value of items acquired through supplier purchases
    purchase_item_value = db.session.query(db.func.coalesce(db.func.sum(PurchaseItem.total_price), 0)).scalar() or 0
    
    # In-Hand Cash = (Total Capital Injections + Total Sales Revenue) - (Total Expenses + Total Capital Withdrawals)
    # Total Sales Revenue (all time, completed sales)
    total_sales_revenue = db.session.query(db.func.coalesce(db.func.sum(SaleItem.total_price), 0)).join(Sale).filter(
        Sale.status == 'Completed'
    ).scalar() or 0
    
    # Total Expenses (all time)
    total_expenses_all = db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0)).scalar() or 0
    
    in_hand_cash = (total_injections + total_sales_revenue) - (total_expenses_all + total_withdrawals)
    
    # Current Business Value = Purchase Item Value + In-Hand Cash
    current_business_value = purchase_item_value + in_hand_cash
    
    # Top selling products (by quantity)
    top_sales = db.session.query(
        Product.product_code,
        Product.item_name,
        func.sum(SaleItem.quantity).label('total_qty'),
        func.sum(SaleItem.total_price).label('total_revenue')
    ).join(SaleItem).join(Sale).filter(
        Sale.date >= start_date, Sale.date <= end_date
    ).group_by(Product.id).order_by(func.sum(SaleItem.quantity).desc()).limit(10).all()
    
    return render_template('dashboard/index.html',
                           period=period,
                           date_from=date_from,
                           date_to=date_to,
                           start_date=start_date,
                           end_date=end_date,
                           total_sales=total_sales,
                           total_items_sold=total_items_sold,
                           total_purchases=total_purchases,
                           total_cogs=total_cogs,
                           gross_profit=gross_profit,
                           total_adv_expense=total_adv_expense,
                           total_other_expense=total_other_expense,
                           total_expenses=total_expenses,
                           net_profit=net_profit,
                           total_stock_value=total_stock_value,
                           low_stock_count=len(low_stock_items),
                           out_of_stock_count=len(out_of_stock_items),
                           low_stock_items=low_stock_items[:5],
                           top_sales=top_sales,
                           total_returns_qty=total_returns_qty,
                           total_returns_amount=total_returns_amount,
                           return_ratio=round(return_ratio, 2),
                           total_capital=total_capital,
                           total_injections=total_injections,
                           total_withdrawals=total_withdrawals,
                           current_business_value=current_business_value,
                           purchase_item_value=purchase_item_value,
                           in_hand_cash=in_hand_cash,
                           all_total_sales=all_total_sales,
                           all_outstanding=all_outstanding,
                           all_paid=all_paid)

@bp.route('/api/stats')
@login_required
def api_stats():
    period = request.args.get('period', 'today')
    start_date, end_date = get_date_range(period)
    
    sales = Sale.query.filter(Sale.date >= start_date, Sale.date <= end_date).all()
    total_sales = sum(sum(item.total_price for item in s.items) for s in sales)
    total_cogs = sum(sum(item.total_cost for item in s.items) for s in sales)
    
    purchases = Purchase.query.filter(Purchase.date >= start_date, Purchase.date <= end_date).all()
    total_purchases = sum(sum(item.total_price for item in p.items) for p in purchases)
    
    return jsonify({
        'total_sales': float(total_sales),
        'total_purchases': float(total_purchases),
        'gross_profit': float(total_sales - total_cogs)
    })

@bp.route('/capital')
@login_required
def capital():
    page = request.args.get('page', 1, type=int)
    capitals = Capital.query.order_by(Capital.date.desc(), Capital.id.desc()).paginate(page=page, per_page=20, error_out=False)
    
    total_injections = Capital.get_total_injections()
    total_withdrawals = Capital.get_total_withdrawals()
    total_capital = Capital.get_total_capital()
    
    return render_template('dashboard/capital.html',
                           capitals=capitals,
                           total_injections=total_injections,
                           total_withdrawals=total_withdrawals,
                           total_capital=total_capital)

@bp.route('/capital/add', methods=['GET', 'POST'])
@login_required
def capital_add():
    if request.method == 'POST':
        try:
            amount = Decimal(request.form.get('amount', '0'))
            if amount <= 0:
                flash('Amount must be greater than zero.', 'danger')
                return redirect(url_for('dashboard.capital_add'))
            
            capital_type = request.form.get('type', 'injection')
            if capital_type not in ['injection', 'withdrawal']:
                capital_type = 'injection'
            
            capital = Capital(
                date=request.form.get('date') or date.today(),
                amount=amount,
                description=request.form.get('description', '').strip() or None,
                type=capital_type,
                created_by=current_user.id
            )
            db.session.add(capital)
            db.session.commit()
            
            flash(f'Capital {capital_type} of {amount:,.2f} Ks recorded successfully.', 'success')
            return redirect(url_for('dashboard.capital'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('dashboard/capital_form.html', title='Add Capital', today=date.today())

@bp.route('/capital/<int:id>/delete', methods=['POST'])
@login_required
def capital_delete(id):
    if not current_user.is_admin():
        flash('Only administrators can delete capital entries.', 'danger')
        return redirect(url_for('dashboard.capital'))
    
    capital = Capital.query.get_or_404(id)
    try:
        db.session.delete(capital)
        db.session.commit()
        flash('Capital entry deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard.capital'))


# Tier Management Routes
@bp.route('/tiers')
@login_required
def tiers():
    if not current_user.is_admin():
        flash('Only administrators can manage tiers.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    TierConfig.initialize_default_tiers()
    tiers = TierConfig.query.order_by(TierConfig.min_spend).all()
    return render_template('dashboard/tiers.html', tiers=tiers)


@bp.route('/tiers/add', methods=['GET', 'POST'])
@login_required
def tier_add():
    if not current_user.is_admin():
        flash('Only administrators can manage tiers.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        try:
            tier = TierConfig(
                tier_name=request.form.get('tier_name', '').strip(),
                min_spend=Decimal(request.form.get('min_spend', '0')),
                discount_percent=Decimal(request.form.get('discount_percent', '0')),
                description=request.form.get('description', '').strip() or None,
                is_active=bool(request.form.get('is_active'))
            )
            db.session.add(tier)
            db.session.commit()
            flash('Tier added successfully.', 'success')
            return redirect(url_for('dashboard.tiers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('dashboard/tier_form.html', title='Add Tier', tier=None)


@bp.route('/tiers/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def tier_edit(id):
    if not current_user.is_admin():
        flash('Only administrators can manage tiers.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    tier = TierConfig.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            tier.tier_name = request.form.get('tier_name', '').strip()
            tier.min_spend = Decimal(request.form.get('min_spend', '0'))
            tier.discount_percent = Decimal(request.form.get('discount_percent', '0'))
            tier.description = request.form.get('description', '').strip() or None
            tier.is_active = bool(request.form.get('is_active'))
            tier.updated_at = datetime.utcnow()
            db.session.commit()
            flash('Tier updated successfully.', 'success')
            return redirect(url_for('dashboard.tiers'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('dashboard/tier_form.html', title='Edit Tier', tier=tier)


@bp.route('/tiers/<int:id>/delete', methods=['POST'])
@login_required
def tier_delete(id):
    if not current_user.is_admin():
        flash('Only administrators can manage tiers.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    tier = TierConfig.query.get_or_404(id)
    try:
        db.session.delete(tier)
        db.session.commit()
        flash('Tier deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard.tiers'))


# API endpoint to get customer tier info
@bp.route('/api/customer/<int:customer_id>/tier')
@login_required
def api_customer_tier(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    tier_config = customer.get_tier_config()
    
    return jsonify({
        'customer_id': customer.id,
        'customer_name': customer.name,
        'customer_phone': customer.phone,
        'tier': customer.tier,
        'discount_percent': float(tier_config.discount_percent) if tier_config else 0,
        'total_spend': float(customer.get_total_spend()),
        'total_buy_items': customer.get_total_buy_items()
    })