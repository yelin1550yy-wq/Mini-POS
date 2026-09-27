from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Optional
from app.models import Supplier

class SupplierForm(FlaskForm):
    name = StringField('Supplier Name', validators=[DataRequired(), Length(1, 200)])
    phone = StringField('Phone', validators=[Optional(), Length(0, 50)])
    address = TextAreaField('Address', validators=[Optional()])
    notes = TextAreaField('Notes', validators=[Optional()])
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save')
    
    def validate_name(self, field):
        supplier = Supplier.query.filter_by(name=field.data.strip()).first()
        if supplier and (not hasattr(self, 'obj') or supplier.id != self.obj.id):
            raise ValidationError('Supplier name already exists.')