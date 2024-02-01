import smtplib
from email.mime.text import MIMEText


EMAIL_TEMPLATE = """
Hello {name}!

Please click the below link, or copy it into your browser to verify your account!:
{verification_url}

Thanks for interacting with my cookbook!

Dennis
"""


def verify_email(email, name, verification_url):
    msg = MIMEText(EMAIL_TEMPLATE.format(name=name, verification_url=verification_url))
    msg['Subject'] = "Verify your account!"
    me = "chef@dennishilhorst.nl"
    msg['From'] = me
    msg['To'] = email

    with smtplib.SMTP("localhost") as s:
        s.sendmail(me, [email], msg.as_string())
