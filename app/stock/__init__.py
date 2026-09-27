from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models import db, Product, StockMovement, PurchaseItem, SaleItem
from sqlalchemy import func, or_
from decimal import Decimal

bp = Blueprint('stock', __name__)

@bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    type_filter = request.args.get('type', '')
    status_filter = request.args.get('status', '')
    
    # Get all products with calculated fields
    products = Product.query
    
    if search:
        products = products.filter(or_(
            Product.product_code.ilike(f'%{search}%'),
            Product.item_name.ilike(f'%{search}%')
        ))
    if type_filter:
        products = products.filter(Product.product_type == type_filter)
    if status_filter == 'active':
        products = products.filter(Product.is_active == True)
    elif status_filter == 'inactive':
        products = products.filter(Product.is_active == False)
    
    all_products = products.order_by(Product.product_code).all()
    
    # Calculate stock for each product
    product_data = []
    for p in all_products:
        current_stock = p.get_current_stock()
        avg_cost = p.get_weighted_average_cost()
        stock_value = current_stock * avg_cost
        status = p.get_stock_status()
        
        if status_filter:
            if status_filter == 'low' and status != 'Low Stock':
                continue
            elif status_filter == 'out' and status != 'Out of Stock':
                continue
            elif status_filter == 'normal' and status != 'Normal':
                continue
        
        product_data.append({
            'product': p,
            'current_stock': current_stock,
            'avg_cost': avg_cost,
            'stock_value': stock_value,
            'status': status
        })
    
    # Manual pagination
    per_page = 20
    total = len(product_data)
    start = (page - 1) * per_page
    end = start + per_page
    paginated = product_data[start:end]
    
    class Pagination:
        def __init__(self, page, per_page, total, items):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.items = items
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1
            self.next_num = page + 1
        
        def iter_pages(self, left_edge=1, right_edge=1, left_current=2, right_current=2):
            last = 0
            for num in range(1, self.pages + 1):
                if num <= left_edge or \
                   (num > self.page - left_current - 1 and num < self.page + right_current) or \
                   num > self.pages - right_edge:
                    if last + 1 != num:
                        yield None
                    yield num
                    last = num
    
    pagination = Pagination(page, per_page, total, paginated)
    product_types = ['စပန့်', 'ချည်နု']
    
    # Summary stats
    total_stock_value = sum(p['stock_value'] for p in product_data)
    low_stock_count = sum(1 for p in product_data if p['status'] == 'Low Stock')
    out_of_stock_count = sum(1 for p in product_data if p['status'] == 'Out of Stock')
    
    return render_template('stock/index.html',
                           pagination=pagination,
                           search=search,
                           type_filter=type_filter,
                           status_filter=status_filter,
                           product_types=product_types,
                           total_stock_value=total_stock_value,
                           low_stock_count=low_stock_count,
                           out_of_stock_count=out_of_stock_count)

@bp.route('/movement')
@login_required
def movement():
    page = request.args.get('page', 1, type=int)
    product_filter = request.args.get('product', '', type=int)
    type_filter = request.args.get('type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = StockMovement.query.join(Product)
    
    if product_filter:
        query = query.filter(StockMovement.product_id == product_filter)
    if type_filter:
        query = query.filter(StockMovement.transaction_type == type_filter)
    if date_from:
        query = query.filter(StockMovement.date >= date_from)
    if date_to:
        query = query.filter(StockMovement.date <= date_to)
    
    movements = query.order_by(StockMovement.date.desc(), StockMovement.id.desc()).paginate(page=page, per_page=50, error_out=False)
    products = Product.query.filter_by(is_active=True).order_by(Product.product_code).all()
    trans_types = ['Purchase', 'Sale', 'Customer Return', 'Damaged/Lost', 'Adjustment', 'Purchase Deleted']
    
    return render_template('stock/movement.html',
                           movements=movements,
                           products=products,
                           trans_types=trans_types,
                           product_filter=product_filter,
                           type_filter=type_filter,
                           date_from=date_from,
                           date_to=date_to)

@bp.route('/<int:id>')
@bp.route('/view/<int:id>')
@login_required
def detail(id):
    product = Product.query.get_or_404(id)
    
    # Get recent movements
    movements = StockMovement.query.filter_by(product_id=id).order_by(StockMovement.date.desc()).limit(50).all()
    
    # Get purchase history
    from app.models import Purchase
    purchases = PurchaseItem.query.filter_by(product_id=id).join(Purchase).order_by(Purchase.date.desc()).all()
    
    # Get sale history
    from app.models import Sale
    sales = SaleItem.query.filter_by(product_id=id).join(Sale).order_by(Sale.date.desc()).all()
    
    current_stock = product.get_current_stock()
    avg_cost = product.get_weighted_average_cost()
    
    return render_template('stock/detail.html',
                           product=product,
                           movements=movements,
                           purchases=purchases,
                           sales=sales,
                           current_stock=current_stock,
                           avg_cost=avg_cost)