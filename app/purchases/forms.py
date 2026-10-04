from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional, Length, ValidationError
from app.models import Purchase
from datetime import date

class PurchaseForm(FlaskForm):
    purchase_no = StringField('Purchase No.', validators=[DataRequired(), Length(1, 30)])
    date = DateField('Date', validators=[DataRequired()], default=date.today)
    supplier_id = SelectField('Supplier', coerce=int, validators=[DataRequired()])
    payment_source = SelectField(
        'Payment Source',
        choices=[
            ('in_hand_cash', 'In-Hand Cash'),
            ('external', 'External / Credit / Bank')
        ],
        default='in_hand_cash',
        validators=[DataRequired()]
    )
    notes = TextAreaField('Notes', validators=[Optional()])
    purchase_id = HiddenField('Purchase ID')
    submit = SubmitField('Save')
    
    def validate_purchase_no(self, field):
        purchase = Purchase.query.filter_by(purchase_no=field.data.strip()).first()
        current_purchase_id = None
        # Primary: use hidden field (works in POST)
        if self.purchase_id.data:
            try:
                current_purchase_id = int(self.purchase_id.data)
            except (ValueError, TypeError):
                pass
        # Fallback: _obj (works in GET)
        elif hasattr(self, '_obj') and self._obj and hasattr(self._obj, 'id'):
            current_purchase_id = self._obj.id
        if purchase and purchase.id != current_purchase_id:
            raise ValidationError('Purchase number already exists.')

class PurchaseItemForm(FlaskForm):
    product_id = HiddenField('Product ID')
    quantity = StringField('Qty', validators=[DataRequired()])
    unit_price = StringField('Unit Price (Cost)', validators=[DataRequired()])
    reference_price = StringField('Reference Price', validators=[DataRequired()])
    total_price = StringField('Total')