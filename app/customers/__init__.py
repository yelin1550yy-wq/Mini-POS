from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import db, Customer
from app.customers.forms import CustomerForm
from sqlalchemy import or_

bp = Blueprint('customers', __name__)

@bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = Customer.query
    
    if search:
        query = query.filter(or_(
            Customer.name.ilike(f'%{search}%'),
            Customer.phone.ilike(f'%{search}%'),
            Customer.customer_code.ilike(f'%{search}%')
        ))
    if status_filter == 'active':
        query = query.filter(Customer.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(Customer.is_active == False)
    
    # Sort by newest first (latest registered customers first)
    customers = query.order_by(Customer.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('customers/index.html', 
                           customers=customers, 
                           search=search,
                           status_filter=status_filter)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_admin():
        flash('Only administrators can create customers.', 'danger')
        return redirect(url_for('customers.index'))
    form = CustomerForm()
    if form.validate_on_submit():
        customer_code = form.customer_code.data.strip().upper() if form.customer_code.data else Customer.generate_customer_code()
        customer = Customer(
            customer_code=customer_code,
            name=form.name.data.strip(),
            account_name=form.account_name.data.strip() if form.account_name.data else None,
            phone=form.phone.data.strip() if form.phone.data else None,
            township=form.township.data.strip() if form.township.data else None,
            address=form.address.data.strip() if form.address.data else None,
            notes=form.notes.data.strip() if form.notes.data else None,
            is_blacklisted=form.is_blacklisted.data,
            is_active=form.is_active.data
        )
        db.session.add(customer)
        db.session.commit()
        flash('Customer created successfully.', 'success')
        return redirect(url_for('customers.index'))
    return render_template('customers/form.html', form=form, title='Create Customer')

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.is_admin():
        flash('Only administrators can edit customers.', 'danger')
        return redirect(url_for('customers.index'))
    customer = Customer.query.get_or_404(id)
    form = CustomerForm(obj=customer)
    form.customer_id.data = str(customer.id)  # For validation uniqueness check
    if form.validate_on_submit():
        customer_code = form.customer_code.data.strip().upper() if form.customer_code.data else customer.customer_code
        customer.customer_code = customer_code
        customer.name = form.name.data.strip()
        customer.account_name = form.account_name.data.strip() if form.account_name.data else None
        customer.phone = form.phone.data.strip() if form.phone.data else None
        customer.township = form.township.data.strip() if form.township.data else None
        customer.address = form.address.data.strip() if form.address.data else None
        customer.notes = form.notes.data.strip() if form.notes.data else None
        customer.is_blacklisted = form.is_blacklisted.data
        customer.is_active = form.is_active.data
        db.session.commit()
        flash('Customer updated successfully.', 'success')
        return redirect(url_for('customers.index'))
    return render_template('customers/form.html', form=form, title='Edit Customer', customer=customer)

@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.is_admin():
        flash('Only administrators can delete customers.', 'danger')
        return redirect(url_for('customers.index'))
    customer = Customer.query.get_or_404(id)
    if customer.sales.count() > 0:
        flash('Cannot delete customer with existing sales. Set to inactive instead.', 'danger')
        return redirect(url_for('customers.index'))
    db.session.delete(customer)
    db.session.commit()
    flash('Customer deleted.', 'success')
    return redirect(url_for('customers.index'))

@bp.route('/api/search')
@login_required
def api_search():
    """API endpoint for searching customers by name or code"""
    q = request.args.get('q', '')
    customers = Customer.query.filter(
        Customer.is_active == True,
        db.or_(
            Customer.name.ilike(f'%{q}%'),
            Customer.customer_code.ilike(f'%{q}%')
        )
    ).order_by(Customer.created_at.desc()).limit(20).all()
    return jsonify([{
        'id': c.id,
        'customer_code': c.customer_code,
        'name': c.name,
        'phone': c.phone,
        'tier': c.tier,
        'discount_percent': float(c.get_discount_percent())
    } for c in customers])