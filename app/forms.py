from wtforms import StringField, PasswordField
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, EqualTo


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




class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=160)])
    phone = StringField("Phone", validators=[Optional(), Length(max=40)])
    subject = StringField("Subject", validators=[DataRequired(), Length(max=160)])
    message = TextAreaField("Message", validators=[DataRequired(), Length(min=5, max=5000)])


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[
        DataRequired(),
        Length(min=8, message="Password must be at least 8 characters.")
    ])

    confirm_password = PasswordField("Confirm Password", validators=[
        DataRequired(),
        EqualTo("password", message="Passwords do not match.")
    ])

class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=160)])


