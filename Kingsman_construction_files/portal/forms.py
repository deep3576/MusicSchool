from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SelectField, TextAreaField, SubmitField

class UploadForm(FlaskForm):
    category = SelectField("Category", choices=[
        ('document','Document'),('photo','Photo'),('permit','Permit'),
        ('design','Design'),('invoice','Invoice'),('inspection','Inspection'),('other','Other')
    ])
    note = TextAreaField("Note (optional)")
    file = FileField("File", validators=[FileRequired(), FileAllowed(['jpg','jpeg','png','pdf','doc','docx','xls','xlsx','txt'])])
    submit = SubmitField("Upload")
