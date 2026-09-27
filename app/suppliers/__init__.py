from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import db, Supplier
from app.suppliers.forms import SupplierForm
from sqlalchemy import or_

bp = Blueprint('suppliers', __name__)

@bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    
    query = Supplier.query
    
    if search:
        query = query.filter(or_(
            Supplier.name.ilike(f'%{search}%'),
            Supplier.phone.ilike(f'%{search}%')
        ))
    if status_filter == 'active':
        query = query.filter(Supplier.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(Supplier.is_active == False)
    
    suppliers = query.order_by(Supplier.name).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('suppliers/index.html', 
                           suppliers=suppliers, 
                           search=search,
                           status_filter=status_filter)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_admin():
        flash('Only administrators can create suppliers.', 'danger')
        return redirect(url_for('suppliers.index'))
    form = SupplierForm()
    if form.validate_on_submit():
        supplier = Supplier(
            name=form.name.data.strip(),
            phone=form.phone.data.strip() if form.phone.data else None,
            address=form.address.data.strip() if form.address.data else None,
            notes=form.notes.data.strip() if form.notes.data else None,
            is_active=form.is_active.data
        )
        db.session.add(supplier)
        db.session.commit()
        flash('Supplier created successfully.', 'success')
        return redirect(url_for('suppliers.index'))
    return render_template('suppliers/form.html', form=form, title='Create Supplier')

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.is_admin():
        flash('Only administrators can edit suppliers.', 'danger')
        return redirect(url_for('suppliers.index'))
    supplier = Supplier.query.get_or_404(id)
    form = SupplierForm(obj=supplier)
    if form.validate_on_submit():
        supplier.name = form.name.data.strip()
        supplier.phone = form.phone.data.strip() if form.phone.data else None
        supplier.address = form.address.data.strip() if form.address.data else None
        supplier.notes = form.notes.data.strip() if form.notes.data else None
        supplier.is_active = form.is_active.data
        db.session.commit()
        flash('Supplier updated successfully.', 'success')
        return redirect(url_for('suppliers.index'))
    return render_template('suppliers/form.html', form=form, title='Edit Supplier', supplier=supplier)

@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.is_admin():
        flash('Only administrators can delete suppliers.', 'danger')
        return redirect(url_for('suppliers.index'))
    supplier = Supplier.query.get_or_404(id)
    if supplier.purchases.count() > 0:
        flash('Cannot delete supplier with existing purchases. Set to inactive instead.', 'danger')
        return redirect(url_for('suppliers.index'))
    db.session.delete(supplier)
    db.session.commit()
    flash('Supplier deleted.', 'success')
    return redirect(url_for('suppliers.index'))