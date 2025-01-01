import streamlit as st
import requests

# Constants
BASE_URL = "http://localhost:5000"  # Backend API URL


# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "wallet_address" not in st.session_state:
    st.session_state.wallet_address = None

# Helper functions
def login(email, password):
    """Handles login and saves token on success."""
    response = requests.post(f"{BASE_URL}/login", json={"email": email, "password": password})
    if response.status_code == 200:
        response_data = response.json()
        st.session_state.token = response_data["token"]
        st.session_state.user = response_data["user"]
        st.session_state.wallet_address = response_data["user"]["wallet_address"]
        st.session_state.logged_in = True
        st.success(f"Welcome, {response_data['user']['name']}!")
    else:
        st.error(response.json().get("error", "Login failed."))

def logout():
    """Clears session state for logout."""
    st.session_state.logged_in = False
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.wallet_address = None
    st.success("Logged out successfully!")
    st.stop()

def get_headers():
    """Returns headers with Authorization token."""
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

def add_apartment(title, location, description, price_in_jod, lease_duration, availability, photos=None):
    headers = get_headers()

    # Calculate equivalent ETH price
    JOD_TO_ETH_RATE = 0.001  # Ensure this matches the backend
    rent_amount_eth = price_in_jod * JOD_TO_ETH_RATE

    # Prepare form data
    apartment_data = {
        "landlord_wallet": st.session_state.wallet_address,
        "title": title,
        "location": location,
        "description": description,
        "price_in_jod": price_in_jod,
        "lease_duration": lease_duration,
        "availability": availability
    }

    # Prepare files
    files = []
    if photos:
        for idx, photo in enumerate(photos):
            files.append(('photos', (f'photo_{idx}.jpg', photo, 'image/jpeg')))

    try:
        # Display ETH price for confirmation
        st.write(f"Price in ETH (converted): {rent_amount_eth:.6f} ETH")

        response = requests.post(
            f"{BASE_URL}/add-apartment",
            data=apartment_data,
            headers=headers,
            files=files
        )

        if response.status_code == 200:
            response_data = response.json()
            st.success("Apartment listed successfully!")
            st.write(f"*Price in JOD:* {response_data['price_in_jod']} JOD")
            st.write(f"*Price in ETH:* {response_data['rent_amount_eth']} ETH")
        else:
            st.error(response.json().get("error", "Failed to list apartment."))
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")



def edit_apartment(apartment_id, location, title, description, price_in_jod, lease_duration, availability, photos=None):
    headers = get_headers()

    apartment_data = {
        "title": title,
        "location": location,
        "description": description,
        "price_in_jod": price_in_jod,
        "lease_duration": lease_duration,
        "availability": availability
    }

    files = []
    if photos:
        for idx, photo in enumerate(photos):
            files.append(('photos', (f'photo_{idx}.jpg', photo, 'image/jpeg')))

    try:
       
        st.write(f"Uploading {len(files)} photos")

        response = requests.put(
            f"{BASE_URL}/edit-apartment/{apartment_id}",
            data=apartment_data,
            headers=headers,
            files=files
        )

       

        if response.status_code != 200:
            
            st.error(response.json().get("error", "Failed to update apartment."))
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")



def delete_apartment(apartment_id):
    """Sends a request to delete an apartment."""
    headers = get_headers()
    response = requests.delete(f"{BASE_URL}/delete-apartment/{apartment_id}", headers=headers)
    if response.status_code == 200:
        
         # Trigger a refresh of the apartment listings
        st.session_state["refresh_apartments"] = True
    else:
        st.error(response.json().get("error", "Failed to delete apartment."))

def sign_agreement(apartment_id, role):
    with st.form(f"sign_form_{apartment_id}_{role}", clear_on_submit=True):
        st.write(f"Sign agreement for Apartment {apartment_id}")
        private_key = st.text_input("Enter private key", type="password", key=f"key_{apartment_id}")
        submitted = st.form_submit_button("Sign Agreement")
        
        if submitted:
            if not private_key or private_key.isspace():
                st.error("Private key is required!")
                return
            
            try:
                response = requests.post(
                    f"{BASE_URL}/contracts/sign",
                    json={
                        "apartment_id": apartment_id,
                        "wallet_address": st.session_state.wallet_address,
                        "role": role,
                        "private_key": private_key
                    },
                    headers=get_headers()
                )
                
                if response.status_code == 200:
                    st.success("Agreement signed successfully!")
                else:
                    st.error(f"Failed: {response.json().get('error', 'Unknown error')}")
            except Exception as e:
                st.error(f"Error: {str(e)}")



