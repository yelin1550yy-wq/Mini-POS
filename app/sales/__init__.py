from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import db, Sale, SaleItem, Product, Customer, StockMovement, SalePayment
from app.sales.forms import SaleForm
from sqlalchemy import or_, func
from datetime import date, datetime
from decimal import Decimal

bp = Blueprint('sales', __name__)

@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST' and ('amount_received' in request.form or 'sale_id' in request.form):
        return receive_payment()
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    customer_filter = request.args.get('customer', '', type=int)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = Sale.query.outerjoin(Customer)
    
    if search:
        query = query.filter(or_(
            Sale.sale_no.ilike(f'%{search}%'),
            Customer.name.ilike(f'%{search}%')
        ))
    if customer_filter:
        query = query.filter(Sale.customer_id == customer_filter)
    if date_from:
        query = query.filter(Sale.date >= date_from)
    if date_to:
        query = query.filter(Sale.date <= date_to)
    
    sales = query.order_by(Sale.date.desc(), Sale.id.desc()).paginate(page=page, per_page=20, error_out=False)
    # Sort customers by newest first (latest registered)
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.created_at.desc()).all()
    
    return render_template('sales/index.html', 
                           sales=sales, 
                           customers=customers,
                           search=search,
                           customer_filter=customer_filter,
                           date_from=date_from,
                           date_to=date_to)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form = SaleForm()
    # Sort customers by newest first
    form.customer_id.choices = [(0, 'Walk-in Customer')] + [(c.id, f"[{c.customer_code}] {c.name}") for c in Customer.query.filter_by(is_active=True).order_by(Customer.created_at.desc()).all()]
    
    # Generate next sale number
    last_sale = Sale.query.order_by(Sale.id.desc()).first()
    next_no = f"SO-{date.today().strftime('%Y%m%d')}-{(last_sale.id + 1) if last_sale else 1:04d}"
    
    if request.method == 'GET':
        form.sale_no.data = next_no
        form.date.data = date.today()
    
    if form.validate_on_submit():
        customer_id = form.customer_id.data if form.customer_id.data != 0 else None
        
        # Check if customer is blacklisted
        if customer_id:
            customer = Customer.query.get(customer_id)
            if customer and customer.is_blacklisted:
                phone_info = f" (Phone: {customer.phone})" if customer.phone else ""
                flash(f'Error: Customer {customer.name}{phone_info} is blacklisted and cannot make a purchase!', 'danger')
                return redirect(url_for('sales.create'))
        
        # Get discount and channel from form
        discount_percent = Decimal('0')  # No longer used — discount is now amount-based
        discount_amount_direct = Decimal(request.form.get('discount_amount', '0') or '0')
        channel = request.form.get('channel', 'Direct Sale')
        
        sale = Sale(
            sale_no=form.sale_no.data.strip(),
            date=form.date.data,
            customer_id=customer_id,
            channel=channel,
            status='Completed',  # Default to Completed
            payment_status='Unpaid',  # Default to Unpaid
            notes=form.notes.data.strip() if form.notes.data else None,
            discount_percent=discount_percent,
            discount_amount=0,  # Will be calculated after items are processed
            outstanding_amount=0,  # Will be calculated
            created_by=current_user.id
        )
        
        try:
            db.session.add(sale)
            db.session.flush()
            
            # Process items from form
            product_ids = request.form.getlist('product_id[]')
            quantities = request.form.getlist('quantity[]')
            reference_prices = request.form.getlist('reference_price[]')
            actual_prices = request.form.getlist('actual_price[]')
            
            subtotal = Decimal('0')
            
            for pid, qty, ref_price, act_price in zip(product_ids, quantities, reference_prices, actual_prices):
                if pid and qty and act_price:
                    product = Product.query.get(int(pid))
                    if not product:
                        continue
                    
                    qty = int(qty)
                    ref_price = Decimal(str(ref_price))
                    act_price = Decimal(str(act_price))
                    total_price = qty * act_price
                    
                    # Get weighted average cost at this moment
                    avg_cost = product.get_weighted_average_cost()
                    total_cost = qty * avg_cost
                    gross_profit = total_price - total_cost
                    
                    # Check stock availability
                    current_stock = product.get_current_stock()
                    if current_stock < qty:
                        raise Exception(f'Insufficient stock for {product.product_code}. Available: {current_stock}, Requested: {qty}')
                    
                    item = SaleItem(
                        sale_id=sale.id,
                        product_id=int(pid),
                        quantity=qty,
                        reference_price=ref_price,
                        actual_price=act_price,
                        total_price=total_price,
                        unit_cost=avg_cost,
                        total_cost=total_cost,
                        gross_profit=gross_profit
                    )
                    db.session.add(item)
                    
                    # Create stock movement
                    new_balance = current_stock - qty
                    movement = StockMovement(
                        date=sale.date,
                        transaction_type='Sale',
                        reference_no=sale.sale_no,
                        product_id=product.id,
                        quantity_in=0,
                        quantity_out=qty,
                        balance=new_balance,
                        unit_cost=avg_cost
                    )
                    db.session.add(movement)
                    
                    subtotal += total_price
            
            # Discount is now a direct amount entered by user
            sale.discount_amount = min(discount_amount_direct, subtotal).quantize(Decimal('0.01'))
            sale.discount_percent = Decimal('0')  # No longer used
            
            # Set outstanding amount and initial paid amount
            sale.paid_amount = Decimal('0')
            sale.outstanding_amount = sale.total_amount
            sale.update_payment_status()
            
            db.session.commit()
            flash('Sale saved successfully. Stock updated.', 'success')
            return redirect(url_for('sales.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving sale: {str(e)}', 'danger')
    
    products = Product.query.filter_by(is_active=True).order_by(Product.product_code).all()
    products_data = [{
        'id': p.id,
        'product_code': p.product_code,
        'item_name': p.item_name,
        'reference_price': float(p.reference_selling_price),
        'current_stock': p.get_current_stock(),
        'avg_cost': float(p.get_weighted_average_cost())
    } for p in products]
    return render_template('sales/form.html', form=form, title='New Sale', products=products_data, sale=None)

@bp.route('/<int:id>')
@login_required
def view(id):
    sale = Sale.query.get_or_404(id)
    return render_template('sales/view.html', sale=sale)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    sale = Sale.query.get_or_404(id)
    
    # Only allow editing if sale is not Closed or Returned (final states)
    if sale.status in ['Closed', 'Returned']:
        flash(f'Cannot edit a {sale.status} sale.', 'warning')
        return redirect(url_for('sales.view', id=id))
    
    form = SaleForm(obj=sale)
    # Sort customers by newest first
    form.customer_id.choices = [(0, 'Walk-in Customer')] + [(c.id, f"[{c.customer_code}] {c.name}") for c in Customer.query.filter_by(is_active=True).order_by(Customer.created_at.desc()).all()]
    if sale.customer_id is None:
        form.customer_id.data = 0
    form.sale_id.data = str(sale.id)  # For validation uniqueness check
    
    if form.validate_on_submit():
        customer_id = form.customer_id.data if form.customer_id.data != 0 else None
        
        # Check if customer is blacklisted
        if customer_id:
            customer = Customer.query.get(customer_id)
            if customer and customer.is_blacklisted:
                phone_info = f" (Phone: {customer.phone})" if customer.phone else ""
                flash(f'Error: Customer {customer.name}{phone_info} is blacklisted and cannot make a purchase!', 'danger')
                return redirect(url_for('sales.edit', id=id))
        
        # Get discount and channel from form
        discount_percent = Decimal('0')  # No longer used — discount is now amount-based
        discount_amount_direct = Decimal(request.form.get('discount_amount', '0') or '0')
        channel = request.form.get('channel', 'Direct Sale')
        
        try:
            # Update sale header
            sale.sale_no = form.sale_no.data.strip()
            sale.date = form.date.data
            sale.customer_id = customer_id
            sale.channel = channel
            sale.notes = form.notes.data.strip() if form.notes.data else None
            sale.discount_percent = Decimal('0')  # No longer used
            
            # Delete existing items and stock movements
            for item in sale.items:
                # Reverse stock movement for this item
                product = item.product
                current_stock = product.get_current_stock()
                new_balance = current_stock + item.quantity
                
                movement = StockMovement(
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
                db.session.add(movement)
            
            SaleItem.query.filter_by(sale_id=sale.id).delete()
            db.session.flush()
            
            # Process new items from form
            product_ids = request.form.getlist('product_id[]')
            quantities = request.form.getlist('quantity[]')
            reference_prices = request.form.getlist('reference_price[]')
            actual_prices = request.form.getlist('actual_price[]')
            
            subtotal = Decimal('0')
            
            for pid, qty, ref_price, act_price in zip(product_ids, quantities, reference_prices, actual_prices):
                if pid and qty and act_price:
                    product = Product.query.get(int(pid))
                    if not product:
                        continue
                    
                    qty = int(qty)
                    ref_price = Decimal(str(ref_price))
                    act_price = Decimal(str(act_price))
                    total_price = qty * act_price
                    
                    # Get weighted average cost at this moment
                    avg_cost = product.get_weighted_average_cost()
                    total_cost = qty * avg_cost
                    gross_profit = total_price - total_cost
                    
                    # Check stock availability (including what we're adding back from deleted items)
                    current_stock = product.get_current_stock()
                    if current_stock < qty:
                        raise Exception(f'Insufficient stock for {product.product_code}. Available: {current_stock}, Requested: {qty}')
                    
                    item = SaleItem(
                        sale_id=sale.id,
                        product_id=int(pid),
                        quantity=qty,
                        reference_price=ref_price,
                        actual_price=act_price,
                        total_price=total_price,
                        unit_cost=avg_cost,
                        total_cost=total_cost,
                        gross_profit=gross_profit
                    )
                    db.session.add(item)
                    
                    # Create new stock movement
                    new_balance = current_stock - qty
                    movement = StockMovement(
                        date=sale.date,
                        transaction_type='Sale',
                        reference_no=sale.sale_no,
                        product_id=product.id,
                        quantity_in=0,
                        quantity_out=qty,
                        balance=new_balance,
                        unit_cost=avg_cost
                    )
                    db.session.add(movement)
                    
                    subtotal += total_price
            
            # Discount is now a direct amount entered by user
            sale.discount_amount = min(discount_amount_direct, subtotal).quantize(Decimal('0.01'))
            
            # Recalculate outstanding amount while preserving payments
            prev_paid = Decimal(str(sale.paid_amount or 0))
            new_total = sale.total_amount
            sale.paid_amount = min(prev_paid, new_total)
            sale.outstanding_amount = max(Decimal('0'), new_total - sale.paid_amount)
            sale.update_payment_status()
            
            db.session.commit()
            flash('Sale updated successfully. Stock recalculated.', 'success')
            return redirect(url_for('sales.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating sale: {str(e)}', 'danger')
    
    products = Product.query.filter_by(is_active=True).order_by(Product.product_code).all()
    products_data = [{
        'id': p.id,
        'product_code': p.product_code,
        'item_name': p.item_name,
        'reference_price': float(p.reference_selling_price),
        'current_stock': p.get_current_stock(),
        'avg_cost': float(p.get_weighted_average_cost())
    } for p in products]
    return render_template('sales/form.html', form=form, title='Edit Sale', products=products_data, sale=sale)

@bp.route('/api/customer/<int:customer_id>/tier')
@login_required
def api_customer_tier(customer_id):
    """Get customer tier and discount info"""
    customer = Customer.query.get_or_404(customer_id)
    return jsonify({
        'customer_id': customer.id,
        'customer_code': customer.customer_code,
        'name': customer.name,
        'tier': customer.tier,
        'discount_percent': float(customer.get_discount_percent())
    })

@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.is_admin():
        flash('Only administrators can delete sales.', 'danger')
        return redirect(url_for('sales.index'))
    
    sale = Sale.query.get_or_404(id)
    
    try:
        # Reverse stock movements
        for item in sale.items:
            product = item.product
            current_stock = product.get_current_stock()
            new_balance = current_stock + item.quantity
            
            movement = StockMovement(
                date=datetime.now(),
                transaction_type='Sale Deleted',
                reference_no=sale.sale_no,
                product_id=product.id,
                quantity_in=item.quantity,
                quantity_out=0,
                balance=new_balance,
                unit_cost=item.unit_cost,
                notes=f'Reversal of sale {sale.sale_no}'
            )
            db.session.add(movement)
        
        db.session.delete(sale)
        db.session.commit()
        flash('Sale deleted. Stock restored.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('sales.index'))

@bp.route('/api/products')
@login_required
def api_products():
    products = Product.query.filter_by(is_active=True).order_by(Product.product_code).all()
    return jsonify([{
        'id': p.id,
        'product_code': p.product_code,
        'item_name': p.item_name,
        'reference_price': float(p.reference_selling_price),
        'current_stock': p.get_current_stock(),
        'avg_cost': float(p.get_weighted_average_cost())
    } for p in products])

@bp.route('/api/products/<int:product_id>/price-history')
@login_required
def api_product_price_history(product_id):
    product = Product.query.get_or_404(product_id)
    history = product.get_purchase_price_history()
    return jsonify({
        'success': True,
        'history': history,
        'reference_price': float(product.reference_selling_price)
    })

@bp.route('/<int:id>/return', methods=['POST'])
@login_required
def return_sale(id):
    sale = Sale.query.get_or_404(id)
    
    if sale.status == 'Returned':
        flash('This sale is already marked as returned.', 'warning')
        return redirect(url_for('sales.index'))
    
    try:
        sale.status = 'Returned'
        
        for item in sale.items:
            product = item.product
            current_stock = product.get_current_stock()
            new_balance = current_stock + item.quantity
            
            # Restore stock
            movement = StockMovement(
                date=datetime.now(),
                transaction_type='Customer Return',
                reference_no=sale.sale_no,
                product_id=product.id,
                quantity_in=item.quantity,
                quantity_out=0,
                balance=new_balance,
                unit_cost=item.unit_cost,
                notes=f'Return of sale {sale.sale_no}'
            )
            db.session.add(movement)
        
        db.session.commit()
        flash(f'Sale {sale.sale_no} successfully marked as Returned. Stock restored.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error processing return: {str(e)}', 'danger')
    
    return redirect(url_for('sales.index'))

# New routes for Sale Close and Payment Received
@bp.route('/<int:id>/close', methods=['POST'])
@login_required
def close_sale(id):
    """Close a sale - finalize the transaction workflow"""
    sale = Sale.query.get_or_404(id)
    
    if sale.status == 'Closed':
        flash('Sale is already closed.', 'warning')
        return redirect(url_for('sales.view', id=id))
    
    if sale.status == 'Returned':
        flash('Cannot close a returned sale.', 'danger')
        return redirect(url_for('sales.view', id=id))
    
    try:
        sale.status = 'Closed'
        sale.closed_date = datetime.utcnow()
        sale.closed_by = current_user.id
        db.session.commit()
        flash(f'Sale {sale.sale_no} has been closed.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error closing sale: {str(e)}', 'danger')
    
    return redirect(url_for('sales.view', id=id))

@bp.route('/receive-payment', methods=['POST'], endpoint='receive_payment_direct')
@bp.route('/<int:id>/receive-payment', methods=['POST'], endpoint='receive_payment')
@login_required
def receive_payment(id=None):
    """Process incoming payments for a sale order (partial or full)"""
    if id is None:
        try:
            id = int(request.form.get('sale_id', '0'))
        except (ValueError, TypeError):
            id = None
    
    return_url = request.form.get('return_url') or request.referrer or url_for('sales.index')
    
    if not id:
        flash('Invalid sale order specified.', 'danger')
        return redirect(return_url)
    
    sale = Sale.query.get_or_404(id)
    
    # Check if sale is already settled
    if sale.payment_status in ['Paid', 'Fully Paid'] or (sale.outstanding_amount or 0) <= 0:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': f'Sale {sale.sale_no} is already fully paid.'}), 400
        flash(f'Sale {sale.sale_no} is already fully paid.', 'info')
        return redirect(return_url)
    
    # Parse payment amount
    amount_received_str = request.form.get('amount_received', '').strip()
    if amount_received_str:
        try:
            amount_received_str = amount_received_str.replace(',', '').replace(' ', '')
            amount_received = Decimal(amount_received_str)
        except Exception:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'Invalid payment amount entered.'}), 400
            flash('Invalid payment amount entered.', 'danger')
            return redirect(return_url)
    else:
        # Full payment of remaining balance
        amount_received = Decimal(str(sale.outstanding_amount or 0))
    
    if amount_received <= Decimal('0'):
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Payment amount must be greater than zero.'}), 400
        flash('Payment amount must be greater than zero.', 'danger')
        return redirect(return_url)
    
    try:
        current_outstanding = Decimal(str(sale.outstanding_amount or 0))
        # Deduct up to current balance due
        actual_paid = min(amount_received, current_outstanding)
        
        # Add to existing paid_amount and recalculate remaining balance
        current_paid = Decimal(str(sale.paid_amount or 0))
        sale.paid_amount = current_paid + actual_paid
        sale.outstanding_amount = max(Decimal('0'), current_outstanding - actual_paid)
        
        # Update payment status
        sale.update_payment_status()
        
        # Capture payment notes & method
        payment_notes = request.form.get('payment_notes', '').strip() or None
        payment_method = request.form.get('payment_method', 'Cash').strip() or 'Cash'
        
        # Record payment transaction in history
        payment_record = SalePayment(
            sale_id=sale.id,
            amount=actual_paid,
            payment_date=datetime.utcnow(),
            payment_method=payment_method,
            notes=payment_notes,
            created_by=current_user.id if current_user and current_user.is_authenticated else None
        )
        db.session.add(payment_record)
        
        if sale.payment_status in ['Paid', 'Fully Paid']:
            sale.payment_received_date = datetime.utcnow()
            sale.payment_received_by = current_user.id if current_user and current_user.is_authenticated else None
        
        db.session.commit()
        
        status_label = 'Fully Paid' if sale.payment_status in ['Paid', 'Fully Paid'] else 'Partially Paid'
        success_msg = f'Payment of {actual_paid:,.0f} Ks received for {sale.sale_no}. Status: {status_label}. Remaining Balance: {sale.outstanding_amount:,.0f} Ks'
        
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': True,
                'message': success_msg,
                'sale_id': sale.id,
                'sale_no': sale.sale_no,
                'paid_amount': float(sale.paid_amount),
                'outstanding_amount': float(sale.outstanding_amount),
                'balance_due': float(sale.balance_due),
                'payment_status': sale.payment_status
            })
        
        flash(success_msg, 'success')
    except Exception as e:
        db.session.rollback()
        err_msg = f'Error recording payment: {str(e)}'
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': err_msg}), 500
        flash(err_msg, 'danger')
    
    return redirect(return_url)
