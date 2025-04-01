from flask import Flask
from s3_cloudfront import s3_bp
import os 
app = Flask(__name__)
app.secret_key = os.urandom(24)

app.register_blueprint(s3_bp)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port="5000", debug="True")