def fetch_contracts(endpoint):
    response = requests.get(f"{BASE_URL}/{endpoint}", headers=get_headers())

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError:
            st.error("Invalid JSON response from server.")
            return []
    else:
        st.error(f"API Error {response.status_code}: {response.text}")
        return []


def make_payment(apartment_id, amount, unique_key):
    with st.form(f"payment_form_{apartment_id}_{unique_key}", clear_on_submit=True):  # Use unique_key for uniqueness
        st.write(f"Make Payment for Apartment {apartment_id}")
        private_key = st.text_input("Enter your private key", type="password", key=f"private_key_{apartment_id}_{unique_key}")
        submitted = st.form_submit_button("Make Payment")

        if submitted:
            if not private_key or private_key.isspace():
                st.error("Private key is required to make the payment!")
                return

            payload = {
                "apartment_id": apartment_id,
                "wallet_address": st.session_state.wallet_address,  # Ensure wallet address is included
                "private_key": private_key,  # Include the private key for signing the transaction
                "payment_amount": amount
            }

            try:
                response = requests.post(f"{BASE_URL}/contracts/pay", json=payload, headers=get_headers())
                if response.status_code == 200:
                    st.success("Payment made successfully!")
                else:
                    error_message = response.json().get("error", "Failed to make payment.")
                    st.error(f"Error: {error_message}")
            except Exception as e:
                st.error(f"An error occurred while making payment: {e}")

def terminate_contract(apartment_id, role, unique_key):
    with st.form(f"termination_form_{apartment_id}_{unique_key}", clear_on_submit=True):
        st.write(f"Terminate Contract for Apartment {apartment_id}")
        private_key = st.text_input("Enter your private key", type="password", key=f"private_key_{apartment_id}_{unique_key}_termination")
        submitted = st.form_submit_button("Terminate Contract")

        if submitted:
            if not private_key or private_key.isspace():
                st.error("Private key is required to terminate the contract!")
                return

            # Construct the payload
            payload = {
                "apartment_id": apartment_id,
                "role": role,
                "wallet_address": st.session_state.wallet_address,
                "private_key": private_key
            }

            # Make the API request to terminate the contract
            try:
                response = requests.post(f"{BASE_URL}/contracts/terminate", json=payload, headers=get_headers())
                if response.status_code == 200:
                    st.success("Contract terminated successfully!")
                    st.json(response.json())  # Optionally display the transaction details
                else:
                    error_message = response.json().get("error", "Failed to terminate contract.")
                    st.error(f"Error: {error_message}")
            except Exception as e:
                st.error(f"An error occurred while terminating the contract: {e}")



# Main Application
st.set_page_config(page_title="Rental System", layout="wide")

# Login Form
def login_form():
    st.subheader("Login")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login", key="login_button"):
        if email and password:
            login(email, password)
        else:
            st.warning("Please enter your email and password.")

# Register Form
def register_form():
    st.subheader("Register")
    name = st.text_input("Name", key="register_name")
    email = st.text_input("Email", key="register_email")
    wallet_address = st.text_input("Ethereum Wallet Address", key="register_wallet")
    phone = st.text_input("Phone Number", key="register_phone")
    password = st.text_input("Password", type="password", key="register_password")
    role = st.radio("Role", ["Tenant", "Landlord"], key="register_role")

    if st.button("Register", key="register_button"):
        if name and email and phone and password and role and wallet_address:
            user_data = {
                "name": name.strip(),
                "email": email.strip(),
                "wallet_address": wallet_address.strip(),
                "phone": phone.strip(),
                "password": password.strip(),
                "role": role
            }
            response = requests.post(f"{BASE_URL}/register", json=user_data)
            if response.status_code == 200:
                st.success("Registration successful! Please log in.")
            else:
                st.error(response.json().get("error", "Registration failed."))
        else:
            st.warning("Please fill in all fields.")

