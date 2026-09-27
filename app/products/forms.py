from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, IntegerField, SelectField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError
from app.models import Product

class ProductForm(FlaskForm):
    product_code = StringField('Product Code', validators=[DataRequired(), Length(1, 20)])
    item_name = StringField('Item Name', validators=[DataRequired(), Length(1, 200)])
    product_type = SelectField('Type', validators=[DataRequired()])
    reference_selling_price = DecimalField('Reference Selling Price', places=2, validators=[DataRequired(), NumberRange(min=0)])
    minimum_stock = IntegerField('Minimum Stock', validators=[DataRequired(), NumberRange(min=0)], default=0)
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save')
    
    def validate_product_code(self, field):
        product = Product.query.filter_by(product_code=field.data.upper().strip()).first()
        if product and (not hasattr(self, 'obj') or product.id != self.obj.id):
            raise ValidationError('Product code already exists.')