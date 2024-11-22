import streamlit as st
import requests

# Set up the base URL for backend API
BASE_URL = "http://localhost:5000"  # Change this to the address of your deployed backend
ETH_TO_JOD_RATE = 1000  # Example conversion rate, adjust as per the latest exchange rate

# Define session state for user authentication
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "wallet_address" not in st.session_state:
    st.session_state.wallet_address = None
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# User Registration and Login
st.title("Blockchain-Based Rental Agreement System")

if not st.session_state.logged_in:
    menu = ["Login", "Register"]
    choice = st.selectbox("Menu", menu)

    if choice == "Register":
        st.header("Create an Account")
        name = st.text_input("Full Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        wallet_address = st.text_input("Ethereum Wallet Address")
        role = st.selectbox("Select your role", ["Select", "Landlord", "Tenant"])

        if st.button("Register"):
            if name and email and password and wallet_address and role != "Select":
                user_data = {
                    "name": name,
                    "email": email,
                    "password": password,
                    "wallet_address": wallet_address,
                    "role": role
                }
                response = requests.post(f"{BASE_URL}/register", json=user_data)
                if response.status_code == 200:
                    st.success(f"Account created successfully as a {role}.")
                else:
                    st.error(f"Error: {response.json().get('error')}")
            else:
                st.error("Please fill in all fields.")

    elif choice == "Login":
        st.header("Login")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if email and password:
                response = requests.post(f"{BASE_URL}/login", json={"email": email, "password": password})
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        if "user" in response_data:
                            user_data = response_data["user"]
                            if "role" in user_data and "wallet_address" in user_data:
                                st.session_state.user_role = user_data["role"]
                                st.session_state.wallet_address = user_data["wallet_address"]
                                st.session_state.logged_in = True
                                st.session_state.user_name = user_data["name"]
                                st.success(f"Welcome, {user_data['name']}! You are logged in as a {user_data['role']}.")
                            else:
                                st.error("Unexpected user data structure. Missing 'role' or 'wallet_address' in user data.")
                        else:
                            st.error("Unexpected response structure. Missing 'user' key in response.")
                    except requests.exceptions.JSONDecodeError:
                        st.error("Failed to decode the response from the backend.")
                else:
                    try:
                        error_message = response.json().get('error')
                        st.error(f"Error: {error_message}")
                    except requests.exceptions.JSONDecodeError:
                        st.error(f"Error: Received an unexpected response: {response.text}")
            else:
                st.error("Please enter your email and password to login.")

# If the user is logged in, display their respective dashboard
if st.session_state.logged_in:
    st.header(f"Welcome to your {st.session_state.user_role} Dashboard")

    # Logout button
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user_role = None
        st.session_state.wallet_address = None
        st.session_state.user_name = None
        # Instead of rerun, we rely on the conditions to render the correct view next time the user interacts.

    if st.session_state.user_role == "Tenant":
        st.header("Tenant Dashboard: View Available Apartments")
        response = requests.get(f"{BASE_URL}/available-apartments")
        if response.status_code == 200:
            apartments = response.json()
            if apartments:
                for apt in apartments:
                    st.subheader(f"Apartment {apt['id']}: {apt['description']}")
                    st.write(f"Location: {apt['location']}")
                    st.write(f"Rent: {apt['price']} ETH")

                    # Convert ETH price to Jordanian Dinar
                    rent_price_jod = apt['price'] * ETH_TO_JOD_RATE
                    st.write(f"Rent (in JOD): {rent_price_jod:.2f} JOD")

                    if apt["is_available"]:
                        if st.button(f"Rent Apartment {apt['id']}"):
                            try:
                                # Convert order_id to string
                                order_id = str(apt['id'])
                                
                                # Convert rent_price_jod to a string
                                amount_in_jod = str(int(rent_price_jod))

                                # Create a payment using Zain Cash
                                payment_data = {
                                    "amount": amount_in_jod,  # Ensure amount is a string
                                    "order_id": order_id,  # Ensure order ID is a string
                                    "redirect_url": f"{BASE_URL}/zaincash-callback"  # Redirect URL must be a string
                                }

                                # Make the request to the back-end to create a payment
                                payment_response = requests.post(f"{BASE_URL}/create-payment", json=payment_data)

                                # Check the response from the backend
                                if payment_response.status_code == 200:
                                    payment_url = payment_response.json()["payment_url"]
                                    st.markdown(f"[Click here to pay with Zain Cash]({payment_url})", unsafe_allow_html=True)
                                else:
                                    try:
                                        error_message = payment_response.json().get('error')
                                        st.error(f"Error: {error_message}")
                                    except requests.exceptions.JSONDecodeError:
                                        st.error(f"Error: Received an unexpected response: {payment_response.text}")

                            except Exception as e:
                                st.error(f"Error occurred while processing payment: {e}")
            else:
                st.info("No apartments available for rent at the moment.")
        else:
            try:
                error_message = response.json().get('error')
                st.error(f"Failed to load apartments. Error: {error_message}")
            except requests.exceptions.JSONDecodeError:
                st.error(f"Failed to load apartments. Received an unexpected response: {response.text}")

    elif st.session_state.user_role == "Landlord":
        st.header("Landlord Dashboard: Add Apartment for Rent")
        description = st.text_area("Apartment Description")
        location = st.text_input("Apartment Location")
        price = st.number_input("Rent Price (ETH)", min_value=0.0)

        if st.button("Add Apartment"):
            if description and location and price > 0:
                apartment_data = {
                    "landlord_wallet": st.session_state.wallet_address,
                    "description": description,
                    "location": location,
                    "price": price
                }
                response = requests.post(f"{BASE_URL}/add-apartment", json=apartment_data)
                if response.status_code == 200:
                    st.success("Apartment listed successfully!")
                else:
                    st.error(f"Error: {response.json().get('error')}")
            else:
                st.error("Please provide all the apartment details.")
