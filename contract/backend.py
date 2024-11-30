from web3 import Web3
import json
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import bcrypt
import jwt
import sqlite3
import time
from dotenv import load_dotenv
from flask import send_from_directory
from werkzeug.utils import secure_filename


# Load environment variables
load_dotenv()

INFURA_URL = os.getenv("INFURA_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
JWT_SECRET = os.getenv("JWT_SECRET")

# Connect to Ethereum blockchain
web3 = Web3(Web3.HTTPProvider(INFURA_URL))
if not web3.is_connected():
    raise Exception("Failed to connect to Ethereum network.")

ACCOUNT_ADDRESS = web3.eth.account.from_key(PRIVATE_KEY).address

# Load Smart Contract ABI
with open("RentalAgreementABI.json") as abi_file:
    CONTRACT_ABI = json.load(abi_file)

rental_contract = web3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)

# Flask app initialization
app = Flask(__name__)
CORS(app)

DATABASE_FILE = "rental_agreement.db"

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            wallet_address TEXT NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Landlord', 'Tenant', 'Admin'))
        )
    ''')

    # Apartments table with added columns for price in JOD and ETH
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS apartments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            landlord_wallet TEXT NOT NULL,
            location TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            price_in_jod REAL NOT NULL, -- Price in JOD entered by the landlord
            rent_amount_eth REAL NOT NULL, -- Converted ETH price for the smart contract
            lease_duration INTEGER NOT NULL,
            availability TEXT NOT NULL CHECK(availability IN ('Available', 'Unavailable')),
            contract_address TEXT -- Column for the smart contract address
        )
    ''')

    # Apartment photos table to handle multiple photos per apartment
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS apartment_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL,
            photo_url TEXT NOT NULL,
            FOREIGN KEY (apartment_id) REFERENCES apartments (id) ON DELETE CASCADE
        )
    ''')

    # Contracts table for storing agreements between landlords and tenants
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            landlord_wallet TEXT NOT NULL,
            tenant_wallet TEXT NOT NULL,
            apartment_id INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            contract_hash TEXT NOT NULL,
            FOREIGN KEY (apartment_id) REFERENCES apartments (id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()


# Initialize the database
init_db()


# Helper functions
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_token(user_id, role, wallet_address):
    payload = {
        "user_id": user_id,
        "role": role,
        "wallet_address": wallet_address,  # Include wallet_address in the token payload
        "exp": int(time.time()) + 3600  # Token valid for 1 hour
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None

# Routes
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json
        name = data.get('name')
        email = data.get('email')
        wallet_address = data.get('wallet_address')
        phone = data.get('phone')
        password = data.get('password')
        role = data.get('role')

        if not all([name, email, wallet_address, phone, password, role]):
            return jsonify({"error": "All fields are required"}), 400

        hashed_password = hash_password(password)

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (name, email, wallet_address, phone, password, role) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, email, wallet_address, phone, hashed_password, role))
        conn.commit()
        conn.close()

        return jsonify({"message": "User registered successfully"}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": "User with this email or wallet address already exists"}), 400
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

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
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()

        if user and verify_password(password, user[5]):
            token = generate_token(user[0], user[6], user[3])  # Pass user_id, role, and wallet_address
            return jsonify({
                "message": "Login successful",
                "token": token,
                "user": {
                    "id": user[0],
                    "name": user[1],
                    "email": user[2],
                    "wallet_address": user[3],
                    "phone": user[4],
                    "role": user[6]
                }
            }), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/update-profile', methods=['PUT'])
def update_profile():
    try:
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Authorization header missing"}), 401

        decoded = decode_token(token.split("Bearer ")[-1])
        if not decoded:
            return jsonify({"error": "Invalid or expired token"}), 401

        user_id = decoded["user_id"]
        data = request.json
        name = data.get("name")
        phone = data.get("phone")

        if not all([name, phone]):
            return jsonify({"error": "Name and phone are required"}), 400

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users SET name = ?, phone = ? WHERE id = ?
        ''', (name, phone, user_id))
        conn.commit()
        conn.close()

        return jsonify({"message": "Profile updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

JOD_TO_ETH_RATE = 0.001  # Example conversion rate, update this value as needed

@app.route('/add-apartment', methods=['POST'])
def add_apartment():
    try:
        # Ensure the uploads directory exists
        os.makedirs("uploads", exist_ok=True)

        # Extract form fields
        landlord_wallet = request.form.get('landlord_wallet')
        title = request.form.get('title')
        location = request.form.get('location')
        description = request.form.get('description')
        price_in_jod = float(request.form.get('price_in_jod'))  # Input price in JOD
        lease_duration = int(request.form.get('lease_duration'))
        availability = request.form.get('availability')

        # Convert JOD to ETH
        rent_amount_eth = price_in_jod * JOD_TO_ETH_RATE

        # Validate required fields
        if not all([landlord_wallet, title, location, description, price_in_jod, lease_duration, availability]):
            return jsonify({"error": "All fields are required"}), 400

        # Get photos
        photos = request.files.getlist('photos')
        if not photos:
            return jsonify({"error": "At least one photo is required"}), 400

        # Save photos and generate URLs
        photo_urls = []
        for photo in photos:
            photo_filename = secure_filename(f"{title.replace(' ', '_')}_{int(time.time())}_{photo.filename}")
            photo_path = os.path.join("uploads", photo_filename)
            photo.save(photo_path)
            photo_urls.append(f"{request.host_url}uploads/{photo_filename}")

        # Interact with the smart contract to create agreement details
        nonce = web3.eth.get_transaction_count(ACCOUNT_ADDRESS)
        tx = rental_contract.functions.setAgreementDetails(
            int(Web3.to_wei(rent_amount_eth, 'ether')),  # Rent amount in ETH converted to wei
            lease_duration
        ).build_transaction({
            'from': ACCOUNT_ADDRESS,
            'nonce': nonce,
            'gas': 150000,
            'gasPrice': web3.to_wei('20', 'gwei')
        })

        # Sign and send the transaction
        signed_tx = web3.eth.account.sign_transaction(tx, PRIVATE_KEY)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        # Save apartment details to the database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO apartments (
                landlord_wallet, location, title, description, price_in_jod, rent_amount_eth, lease_duration, availability, contract_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (landlord_wallet, location, title, description, price_in_jod, rent_amount_eth, lease_duration, availability, rental_contract.address))
        apartment_id = cursor.lastrowid

        # Save photo URLs to apartment_photos table
        for photo_url in photo_urls:
            cursor.execute('''
                INSERT INTO apartment_photos (apartment_id, photo_url) VALUES (?, ?)
            ''', (apartment_id, photo_url))

        conn.commit()
        conn.close()

        # Return response
        return jsonify({
            "message": "Apartment added successfully",
            "apartment_id": apartment_id,
            "price_in_jod": price_in_jod,
            "rent_amount_eth": rent_amount_eth,
            "contract_address": rental_contract.address,
            "transaction_hash": web3.to_hex(tx_hash),
            "photo_urls": photo_urls
        }), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/landlord-contracts', methods=['GET'])
def landlord_contracts():
    try:
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Authorization header missing"}), 401

        decoded = decode_token(token.split("Bearer ")[-1])
        if not decoded:
            return jsonify({"error": "Invalid or expired token"}), 401

        landlord_wallet = decoded["wallet_address"]

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT c.id, c.tenant_wallet, c.start_date, c.end_date, c.contract_hash, 
                   c.apartment_id, a.title AS apartment_title, a.contract_address, c.status
            FROM contracts c
            JOIN apartments a ON c.apartment_id = a.id
            WHERE a.landlord_wallet = ?
        ''', (landlord_wallet,))
        contracts = cursor.fetchall()

        contracts_list = [
            {
                "id": contract[0],
                "tenant_wallet": contract[1],
                "start_date": contract[2],
                "end_date": contract[3],
                "contract_hash": contract[4],
                "apartment_id": contract[5],
                "apartment_title": contract[6],
                "contract_address": contract[7],
                "status": contract[8]
            }
            for contract in contracts
        ]

        conn.close()
        return jsonify(contracts_list), 200
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/edit-apartment/<int:apartment_id>', methods=['PUT'])
def edit_apartment(apartment_id):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Parse form data
        title = request.form.get('title')
        location = request.form.get('location')
        description = request.form.get('description')
        price_in_jod = float(request.form.get('price_in_jod'))
        lease_duration = int(request.form.get('lease_duration'))
        availability = request.form.get('availability')

        # Validate inputs
        if not all([title, location, description, price_in_jod, lease_duration, availability]):
            return jsonify({"error": "All fields are required"}), 400

        # Update apartment details in the database
        cursor.execute('''
            UPDATE apartments
            SET title = ?, location = ?, description = ?, price_in_jod = ?, 
                lease_duration = ?, availability = ?
            WHERE id = ?
        ''', (title, location, description, price_in_jod, lease_duration, availability, apartment_id))

        # Handle photo updates (if provided)
        photos = request.files.getlist('photos')
        if photos:
            # Delete existing photos for this apartment
            cursor.execute('DELETE FROM apartment_photos WHERE apartment_id = ?', (apartment_id,))
            for photo in photos:
                photo_filename = secure_filename(f"{title.replace(' ', '_')}_{int(time.time())}_{photo.filename}")
                photo_path = os.path.join("uploads", photo_filename)
                photo.save(photo_path)
                photo_url = f"{request.host_url}uploads/{photo_filename}"
                cursor.execute('INSERT INTO apartment_photos (apartment_id, photo_url) VALUES (?, ?)', (apartment_id, photo_url))

        conn.commit()
        conn.close()

        return jsonify({"message": "Apartment updated successfully"}), 200

    except Exception as e:
        print(f"Error during update: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500




@app.route('/delete-apartment/<int:apartment_id>', methods=['DELETE'])
def delete_apartment(apartment_id):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Delete photos associated with the apartment from the apartment_photos table
        cursor.execute('DELETE FROM apartment_photos WHERE apartment_id = ?', (apartment_id,))

        # Delete the apartment record from the apartments table
        cursor.execute('DELETE FROM apartments WHERE id = ?', (apartment_id,))

        conn.commit()
        conn.close()

        return jsonify({"message": "Apartment and associated photos deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/landlord-apartments', methods=['GET'])
def landlord_apartments():
    try:
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Authorization header missing"}), 401

        decoded = decode_token(token.split("Bearer ")[-1])
        if not decoded or "error" in decoded:
            return jsonify(decoded or {"error": "Invalid or expired token"}), 401

        landlord_wallet = decoded.get("wallet_address")
        if not landlord_wallet:
            return jsonify({"error": "Unauthorized access"}), 403

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Query apartments
        cursor.execute('''
            SELECT id, landlord_wallet, title, location, description, price_in_jod, 
                   rent_amount_eth, lease_duration, availability, contract_address
            FROM apartments WHERE landlord_wallet = ?
        ''', (landlord_wallet,))
        apartments = cursor.fetchall()

        apartments_list = []
        for apt in apartments:
            apt_id = apt[0]
            cursor.execute('SELECT photo_url FROM apartment_photos WHERE apartment_id = ?', (apt_id,))
            photos = cursor.fetchall()
            photo_urls = [photo[0] for photo in photos]  # Extract photo URLs

            apartments_list.append({
                "id": apt_id,
                "landlord_wallet": apt[1],
                "title": apt[2],
                "location": apt[3],
                "description": apt[4],
                "price_in_jod": apt[5],  # Include price in JOD
                "rent_amount_eth": apt[6],  # Include rent amount in ETH
                "lease_duration": apt[7],
                "availability": apt[8],
                "contract_address": apt[9],
                "photo_urls": photo_urls  # Include photo URLs in the response
            })

        conn.close()
        return jsonify(apartments_list), 200
    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/available-apartments', methods=['GET'])
def available_apartments():
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Fetch apartments and join photos
        cursor.execute('''
            SELECT a.id, a.landlord_wallet, a.title, a.location, a.description, a.rent_amount,
                   a.lease_duration, a.availability, a.contract_address, 
                   GROUP_CONCAT(p.photo_url) AS photos
            FROM apartments a
            LEFT JOIN apartment_photos p ON a.id = p.apartment_id
            WHERE a.availability = "Available"
            GROUP BY a.id
        ''')
        apartments = cursor.fetchall()
        conn.close()

        # Format the response to include all photo URLs
        apartments_list = [
            {
                "id": apt[0],
                "landlord_wallet": apt[1],
                "title": apt[2],
                "location": apt[3],
                "description": apt[4],
                "rent_amount": apt[5],
                "lease_duration": apt[6],
                "availability": apt[7],
                "contract_address": apt[8],
                "photos": apt[9].split(",") if apt[9] else []  # Split photo URLs into a list
            }
            for apt in apartments
        ]

        return jsonify(apartments_list), 200

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    return send_from_directory("uploads", filename)

if __name__ == "__main__":
    app.run(debug=True)
