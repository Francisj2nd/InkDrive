from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional
from wtforms.widgets import TextArea

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()], 
                       render_kw={"placeholder": "Enter your email"})
    password = PasswordField('Password', validators=[DataRequired()],
                           render_kw={"placeholder": "Enter your password"})
    remember_me = BooleanField('Remember Me')

class RegisterForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)],
                      render_kw={"placeholder": "Enter your full name"})
    email = StringField('Email', validators=[DataRequired(), Email()],
                       render_kw={"placeholder": "Enter your email"})
    password = PasswordField('Password', validators=[
        DataRequired(), 
        Length(min=8, message="Password must be at least 8 characters long")
    ], render_kw={"placeholder": "Create a password"})
    password2 = PasswordField('Confirm Password', validators=[
        DataRequired(), 
        EqualTo('password', message='Passwords must match')
    ], render_kw={"placeholder": "Confirm your password"})

class ProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()], 
                       render_kw={"readonly": True})
    theme_preference = SelectField('Theme Preference', 
                                 choices=[('auto', 'Auto'), ('light', 'Light'), ('dark', 'Dark')],
                                 default='auto')
    
class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()],
                                   render_kw={"placeholder": "Enter current password"})
    new_password = PasswordField('New Password', validators=[
        DataRequired(), 
        Length(min=8, message="Password must be at least 8 characters long")
    ], render_kw={"placeholder": "Enter new password"})
    new_password2 = PasswordField('Confirm New Password', validators=[
        DataRequired(), 
        EqualTo('new_password', message='Passwords must match')
    ], render_kw={"placeholder": "Confirm new password"})
