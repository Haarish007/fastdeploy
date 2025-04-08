import re
from flask import Blueprint, request, jsonify
from db import db, User

auth_bp = Blueprint('auth_bp', __name__)

# Regex patterns
USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,30}$')
EMAIL_PATTERN = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
PASSWORD_PATTERN = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[\W_]).{8,}$')

def validate_signup_input(username, email, password):
    if not USERNAME_PATTERN.match(username):
        return "Invalid username. Use 3–30 characters (letters, numbers, underscore)."

    if not EMAIL_PATTERN.match(email):
        return "Invalid email format."

    if not PASSWORD_PATTERN.match(password):
        return "Password must be at least 8 characters long with uppercase, lowercase, number, and special character."

    return None

@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({"message": "All fields are required", "status": "error"}), 400

    # Validate input formats
    error = validate_signup_input(username, email, password)
    if error:
        return jsonify({"message": error, "status": "error"}), 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({"message": "Username or email already exists", "status": "error"}), 409

    new_user = User(username=username, email=email)
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully", "status": "success"}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"message": "Email and password are required", "status": "error"}), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"message": "Email not found", "status": "error"}), 401

    if not user.check_password(password):
        return jsonify({"message": "Incorrect password", "status": "error"}), 401

    return jsonify({
        "message": "Login successful",
        "status": "success",
        "user": user.username
    }), 200
