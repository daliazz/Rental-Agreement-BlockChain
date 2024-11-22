from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
import requests
import time
import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

# Zain Cash Credentials from .env
zaincash_secret = os.getenv("ZAINCASH_SECRET")
merchant_id = os.getenv("MERCHANT_ID")
msisdn = os.getenv("MSISDN")

# Database file
DATABASE_FILE = "rental_agreement.db"

# Create SQLite database tables
def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            wallet_address TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS apartments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            landlord_wallet TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            price REAL NOT NULL,
            is_available BOOLEAN DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()

# Initialize the database
init_db()

# User Registration
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        wallet_address = data.get('wallet_address')
        role = data.get('role')

        if not all([name, email, password, wallet_address, role]):
            return jsonify({"error": "All fields are required"}), 400

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (name, email, password, wallet_address, role) VALUES (?, ?, ?, ?, ?)',
                       (name, email, password, wallet_address, role))
        conn.commit()
        conn.close()

        return jsonify({"message": "User registered successfully"}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": "User with this email already exists"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# User Login
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        if not all([email, password]):
            return jsonify({"error": "Email and password are required"}), 400

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            return jsonify({
                "message": "Login successful",
                "user": {
                    "id": user[0],
                    "name": user[1],
                    "email": user[2],
                    "wallet_address": user[4],
                    "role": user[5]
                }
            }), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Add Apartment (Landlord)
@app.route('/add-apartment', methods=['POST'])
def add_apartment():
    try:
        data = request.json
        landlord_wallet = data.get('landlord_wallet')
        description = data.get('description')
        location = data.get('location')
        price = data.get('price')

        if not all([landlord_wallet, description, location, price]):
            return jsonify({"error": "All fields are required"}), 400

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO apartments (landlord_wallet, description, location, price) VALUES (?, ?, ?, ?)',
                       (landlord_wallet, description, location, price))
        conn.commit()
        conn.close()

        return jsonify({"message": "Apartment added successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# View Available Apartments (Tenant)
@app.route('/available-apartments', methods=['GET'])
def available_apartments():
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM apartments WHERE is_available = 1')
        apartments = cursor.fetchall()
        conn.close()

        apartments_list = [
            {
                "id": apt[0],
                "landlord_wallet": apt[1],
                "description": apt[2],
                "location": apt[3],
                "price": apt[4],
                "is_available": bool(apt[5])
            }
            for apt in apartments
        ]

        return jsonify(apartments_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Create Zain Cash Payment for Renting an Apartment
@app.route('/create-payment', methods=['POST'])
def create_payment():
    try:
        data = request.json
        amount = data["amount"]  # Amount in JOD
        order_id = data["order_id"]
        redirect_url = data["redirect_url"]

        # Convert JOD to IQD (assuming 1 JOD = 1400 IQD for example)
        amount_in_iqd = int(amount) * 1400

        # Debug: Log the payment creation request
        app.logger.debug(f"Creating payment - Amount in JOD: {amount}, Amount in IQD: {amount_in_iqd}, Order ID: {order_id}")

        # Building payment data for Zain Cash
        payment_data = {
            "amount": amount_in_iqd,  # Amount in IQD
            "serviceType": "Rent Payment",
            "msisdn": msisdn,
            "orderId": order_id,
            "redirectUrl": redirect_url,
            "iat": int(time.time()),
            "exp": int(time.time()) + 60 * 60 * 4  # Expiry time: 4 hours
        }

        # Encode the payment data to JWT token
        token = jwt.encode(payment_data, zaincash_secret, algorithm="HS256")

        # Debug: Log the encoded token
        app.logger.debug(f"Encoded JWT Token: {token}")

        # Send the POST request to Zain Cash API to create payment
        payment_url = 'https://test.zaincash.iq/transaction/init'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        payload = {
            'token': token,
            'merchantId': merchant_id,
            'lang': 'en'
        }

        # URL-encode the payload
        encoded_payload = requests.compat.urlencode(payload)

        response = requests.post(payment_url, data=encoded_payload, headers=headers)

        # Debug: Log the response from ZainCash
        app.logger.debug(f"Response from ZainCash - Status Code: {response.status_code}, Response Text: {response.text}")

        if response.status_code == 200:
            response_data = response.json()
            transaction_id = response_data.get("id")
            if not transaction_id:
                raise Exception("Transaction ID not found in response.")
            payment_redirect_url = f"https://test.zaincash.iq/transaction/pay?id={transaction_id}"
            return jsonify({"payment_url": payment_redirect_url}), 200
        else:
            return jsonify({"error": f"Failed to create payment. Response: {response.text}"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Handle Zain Cash Callback
@app.route('/zaincash-callback', methods=['GET'])
def zaincash_callback():
    try:
        # ZainCash appends a 'token' parameter to the redirect URL after payment
        token = request.args.get('token')

        if not token:
            return jsonify({"error": "Missing token in the callback"}), 400

        # Decode the token to verify the transaction details
        decoded_token = jwt.decode(token, zaincash_secret, algorithms=["HS256"])

        # Debug: Log the decoded token to check its content
        app.logger.debug(f"Decoded Token: {decoded_token}")

        status = decoded_token.get("status")
        order_id = decoded_token.get("orderid")
        transaction_id = decoded_token.get("id")
        message = decoded_token.get("msg")

        # Check the transaction status
        if status == "success":
            # Update the payment status in your system (e.g., mark the apartment as rented)
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute('UPDATE apartments SET is_available = 0 WHERE id = ?', (order_id,))
            conn.commit()
            conn.close()

            return jsonify({"message": "Payment successful and apartment rented successfully"}), 200
        else:
            return jsonify({"error": f"Payment failed with status: {status}, message: {message}"}), 400
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token has expired"}), 400
    except jwt.DecodeError:
        return jsonify({"error": "Failed to decode token"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
