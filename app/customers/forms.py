from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SelectField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from app.models import Customer

class CustomerForm(FlaskForm):
    customer_code = StringField('Customer Code', validators=[Optional(), Length(1, 20)])
    name = StringField('Customer Name', validators=[DataRequired(), Length(1, 200)])
    account_name = StringField('Account Name', validators=[Optional(), Length(0, 200)])
    phone = StringField('Phone', validators=[Optional(), Length(0, 50)])
    township = StringField('Township', validators=[Optional(), Length(0, 100)])
    address = TextAreaField('Address', validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional()])
    tier = SelectField('Tier', choices=[
        ('Silver', 'Silver'),
        ('Gold', 'Gold'),
        ('Platinum', 'Platinum'),
        ('Diamond', 'Diamond'),
        ('Loyal', 'Loyal')
    ], default='Silver')
    is_blacklisted = BooleanField('Blacklisted', default=False)
    is_active = BooleanField('Active', default=True)
    customer_id = HiddenField('Customer ID')
    submit = SubmitField('Save')
    
    def validate_customer_code(self, field):
        if field.data:
            code = field.data.strip().upper()
            customer = Customer.query.filter_by(customer_code=code).first()
            current_customer_id = None
            # Primary: use hidden field (works in POST)
            if self.customer_id.data:
                try:
                    current_customer_id = int(self.customer_id.data)
                except (ValueError, TypeError):
                    pass
            # Fallback: _obj (works in GET)
            elif hasattr(self, '_obj') and self._obj and hasattr(self._obj, 'id'):
                current_customer_id = self._obj.id
            if customer and customer.id != current_customer_id:
                raise ValidationError('Customer code already exists.')