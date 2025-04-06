from flask import Flask
from flask_cors import CORS
from s3_cloudfront import s3_bp
import os

app = Flask(__name__)
app.register_blueprint(s3_bp)

CORS(app,supports_credentials=True)

app.secret_key = os.urandom(24)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8004, debug=True)
    
@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE, PUT")
    return response