from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField, DecimalField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Optional
from datetime import date

class ExpenseForm(FlaskForm):
    date = DateField('Date', validators=[DataRequired()], default=date.today)
    category = SelectField('Category', validators=[DataRequired()])
    sub_category = SelectField('Sub-Category', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    amount = DecimalField('Amount', places=2, validators=[DataRequired(), NumberRange(min=0.01)])
    submit = SubmitField('Save')