from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import db, Sale, SaleItem, Product, Customer, StockMovement
from app.sales.forms import SaleForm
from sqlalchemy import or_, func
from datetime import date, datetime
from decimal import Decimal

bp = Blueprint('sales', __name__)

@bp.route('/')
@login_required
def index():
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
        discount_percent = Decimal(request.form.get('discount_percent', '0'))
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
            
            # Calculate discount amount and update sale
            if discount_percent > 0:
                sale.discount_amount = (subtotal * discount_percent / Decimal('100')).quantize(Decimal('0.01'))
            else:
                sale.discount_amount = Decimal('0')
            
            # Set outstanding amount (initially full amount, will be updated when payment received)
            sale.outstanding_amount = sale.total_amount
            
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
        discount_percent = Decimal(request.form.get('discount_percent', '0'))
        channel = request.form.get('channel', 'Direct Sale')
        
        try:
            # Update sale header
            sale.sale_no = form.sale_no.data.strip()
            sale.date = form.date.data
            sale.customer_id = customer_id
            sale.channel = channel
            sale.notes = form.notes.data.strip() if form.notes.data else None
            sale.discount_percent = discount_percent
            
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
            
            # Calculate discount amount and update sale
            if discount_percent > 0:
                sale.discount_amount = (subtotal * discount_percent / Decimal('100')).quantize(Decimal('0.01'))
            else:
                sale.discount_amount = Decimal('0')
            
            # Recalculate outstanding amount
            sale.outstanding_amount = sale.total_amount
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

@bp.route('/<int:id>/receive-payment', methods=['POST'])
@login_required
def receive_payment(id):
    """Mark payment as received for a sale"""
    sale = Sale.query.get_or_404(id)
    
    if sale.payment_status == 'Paid':
        flash('Payment already received for this sale.', 'warning')
        return redirect(url_for('sales.view', id=id))
    
    # Get amount received from form (optional - can be partial)
    amount_received_str = request.form.get('amount_received', '').strip()
    if amount_received_str:
        try:
            # Remove commas and other formatting
            amount_received_str = amount_received_str.replace(',', '').replace(' ', '')
            amount_received = Decimal(amount_received_str)
        except:
            flash('Invalid amount entered.', 'danger')
            return redirect(url_for('sales.view', id=id))
    else:
        # Full payment
        amount_received = sale.outstanding_amount
    
    try:
        # Reduce outstanding amount
        sale.outstanding_amount = max(Decimal('0'), sale.outstanding_amount - amount_received)
        sale.update_payment_status()
        
        if sale.payment_status == 'Paid':
            sale.payment_received_date = datetime.utcnow()
            sale.payment_received_by = current_user.id
        
        db.session.commit()
        flash(f'Payment of {amount_received:,.2f} Ks received for sale {sale.sale_no}. Outstanding: {sale.outstanding_amount:,.2f} Ks', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording payment: {str(e)}', 'danger')
    
    return redirect(url_for('sales.view', id=id))