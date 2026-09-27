from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models import db, Product
from app.products.forms import ProductForm
from sqlalchemy import or_

bp = Blueprint('products', __name__)

PRODUCT_TYPES = ['စပန့်', 'ချည်နု']

@bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    type_filter = request.args.get('type', '')
    status_filter = request.args.get('status', '')
    
    query = Product.query
    
    if search:
        query = query.filter(or_(
            Product.product_code.ilike(f'%{search}%'),
            Product.item_name.ilike(f'%{search}%')
        ))
    if type_filter:
        query = query.filter(Product.product_type == type_filter)
    if status_filter == 'active':
        query = query.filter(Product.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(Product.is_active == False)
    
    products = query.order_by(Product.product_code).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('products/index.html', 
                           products=products, 
                           search=search,
                           type_filter=type_filter,
                           status_filter=status_filter,
                           product_types=PRODUCT_TYPES)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_admin():
        flash('Only administrators can create products.', 'danger')
        return redirect(url_for('products.index'))
    form = ProductForm()
    form.product_type.choices = [(t, t) for t in PRODUCT_TYPES]
    if form.validate_on_submit():
        product = Product(
            product_code=form.product_code.data.upper().strip(),
            item_name=form.item_name.data.strip(),
            product_type=form.product_type.data,
            reference_selling_price=form.reference_selling_price.data,
            minimum_stock=form.minimum_stock.data,
            is_active=form.is_active.data
        )
        db.session.add(product)
        try:
            db.session.commit()
            flash('Product created successfully.', 'success')
            return redirect(url_for('products.index'))
        except Exception as e:
            db.session.rollback()
            flash('Product code already exists.', 'danger')
    return render_template('products/form.html', form=form, title='Create Product')

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.is_admin():
        flash('Only administrators can edit products.', 'danger')
        return redirect(url_for('products.index'))
    product = Product.query.get_or_404(id)
    form = ProductForm(obj=product)
    form.product_type.choices = [(t, t) for t in PRODUCT_TYPES]
    if form.validate_on_submit():
        product.product_code = form.product_code.data.upper().strip()
        product.item_name = form.item_name.data.strip()
        product.product_type = form.product_type.data
        product.reference_selling_price = form.reference_selling_price.data
        product.minimum_stock = form.minimum_stock.data
        product.is_active = form.is_active.data
        try:
            db.session.commit()
            flash('Product updated successfully.', 'success')
            return redirect(url_for('products.index'))
        except Exception as e:
            db.session.rollback()
            flash('Product code already exists.', 'danger')
    return render_template('products/form.html', form=form, title='Edit Product', product=product)

@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.is_admin():
        flash('Only administrators can delete products.', 'danger')
        return redirect(url_for('products.index'))
    product = Product.query.get_or_404(id)
    if product.purchases.count() > 0 or product.sales.count() > 0:
        flash('Cannot delete product with existing transactions. Set to inactive instead.', 'danger')
        return redirect(url_for('products.index'))
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted.', 'success')
    return redirect(url_for('products.index'))

@bp.route('/<int:id>/price-history')
@login_required
def price_history(id):
    product = Product.query.get_or_404(id)
    history = product.get_purchase_price_history()
    return render_template('products/price_history.html', product=product, history=history)

@bp.route('/<int:id>/set-reference-price', methods=['POST'])
@login_required
def set_reference_price(id):
    if not current_user.is_admin():
        flash('Only administrators can update reference price.', 'danger')
        return redirect(url_for('products.price_history', id=id))
    
    product = Product.query.get_or_404(id)
    new_price = request.form.get('reference_price', type=float)
    if new_price is not None and new_price >= 0:
        product.reference_selling_price = new_price
        db.session.commit()
        flash(f'Reference price updated to {new_price:,.0f} Ks', 'success')
    else:
        flash('Invalid price.', 'danger')
    return redirect(url_for('products.price_history', id=id))

@bp.route('/api/search')
@login_required
def api_search():
    q = request.args.get('q', '')
    products = Product.query.filter(
        Product.is_active == True,
        db.or_(
            Product.product_code.ilike(f'%{q}%'),
            Product.item_name.ilike(f'%{q}%')
        )
    ).limit(20).all()
    return jsonify([{
        'id': p.id,
        'product_code': p.product_code,
        'item_name': p.item_name,
        'product_type': p.product_type,
        'reference_selling_price': float(p.reference_selling_price),
        'current_stock': p.get_current_stock(),
        'average_cost': float(p.get_weighted_average_cost())
    } for p in products])