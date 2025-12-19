from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Email, Length

class SignupForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    phone = StringField("Phone", validators=[Length(max=60)])
    address_1 = StringField("Address 1", validators=[Length(max=200)])
    address_2 = StringField("Address 2", validators=[Length(max=200)])
    city = StringField("City", validators=[Length(max=120)])
    province = StringField("Province", validators=[Length(max=120)])
    postal_code = StringField("Postal Code", validators=[Length(max=30)])
    country = StringField("Country", validators=[Length(max=80)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])
