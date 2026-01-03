
import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
SHEET_NAME = "Product_System_DB"  # Make sure your Google Sheet has this EXACT name
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

st.set_page_config(page_title="Product Management System", page_icon="🏭", layout="wide")

# --- CONSTANTS ---
BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]

# --- GOOGLE SHEETS CONNECTION ---
# This function caches the connection so we don't reconnect on every button click
@st.cache_resource
def get_gspread_client():
    try:
        # Load credentials from Streamlit secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ Error connecting to Google Cloud: {e}")
        return None

def get_worksheet(sheet_name, tab_name):
    client = get_gspread_client()
    if not client: return None
    try:
        sh = client.open(sheet_name)
        return sh.worksheet(tab_name)
    except Exception as e:
        st.error(f"❌ Error opening tab '{tab_name}': {e}")
        return None

# --- DATA HANDLING (READ/WRITE) ---

def load_data(tab_name):
    """Fetches all data from a specific tab."""
    ws = get_worksheet(SHEET_NAME, tab_name)
    if not ws: return pd.DataFrame()
    
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    
    # Force everything to string to avoid crashes
    return df.astype(str)

def append_to_sheet(tab_name, data_dict):
    """Appends a new row to the sheet."""
    ws = get_worksheet(SHEET_NAME, tab_name)
    if not ws: return False
    try:
        # gspread expects a list of values in the order of headers
        # We assume headers exist. We use the keys of data_dict.
        # However, append_row usually takes a list. 
        # Better strategy: Get headers first to align data.
        headers = ws.row_values(1)
        row_values = [str(data_dict.get(h, "")) for h in headers]
        ws.append_row(row_values)
        return True
    except Exception as e:
        st.error(f"Error saving to {tab_name}: {e}")
        return False

def update_sim_status(sim_number, new_status, used_in_sn):
    """Finds a SIM and updates its status."""
    ws = get_worksheet(SHEET_NAME, "Sims")
    if not ws: return
    try:
        # Find the cell with the SIM number
        cell = ws.find(sim_number)
        if cell:
            # Assuming "Status" is col 3 and "Used In S/N" is col 6 (based on typical layout)
            # Safe way: find column index by header
            headers = ws.row_values(1)
            status_col = headers.index("Status") + 1
            used_col = headers.index("Used In S/N") + 1
            
            ws.update_cell(cell.row, status_col, new_status)
            ws.update_cell(cell.row, used_col, used_in_sn)
    except Exception as e:
        st.warning(f"Could not update SIM status automatically: {e}")

def update_client_details(old_name, new_data):
    """Updates client details. This is tricky in GSheets, so we do a find-and-update."""
    ws = get_worksheet(SHEET_NAME, "Clients")
    if not ws: return False
    try:
        cell = ws.find(old_name)
        if cell:
            headers = ws.row_values(1)
            row_num = cell.row
            # Update each cell in the row
            for key, value in new_data.items():
                if key in headers:
                    col_idx = headers.index(key) + 1
                    ws.update_cell(row_num, col_idx, str(value))
            return True
    except Exception as e:
        st.error(f"Error updating client: {e}")
        return False
    return False

# --- UTILITY FUNCTIONS ---
def calculate_renewal(activation_date, months):
    if not activation_date: return None
    try:
        d = pd.to_datetime(activation_date).date()
        return d + relativedelta(months=int(months))
    except: return None

def check_expiry_status(renewal_date):
    if pd.isna(renewal_date) or str(renewal_date) == "" or str(renewal_date) == "NaT":
        return "Unknown"
    try:
        today = datetime.now().date()
        renewal = pd.to_datetime(renewal_date).date()
        days_left = (renewal - today).days
        if days_left < 0: return "Expired"
        elif days_left <= 30: return "Expiring Soon"
        else: return "Active"
    except: return "Unknown"

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# --- AUTHENTICATION ---
def check_login(username, password):
    df = load_data("Credentials")
    if df.empty: return None
    
    user_match = df[
        (df['Username'].str.strip() == username.strip()) & 
        (df['Password'].str.strip() == password.strip())
    ]
    if not user_match.empty:
        return user_match.iloc[0]['Name']
    return None

# --- MAIN APP ---

