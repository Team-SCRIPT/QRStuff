#!/usr/bin/env python3
"""
Flask application to accept some details, generate, display, and email a QR code to users
"""

# pylint: disable=invalid-name,too-few-public-methods,no-member,line-too-long,too-many-locals

import base64
import os

import qrcode
import sendgrid
from sendgrid.helpers.mail import Attachment, Content, Email, Mail, Personalization

from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import exc


FROM_EMAIL = os.getenv('FROM_EMAIL')
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')

app = Flask(__name__, static_url_path='')
sg = sendgrid.SendGridAPIClient(SENDGRID_API_KEY)

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')

db = SQLAlchemy(app)

DEPARTMENTS = {'cse': 'Computer Science and Engineering',
               'ece': 'Electronics and Communication Engineering',
               'mech': 'Mechanical Engineering',
               'civil': 'Civil Engineering',
               'chem': 'Chemical Engineering',
               'others': 'Others'}


class User(db.Model):
    """
    Database model class
    """
    __tablename__ = 'users'
    codex_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30))
    email = db.Column(db.String(50), unique=True)
    phone = db.Column(db.BigInteger, unique=True)
    department = db.Column(db.String(50))

    def __repr__(self):
        return '%r' % [self.codex_id, self.name, self.email, self.phone, self.department]

    def get_email(self):
        """
        Return User's email
        """
        return self.email

    def get_phone(self):
        """
        Return User's phone number
        """
        return self.phone


@app.route('/submit', methods=['POST'])
def stuff():
    """
    Accept data from the form, generate, display, and email QR code to user
    """

    for user in db.session.query(User).all():
        if request.form['email'] == user.get_email():
            return 'Email address {} already found in database!\
            Please re-enter the form correctly!'.format(request.form['email'])

        if str(request.form['phone_number']) == str(user.get_phone()):
            return 'Phone number {} already found in database!\
            Please re-enter the form correctly!'.format(request.form['phone_number'])

    codex_id = get_current_id()

    user = User(name=request.form['name'], email=request.form['email'],
                phone=request.form['phone_number'], codex_id=codex_id,
                department=DEPARTMENTS[request.form['department']])
    try:
        db.session.add(user)
        db.session.commit()
    except exc.IntegrityError:
        return "Error occurred trying to enter values into the database!"

    img = generate_qr(request.form, codex_id)
    img.save('qr.png')
    img_data = open('qr.png', 'rb').read()
    encoded = base64.b64encode(img_data).decode()

    name = request.form['name']
    from_email = Email(FROM_EMAIL)
    to_email = Email(request.form['email'])
    p = None
    if request.form['email_second_person'] and request.form['name_second_person']:
        cc_email = Email(request.form['email_second_person'])
        name += ', {}'.format(request.form['name_second_person'])
        p = Personalization()
        p.add_to(cc_email)

    subject = 'Registration for CodeX April 2019 - ID {}'.format(codex_id)
    message = """<img src='https://drive.google.com/uc?id=12VCUzNvU53f_mR7Hbumrc6N66rCQO5r-&export=download'>
    <hr>
    {}, your registration is done!
    <br/>
    A QR code has been attached below!
    <br/>
    You're <b>required</b> to present this on the day of the event.
    """.format(name)
    content = Content('text/html', message)
    mail = Mail(from_email, subject, to_email, content)
    if p:
        mail.add_personalization(p)

    attachment = Attachment()
    attachment.type = 'image/png'
    attachment.filename = 'qr.png'
    attachment.content = encoded

    mail.add_attachment(attachment)

    response = sg.client.mail.send.post(request_body=mail.get())
    print(response.status_code)
    print(response.body)
    print(response.headers)

    return 'Please save this QR Code. It has also been emailed to you.<br><img src=\
            "data:image/png;base64, {}"/>'.format(encoded)


@app.route('/users', methods=['GET', 'POST'])
def display_users():
    """
    Display the list of users, after authentication
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == os.getenv('USERNAME'):
            if password == os.getenv('PASSWORD'):
                return render_template('users.html', users=db.session.query(User).all())
            return 'Invalid password!'
        return 'Invalid user!'
    return '''
            <form action="" method="post">
                <p><input type=text name=username required>
                <p><input type=password name=password required>
                <p><input type=submit value=Login>
            </form>
            '''


@app.route('/')
def root():
    """
    Main endpoint. Display the form to the user.
    """
    return app.send_static_file('form.html')


def get_current_id():
    """
    Function to return the latest ID
    """
    try:
        codex_id = db.session.query(User).all()[-1].codex_id
    except IndexError:
        codex_id = 0
    return int(codex_id) + 1


def generate_qr(form_data, codex_id):
    """
    Function to generate and return a QR code based on the given data
    """
    return qrcode.make("\nName: {}\nEmail: {}\nCodeX ID: {}\nPhone Number: {}"
                       .format(form_data['name'], form_data['email'],
                               codex_id, form_data['phone_number']))


if __name__ == '__main__':
    app.run()
