from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import db, Expense
from app.expenses.forms import ExpenseForm
from sqlalchemy import func
from datetime import date

bp = Blueprint('expenses', __name__)

EXPENSE_CATEGORIES = {
    'advertisement': ['Facebook', 'TikTok', 'Google', 'Other'],
    'other': ['Delivery', 'Packaging', 'Bank Fee', 'Utilities', 'Rent', 'Salary', 'Other']
}

@bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    category_filter = request.args.get('category', '')
    sub_category_filter = request.args.get('sub_category', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    query = Expense.query
    
    if category_filter:
        query = query.filter(Expense.category == category_filter)
    if sub_category_filter:
        query = query.filter(Expense.sub_category == sub_category_filter)
    if date_from:
        query = query.filter(Expense.date >= date_from)
    if date_to:
        query = query.filter(Expense.date <= date_to)
    
    expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).paginate(page=page, per_page=20, error_out=False)
    
    # Summary
    total_adv = db.session.query(func.sum(Expense.amount)).filter(Expense.category == 'advertisement').scalar() or 0
    total_other = db.session.query(func.sum(Expense.amount)).filter(Expense.category == 'other').scalar() or 0
    
    return render_template('expenses/index.html',
                           expenses=expenses,
                           category_filter=category_filter,
                           sub_category_filter=sub_category_filter,
                           date_from=date_from,
                           date_to=date_to,
                           total_adv=total_adv,
                           total_other=total_other,
                           total_expenses=total_adv + total_other,
                           categories=EXPENSE_CATEGORIES)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_admin():
        flash('Only administrators can create expenses.', 'danger')
        return redirect(url_for('expenses.index'))
    form = ExpenseForm()
    form.category.choices = [('advertisement', 'Advertisement'), ('other', 'Other Cost')]
    form.sub_category.choices = []
    
    if request.method == 'GET':
        form.date.data = date.today()
    
    # Populate sub_category choices from submitted category for validation
    if request.method == 'POST':
        cat = request.form.get('category')
        form.sub_category.choices = [(s, s) for s in EXPENSE_CATEGORIES.get(cat, [])]
    
    if form.validate_on_submit():
        expense = Expense(
            date=form.date.data,
            category=form.category.data,
            sub_category=form.sub_category.data,
            description=form.description.data.strip() if form.description.data else None,
            amount=form.amount.data,
            created_by=current_user.id
        )
        db.session.add(expense)
        db.session.commit()
        flash('Expense recorded successfully.', 'success')
        return redirect(url_for('expenses.index'))
    
    return render_template('expenses/form.html', form=form, title='New Expense', categories=EXPENSE_CATEGORIES)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.is_admin():
        flash('Only administrators can edit expenses.', 'danger')
        return redirect(url_for('expenses.index'))
    expense = Expense.query.get_or_404(id)
    form = ExpenseForm(obj=expense)
    form.category.choices = [('advertisement', 'Advertisement'), ('other', 'Other Cost')]
    form.sub_category.choices = EXPENSE_CATEGORIES.get(expense.category, [])
    
    # Populate sub_category choices from submitted category for validation
    if request.method == 'POST':
        cat = request.form.get('category')
        form.sub_category.choices = [(s, s) for s in EXPENSE_CATEGORIES.get(cat, [])]
    
    if form.validate_on_submit():
        expense.date = form.date.data
        expense.category = form.category.data
        expense.sub_category = form.sub_category.data
        expense.description = form.description.data.strip() if form.description.data else None
        expense.amount = form.amount.data
        db.session.commit()
        flash('Expense updated successfully.', 'success')
        return redirect(url_for('expenses.index'))
    
    return render_template('expenses/form.html', form=form, title='Edit Expense', expense=expense, categories=EXPENSE_CATEGORIES)

@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.is_admin():
        flash('Only administrators can delete expenses.', 'danger')
        return redirect(url_for('expenses.index'))
    expense = Expense.query.get_or_404(id)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense deleted.', 'success')
    return redirect(url_for('expenses.index'))

@bp.route('/api/subcategories')
@login_required
def api_subcategories():
    category = request.args.get('category', '')
    subcats = EXPENSE_CATEGORIES.get(category, [])
    return jsonify([{'value': s, 'label': s} for s in subcats])