# Landing Page
def landing_page():
    st.image("background.jpg", use_container_width=True)
    st.title("Welcome to the Rental System")
    st.subheader("Your trusted platform for finding or renting apartments")

    # Reordered navigation tabs
    tabs = st.tabs(["About Us", "Home", "Login", "Register", "Contact Us"])

    with tabs[0]:  # About Us Tab
        st.title("About Us")
        st.write("""
        Welcome to our Rental Agreement Platform, where we simplify rental processes for both tenants and landlords. We believe in transparency, security, and efficiency in every transaction. Our platform leverages blockchain technology to ensure non-reputation of contracts

        Whether you’re a landlord looking to easily manage your property listings or a tenant searching for your next home, our system is designed to provide a seamless experience. By integrating blockchain to record all agreements and payments, we guarantee the safety and reliability of every interaction.

        Join us today to experience a modern, hassle-free way to rent and manage properties, with the assurance of cutting-edge technology securing your interests.
        """)

    with tabs[1]:  # Home Tab
        st.write("Welcome to the home page! Find apartments or learn more about our platform.")

    with tabs[2]:  # Login Tab
        login_form()

    with tabs[3]:  # Register Tab
        register_form()

    with tabs[4]:  # Contact Us Tab
        st.write("Contact Us: Reach out at support@rentalsystem.com or call +123456789.")


