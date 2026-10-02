from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import db, Purchase, PurchaseItem, Product, Supplier, StockMovement
from app.purchases.forms import PurchaseForm, PurchaseItemForm
from sqlalchemy import or_, func
from datetime import date, datetime
from decimal import Decimal

bp = Blueprint('purchases', __name__)

@bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    supplier_filter = request.args.get('supplier', '', type=int)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = Purchase.query.join(Supplier)
    
    if search:
        query = query.filter(or_(
            Purchase.purchase_no.ilike(f'%{search}%'),
            Supplier.name.ilike(f'%{search}%')
        ))
    if supplier_filter:
        query = query.filter(Purchase.supplier_id == supplier_filter)
    if date_from:
        query = query.filter(Purchase.date >= date_from)
    if date_to:
        query = query.filter(Purchase.date <= date_to)
    
    purchases = query.order_by(Purchase.date.desc(), Purchase.id.desc()).paginate(page=page, per_page=20, error_out=False)
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    
    return render_template('purchases/index.html', 
                           purchases=purchases, 
                           suppliers=suppliers,
                           search=search,
                           supplier_filter=supplier_filter,
                           date_from=date_from,
                           date_to=date_to)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form = PurchaseForm()
    form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()]
    
    # Generate next purchase number
    last_purchase = Purchase.query.order_by(Purchase.id.desc()).first()
    next_no = f"PO-{date.today().strftime('%Y%m%d')}-{(last_purchase.id + 1) if last_purchase else 1:04d}"
    
    if request.method == 'GET':
        form.purchase_no.data = next_no
        form.date.data = date.today()
    
    if form.validate_on_submit():
        purchase = Purchase(
            purchase_no=form.purchase_no.data.strip(),
            date=form.date.data,
            supplier_id=form.supplier_id.data,
            status='Ordered',  # Initial status: Ordered
            notes=form.notes.data.strip() if form.notes.data else None,
            created_by=current_user.id
        )
        
        try:
            db.session.add(purchase)
            db.session.flush()  # Get purchase ID
            
            # Process items from form
            product_ids = request.form.getlist('product_id[]')
            quantities = request.form.getlist('quantity[]')
            unit_prices = request.form.getlist('unit_price[]')
            reference_prices = request.form.getlist('reference_price[]')
            
            for pid, qty, price, ref_price in zip(product_ids, quantities, unit_prices, reference_prices):
                if pid and qty and price:
                    product = Product.query.get(int(pid))
                    if not product:
                        continue
                    
                    qty = int(qty)
                    price = Decimal(str(price))
                    ref_price = Decimal(str(ref_price)) if ref_price else Decimal('0')
                    total = qty * price
                    
                    item = PurchaseItem(
                        purchase_id=purchase.id,
                        product_id=int(pid),
                        quantity=qty,
                        unit_price=price,
                        reference_price=ref_price,
                        total_price=total
                    )
                    db.session.add(item)
                    
                    # NOTE: Stock movement is NOT created here.
                    # Stock is only updated when purchase is marked as "Accepted"
                    # This ensures ordered items don't appear in available inventory until received
            
            db.session.commit()
            flash('Purchase Order created successfully. Stock will be updated when marked as Accepted.', 'success')
            return redirect(url_for('purchases.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving purchase: {str(e)}', 'danger')
    
    products = Product.query.filter_by(is_active=True).order_by(Product.product_code).all()
    products_data = [{
        'id': p.id,
        'product_code': p.product_code,
        'item_name': p.item_name,
        'reference_price': float(p.reference_selling_price),
        'current_stock': p.get_current_stock(),
        'avg_cost': float(p.get_weighted_average_cost())
    } for p in products]
    return render_template('purchases/form.html', form=form, title='New Purchase Order', products=products_data, purchase=None)

@bp.route('/<int:id>/receive', methods=['POST'])
@login_required
def receive(id):
    """Mark purchase as Received - goods have arrived but not yet inspected/accepted"""
    purchase = Purchase.query.get_or_404(id)
    
    if purchase.status not in ['Ordered']:
        flash(f'Cannot receive: Purchase is currently {purchase.status}', 'warning')
        return redirect(url_for('purchases.view', id=id))
    
    try:
        purchase.status = 'Received'
        purchase.received_date = datetime.utcnow()
        purchase.received_by = current_user.id
        db.session.commit()
        flash(f'Purchase {purchase.purchase_no} marked as Received. Awaiting inspection for Acceptance.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('purchases.view', id=id))

@bp.route('/<int:id>/accept', methods=['POST'])
@login_required
def accept(id):
    """Mark purchase as Accepted - goods inspected and accepted, stock is now added to inventory"""
    purchase = Purchase.query.get_or_404(id)
    
    if purchase.status not in ['Ordered', 'Received']:
        flash(f'Cannot accept: Purchase is currently {purchase.status}', 'warning')
        return redirect(url_for('purchases.view', id=id))
    
    try:
        purchase.status = 'Accepted'
        purchase.accepted_date = datetime.utcnow()
        purchase.accepted_by = current_user.id
        
        # NOW create stock movements for all items (only when Accepted)
        for item in purchase.items:
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
        flash(f'Purchase {purchase.purchase_no} Accepted. Stock updated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error accepting purchase: {str(e)}', 'danger')
    
    return redirect(url_for('purchases.view', id=id))

@bp.route('/<int:id>/cancel', methods=['POST'])
@login_required
def cancel(id):
    """Cancel a purchase order"""
    purchase = Purchase.query.get_or_404(id)
    
    if purchase.status == 'Accepted':
        flash('Cannot cancel: Purchase has already been Accepted and stock added', 'danger')
        return redirect(url_for('purchases.view', id=id))
    
    try:
        purchase.status = 'Cancelled'
        db.session.commit()
        flash(f'Purchase {purchase.purchase_no} cancelled.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('purchases.view', id=id))

@bp.route('/<int:id>')
@login_required
def view(id):
    purchase = Purchase.query.get_or_404(id)
    return render_template('purchases/view.html', purchase=purchase)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    purchase = Purchase.query.get_or_404(id)
    
    # Only allow editing if no other transactions depend on this purchase's stock
    # For simplicity, we'll allow editing but warn user
    
    form = PurchaseForm(obj=purchase)
    form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()]
    
    if form.validate_on_submit():
        # This is complex - would need to reverse stock movements and recreate
        # For now, just update basic info
        purchase.purchase_no = form.purchase_no.data.strip()
        purchase.date = form.date.data
        purchase.supplier_id = form.supplier_id.data
        purchase.notes = form.notes.data.strip() if form.notes.data else None
        
        try:
            db.session.commit()
            flash('Purchase updated. Note: Stock movements not recalculated.', 'warning')
            return redirect(url_for('purchases.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    products = Product.query.filter_by(is_active=True).order_by(Product.product_code).all()
    products_data = [{
        'id': p.id,
        'product_code': p.product_code,
        'item_name': p.item_name,
        'reference_price': float(p.reference_selling_price),
        'current_stock': p.get_current_stock(),
        'avg_cost': float(p.get_weighted_average_cost())
    } for p in products]
    return render_template('purchases/form.html', form=form, title='Edit Purchase', products=products_data, purchase=purchase)

@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.is_admin():
        flash('Only administrators can delete purchases.', 'danger')
        return redirect(url_for('purchases.index'))
    
    purchase = Purchase.query.get_or_404(id)
    
    try:
        # Only reverse stock movements if the purchase was Accepted (stock was added)
        if purchase.status == 'Accepted':
            for item in purchase.items:
                product = item.product
                current_stock = product.get_current_stock()
                new_balance = current_stock - item.quantity
                
                if new_balance < 0:
                    flash(f'Cannot delete: Would result in negative stock for {product.product_code}', 'danger')
                    return redirect(url_for('purchases.index'))
                
                movement = StockMovement(
                    date=date.today(),
                    transaction_type='Purchase Deleted',
                    reference_no=purchase.purchase_no,
                    product_id=product.id,
                    quantity_in=0,
                    quantity_out=item.quantity,
                    balance=new_balance,
                    unit_cost=item.unit_price,
                    notes=f'Reversal of purchase {purchase.purchase_no}'
                )
                db.session.add(movement)
        
        db.session.delete(purchase)
        db.session.commit()
        flash('Purchase deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('purchases.index'))

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