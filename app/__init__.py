from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_moment import Moment

app = Flask(__name__)
app.config.from_object(Config)
login = LoginManager(app)
login.login_view = 'login'
db = SQLAlchemy(app)
migrate = Migrate(app, db)
moment = Moment(app)

from app import routes, models, errors

# from app import app, db
# from app.models import User, Post
# import sqlalchemy as sa
# app.app_context().push()
# db.create_all()
# db.session.add(u)
# db.session.commit()