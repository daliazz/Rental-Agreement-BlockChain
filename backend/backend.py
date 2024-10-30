import os
import requests
import jwt
import json
from web3 import Web3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
infura_url = os.getenv("INFURA_URL")
private_key = os.getenv("PRIVATE_KEY")
contract_address = os.getenv("CONTRACT_ADDRESS")

# Connect to Ethereum network
web3 = Web3(Web3.HTTPProvider(infura_url))

# Load the ABI for the smart contract
with open('RentalAgreementABI.json', 'r') as abi_file:
    contract_abi = json.load(abi_file)

contract = web3.eth.contract(address=contract_address, abi=contract_abi)

def handle_zaincash_callback(token):
    """Handle the Zain Cash callback by decoding the token and logging the payment on-chain."""
    try:
        # Decode the Zain Cash JWT token
        zaincash_secret = os.getenv("ZAINCASH_SECRET")
        decoded_token = jwt.decode(token, zaincash_secret, algorithms=["HS256"])

        status = decoded_token.get("status")
        order_id = decoded_token.get("orderid")
        transaction_id = decoded_token.get("id")
        amount = decoded_token.get("amount")

        if status == "success":
            # Record the payment on the blockchain
            tx_hash = record_off_chain_payment(order_id, amount, "Zain Cash", transaction_id)
            return tx_hash
        else:
            raise Exception("Payment failed or status is not success.")
    except Exception as e:
        raise Exception(f"Error handling Zain Cash callback: {str(e)}")

def record_off_chain_payment(order_id, amount, payment_method, transaction_id):
    """Record the off-chain Zain Cash payment on the blockchain."""
    account_address = os.getenv("ACCOUNT_ADDRESS")  # Default admin/landlord address
    nonce = web3.eth.getTransactionCount(account_address)

    # Build the transaction to log the payment
    txn = contract.functions.recordOffChainPayment(
        int(order_id), amount, payment_method, transaction_id
    ).buildTransaction({
        'from': account_address,
        'nonce': nonce,
        'gas': 200000,
        'gasPrice': web3.toWei('50', 'gwei')
    })

    # Sign and send the transaction
    signed_txn = web3.eth.account.signTransaction(txn, private_key=private_key)
    tx_hash = web3.eth.sendRawTransaction(signed_txn.rawTransaction)
    web3.eth.waitForTransactionReceipt(tx_hash)

    return web3.toHex(tx_hash)