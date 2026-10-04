from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import event

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    item_name = db.Column(db.String(200), nullable=False)
    product_type = db.Column(db.String(50), nullable=False)
    reference_selling_price = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    minimum_stock = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    purchases = db.relationship('PurchaseItem', backref='product', lazy='dynamic')
    sales = db.relationship('SaleItem', backref='product', lazy='dynamic')
    stock_movements = db.relationship('StockMovement', backref='product', lazy='dynamic')
    
    def get_current_stock(self):
        """Current stock = Accepted-purchase IN + (Customer Return / Adjustment / Sale Deleted / Purchase Deleted) IN
        - Sale OUT (only for sales that still exist) - other non-reversal OUT.

        Reversals ('Sale Deleted', 'Purchase Deleted') add stock back via their quantity_in.
        Outs are joined to their parent row so movements orphaned by a deleted
        sale/purchase drop out instead of leaving a stale negative balance.
        """
        # Stock IN from Accepted purchases (join drops deleted/non-accepted purchases)
        accepted_purchase_in = db.session.query(db.func.coalesce(db.func.sum(StockMovement.quantity_in), 0)).join(
            Purchase, StockMovement.reference_no == Purchase.purchase_no
        ).filter(
            StockMovement.product_id == self.id,
            StockMovement.transaction_type == 'Purchase',
            Purchase.status == 'Accepted'
        ).scalar() or 0
        
        # Stock IN from other sources (Customer Return, Adjustment, Sale Deleted, Purchase Deleted)
        other_in = db.session.query(db.func.coalesce(db.func.sum(StockMovement.quantity_in), 0)).filter(
            StockMovement.product_id == self.id,
            StockMovement.transaction_type.in_(['Customer Return', 'Adjustment', 'Sale Deleted', 'Purchase Deleted'])
        ).scalar() or 0
        
        # Stock OUT from sales that still exist (join drops outs orphaned by deleted sales)
        sale_out = db.session.query(db.func.coalesce(db.func.sum(StockMovement.quantity_out), 0)).join(
            Sale, StockMovement.reference_no == Sale.sale_no
        ).filter(
            StockMovement.product_id == self.id,
            StockMovement.transaction_type == 'Sale'
        ).scalar() or 0
        
        # Stock OUT from adjustments/other, excluding sale/purchase rows and their reversals
        other_out = db.session.query(db.func.coalesce(db.func.sum(StockMovement.quantity_out), 0)).filter(
            StockMovement.product_id == self.id,
            StockMovement.transaction_type.notin_(['Sale', 'Purchase', 'Sale Deleted', 'Purchase Deleted'])
        ).scalar() or 0
        
        return accepted_purchase_in + other_in - sale_out - other_out
    
    def get_weighted_average_cost(self):
        purchases = PurchaseItem.query.filter_by(product_id=self.id).all()
        if not purchases:
            return Decimal('0')
        total_qty = sum(p.quantity for p in purchases)
        total_cost = sum(p.total_price for p in purchases)
        if total_qty == 0:
            return Decimal('0')
        return (total_cost / total_qty).quantize(Decimal('0.01'))
    
    def get_stock_status(self):
        current_stock = self.get_current_stock()
        if current_stock <= 0:
            return 'Out of Stock'
        elif current_stock <= self.minimum_stock:
            return 'Low Stock'
        return 'Normal'
    
    def get_purchase_price_history(self):
        """Get all unique purchase prices with quantities for this product"""
        purchases = PurchaseItem.query.filter_by(product_id=self.id).order_by(PurchaseItem.id.desc()).all()
        history = []
        for p in purchases:
            history.append({
                'purchase_no': p.purchase.purchase_no,
                'date': p.purchase.date,
                'supplier': p.purchase.supplier.name,
                'quantity': p.quantity,
                'unit_price': p.unit_price,
                'reference_price': p.reference_price,
                'total_price': p.total_price,
            })
        return history
    
    def get_latest_purchase_reference_price(self):
        """Get the most recent purchase's reference price"""
        latest = PurchaseItem.query.filter_by(product_id=self.id).order_by(PurchaseItem.id.desc()).first()
        if latest and latest.reference_price:
            return latest.reference_price
        return self.reference_selling_price

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    purchases = db.relationship('Purchase', backref='supplier', lazy='dynamic')

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    account_name = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    township = db.Column(db.String(100))
    address = db.Column(db.Text)
    notes = db.Column(db.Text)
    is_blacklisted = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Tier system
    tier = db.Column(db.String(20), default='Silver')  # Silver, Gold, Platinum, Diamond, Loyal
    
    sales = db.relationship('Sale', backref='customer', lazy='dynamic')
    
    @staticmethod
    def generate_customer_code():
        """Generate next customer code in format CUST-XXXX"""
        last_customer = Customer.query.order_by(Customer.id.desc()).first()
        if last_customer and last_customer.customer_code:
            try:
                last_num = int(last_customer.customer_code.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        return f'CUST-{next_num:04d}'
    
    def get_total_buy_items(self):
        """Get total items purchased in completed/closed sales"""
        completed_sales = self.sales.filter(Sale.status.in_(['Completed', 'Closed'])).all()
        return sum(sum(item.quantity for item in s.items) for s in completed_sales)
    
    def get_total_spend(self):
        """Get total spend in completed/closed sales"""
        completed_sales = self.sales.filter(Sale.status.in_(['Completed', 'Closed'])).all()
        return sum(sum(item.total_price for item in s.items) for s in completed_sales)
    
    def get_tier_config(self):
        """Get the tier configuration for this customer's tier"""
        return TierConfig.query.filter_by(tier_name=self.tier, is_active=True).first()
    
    def get_discount_percent(self):
        """Get the discount percentage for this customer's tier"""
        config = self.get_tier_config()
        return config.discount_percent if config else Decimal('0')
    
    def update_tier_based_on_spend(self):
        """Update customer tier based on total spend"""
        total_spend = self.get_total_spend()
        tiers = TierConfig.query.filter_by(is_active=True).order_by(TierConfig.min_spend.desc()).all()
        for tier in tiers:
            if total_spend >= tier.min_spend:
                if self.tier != tier.tier_name:
                    self.tier = tier.tier_name
                    self.updated_at = datetime.utcnow()
                break
    
    def get_total_outstanding(self):
        """Get total outstanding amount for this customer"""
        return db.session.query(db.func.coalesce(db.func.sum(Sale.outstanding_amount), 0)).filter(
            Sale.customer_id == self.id,
            Sale.outstanding_amount > 0
        ).scalar() or 0
    
    def get_outstanding_sales(self):
        """Get all sales with outstanding amounts"""
        return self.sales.filter(Sale.outstanding_amount > 0).all()


# Auto-generate customer_code on insert if not provided
@db.event.listens_for(Customer, 'before_insert')
def generate_customer_code_listener(mapper, connection, target):
    if not target.customer_code:
        target.customer_code = Customer.generate_customer_code()


class Purchase(db.Model):
    __tablename__ = 'purchases'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_no = db.Column(db.String(30), unique=True, nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    # Purchase workflow status: Ordered, Received, Accepted, Cancelled
    status = db.Column(db.String(20), default='Ordered')
    received_date = db.Column(db.DateTime)
    accepted_date = db.Column(db.DateTime)
    received_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    accepted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    items = db.relationship('PurchaseItem', backref='purchase', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def is_received(self):
        return self.status in ['Received', 'Accepted']
    
    @property
    def is_accepted(self):
        return self.status == 'Accepted'

class PurchaseItem(db.Model):
    __tablename__ = 'purchase_items'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(15, 2), nullable=False)  # Actual purchase cost per unit
    reference_price = db.Column(db.Numeric(15, 2), nullable=False, default=0)  # Manual reference price for this batch
    total_price = db.Column(db.Numeric(15, 2), nullable=False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.quantity and self.unit_price:
            self.total_price = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))

class Sale(db.Model):
    __tablename__ = 'sales'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_no = db.Column(db.String(30), unique=True, nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    # Sales channel: Direct Sale, Online Sale
    channel = db.Column(db.String(20), default='Direct Sale')
    # Sale status: Draft, Completed, Returned, Closed
    status = db.Column(db.String(20), default='Draft')
    # Payment status: Unpaid, Partial, Paid
    payment_status = db.Column(db.String(20), default='Unpaid')
    # Payment received date
    payment_received_date = db.Column(db.DateTime)
    payment_received_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    # Outstanding amount (unpaid portion)
    outstanding_amount = db.Column(db.Numeric(15, 2), default=0)
    # Sale closed date
    closed_date = db.Column(db.DateTime)
    closed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    discount_percent = db.Column(db.Numeric(5, 2), default=0)  # Discount applied to this sale
    discount_amount = db.Column(db.Numeric(15, 2), default=0)  # Calculated discount amount
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    items = db.relationship('SaleItem', backref='sale', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def total_amount(self):
        """Calculate total sale amount (after discount)"""
        return sum(item.total_price for item in self.items) - (self.discount_amount or 0)
    
    @property
    def is_paid(self):
        return self.payment_status == 'Paid'
    
    @property
    def is_closed(self):
        return self.status == 'Closed'
    
    @property
    def is_outstanding(self):
        return self.outstanding_amount > 0
    
    def update_payment_status(self):
        """Update payment status based on outstanding amount"""
        if self.outstanding_amount <= 0:
            self.payment_status = 'Paid'
        elif self.outstanding_amount < self.total_amount:
            self.payment_status = 'Partial'
        else:
            self.payment_status = 'Unpaid'

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reference_price = db.Column(db.Numeric(15, 2), nullable=False)
    actual_price = db.Column(db.Numeric(15, 2), nullable=False)
    total_price = db.Column(db.Numeric(15, 2), nullable=False)
    unit_cost = db.Column(db.Numeric(15, 2), nullable=False)
    total_cost = db.Column(db.Numeric(15, 2), nullable=False)
    gross_profit = db.Column(db.Numeric(15, 2), nullable=False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.quantity and self.actual_price:
            self.total_price = Decimal(str(self.quantity)) * Decimal(str(self.actual_price))
        if self.quantity and self.unit_cost:
            self.total_cost = Decimal(str(self.quantity)) * Decimal(str(self.unit_cost))
        if self.total_price is not None and self.total_cost is not None:
            self.gross_profit = self.total_price - self.total_cost

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    transaction_type = db.Column(db.String(30), nullable=False)
    reference_no = db.Column(db.String(30), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity_in = db.Column(db.Integer, default=0)
    quantity_out = db.Column(db.Integer, default=0)
    balance = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(15, 2))
    notes = db.Column(db.Text)

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    category = db.Column(db.String(50), nullable=False)
    sub_category = db.Column(db.String(50))
    description = db.Column(db.String(200))
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

class Capital(db.Model):
    __tablename__ = 'capital'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    description = db.Column(db.String(200))
    type = db.Column(db.String(20), nullable=False, default='injection')  # injection, withdrawal
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_by_user = db.relationship('User', foreign_keys=[created_by])
    
    @classmethod
    def get_total_capital(cls):
        """Get total capital (injections - withdrawals)"""
        total_in = db.session.query(db.func.coalesce(db.func.sum(Capital.amount), 0)).filter(
            Capital.type == 'injection'
        ).scalar() or 0
        total_out = db.session.query(db.func.coalesce(db.func.sum(Capital.amount), 0)).filter(
            Capital.type == 'withdrawal'
        ).scalar() or 0
        return total_in - total_out
    
    @classmethod
    def get_total_injections(cls):
        return db.session.query(db.func.coalesce(db.func.sum(Capital.amount), 0)).filter(
            Capital.type == 'injection'
        ).scalar() or 0
    
    @classmethod
    def get_total_withdrawals(cls):
        return db.session.query(db.func.coalesce(db.func.sum(Capital.amount), 0)).filter(
            Capital.type == 'withdrawal'
        ).scalar() or 0


class TierConfig(db.Model):
    __tablename__ = 'tier_config'
    
    id = db.Column(db.Integer, primary_key=True)
    tier_name = db.Column(db.String(20), unique=True, nullable=False)  # Silver, Gold, Platinum, Diamond, Loyal
    min_spend = db.Column(db.Numeric(15, 2), nullable=False, default=0)  # Minimum spend to reach this tier
    discount_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0)  # Discount percentage for this tier
    description = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_default_tiers(cls):
        """Get default tier configuration"""
        return [
            {'tier_name': 'Silver', 'min_spend': 0, 'discount_percent': 0, 'description': 'New customers'},
            {'tier_name': 'Gold', 'min_spend': 100000, 'discount_percent': 2, 'description': 'Regular customers'},
            {'tier_name': 'Platinum', 'min_spend': 500000, 'discount_percent': 5, 'description': 'Valued customers'},
            {'tier_name': 'Diamond', 'min_spend': 1000000, 'discount_percent': 8, 'description': 'Premium customers'},
            {'tier_name': 'Loyal', 'min_spend': 2000000, 'discount_percent': 10, 'description': 'Most loyal customers'},
        ]
    
    @classmethod
    def initialize_default_tiers(cls):
        """Initialize default tier configurations if none exist"""
        if cls.query.count() == 0:
            for tier_data in cls.get_default_tiers():
                tier = cls(**tier_data)
                db.session.add(tier)
            db.session.commit()

EXPENSE_CATEGORIES = {
    'advertisement': ['Facebook', 'TikTok', 'Google', 'Other'],
    'other': ['Delivery', 'Packaging', 'Bank Fee', 'Utilities', 'Rent', 'Salary', 'Other']
}