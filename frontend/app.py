import streamlit as st
from backend import handle_zaincash_callback, record_off_chain_payment
import json

# Title of the app
st.title("Blockchain Rental Agreement with Zain Cash Payment")

# JavaScript to connect MetaMask and retrieve the user's address
metamask_js = """
<script>
async function connectWallet() {
    if (typeof window.ethereum !== 'undefined') {
        try {
            const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
            const userAddress = accounts[0];
            document.getElementById('userAddress').value = userAddress;
        } catch (error) {
            console.error('User denied account access or other error:', error);
        }
    } else {
        alert('MetaMask is not installed. Please install it to use this feature.');
    }
}
</script>
<button onclick="connectWallet()">Connect Wallet</button>
<input type="text" id="userAddress" readonly>
"""

# Display the MetaMask connection button
st.markdown(metamask_js, unsafe_allow_html=True)

# Input for off-chain Zain Cash payment token (manually for testing purposes)
st.subheader("Enter Zain Cash Callback Token")
token = st.text_input("Zain Cash Token")

if st.button("Confirm Payment"):
    if token:
        try:
            # Call the backend to handle the Zain Cash payment
            tx_hash = handle_zaincash_callback(token)
            st.success(f"Payment confirmed and logged on blockchain! Transaction Hash: {tx_hash}")
        except Exception as e:
            st.error(f"Error processing payment: {e}")
    else:
        st.error("Please enter a valid token.")