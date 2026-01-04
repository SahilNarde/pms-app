import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import io

# --- CONFIGURATION ---
SHEET_NAME = "PMS DB"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

st.set_page_config(page_title="Product Management System", page_icon="🏭", layout="wide")

# --- CONSTANTS ---
BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def get_gspread_client():
    try:
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
        print(f"❌ Error opening tab '{tab_name}': {e}")
        return None

# --- DATA HANDLING ---

@st.cache_data(ttl=60)
def load_data(tab_name):
    """
    ROBUST LOAD: Uses get_all_values() instead of get_all_records() 
    to prevent type errors and missing data.
    """
    ws = get_worksheet(SHEET_NAME, tab_name)
    if not ws: return pd.DataFrame()
    try:
        # Get raw list of lists (everything as strings)
        data = ws.get_all_values()
        
        if not data:
            return pd.DataFrame()
            
        # First row is headers
        headers = data[0]
        rows = data[1:]
        
        # Create DataFrame
        df = pd.DataFrame(rows, columns=headers)
        
        # CLEANUP: Ensure headers are strings and stripped of whitespace
        df.columns = df.columns.astype(str).str.strip()
        
        return df
    except Exception as e:
        st.error(f"Error reading {tab_name}: {e}")
        return pd.DataFrame()

def get_clean_list(df, column_name):
    """Helper to extract a clean list of unique values from a column."""
    if df.empty or column_name not in df.columns:
        return []
    
    series = df[column_name].astype(str)
    values = series.unique().tolist()
    
    clean_values = [
        v.strip() for v in values 
        if v and str(v).lower() not in ["", "nan", "none", "null"] and v.strip() != ""
    ]
    return sorted(list(set(clean_values)))

def append_to_sheet(tab_name, data_dict):
    """Appends a single row."""
    ws = get_worksheet(SHEET_NAME, tab_name)
    if not ws: return False
    try:
        # Check if headers exist (using raw fetch)
        raw_headers = ws.row_values(1)
        if not raw_headers:
            headers = list(data_dict.keys())
            ws.append_row(headers)
            raw_headers = headers
            
        # Map dictionary values to header order
        row_values = []
        for h in raw_headers:
            val = data_dict.get(h.strip(), "") # Strip header key to match
            row_values.append(str(val))
            
        ws.append_row(row_values)
        load_data.clear()
        return True
    except Exception as e:
        st.error(f"Error saving to {tab_name}: {e}")
        return False

def bulk_append_to_sheet(tab_name, df):
    ws = get_worksheet(SHEET_NAME, tab_name)
    if not ws: return False
    try:
        sheet_headers = ws.row_values(1)
        if not sheet_headers:
            st.error(f"Tab '{tab_name}' is empty. Add headers first.")
            return False
            
        # Ensure DF has all columns needed
        for h in sheet_headers:
            h_clean = h.strip()
            if h_clean not in df.columns:
                df[h_clean] = ""
        
        # Sort DF columns to match sheet order
        clean_headers = [h.strip() for h in sheet_headers]
        df_sorted = df[clean_headers]
        
        data_to_upload = df_sorted.astype(str).values.tolist()
        ws.append_rows(data_to_upload)
        load_data.clear()
        return True
    except Exception as e:
        st.error(f"Bulk upload failed: {e}")
        return False

def update_sim_status(sim_number, new_status, used_in_sn):
    ws = get_worksheet(SHEET_NAME, "Sims")
    if not ws: return
    try:
        cell = ws.find(sim_number)
        if cell:
            headers = ws.row_values(1)
            try:
                # Find column index by name (1-based for gspread)
                status_col = headers.index("Status") + 1
                used_col = headers.index("Used In S/N") + 1
                
                ws.update_cell(cell.row, status_col, new_status)
                ws.update_cell(cell.row, used_col, used_in_sn)
                load_data.clear()
            except ValueError:
                pass
    except Exception as e:
        st.warning(f"Could not update SIM status: {e}")

# --- UTILITY ---
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

# --- AUTH ---
def check_login(username, password):
    ws = get_worksheet(SHEET_NAME, "Credentials")
    if not ws: return None
    data = ws.get_all_values()
    if not data: return None
    
    headers = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=headers)
    
    # Strip whitespace
    df.columns = df.columns.str.strip()
    
    if 'Username' not in df.columns or 'Password' not in df.columns:
        return None

    user_match = df[(df['Username'].str.strip() == username.strip()) & (df['Password'].str.strip() == password.strip())]
    if not user_match.empty:
        return user_match.iloc[0]['Name']
    return None

