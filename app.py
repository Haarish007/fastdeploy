from flask import Flask
from flask_cors import CORS
from s3_cloudfront import s3_bp
from auth import auth_bp
from db import db  # <- this is now clean
import os

app = Flask(__name__)

# ✅ Set config here
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:pentafox@localhost:5432/fastdeploy'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ✅ Init db here
db.init_app(app)

# Register blueprints
app.register_blueprint(s3_bp)
app.register_blueprint(auth_bp)

from flask_cors import CORS

# Add both local and production frontend URLs here
CORS(app, origins=["https://deployzone.pentafox.in", "http://localhost:5173"], supports_credentials=True)
app.secret_key = os.urandom(24)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8004, debug=True)