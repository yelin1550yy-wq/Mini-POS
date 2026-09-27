from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from app.models import User

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(1, 50)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(1, 50)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(1, 100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(6, 40)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    role = SelectField('Role', choices=[('admin', 'Admin'), ('user', 'User')], validators=[DataRequired()])
    submit = SubmitField('Create User')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')