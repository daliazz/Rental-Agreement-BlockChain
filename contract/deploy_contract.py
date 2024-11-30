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
# This value is required to prevent double-spending and to create a unique transaction.

nonce = web3.eth.get_transaction_count(ACCOUNT_ADDRESS)

# Create the contract instance for deployment
RentalAgreement = web3.eth.contract(abi=abi, bytecode=bytecode)

# Build transaction for deploying the contract
transaction = RentalAgreement.constructor().build_transaction({
    'from': ACCOUNT_ADDRESS,
    'nonce': nonce,
    'gas': 1500000,  # Adjust gas limit as needed
    'gasPrice': web3.to_wei('30', 'gwei')  # Adjust gas price as needed
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

# Create the contract instance at the deployed address
rental_agreement = web3.eth.contract(address=contract_address, abi=abi)

# Example: Set Rent Amount and Lease Duration in a Single Call
rent_amount = 1000  # Example rent amount
lease_duration = 12  # Example lease duration in months

# Build transaction to set agreement details
set_agreement_tx = rental_agreement.functions.setAgreementDetails(rent_amount, lease_duration).build_transaction({
    'from': ACCOUNT_ADDRESS,
    'nonce': web3.eth.get_transaction_count(ACCOUNT_ADDRESS),
    'gas': 150000,
    'gasPrice': web3.to_wei('30', 'gwei')
})

# Sign and send the transaction
signed_agreement_tx = web3.eth.account.sign_transaction(set_agreement_tx, private_key=PRIVATE_KEY)
agreement_tx_hash = web3.eth.send_raw_transaction(signed_agreement_tx.raw_transaction)

print(f"Setting agreement details... Transaction hash: {web3.to_hex(agreement_tx_hash)}")
