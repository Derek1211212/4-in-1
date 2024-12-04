# app/__init__.py
from flask import Flask
from flask_mysql import MySQL

app = Flask(__name__)
app.config.from_object('config.Config')

mysql = MySQL(app)

from app import routes