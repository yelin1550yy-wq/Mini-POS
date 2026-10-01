from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, IntegerField, SelectField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError
from app.models import Product

class ProductForm(FlaskForm):
    product_code = StringField('Product Code', validators=[DataRequired(), Length(1, 20)])
    item_name = StringField('Item Name', validators=[DataRequired(), Length(1, 200)])
    product_type = SelectField('Type', validators=[DataRequired()])
    reference_selling_price = DecimalField('Reference Selling Price', places=2, validators=[DataRequired(), NumberRange(min=0)])
    minimum_stock = IntegerField('Minimum Stock', validators=[DataRequired(), NumberRange(min=0)], default=0)
    is_active = BooleanField('Active', default=True)
    product_id = HiddenField('Product ID')
    submit = SubmitField('Save')
    
    def validate_product_code(self, field):
        product = Product.query.filter_by(product_code=field.data.upper().strip()).first()
        current_product_id = None
        if self.product_id.data:
            try:
                current_product_id = int(self.product_id.data)
            except (ValueError, TypeError):
                pass
        elif hasattr(self, 'obj') and self.obj and hasattr(self.obj, 'id'):
            current_product_id = self.obj.id
        
        if product and product.id != current_product_id:
            raise ValidationError('Product code already exists.')