def landlord_dashboard():
    st.header(f"Welcome, {st.session_state.user['name']} (Landlord)")
    tab1, tab2, tab3, tab4 = st.tabs(["Add Apartment", "Manage Listings", "My Profile", "My Contracts"])

    # Add Apartment
    with tab1:
        st.subheader("Add a New Apartment")
        title = st.text_input("Apartment Title", key="add_title")
        location = st.text_input("Apartment Location", key="add_location")
        description = st.text_area("Description", key="add_description")
        price_in_jod = st.number_input("Monthly Rent (in JOD)", min_value=0.0, key="add_price_jod")
        lease_duration = st.number_input("Lease Duration (in months)", min_value=1, key="add_duration")
        availability = st.selectbox("Availability", ["Available", "Unavailable"], key="add_availability")
        photos = st.file_uploader("Upload Apartment Photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="add_photos")

        if st.button("List Apartment", key="list_apartment"):
            if not photos:
                st.warning("Please upload at least one photo before listing the apartment.")
            else:
                photo_data_list = [photo.read() for photo in photos]
                add_apartment(title, location, description, price_in_jod, lease_duration, availability, photo_data_list)

    # Manage Listings
    with tab2:
        st.subheader("Your Current Listings")
        response = requests.get(f"{BASE_URL}/landlord-apartments", headers=get_headers())
        if response.status_code == 200:
            apartments = response.json()
            for apt in apartments:
                st.write(f"**Title:** {apt['title']}")
                if apt.get("photo_urls"):
                    st.write("Photos:")
                    for photo_url in apt["photo_urls"]:
                        st.image(photo_url, width=300)
                st.write(f"**Location:** {apt['location']}")
                st.write(f"**Description:** {apt['description']}")
                st.write(f"**Price in JOD:** {apt['price_in_jod']} JOD")
                st.write(f"**Rent Amount:** {apt['rent_amount_eth']} ETH")
                st.write(f"**Lease Duration:** {apt['lease_duration']} months")
                st.write(f"**Availability:** {apt['availability']}")
            
                if st.button(f"Delete {apt['title']}", key=f"delete_{apt['id']}"):
                    delete_apartment(apt["id"])
                    st.success(f"Apartment \"{apt['title']}\" deleted successfully!")
        else:
            st.error("Failed to load your listings.")

    # My Profile
    with tab3:
        st.subheader("My Profile")
        user = st.session_state.user

        # Display current user details
        name = st.text_input("Name", value=user["name"])
        email = st.text_input("Email", value=user["email"], disabled=True)  # Email cannot be changed
        wallet_address = st.text_input("Ethereum Wallet Address", value=user["wallet_address"], disabled=True)
        phone = st.text_input("Phone Number", value=user["phone"])

        # Button to save profile changes
        if st.button("Save Profile Changes"):
            try:
                response = requests.put(
                    f"{BASE_URL}/update-profile",
                    headers=get_headers(),
                    json={
                        "name": name,
                        "phone": phone
                    }
                )
                if response.status_code == 200:
                    st.success("Profile updated successfully!")
                    st.session_state.user["name"] = name
                    st.session_state.user["phone"] = phone
                else:
                    st.error(response.json().get("error", "Failed to update profile."))
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

    # My Contracts Tab
    with tab4:
        tab1, tab2 = st.tabs(["Pending Contracts", "Active Contracts"])

        # Pending Contracts Tab
        with tab1:
            
            contracts = fetch_contracts("landlord-contracts")
            pending_contracts = [contract for contract in contracts if contract["status"] == "Pending"]
            landlord_signed_contracts = [contract for contract in contracts if contract["status"] == "Landlord Signed"]
            # Display Pending Contracts
            st.subheader("Pending Contracts")
            for contract in pending_contracts:
              st.subheader(f"Apartment {contract['apartment_id']}")
              st.write(f"**Tenant Wallet:** {contract['tenant_wallet']}")
              st.write(f"**Apartment ID:** {contract['apartment_id']}")
              st.write(f"**Start Date:** {contract.get('start_date', 'Not Specified')}")
              st.write(f"**End Date:** {contract.get('end_date', 'Not Specified')}")
              st.write(f"**Rent Amount:** {contract['rent_amount']} ETH")
              st.write(f"**Lease Duration:** {contract['lease_duration']} months")
              sign_agreement(contract['apartment_id'], "Landlord")

            # Display Landlord Signed Contracts
            st.subheader("Landlord Signed Contracts")
            for contract in landlord_signed_contracts:
             st.subheader(f"Apartment {contract['apartment_id']}")
             st.write(f"**Tenant Wallet:** {contract['tenant_wallet']}")
             st.write(f"**Apartment ID:** {contract['apartment_id']}")
             st.write(f"**Start Date:** {contract.get('start_date', 'Not Specified')}")
             st.write(f"**End Date:** {contract.get('end_date', 'Not Specified')}")
             st.write(f"**Rent Amount:** {contract['rent_amount']} ETH")
             st.write(f"**Lease Duration:** {contract['lease_duration']} months")
             st.write(f"**Status:** {contract['status']}")
             st.info("Waiting for Tenant to Sign")

        
            
                

        # Active Contracts Tab
        with tab2:
            st.subheader("Active Contracts")
            contracts = fetch_contracts("landlord-contracts?status=Active")
            for contract in contracts:
                st.subheader(f"Apartment {contract['apartment_id']}")
                st.write(f"**Contract Address:** {contract['contract_address']}")
                st.write(f"**Tenant Wallet:** {contract['tenant_wallet']}")
                st.write(f"**Apartment ID:** {contract['apartment_id']}")
                st.write(f"**Start Date:** {contract['start_date']}")
                st.write(f"**End Date:** {contract['end_date']}")
                st.write(f"**Rent Amount:** {contract['rent_amount']} ETH")
                st.write(f"**Lease Duration:** {contract['lease_duration']} months")
                st.write(f"**Status:** {contract['status']}")
                terminate_contract(contract['apartment_id'], 'Landlord',contract['id'])
                





def tenant_dashboard():
    st.header(f"Welcome, {st.session_state.user['name']} (Tenant)")
    tab1, tab2, tab3 = st.tabs(["Available Apartments", "My Contracts", "My Profile"])

    # Available Apartments
    with tab1:
        st.subheader("Browse Available Apartments")
        try:
            response = requests.get(f"{BASE_URL}/available-apartments", headers=get_headers())

            if response.status_code == 200:
                apartments = response.json()

                if not apartments:
                    st.info("No apartments are currently available.")

                for apt in apartments:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{apt['title']}**")
                        st.write(f"Location: {apt.get('location', 'N/A')}")
                        st.write(f"Description: {apt.get('description', 'No description')}")
                        st.write(f"Lease Duration: {apt.get('lease_duration', 'N/A')} months")

                    with col2:
                        st.write(f"Price: {apt.get('price_in_jod', 'N/A')} JOD")
                        st.write(f"Rent in ETH: {apt.get('rent_amount_eth', 'N/A')} ETH")

                    # Display apartment photos
                    if apt.get('photo_urls'):
                        for photo_url in apt['photo_urls']:
                            st.image(photo_url, width=200)

                    # Handle Rent button click
                    
                        with st.form(key=f"rental_form_{apt['id']}"):
                            start_date = st.date_input("Start Date", key=f"start_date_{apt['id']}")
                            end_date = st.date_input("End Date", key=f"end_date_{apt['id']}")
                            submitted = st.form_submit_button("Submit Rental Request")

                            if submitted:
                                # Validate dates
                                if not start_date or not end_date:
                                    st.warning("Please provide both start and end dates.")
                                elif (end_date - start_date).days < 30:
                                    st.error("The rental period must be at least 1 month.")
                                else:
                                    try:
                                        rent_response = requests.post(
                                            f"{BASE_URL}/contracts/initiate",
                                            json={
                                                "tenant_wallet": st.session_state.wallet_address,
                                                "apartment_id": apt["id"],
                                                "start_date": start_date.strftime('%Y-%m-%d'),
                                                "end_date": end_date.strftime('%Y-%m-%d')
                                            },
                                            headers=get_headers()
                                        )

                                        if rent_response.status_code == 200:
                                            st.success(f"Successfully initiated rental for '{apt['title']}'!")
                                        else:
                                            st.error(rent_response.json().get("error", "Failed to initiate rental process."))
                                    except requests.RequestException as e:
                                        st.error(f"Network error occurred: {e}")
                                    except Exception as e:
                                        st.error(f"An unexpected error occurred: {e}")

                    st.markdown("---")

            else:
                st.error(f"Failed to load apartments. Error: {response.text}")

        except requests.RequestException as e:
            st.error(f"Network error occurred: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")

    # My Contracts
    with tab2:
        st.subheader("My Contracts")
        tab1, tab2 = st.tabs(["Pending Contracts", "Active Contracts"])

        # Pending Contracts
        with tab1:
            st.subheader("Landlord Signed Contracts")
            contracts = fetch_contracts("tenant-contracts")
            pending_contracts = [contract for contract in contracts if contract["status"] == "Pending"]
            landlord_signed_contracts = [contract for contract in contracts if contract["status"] == "Landlord Signed"]
            for contract in landlord_signed_contracts:
                st.write(f"**Landlord Wallet:** {contract['landlord_wallet']}")
                st.write(f"**Apartment ID:** {contract['apartment_id']}")
                st.write(f"**Start Date:** {contract.get('start_date', 'Not Specified')}")
                st.write(f"**End Date:** {contract.get('end_date', 'Not Specified')}")
                st.write(f"**Status:** {contract['status']}")
                st.info("Ready for you to sign.")
                sign_agreement(contract['apartment_id'], "Tenant")
                
            st.subheader("Pending Contracts")
            for contract in pending_contracts:
                st.write(f"**Landlord Wallet:** {contract['landlord_wallet']}")
                st.write(f"**Apartment ID:** {contract['apartment_id']}")
                st.write(f"**Start Date:** {contract.get('start_date', 'Not Specified')}")
                st.write(f"**End Date:** {contract.get('end_date', 'Not Specified')}")
                st.write(f"**Status:** {contract['status']}")
                st.info("Waiting for Landlord to Sign")
                
            
            
            

        # Active Contracts
        with tab2:
            st.subheader("Active Contracts")
            contracts = fetch_contracts("tenant-contracts?status=Active")
            for contract in contracts:
                st.subheader(f"Apartment {contract['apartment_id']}")
                st.write(f"**Contract Address:** {contract['contract_address']}")
                st.write(f"**Landlord Wallet:** {contract['landlord_wallet']}")
                st.write(f"**Apartment ID:** {contract['apartment_id']}")
                st.write(f"**Start Date:** {contract['start_date']}")
                st.write(f"**End Date:** {contract['end_date']}")
                st.write(f"**Next Payment Due:** {contract.get('next_payment_due', 'Not Specified')}")
                make_payment(contract['apartment_id'], contract['rent_amount'],contract['id'])
                
                terminate_contract(contract['apartment_id'], 'tenant',contract['id'])


    # My Profile
    with tab3:
        st.subheader("My Profile")
        user = st.session_state.user

        # Display current user details
        name = st.text_input("Name", value=user["name"])
        email = st.text_input("Email", value=user["email"], disabled=True)  # Email cannot be changed
        wallet_address = st.text_input("Ethereum Wallet Address", value=user["wallet_address"], disabled=True)
        phone = st.text_input("Phone Number", value=user["phone"])

        # Button to save profile changes
        if st.button("Save Profile Changes"):
            try:
                response = requests.put(
                    f"{BASE_URL}/update-profile",
                    headers=get_headers(),
                    json={
                        "name": name,
                        "phone": phone
                    }
                )

                if response.status_code == 200:
                    st.success("Profile updated successfully!")
                    st.session_state.user["name"] = name
                    st.session_state.user["phone"] = phone
                else:
                    st.error(response.json().get("error", "Failed to update profile."))

            except requests.RequestException as e:
                st.error(f"Network error: {e}")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")


# Routing Logic
if not st.session_state.get("logged_in", False):
    landing_page()
else:
    role = st.session_state.user["role"]
    if role == "Landlord":
        landlord_dashboard()
    elif role == "Tenant":
        tenant_dashboard()