def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_name = ""

    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            st.markdown("## 🔒 System Login")
            with st.form("login_form"):
                user_input = st.text_input("Username")
                pass_input = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    name = check_login(user_input, pass_input)
                    if name:
                        st.session_state.logged_in = True
                        st.session_state.user_name = name
                        st.success(f"Welcome, {name}!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid Username or Password")
        return

    # --- LOGGED IN UI ---
    with st.sidebar:
        st.info(f"👤 User: **{st.session_state.user_name}**")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
        st.markdown("---")

    st.title("🏭 Product Management System (Cloud)")
    st.markdown("---")

    # LOAD ALL DATA
    with st.spinner("Syncing with Google Cloud..."):
        prod_df = load_data("Products")
        client_df = load_data("Clients")
        sim_df = load_data("Sims")

    # Sidebar Stats
    st.sidebar.caption(f"📦 Products: {len(prod_df)}")
    st.sidebar.caption(f"👥 Clients: {len(client_df)}")
    st.sidebar.caption(f"📶 SIMs: {len(sim_df)}")

    menu = st.sidebar.radio("Go to:", 
        ["Dashboard", "SIM Manager", "New Dispatch Entry", "Installation List", "Client Master", "Channel Partner Analytics"])

    # 1. DASHBOARD
    if menu == "Dashboard":
        st.subheader("📊 Analytics Overview")
        if not prod_df.empty:
            prod_df['Status_Calc'] = prod_df['Renewal Date'].apply(check_expiry_status)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Installations", len(prod_df))
            c2.metric("Active", len(prod_df[prod_df['Status_Calc'] == "Active"]))
            c3.metric("Expiring Soon", len(prod_df[prod_df['Status_Calc'] == "Expiring Soon"]))
            c4.metric("Expired", len(prod_df[prod_df['Status_Calc'] == "Expired"]))
            
            st.divider()
            
            # Simple Graphs
            if "Industry Category" in prod_df.columns:
                fig = px.pie(prod_df, names="Industry Category", title="Industry Distribution")
                st.plotly_chart(fig, use_container_width=True)

            # Alert List
            expiring = prod_df[prod_df['Status_Calc'].isin(["Expiring Soon", "Expired"])]
            if not expiring.empty:
                st.warning("⚠️ Expiring / Expired Devices")
                st.dataframe(expiring[["S/N", "End User", "Renewal Date", "Status_Calc"]], width="stretch")
        else:
            st.info("Database empty. Add entries.")

    # 2. SIM MANAGER
    elif menu == "SIM Manager":
        st.subheader("📶 SIM Inventory")
        with st.form("add_sim"):
            s_prov = st.selectbox("Provider", ["VI", "AIRTEL", "JIO", "BSNL"])
            s_num = st.text_input("SIM Number")
            s_plan = st.text_input("Plan")
            if st.form_submit_button("Add SIM"):
                if s_num in sim_df["SIM Number"].values:
                    st.error("SIM Exists!")
                else:
                    new_sim = {
                        "SIM Number": s_num, "Provider": s_prov, "Status": "Available",
                        "Plan Details": s_plan, "Entry Date": str(date.today()), "Used In S/N": ""
                    }
                    if append_to_sheet("Sims", new_sim):
                        st.success("SIM Added!")
                        st.rerun()
        
        st.dataframe(sim_df, width="stretch")

    # 3. NEW DISPATCH ENTRY
    elif menu == "New Dispatch Entry":
        st.subheader("📝 New Dispatch")
        
        # Form Inputs
        c1, c2 = st.columns(2)
        with c1:
            sn = st.text_input("S/N (Required)")
            oem = st.text_input("OEM S/N")
            prod = st.selectbox("Product", BASE_PRODUCT_LIST)
            model = st.text_input("Model")
            conn = st.selectbox("Conn", ["4G", "2G", "NB-IoT"])
        with c2:
            install_d = st.date_input("Install Date")
            activ_d = st.date_input("Activation Date")
            valid = st.number_input("Validity (Months)", 1, 60, 12)
            uid = st.text_input("UID")
        
        # SIM Selection
        avail_sims = sim_df[sim_df["Status"] == "Available"]["SIM Number"].tolist()
        sim_sel = st.selectbox("SIM", ["None", "New Manual"] + avail_sims)
        final_sim = ""
        if sim_sel == "New Manual":
            final_sim = st.text_input("Enter Manual SIM")
        elif sim_sel != "None":
            final_sim = sim_sel

        # Client Selection
        avail_clients = client_df["Client Name"].tolist()
        client_sel = st.selectbox("Client", ["New"] + avail_clients)
        final_client = st.text_input("New Client Name") if client_sel == "New" else client_sel

        # Save Logic
        if st.button("Save Dispatch", type="primary"):
            if not sn or not final_client:
                st.error("S/N and Client are required!")
            elif sn in prod_df["S/N"].values:
                st.error("S/N already exists!")
            else:
                renew_date = calculate_renewal(activ_d, valid)
                
                # 1. Save Product
                new_prod = {
                    "S/N": sn, "OEM S/N": oem, "Product Name": prod, "Model": model,
                    "Connectivity (2G/4G)": conn, "Installation Date": str(install_d),
                    "Activation Date": str(activ_d), "Validity (Months)": valid,
                    "Renewal Date": str(renew_date), "Device UID": uid, "SIM Number": final_sim,
                    "End User": final_client, "Channel Partner": "", "Industry Category": "",
                    "Cable Length": "", "SIM Provider": "VI" # Add inputs for these if needed
                }
                append_to_sheet("Products", new_prod)

                # 2. Save Client if new
                if client_sel == "New":
                    append_to_sheet("Clients", {"Client Name": final_client})

                # 3. Update SIM
                if final_sim:
                    if final_sim in sim_df["SIM Number"].values:
                        update_sim_status(final_sim, "Used", sn)
                    else:
                        # Auto-add manual SIM
                        append_to_sheet("Sims", {"SIM Number": final_sim, "Status": "Used", "Used In S/N": sn})
                
                st.success("Saved successfully!")
                st.rerun()

    # 4. LISTS
    elif menu == "Installation List":
        st.dataframe(prod_df, width="stretch")
    elif menu == "Client Master":
        st.dataframe(client_df, width="stretch")

if __name__ == "__main__":
    main()
