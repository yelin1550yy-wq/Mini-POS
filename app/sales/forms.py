from flask_wtf import FlaskForm
from wtforms import StringField, DateField, SelectField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, ValidationError
from app.models import Sale
from datetime import date

class SaleForm(FlaskForm):
    sale_no = StringField('Sale No.', validators=[DataRequired(), Length(1, 30)])
    date = DateField('Date', validators=[DataRequired()], default=date.today)
    customer_id = SelectField('Customer', coerce=int, validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save')
    
    def validate_sale_no(self, field):
        sale = Sale.query.filter_by(sale_no=field.data.strip()).first()
        if sale and (not hasattr(self, 'obj') or sale.id != self.obj.id):
            raise ValidationError('Sale number already exists.')