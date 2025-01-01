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
from solcx import compile_source
from datetime import datetime, timedelta
from decimal import Decimal

# Load environment variables
load_dotenv()

GANACHE_URL = os.getenv("GANACHE_URL")
JWT_SECRET = os.getenv("JWT_SECRET")

# Connect to Ethereum blockchain
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))
if not web3.is_connected():
    raise Exception("Failed to connect to Ethereum network.")


# Load Smart Contract ABI
with open("RentalAgreementABI.json") as abi_file:
    CONTRACT_ABI = json.load(abi_file)

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
            rent_amount REAL,
            lease_duration INTEGER,
            start_date TEXT,
            end_date TEXT,
            contract_hash TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            contract_address TEXT, -- Column for the smart contract address
            next_payment_date TEXT,
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

        # Save apartment details to the database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO apartments (
                landlord_wallet, location, title, description, price_in_jod, rent_amount_eth, lease_duration, availability, contract_address
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (landlord_wallet, location, title, description, price_in_jod, rent_amount_eth, lease_duration, availability, None))
        apartment_id = cursor.lastrowid

        # Save photo URLs to the apartment_photos table
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
            "photo_urls": photo_urls
        }), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/tenant-contracts', methods=['GET'])
def get_tenant_contracts():
    try:
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Authorization header missing"}), 401

        decoded = decode_token(token.split("Bearer ")[-1])
        if not decoded:
            return jsonify({"error": "Invalid or expired token"}), 401

        tenant_wallet = decoded.get("wallet_address")
        status = request.args.get("status", "all")  # Get status query parameter

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Adjust query based on status
        if status == "pending":
            query = '''
                SELECT c.id, c.landlord_wallet, c.apartment_id, c.start_date, c.end_date, c.next_payment_date, c.status, c.rent_amount ,c.contract_address 
                FROM contracts c
                WHERE c.tenant_wallet = ? AND c.status = "Pending"
            '''
        elif status == "active":
            query = '''
                SELECT c.id, c.landlord_wallet, c.apartment_id, c.start_date, c.end_date, c.next_payment_date, c.status, c.rent_amount,c.contract_address 
                FROM contracts c
                WHERE c.tenant_wallet = ? AND c.status = "Active"
            '''
        else:
            query = '''
                SELECT c.id, c.landlord_wallet, c.apartment_id, c.start_date, c.end_date, c.next_payment_date, c.status, c.rent_amount ,c.contract_address 
                FROM contracts c
                WHERE c.tenant_wallet = ?
            '''

        cursor.execute(query, (tenant_wallet,))
        contracts = cursor.fetchall()

        # Format contracts for response
        contracts_list = [
            {
                "id": contract[0],
                "landlord_wallet": contract[1],
                "apartment_id": contract[2],
                "start_date": contract[3] if contract[3] else "Not Specified",
                "end_date": contract[4] if contract[4] else "Not Specified",
                "next_payment_due": contract[5] if contract[5] else "Not Specified",
                "status": contract[6],
                "rent_amount": contract[7],  # Include rent amount
                "contract_address": contract[8]
            }
            for contract in contracts
        ]

        conn.close()
        return jsonify(contracts_list), 200

    except Exception as e:
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
        status_filter = request.args.get("status")  # Get the status filter from query parameters

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Build the SQL query dynamically based on the status filter
        query = '''
            SELECT c.id, c.tenant_wallet, c.start_date, c.end_date, c.contract_hash, 
                   c.apartment_id, a.title AS apartment_title, a.contract_address, c.status,
                   c.rent_amount, c.lease_duration
            FROM contracts c
            JOIN apartments a ON c.apartment_id = a.id
            WHERE a.landlord_wallet = ?
        '''
        params = [landlord_wallet]

        if status_filter:
            query += ' AND c.status = ?'
            params.append(status_filter)

        cursor.execute(query, params)
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
                "status": contract[8],
                "rent_amount": contract[9],
                "lease_duration": contract[10]
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
        # Check for Authorization header
        token = request.headers.get("Authorization")
        if not token:
            return jsonify({"error": "Authorization header missing"}), 401

        # Decode the token
        decoded = decode_token(token.split("Bearer ")[-1])
        if not decoded:
            return jsonify({"error": "Invalid or expired token"}), 401

        landlord_wallet = decoded.get("wallet_address")
        if not landlord_wallet:
            return jsonify({"error": "Unauthorized access"}), 403

        # Connect to database and fetch apartments
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, landlord_wallet, title, location, description, price_in_jod, 
                   rent_amount_eth, lease_duration, availability, contract_address
            FROM apartments WHERE landlord_wallet = ?
        ''', (landlord_wallet,))
        apartments = cursor.fetchall()

        apartments_list = []
        for apt in apartments:
            apt_id = apt[0]

            # Fetch photo URLs for the apartment
            cursor.execute('SELECT photo_url FROM apartment_photos WHERE apartment_id = ?', (apt_id,))
            photos = cursor.fetchall()
            photo_urls = [photo[0] for photo in photos]  # Extract photo URLs

            # Append apartment details to the list
            apartments_list.append({
                "id": apt_id,
                "landlord_wallet": apt[1],
                "title": apt[2],
                "location": apt[3],
                "description": apt[4],
                "price_in_jod": apt[5],
                "rent_amount_eth": apt[6],
                "lease_duration": apt[7],
                "availability": apt[8],
                "contract_address": apt[9] if apt[9] else "Not Available",  # Handle None gracefully
                "photo_urls": photo_urls
            })

        conn.close()
        return jsonify(apartments_list), 200

    except sqlite3.Error as db_err:
        print(f"Database error: {db_err}")
        return jsonify({"error": "Database error"}), 500

    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/available-apartments', methods=['GET'])
def available_apartments():
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Query apartments and fetch photos separately
        cursor.execute('''
            SELECT id, landlord_wallet, title, location, description, price_in_jod, 
                   rent_amount_eth, lease_duration, availability, contract_address
            FROM apartments WHERE availability = "Available"
        ''')
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
                "price_in_jod": apt[5],
                "rent_amount_eth": apt[6],
                "lease_duration": apt[7],
                "availability": apt[8],
                "contract_address": apt[9] if apt[9] else "Not Available",
                "photo_urls": photo_urls  # Include photo URLs in the response
            })

        conn.close()
        return jsonify(apartments_list), 200

    except sqlite3.Error as db_err:
        print(f"Database error: {str(db_err)}")
        return jsonify({"error": "Database error"}), 500

    except Exception as e:
        print(f"Error fetching apartments: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

## Routes


@app.route('/contracts/initiate', methods=['POST'])
def initiate_contract():
    try:
        data = request.json
        tenant_wallet = Web3.to_checksum_address(data['tenant_wallet'])
        apartment_id = int(data.get('apartment_id'))
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        # Validate the input
        if not all([apartment_id, start_date, end_date]):
            return jsonify({"error": "Apartment ID, start_date, and end_date are required"}), 400

        # Convert dates to datetime objects
        try:
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

        # Ensure the rental period is at least 1 month
        rental_period_days = (end_date_obj - start_date_obj).days
        if rental_period_days < 30:
            return jsonify({"error": "The rental period must be at least 1 month."}), 400

        # Connect to the database
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        # Fetch apartment details
        cursor.execute('''
            SELECT id, landlord_wallet, rent_amount_eth, lease_duration 
            FROM apartments 
            WHERE id = ?
        ''', (apartment_id,))
        apartment_details = cursor.fetchone()

        if not apartment_details:
            return jsonify({"error": "Apartment not found"}), 404

        fetched_apartment_id, landlord_wallet, rent_amount_eth, lease_duration = apartment_details
        lease_duration = int(lease_duration)

        # Ensure the fetched apartment ID matches the provided ID
        if fetched_apartment_id != apartment_id:
            return jsonify({"error": "Apartment ID mismatch detected"}), 400

        # Save contract details to the database
        next_payment_date = start_date_obj + timedelta(days=30)

        cursor.execute('''
            INSERT INTO contracts (
                landlord_wallet, tenant_wallet, apartment_id, rent_amount, lease_duration, 
                start_date, end_date, next_payment_date, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (landlord_wallet, tenant_wallet, fetched_apartment_id, rent_amount_eth, lease_duration,
              start_date, end_date, next_payment_date.strftime('%Y-%m-%d'), 'Pending'))
        conn.commit()
        conn.close()

        return jsonify({
            "message": "Contract details saved successfully. Deployment will occur upon signing.",
            "landlord": landlord_wallet,
            "tenant": tenant_wallet,
            "apartment_id": fetched_apartment_id,
            "rent_amount_eth": rent_amount_eth,
            "lease_duration": lease_duration,
            "start_date": start_date,
            "end_date": end_date,
            "next_payment_date": next_payment_date.strftime('%Y-%m-%d')
        }), 200

    except sqlite3.Error as db_error:
        app.logger.error(f"Database error: {db_error}")
        return jsonify({"error": "Database error occurred"}), 500
    except Exception as e:
        app.logger.error(f"Unexpected error: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500
    
    
@app.route('/contracts/sign', methods=['POST'])
def sign_contract():
    try:
        tx_hash = None 
        data = request.json
        app.logger.info(f"Debug: Payload received: {data}")
        apartment_id = data['apartment_id']
        wallet_address = data['wallet_address']
        private_key = data['private_key']
        user_role = data['role']

        # Fetch the contract address and current status
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT contract_address, status, start_date, landlord_wallet, tenant_wallet, rent_amount, lease_duration FROM contracts WHERE apartment_id = ?', (apartment_id,))
        result = cursor.fetchone()

        if not result:
            app.logger.error(f"Debug: Contract not found for apartment_id: {apartment_id}")
            return jsonify({"error": "Contract not found."}), 404

        contract_address, current_status, start_date, landlord_wallet, tenant_wallet, rent_amount, lease_duration = result
        app.logger.info(f"Debug: Contract address: {contract_address}, Current status: {current_status}")

        # Verify private key matches wallet
        provided_account = web3.eth.account.from_key(private_key).address
        if wallet_address.lower() != provided_account.lower():
            app.logger.error("Debug: Private key does not match wallet address.")
            return jsonify({"error": "Private key does not match the provided wallet address."}), 400

        # Initialize new_status to avoid unassigned variable errors
        new_status = None

        # Build and sign transaction
        nonce = web3.eth.get_transaction_count(wallet_address)

        if user_role == 'Landlord' and current_status == 'Pending':
            # Landlord deploys the contract
            compiled_contract_path = "RentalAgreement.sol"
            with open(compiled_contract_path, 'r') as file:
                contract_source_code = file.read()

            compiled_sol = compile_source(contract_source_code, solc_version='0.8.0')
            contract_id, contract_interface = compiled_sol.popitem()

            abi = contract_interface['abi']
            bytecode = contract_interface['bin']
            contract = web3.eth.contract(abi=abi, bytecode=bytecode)

            tx = contract.constructor(
                Web3.to_checksum_address(landlord_wallet),
                Web3.to_checksum_address(tenant_wallet),  # Include tenant address in deployment
                int(float(rent_amount) * 10**18),
                lease_duration
            ).build_transaction({
                'from': wallet_address,
                'nonce': nonce,
                'gas': 1500000,
                'gasPrice': web3.to_wei('20', 'gwei')
            })

            signed_tx = web3.eth.account.sign_transaction(tx, private_key)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            
            contract_address = tx_receipt.contractAddress
            contract = web3.eth.contract(address=contract_address, abi=abi)

            # Landlord signs the contract
            tx_sign = contract.functions.signAgreement().build_transaction({
                'from': wallet_address,
                'nonce': nonce + 1,  # Increment nonce for signing
                'gas': 300000,
                'gasPrice': web3.to_wei('20', 'gwei')
            })
            signed_tx_sign = web3.eth.account.sign_transaction(tx_sign, private_key)
            tx_sign_hash = web3.eth.send_raw_transaction(signed_tx_sign.raw_transaction)
            web3.eth.wait_for_transaction_receipt(tx_sign_hash)

            # Verify isSigned is updated
            is_signed = contract.functions.isSigned().call()
            app.logger.info(f"Debug: isSigned after landlord signing: {is_signed}")
            

            new_status = 'Landlord Signed'

            # Update the contract address and status in the database
            cursor.execute('UPDATE contracts SET contract_address = ?, status = ? WHERE apartment_id = ?', 
                           (contract_address, new_status, apartment_id))
            app.logger.info(f"Debug: Contract deployed and signed at {contract_address}")

        if user_role == 'Tenant' and current_status == 'Landlord Signed':
            # Tenant signing
            contract = web3.eth.contract(address=contract_address, abi=CONTRACT_ABI)
            contract_state = contract.functions.state().call()
            app.logger.info(f"Debug: Contract state before tenant signing: {contract_state}")
            if contract_state != 0:  # Assuming 0 = Pending
                 app.logger.error("Error: Contract is not in the Pending state.")
                 return jsonify({"error": "Contract is not in the Pending state."}), 400
            nonce = web3.eth.get_transaction_count(wallet_address)
            tx = contract.functions.signAgreement().build_transaction({
                'from': wallet_address,
                'nonce': nonce,
                'gas': 300000,
                'gasPrice': web3.to_wei('20', 'gwei')
            })
            signed_tx = web3.eth.account.sign_transaction(tx, private_key)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            # Process logs from the transaction receipt
            try:
               for log in tx_receipt.logs:
                 decoded_log = contract.events.AgreementSigned().process_log(log)
                 app.logger.info(f"Event Emitted: {decoded_log}")
            except Exception as e:
             app.logger.error(f"Error decoding event log: {str(e)}")

            # Debugging: Fetch the state from the smart contract
            contract_state = contract.functions.state().call()
            is_signed = contract.functions.isSigned().call()
            app.logger.info(f"Debug: Contract state after tenant signing: {contract_state}, isSigned: {is_signed}")

            if contract_state == 1:  # Active state
                new_status = 'Active'
                app.logger.info(f"Debug: Contract is now active for apartment_id: {apartment_id}")
                current_status=new_status
        if user_role == 'Tenant' and current_status == 'Active':
            # Tenant paying
            contract = web3.eth.contract(address=contract_address, abi=CONTRACT_ABI)
            nonce = web3.eth.get_transaction_count(wallet_address)
            # Fetch rent amount from the database
            payment_amount = int(float(rent_amount) * 10**18)  # Convert rent amount to Wei
            app.logger.info(f"Debug: Payment amount calculated as {payment_amount} Wei")

            tx = contract.functions.makePayment().build_transaction({
                'from': wallet_address,
                'value': payment_amount,  # Set payment amount here
                'nonce': nonce,
                'gas': 300000,
                'gasPrice': web3.to_wei('20', 'gwei')
            })
            signed_tx = web3.eth.account.sign_transaction(tx, private_key)
            tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

            # Debugging: Fetch the state from the smart contract
            contract_state = contract.functions.state().call()
            app.logger.info(f"Debug: Contract state after payment: {contract_state}")

            # Update next payment date
            from datetime import datetime, timedelta
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            next_payment_date = start_date_obj + timedelta(days=30)
            cursor.execute('UPDATE contracts SET next_payment_date = ? WHERE apartment_id = ?', 
                           (next_payment_date.strftime('%Y-%m-%d'), apartment_id))
            app.logger.info(f"Debug: Next payment date set to {next_payment_date}")

        # Ensure new_status is set before updating
        if new_status:
            cursor.execute('UPDATE contracts SET status = ? WHERE apartment_id = ?', (new_status, apartment_id))
            app.logger.info(f"Debug: Updated contract status to '{new_status}' for apartment_id: {apartment_id}")

        # Optionally update apartment availability if the contract becomes active
        if new_status == 'Active':
            cursor.execute('UPDATE apartments SET availability = ? WHERE id = ?', ('Unavailable', apartment_id))

        conn.commit()
        conn.close()

        return jsonify({
            "message": "Contract signed successfully.",
            "transaction_hash": web3.to_hex(tx_hash),
            "new_status": new_status
        }), 200

    except Exception as e:
        app.logger.error(f"Error during sign_contract: {str(e)}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

@app.route('/contracts/pay', methods=['POST'])
def make_payment():
    try:
        data = request.json
        apartment_id = data['apartment_id']
        wallet_address = data['wallet_address']
        private_key = data['private_key']

        # Connect to the database and fetch contract details
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT contract_address, rent_amount FROM contracts WHERE apartment_id = ?', (apartment_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"error": "Contract not found."}), 404

        contract_address, rent_amount = result
        contract = web3.eth.contract(address=contract_address, abi=CONTRACT_ABI)

        # Calculate payment amount from the database
        payment_amount = int(float(rent_amount) * 10**18)  # Convert rent amount to Wei

        # Fetch the nonce for the tenant's wallet
        nonce = web3.eth.get_transaction_count(wallet_address)

        # Build the transaction
        tx = contract.functions.makePayment().build_transaction({
            'from': wallet_address,
            'value': payment_amount,
            'nonce': nonce,
            'gas': 300000,
            'gasPrice': web3.to_wei('20', 'gwei')
        })

        # Sign and send the transaction using the tenant's private key
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        web3.eth.wait_for_transaction_receipt(tx_hash)

        return jsonify({"message": "Payment made successfully.", "transaction_hash": web3.to_hex(tx_hash)}), 200

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500


@app.route('/contracts/terminate', methods=['POST'])
def terminate_contract():
    try:
        data = request.json
        apartment_id = data['apartment_id']
        role = data['role']
        wallet_address = data['wallet_address']
        private_key = data.get('private_key')

        if not private_key:
            return jsonify({"error": "Private key is required."}), 400

        # Verify that the private key matches the provided wallet address
        provided_account = web3.eth.account.from_key(private_key).address
        if provided_account.lower() != wallet_address.lower():
            return jsonify({"error": "Private key does not match the provided wallet address."}), 400

        # Fetch contract details
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT contract_address, rent_amount FROM contracts WHERE apartment_id = ?', (apartment_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"error": "Contract not found."}), 404

        contract_address, rent_amount = result
        contract = web3.eth.contract(address=contract_address, abi=CONTRACT_ABI)
        
        rent_amount_decimal = Decimal(str(rent_amount))  # Ensure exact value
        refund_amount_wei = int(rent_amount_decimal * Decimal(10**18))

        app.logger.info(f"Role: {role}, Value: {0 if role == 'Tenant' else refund_amount_wei}")


        # Build the transaction to call terminateAgreement
        nonce = web3.eth.get_transaction_count(wallet_address)
        tx = contract.functions.terminateAgreement().build_transaction({
            'from': wallet_address,
            'value': 0 if role == 'tenant' else refund_amount_wei,   # Set the refund amount
            'nonce': nonce,
            'gas': 300000,
            'gasPrice': web3.to_wei('20', 'gwei')
        })

        # Sign and send the transaction
        signed_tx = web3.eth.account.sign_transaction(tx, private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        if tx_receipt.status != 1:
            raise Exception("Transaction failed on the blockchain.")

        # Update the database to mark the contract as terminated
        cursor.execute('UPDATE contracts SET status = ? WHERE apartment_id = ?', ('Terminated', apartment_id))
        conn.commit()
        conn.close()

        return jsonify({
            "message": "Contract terminated successfully.",
            "transaction_hash": web3.to_hex(tx_hash)
        }), 200

    except Exception as e:
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500



@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    return send_from_directory("uploads", filename)

if __name__ == "__main__":
    app.run(debug=True)