from flask import Flask
from flask_login import LoginManager
from config import Config
from app.models import db

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    login_manager.init_app(app)
    
    with app.app_context():
        import os
        os.makedirs(app.instance_path, exist_ok=True)
        db.create_all()
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()
            
            # 1. Purchases table migration safety check
            if 'purchases' in table_names:
                cols = [c['name'] for c in inspector.get_columns('purchases')]
                with db.engine.connect() as conn:
                    if 'payment_source' not in cols:
                        conn.execute(text("ALTER TABLE purchases ADD COLUMN payment_source VARCHAR(50) DEFAULT 'in_hand_cash'"))
                    if 'paid_amount' not in cols:
                        conn.execute(text("ALTER TABLE purchases ADD COLUMN paid_amount NUMERIC(15, 2) DEFAULT 0"))
                    if 'balance_due' not in cols:
                        conn.execute(text("ALTER TABLE purchases ADD COLUMN balance_due NUMERIC(15, 2) DEFAULT 0"))
                    conn.execute(text("UPDATE purchases SET payment_source = 'in_hand_cash' WHERE payment_source IS NULL"))
                    conn.execute(text("UPDATE purchases SET paid_amount = 0 WHERE paid_amount IS NULL"))
                    conn.execute(text("UPDATE purchases SET balance_due = 0 WHERE balance_due IS NULL"))
                    conn.commit()
            
            # 2. Sales table migration safety check
            if 'sales' in table_names:
                cols = [c['name'] for c in inspector.get_columns('sales')]
                with db.engine.connect() as conn:
                    if 'paid_amount' not in cols:
                        conn.execute(text("ALTER TABLE sales ADD COLUMN paid_amount NUMERIC(15, 2) DEFAULT 0"))
                    if 'balance_due' not in cols:
                        conn.execute(text("ALTER TABLE sales ADD COLUMN balance_due NUMERIC(15, 2) DEFAULT 0"))
                    if 'payment_source' not in cols:
                        conn.execute(text("ALTER TABLE sales ADD COLUMN payment_source VARCHAR(50) DEFAULT 'in_hand_cash'"))
                    conn.execute(text("UPDATE sales SET paid_amount = 0 WHERE paid_amount IS NULL"))
                    conn.execute(text("UPDATE sales SET balance_due = COALESCE(outstanding_amount, 0) WHERE balance_due IS NULL OR (balance_due = 0 AND outstanding_amount > 0)"))
                    conn.execute(text("UPDATE sales SET payment_source = 'in_hand_cash' WHERE payment_source IS NULL OR payment_source = ''"))
                    conn.commit()
            
            # 3. Sale Payments table migration safety check
            if 'sale_payments' in table_names:
                cols = [c['name'] for c in inspector.get_columns('sale_payments')]
                with db.engine.connect() as conn:
                    if 'payment_source' not in cols:
                        conn.execute(text("ALTER TABLE sale_payments ADD COLUMN payment_source VARCHAR(50) DEFAULT 'in_hand_cash'"))
                    conn.execute(text("UPDATE sale_payments SET payment_source = 'in_hand_cash' WHERE payment_source IS NULL OR payment_source = ''"))
                    conn.commit()
        except Exception as e:
            app.logger.warning(f"Startup migration warning: {e}")
    
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.products import bp as products_bp
    app.register_blueprint(products_bp, url_prefix='/products')
    
    from app.suppliers import bp as suppliers_bp
    app.register_blueprint(suppliers_bp, url_prefix='/suppliers')
    
    from app.purchases import bp as purchases_bp
    app.register_blueprint(purchases_bp, url_prefix='/purchases')
    
    from app.customers import bp as customers_bp
    app.register_blueprint(customers_bp, url_prefix='/customers')
    
    from app.sales import bp as sales_bp
    app.register_blueprint(sales_bp, url_prefix='/sales')
    
    from app.stock import bp as stock_bp
    app.register_blueprint(stock_bp, url_prefix='/stock')
    
    from app.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    
    from app.expenses import bp as expenses_bp
    app.register_blueprint(expenses_bp, url_prefix='/expenses')
    
    from app.reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')
    
    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    @app.shell_context_processor
    def make_shell_context():
        return {'db': db}
    
    return app

from app.models import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))