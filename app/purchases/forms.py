from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional, Length, ValidationError
from app.models import Purchase
from datetime import date

class PurchaseForm(FlaskForm):
    purchase_no = StringField('Purchase No.', validators=[DataRequired(), Length(1, 30)])
    date = DateField('Date', validators=[DataRequired()], default=date.today)
    supplier_id = SelectField('Supplier', coerce=int, validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save')
    
    def validate_purchase_no(self, field):
        purchase = Purchase.query.filter_by(purchase_no=field.data.strip()).first()
        if purchase and (not hasattr(self, 'obj') or purchase.id != self.obj.id):
            raise ValidationError('Purchase number already exists.')

class PurchaseItemForm(FlaskForm):
    product_id = HiddenField('Product ID')
    quantity = StringField('Qty', validators=[DataRequired()])
    unit_price = StringField('Unit Price (Cost)', validators=[DataRequired()])
    reference_price = StringField('Reference Price', validators=[DataRequired()])
    total_price = StringField('Total')