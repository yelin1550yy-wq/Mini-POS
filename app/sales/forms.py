from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional, Length, ValidationError
from app.models import Sale
from datetime import date

class SaleForm(FlaskForm):
    sale_no = StringField('Sale No.', validators=[DataRequired(), Length(1, 30)])
    date = DateField('Date', validators=[DataRequired()], default=date.today)
    customer_id = SelectField('Customer', coerce=int, validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional()])
    sale_id = HiddenField('Sale ID')
    submit = SubmitField('Save')
    
    def validate_sale_no(self, field):
        sale = Sale.query.filter_by(sale_no=field.data.strip()).first()
        current_sale_id = None
        # Primary: use hidden field (works in POST)
        if self.sale_id.data:
            try:
                current_sale_id = int(self.sale_id.data)
            except (ValueError, TypeError):
                pass
        # Fallback: _obj (works in GET)
        elif hasattr(self, '_obj') and self._obj and hasattr(self._obj, 'id'):
            current_sale_id = self._obj.id
        if sale and sale.id != current_sale_id:
            raise ValidationError('Sale number already exists.')