# --- MAIN ---
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
                if st.form_submit_button("Login"):
                    name = check_login(user_input, pass_input)
                    if name:
                        st.session_state.logged_in = True
                        st.session_state.user_name = name
                        st.success(f"Welcome, {name}!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid Username or Password")
        return

    with st.sidebar:
        st.info(f"👤 User: **{st.session_state.user_name}**")
        if st.button("🔄 Refresh Data"):
            load_data.clear()
            st.rerun()
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.rerun()
        st.markdown("---")

    st.title("🏭 Product Management System (Cloud)")
    st.markdown("---")

    # --- LOAD DATA & SANITIZE ---
    try:
        prod_df = load_data("Products")
        client_df = load_data("Clients")
        sim_df = load_data("Sims")
        
        # Fallback for completely empty sheets to avoid crashes
        if "S/N" not in prod_df.columns: prod_df = pd.DataFrame(columns=["S/N", "End User", "Renewal Date", "Industry Category", "Installation Date"])
        if "Client Name" not in client_df.columns: client_df = pd.DataFrame(columns=["Client Name"])
        if "SIM Number" not in sim_df.columns: sim_df = pd.DataFrame(columns=["SIM Number", "Status", "Provider"])

    except Exception as e:
        st.error("⚠️ Data connection error. Please refresh.")
        return

    st.sidebar.caption(f"📦 Products: {len(prod_df)}")
    st.sidebar.caption(f"👥 Clients: {len(client_df)}")
    st.sidebar.caption(f"📶 SIMs: {len(sim_df)}")

    menu = st.sidebar.radio("Go to:", 
        ["Dashboard", "SIM Manager", "New Dispatch Entry", "Installation List", "Client Master", "Channel Partner Analytics", "IMPORT/EXPORT DB"])

    # 1. DASHBOARD
    if menu == "Dashboard":
        st.subheader("📊 Analytics Overview")
        if not prod_df.empty and "Renewal Date" in prod_df.columns:
            prod_df['Status_Calc'] = prod_df['Renewal Date'].apply(check_expiry_status)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Installations", len(prod_df))
            c2.metric("Active", len(prod_df[prod_df['Status_Calc'] == "Active"]))
            c3.metric("Expiring Soon", len(prod_df[prod_df['Status_Calc'] == "Expiring Soon"]))
            c4.metric("Expired", len(prod_df[prod_df['Status_Calc'] == "Expired"]))
            st.divider()
            
            # --- DEBUGGER (Optional: Check what columns are actually loaded) ---
            with st.expander("🛠️ View Raw Data (Debug)"):
                st.write("Loaded Columns:", prod_df.columns.tolist())
                st.dataframe(prod_df.head(), use_container_width=True)

            # --- GRAPHS ---
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                if "Industry Category" in prod_df.columns:
                    # Clean the data for graphing
                    df_pie = prod_df.copy()
                    # Fill blanks with 'Uncategorized' so they appear on the graph
                    df_pie["Industry Category"] = df_pie["Industry Category"].replace(['', 'nan', 'None', 'NaN'], 'Uncategorized')
                    # Strip spaces just in case
                    df_pie["Industry Category"] = df_pie["Industry Category"].astype(str).str.strip()
                    # Replace empty strings again after strip
                    df_pie["Industry Category"] = df_pie["Industry Category"].replace('', 'Uncategorized')

                    ind_counts = df_pie['Industry Category'].value_counts().reset_index()
                    ind_counts.columns = ['Industry Category', 'Count']
                    
                    fig_pie = px.pie(ind_counts, values='Count', names='Industry Category', title="Industry Distribution", hole=0.4)
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.error("Column 'Industry Category' not found.")

            with col_g2:
                if "Installation Date" in prod_df.columns:
                    trend_df = prod_df.copy()
                    trend_df["Installation Date"] = pd.to_datetime(trend_df["Installation Date"], errors='coerce')
                    trend_df = trend_df.dropna(subset=["Installation Date"])
                    
                    if not trend_df.empty:
                        trend_data = trend_df.groupby(trend_df["Installation Date"].dt.to_period("M")).size().reset_index(name="Installations")
                        trend_data["Month"] = trend_data["Installation Date"].astype(str)
                        fig_trend = px.area(trend_data, x="Month", y="Installations", title="Installation Growth (Monthly)", markers=True, color_discrete_sequence=["#00CC96"])
                        st.plotly_chart(fig_trend, use_container_width=True)
                    else:
                        st.info("No valid dates for growth chart.")

            # --- ALERT CENTER ---
            st.markdown("### ⚠️ Alert Center")
            tab_soon, tab_expired = st.tabs(["⏳ Expiring Soon", "❌ Expired"])
            
            with tab_soon:
                df_soon = prod_df[prod_df['Status_Calc'] == "Expiring Soon"]
                if not df_soon.empty:
                    st.dataframe(df_soon[["S/N", "End User", "Renewal Date", "Status_Calc"]], use_container_width=True)
                else:
                    st.success("No subscriptions expiring soon.")
                    
            with tab_expired:
                df_expired = prod_df[prod_df['Status_Calc'] == "Expired"]
                if not df_expired.empty:
                    st.dataframe(df_expired[["S/N", "End User", "Renewal Date", "Status_Calc"]], use_container_width=True)
                else:
                    st.success("No expired subscriptions.")

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
                sim_list = sim_df["SIM Number"].values if "SIM Number" in sim_df.columns else []
                if str(s_num) in sim_list:
                    st.error("SIM Exists!")
                else:
                    new_sim = {"SIM Number": s_num, "Provider": s_prov, "Status": "Available", "Plan Details": s_plan, "Entry Date": str(date.today()), "Used In S/N": ""}
                    if append_to_sheet("Sims", new_sim):
                        st.success("SIM Added!")
                        st.rerun()
        st.dataframe(sim_df, use_container_width=True)

    # 3. NEW DISPATCH ENTRY
    elif menu == "New Dispatch Entry":
        st.subheader("📝 New Dispatch")
        
        st.markdown("### 🛠️ Device & Network")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            sn = st.text_input("Product S/N (Required)")
            oem = st.text_input("OEM S/N")
        with c2:
            prod = st.selectbox("Product Name", BASE_PRODUCT_LIST)
            model = st.text_input("Model")
        with c3:
            conn = st.selectbox("Connectivity", ["4G", "2G", "NB-IoT", "WiFi", "LoRaWAN"])
            cable = st.text_input("Cable Length")
        with c4:
            uid = st.text_input("Device UID")
            avail_sims = get_clean_list(sim_df[sim_df["Status"] == "Available"], "SIM Number") if "Status" in sim_df.columns else []
            sim_opts = ["None"] + avail_sims + ["➕ Add New SIM..."]
            sim_sel = st.selectbox("SIM Card", sim_opts)

        final_sim_num = ""
        final_sim_prov = "VI"
        
        if sim_sel == "➕ Add New SIM...":
            c_s1, c_s2 = st.columns(2)
            with c_s1: final_sim_num = st.text_input("Enter New SIM Number")
            with c_s2: final_sim_prov = st.selectbox("Provider", ["VI", "AIRTEL", "JIO", "BSNL", "Other"])
        elif sim_sel != "None":
            final_sim_num = sim_sel
            if not sim_df.empty:
                match = sim_df[sim_df["SIM Number"] == final_sim_num]
                if not match.empty and "Provider" in match.columns:
                    final_sim_prov = match.iloc[0]["Provider"]

        st.divider()

        st.markdown("### 👥 Client & Partner")
        col_p, col_c, col_i, col_d = st.columns(4)

        with col_p:
            avail_partners = get_clean_list(prod_df, "Channel Partner")
            partner_opts = ["Select..."] + avail_partners + ["➕ Create New..."]
            p_sel = st.selectbox("Channel Partner", partner_opts)
            final_partner = st.text_input("Enter Partner Name", placeholder="Type name...") if p_sel == "➕ Create New..." else (p_sel if p_sel != "Select..." else "")

        with col_c:
            avail_clients = get_clean_list(client_df, "Client Name")
            client_opts = ["Select..."] + avail_clients + ["➕ Create New..."]
            c_sel = st.selectbox("End User (Client)", client_opts)
            final_client = st.text_input("Enter Client Name", placeholder="Type name...") if c_sel == "➕ Create New..." else (c_sel if c_sel != "Select..." else "")

        with col_i:
            avail_inds = get_clean_list(prod_df, "Industry Category")
            ind_opts = ["Select..."] + avail_inds + ["➕ Create New..."]
            i_sel = st.selectbox("Industry", ind_opts)
            final_ind = st.text_input("Enter Industry", placeholder="Type category...") if i_sel == "➕ Create New..." else (i_sel if i_sel != "Select..." else "")

        with col_d:
            install_d = st.date_input("Installation Date")
            valid = st.number_input("Validity (Months)", 1, 60, 12)
            activ_d = st.date_input("Activation Date")

        st.markdown("---")
        if st.button("💾 Save Dispatch Entry", type="primary", use_container_width=True):
            missing_fields = []
            if not sn: missing_fields.append("S/N")
            if not final_client: missing_fields.append("Client")
            
            if missing_fields:
                st.error(f"Missing required fields: {', '.join(missing_fields)}")
            else:
                sn_list = prod_df["S/N"].values if "S/N" in prod_df.columns else []
                if sn in sn_list:
                    st.error("S/N already exists!")
                else:
                    renew_date = calculate_renewal(activ_d, valid)
                    new_prod = {
                        "S/N": sn, "OEM S/N": oem, "Product Name": prod, "Model": model,
                        "Connectivity (2G/4G)": conn, "Cable Length": cable,
                        "Installation Date": str(install_d), "Activation Date": str(activ_d), 
                        "Validity (Months)": valid, "Renewal Date": str(renew_date), 
                        "Device UID": uid, "SIM Number": final_sim_num, "SIM Provider": final_sim_prov,
                        "Channel Partner": final_partner, "End User": final_client, "Industry Category": final_ind
                    }
                    
                    if append_to_sheet("Products", new_prod):
                        if c_sel == "➕ Create New..." and final_client:
                             append_to_sheet("Clients", {"Client Name": final_client})
                        
                        if final_sim_num:
                            sim_db_list = sim_df["SIM Number"].values if "SIM Number" in sim_df.columns else []
                            if final_sim_num in sim_db_list: 
                                update_sim_status(final_sim_num, "Used", sn)
                            else: 
                                append_to_sheet("Sims", {"SIM Number": final_sim_num, "Provider": final_sim_prov, "Status": "Used", "Used In S/N": sn, "Entry Date": str(date.today())})
                        st.success("✅ Dispatch Saved Successfully!")
                        st.balloons()
                        st.rerun()

    elif menu == "Installation List":
        st.dataframe(prod_df, use_container_width=True)
    elif menu == "Client Master":
        st.dataframe(client_df, use_container_width=True)
    
    # 7. CHANNEL PARTNER ANALYTICS
    elif menu == "Channel Partner Analytics":
        st.subheader("🤝 Channel Partner Performance")
        if not prod_df.empty and "Channel Partner" in prod_df.columns:
            partner_df = prod_df[prod_df["Channel Partner"].str.strip() != ""]
            if not partner_df.empty:
                partner_stats = partner_df.groupby("Channel Partner").size().reset_index(name='Total Installations')
                partner_stats = partner_stats.sort_values(by="Total Installations", ascending=False)

                c1, c2 = st.columns([2, 1])
                with c1:
                    fig_part = px.bar(partner_stats, x="Channel Partner", y="Total Installations")
                    st.plotly_chart(fig_part, use_container_width=True)
                with c2:
                    st.metric("🏆 Top Performer", partner_stats.iloc[0]["Channel Partner"])
                st.dataframe(partner_stats, use_container_width=True)
            else: st.info("No Channel Partner data.")
        else: st.info("No Data.")

    # 8. IMPORT/EXPORT DB
    elif menu == "IMPORT/EXPORT DB":
        st.subheader("💾 Database Management")
        tab1, tab2 = st.tabs(["⬇️ Backup / Export", "⬆️ Bulk Import"])
        
        with tab1:
            st.markdown("Download your current Google Sheet data as Excel files.")
            if not prod_df.empty:
                st.download_button("Download Products", convert_df_to_excel(prod_df), "Products_Backup.xlsx")
                st.download_button("Download Clients", convert_df_to_excel(client_df), "Clients_Backup.xlsx")
                st.download_button("Download SIMs", convert_df_to_excel(sim_df), "Sims_Backup.xlsx")
            else: st.warning("Database is empty.")
            
        with tab2:
            st.markdown("### ⚠️ Bulk Append")
            st.markdown("Upload an Excel file to **append** rows to the 'Products' tab in Google Sheets.")
            uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
            
            if uploaded_file:
                try:
                    new_data = pd.read_excel(uploaded_file)
                    st.dataframe(new_data.head(), use_container_width=True)
                    st.info(f"Ready to upload {len(new_data)} rows.")
                    
                    if st.button("Confirm Bulk Upload"):
                        with st.spinner("Uploading... do not close browser..."):
                            if bulk_append_to_sheet("Products", new_data):
                                st.success(f"✅ Successfully uploaded {len(new_data)} rows!")
                                st.rerun()
                except Exception as e:
                    st.error(f"Error reading file: {e}")

if __name__ == "__main__":
    main()
