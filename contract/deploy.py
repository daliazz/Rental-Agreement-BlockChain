from web3 import Web3
from solcx import compile_standard, install_solc
import json

# Install the Solidity compiler
install_solc("0.8.0")

# Connect to Ganache
GANACHE_URL = "http://127.0.0.1:7545"
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))

if not web3.is_connected():
    raise Exception("Failed to connect to Ganache")

# Set the default account (e.g., the first account from Ganache)
web3.eth.default_account = web3.eth.accounts[0]

# Load the smart contract source code
with open("RentalAgreement.sol", "r") as file:
    rental_agreement_source = file.read()

# Compile the smart contract
compiled_sol = compile_standard(
    {
        "language": "Solidity",
        "sources": {"RentalAgreement.sol": {"content": rental_agreement_source}},
        "settings": {
            "outputSelection": {
                "*": {
                    "*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]
                }
            }
        },
    },
    solc_version="0.8.0",
)

# Save the compiled contract to a file (optional)
with open("compiled_RentalAgreement.json", "w") as file:
    json.dump(compiled_sol, file)

# Get ABI and bytecode
contract_abi = compiled_sol["contracts"]["RentalAgreement.sol"]["RentalAgreement"]["abi"]
contract_bytecode = compiled_sol["contracts"]["RentalAgreement.sol"]["RentalAgreement"]["evm"]["bytecode"]["object"]

# Deploy the contract
RentalAgreement = web3.eth.contract(abi=contract_abi, bytecode=contract_bytecode)

# Set deployment parameters
landlord = web3.eth.accounts[0]  # Replace with actual landlord address if needed
tenant = web3.eth.accounts[1]    # Replace with actual tenant address if needed
rent_amount = web3.to_wei(1, "ether")  # Example rent amount in Wei
lease_duration = 12  # Lease duration in months

# Build and send the transaction
transaction = RentalAgreement.constructor(landlord, tenant, rent_amount, lease_duration).transact()
tx_receipt = web3.eth.wait_for_transaction_receipt(transaction)

# Get the deployed contract address
contract_address = tx_receipt.contractAddress
print(f"Contract deployed at address: {contract_address}")

# Save contract ABI and address for use in your project
with open("RentalAgreement_ABI.json", "w") as abi_file:
    json.dump(contract_abi, abi_file)

with open("contract_address.txt", "w") as address_file:
    address_file.write(contract_address)
