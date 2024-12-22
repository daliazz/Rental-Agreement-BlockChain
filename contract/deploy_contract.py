import json
import os
from web3 import Web3
from solcx import compile_source, install_solc
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Install Solidity compiler
install_solc('0.8.0')

# Read the Solidity contract source code
with open('RentalAgreement.sol', 'r') as file:
    contract_source_code = file.read()

# Compile the contract
compiled_sol = compile_source(contract_source_code, solc_version='0.8.0')
contract_id, contract_interface = compiled_sol.popitem()

# Extract ABI and bytecode
abi = contract_interface['abi']
bytecode = contract_interface['bin']

# Save ABI for frontend and backend use
with open('RentalAgreementABI.json', 'w') as abi_file:
    json.dump(abi, abi_file)

# Connect to Ethereum network
INFURA_URL = os.getenv('INFURA_URL')
web3 = Web3(Web3.HTTPProvider(INFURA_URL))

# Ensure connection is successful
if not web3.is_connected():
    raise Exception("Failed to connect to Ethereum network.")

# Set up account
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
ACCOUNT_ADDRESS = web3.eth.account.from_key(PRIVATE_KEY).address

# Get the nonce Represents the number of transactions sent from the account.
nonce = web3.eth.get_transaction_count(ACCOUNT_ADDRESS)

# Create the contract instance for deployment
RentalAgreement = web3.eth.contract(abi=abi, bytecode=bytecode)

# Replace constructor arguments to match your contract
landlord_wallet = Web3.to_checksum_address(os.getenv('LANDLORD_WALLET'))  # Ensure this is provided
rent_amount = int(os.getenv('RENT_AMOUNT'))  # Rent amount in Wei
lease_duration = int(os.getenv('LEASE_DURATION'))  # Lease duration in months

# Build transaction for deploying the contract
transaction = RentalAgreement.constructor(
    landlord_wallet,  # Landlord address
    rent_amount,      # Rent amount (Wei)
    lease_duration    # Lease duration (months)
).build_transaction({
    'from': ACCOUNT_ADDRESS,
    'nonce': nonce,
    'gas': 3000000,  # Adjust gas limit as needed
    'gasPrice': web3.to_wei('20', 'gwei')  # Adjust gas price as needed
})

# Sign the transaction
signed_txn = web3.eth.account.sign_transaction(transaction, private_key=PRIVATE_KEY)

# Send the transaction
tx_hash = web3.eth.send_raw_transaction(signed_txn.raw_transaction)

print(f"Deploying contract... Transaction hash: {web3.to_hex(tx_hash)}")

# Wait for the transaction receipt
tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

contract_address = tx_receipt.contractAddress
print(f"Contract deployed at address: {contract_address}")

# Save the contract address for later use
with open('contract_address.txt', 'w') as file:
    file.write(contract_address)

print("Deployment completed successfully.")
