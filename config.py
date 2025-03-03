import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'fa470fe714e44404511cbad16224f52777068d05bb5c29bc')  # Fallback to default if not set
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'mysql-d5c4473-derickbill3-8b6b.c.aivencloud.com')  # Default to localhost
    MYSQL_USER = os.getenv('MYSQL_USER', 'avnadmin')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', 'AVNS_4pkcb6Wsv03C7lebWrH')
    MYSQL_DB = os.getenv('MYSQL_DB', 'MecApp')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 16484))  # Convert port to an integer


MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587  # Use 587 for TLS
MAIL_USE_TLS = True  # Use TLS instead of SSL
MAIL_USERNAME = 'Derickbill3@gmail.com'  # Your Gmail address
MAIL_PASSWORD = 'bxyw odgw iwvl tpad'  # Your Gmail password or App password
MAIL_DEFAULT_SENDER = 'Derickbill3@gmail.com'  # Sender's email address
