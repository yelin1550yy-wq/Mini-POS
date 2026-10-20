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
        db.create_all()
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            if 'sales' in inspector.get_table_names():
                cols = [c['name'] for c in inspector.get_columns('sales')]
                if 'paid_amount' not in cols:
                    with db.engine.connect() as conn:
                        conn.execute(text('ALTER TABLE sales ADD COLUMN paid_amount NUMERIC(15, 2) DEFAULT 0'))
                        conn.commit()
                with db.engine.connect() as conn:
                    conn.execute(text('UPDATE sales SET paid_amount = 0 WHERE paid_amount IS NULL'))
                    conn.commit()
        except Exception:
            pass
    
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