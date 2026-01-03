# Download required packages:
# pip install streamlit pandas openpyxl python-dateutil plotly

# to run app:
# streamlit run app.py
# cloudflared tunnel --url http://localhost:8501

# to do:
# 1. sync button
# 2. login/authentication
# 3. USFM Pass manager
# 4. Update the reneal (so create another tab to mangage it)


# v6.1
import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import plotly.express as px
import os
import io

# --- CONFIGURATION ---
PRODUCT_FILE = 'product_database.xlsx'
CLIENT_FILE = 'client_database.xlsx'
SIM_FILE = 'sim_database.xlsx'

st.set_page_config(page_title="Product Management System", page_icon="🏭", layout="wide")

# --- CONSTANTS ---
BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]

# Columns for Databases
PROD_COLS = [
    "S/N", "OEM S/N", "Product Name", "Model", "Connectivity (2G/4G)", 
    "Cable Length", "Installation Date", "Activation Date", 
    "Validity (Months)", "Renewal Date", "Device UID", 
    "SIM Provider", "SIM Number", "Channel Partner", 
    "End User", "Industry Category"
]

CLIENT_COLS = ["Client Name", "Contact Person", "Phone Number", "Email", "Address"]

SIM_COLS = ["SIM Number", "Provider", "Status", "Plan Details", "Entry Date", "Used In S/N"]

# --- DATA HANDLING ---

def load_excel(file_path, columns):
    if not os.path.exists(file_path):
        df = pd.DataFrame(columns=columns)
        df.to_excel(file_path, index=False)
        return df
    try:
        df = pd.read_excel(file_path)
        # Ensure proper columns
        for col in columns:
            if col not in df.columns:
                df[col] = "" 
        # specific casting for SIM numbers to string to avoid matching issues
        if "SIM Number" in df.columns:
            df["SIM Number"] = df["SIM Number"].astype(str).str.strip().replace("nan", "")
        return df
    except Exception as e:
        st.error(f"Error loading {file_path}: {e}")
        return pd.DataFrame(columns=columns)

def save_excel(df, file_path):
    try:
        df.to_excel(file_path, index=False)
        return True
    except PermissionError:
        st.error(f"⚠️ Error: Close '{file_path}' before saving!")
        return False

# --- UTILITY FUNCTIONS ---

def calculate_renewal(activation_date, months):
    if not activation_date:
        return None
    return activation_date + relativedelta(months=int(months))

def check_expiry_status(renewal_date):
    if pd.isna(renewal_date):
        return "Unknown"
    today = pd.to_datetime(datetime.now().date())
    renewal = pd.to_datetime(renewal_date)
    days_left = (renewal - today).days
    
    if days_left < 0: return "Expired"
    elif days_left <= 30: return "Expiring Soon"
    else: return "Active"

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# --- MAIN APP ---

def main():
    st.title("🏭 Product Management System")
    st.markdown("Manage installations, clients, SIM stock, and subscriptions.")
    st.markdown("---")

    # Load Data
    prod_df = load_excel(PRODUCT_FILE, PROD_COLS)
    client_df = load_excel(CLIENT_FILE, CLIENT_COLS)
    sim_df = load_excel(SIM_FILE, SIM_COLS)
    
    # Pre-process dates
    date_cols = ["Installation Date", "Activation Date", "Renewal Date"]
    for col in date_cols:
        if col in prod_df.columns:
            prod_df[col] = pd.to_datetime(prod_df[col], errors='coerce').dt.date

    # Auto-seed Client DB if empty
    if client_df.empty and not prod_df.empty:
        unique_users = prod_df["End User"].dropna().unique()
        if len(unique_users) > 0:
            new_entries = [{"Client Name": name} for name in unique_users if str(name).strip() != ""]
            client_df = pd.concat([client_df, pd.DataFrame(new_entries)], ignore_index=True)
            client_df.drop_duplicates(subset=["Client Name"], inplace=True)
            save_excel(client_df, CLIENT_FILE)

    st.sidebar.header("Navigation")
    menu = st.sidebar.radio(
        "Go to:", 
        ["Dashboard", "SIM Manager", "New Dispatch Entry", "Installation List", "Client Master", "Channel Partner Analytics", "IMPORT/EXPORT DB"]
    )
    st.sidebar.markdown("---")
    st.sidebar.caption(f"📦 Products: {len(prod_df)}")
    st.sidebar.caption(f"👥 Clients: {len(client_df)}")
    st.sidebar.caption(f"📶 SIMs: {len(sim_df)}")

    # Show callback messages
    if "msg_type" in st.session_state and st.session_state.msg_type:
        if st.session_state.msg_type == "success":
            st.success(st.session_state.msg_text)
        elif st.session_state.msg_type == "error":
            st.error(st.session_state.msg_text)
        elif st.session_state.msg_type == "warning":
            st.warning(st.session_state.msg_text)
        st.session_state.msg_type = None
        st.session_state.msg_text = None

    # ==========================
    # 1. DASHBOARD
    # ==========================
    if menu == "Dashboard":
        st.subheader("📊 Analytics Overview")
        if not prod_df.empty:
            prod_df['Status'] = prod_df['Renewal Date'].apply(check_expiry_status)
            expired_count = len(prod_df[prod_df['Status'] == "Expired"])
            expiring_count = len(prod_df[prod_df['Status'] == "Expiring Soon"])
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Installations", len(prod_df))
            c2.metric("Active Subscriptions", len(prod_df[prod_df['Status'] == "Active"]))
            c3.metric("Expiring Soon", expiring_count, delta="Action Needed", delta_color="inverse")
            c4.metric("Expired", expired_count, delta="Critical", delta_color="inverse")
            st.divider()

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.markdown("##### 🏭 Industry Distribution")
                if "Industry Category" in prod_df.columns and prod_df["Industry Category"].notna().any():
                    ind_counts = prod_df["Industry Category"].value_counts().reset_index()
                    ind_counts.columns = ["Category", "Count"]
                    fig = px.pie(ind_counts, values='Count', names='Category', hole=0.4)
                    st.plotly_chart(fig, use_container_width=True)
            with col_g2:
                st.markdown("##### 📈 Installation Growth (Monthly)")
                if "Installation Date" in prod_df.columns and prod_df["Installation Date"].notna().any():
                    trend_df = prod_df.copy()
                    trend_df["Installation Date"] = pd.to_datetime(trend_df["Installation Date"])
                    trend_data = trend_df.groupby(trend_df["Installation Date"].dt.to_period("M")).size().reset_index(name="Installations")
                    trend_data["Installation Date"] = trend_data["Installation Date"].astype(str)
                    fig_trend = px.area(trend_data, x="Installation Date", y="Installations", markers=True, color_discrete_sequence=["#00CC96"])
                    st.plotly_chart(fig_trend, use_container_width=True)

            if expired_count > 0 or expiring_count > 0:
                st.markdown("### ⚠️ Alert Center")
                tab_soon, tab_expired = st.tabs(["⏳ Expiring Soon", "❌ Expired"])
                today = pd.to_datetime(date.today())
                with tab_soon:
                    if expiring_count > 0:
                        df_soon = prod_df[prod_df['Status'] == "Expiring Soon"].copy()
                        df_soon["Days Left"] = (pd.to_datetime(df_soon["Renewal Date"]) - today).dt.days
                        st.dataframe(df_soon[["Days Left", "S/N", "End User", "Renewal Date", "Product Name"]].sort_values("Days Left"), use_container_width=True)
                    else: st.success("No devices expiring soon.")
                with tab_expired:
                    if expired_count > 0:
                        df_expired = prod_df[prod_df['Status'] == "Expired"].copy()
                        df_expired["Days Overdue"] = (today - pd.to_datetime(df_expired["Renewal Date"])).dt.days
                        st.dataframe(df_expired[["Days Overdue", "S/N", "End User", "Renewal Date", "Product Name"]].sort_values("Days Overdue", ascending=False), use_container_width=True)
                    else: st.success("No expired devices.")
        else: st.info("Welcome! Go to 'New Dispatch Entry' to add your first product.")

    # ==========================
    # 2. SIM MANAGER
    # ==========================
    elif menu == "SIM Manager":
        st.subheader("📶 SIM Inventory Manager")
        
        # Metrics
        total_sims = len(sim_df)
        available_sims = len(sim_df[sim_df["Status"] == "Available"])
        used_sims = len(sim_df[sim_df["Status"] == "Used"])
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Stock", total_sims)
        m2.metric("Available", available_sims, delta="Ready to Deploy")
        m3.metric("Used / Deployed", used_sims, delta_color="inverse")
        
        st.divider()
        
        col_form, col_view = st.columns([1, 2])
        
        with col_form:
            st.markdown("#### ➕ Add New Stock")
            with st.form("add_sim_form", clear_on_submit=True):
                new_sim_prov = st.selectbox("Provider", ["VI", "AIRTEL", "JIO", "BSNL", "Other"])
                new_sim_num = st.text_input("SIM Number (Required)")
                new_plan = st.text_input("Plan Details (Optional)")
                
                submitted_sim = st.form_submit_button("Add to Stock")
                if submitted_sim:
                    if not new_sim_num:
                        st.error("SIM Number is required.")
                    elif str(new_sim_num) in sim_df["SIM Number"].values:
                        st.error("This SIM Number already exists in stock!")
                    else:
                        new_row = {
                            "SIM Number": str(new_sim_num),
                            "Provider": new_sim_prov,
                            "Status": "Available",
                            "Plan Details": new_plan,
                            "Entry Date": date.today(),
                            "Used In S/N": ""
                        }
                        sim_df = pd.concat([sim_df, pd.DataFrame([new_row])], ignore_index=True)
                        save_excel(sim_df, SIM_FILE)
                        st.success(f"SIM {new_sim_num} added to inventory!")
                        st.rerun()

        with col_view:
            st.markdown("#### 📋 Stock Repository")
            filter_status = st.selectbox("Filter by Status", ["All", "Available", "Used"], index=0)
            
            view_df = sim_df.copy()
            if filter_status != "All":
                view_df = view_df[view_df["Status"] == filter_status]
            
            st.dataframe(view_df, use_container_width=True, height=400)

    # ==========================
    # 3. NEW DISPATCH ENTRY
    # ==========================
    elif menu == "New Dispatch Entry":
        st.subheader("📝 Register New Dispatch")

        # --- INITIALIZATION ---
        if "k_valid" not in st.session_state: st.session_state.k_valid = 12
        if "k_install" not in st.session_state: st.session_state.k_install = date.today()
        if "k_activ" not in st.session_state: st.session_state.k_activ = date.today()
        if "k_prod" not in st.session_state: st.session_state.k_prod = BASE_PRODUCT_LIST[0]
        if "k_conn" not in st.session_state: st.session_state.k_conn = "4G"
        if "k_sim_prov" not in st.session_state: st.session_state.k_sim_prov = "VI"
        if "k_partner_select" not in st.session_state: st.session_state.k_partner_select = "Select or Type New..."
        if "k_client_select" not in st.session_state: st.session_state.k_client_select = "Select or Type New..."
        if "k_ind_select" not in st.session_state: st.session_state.k_ind_select = "Select or Type New..."
        if "k_sim_select" not in st.session_state: st.session_state.k_sim_select = "Select or Type New..."
        
        # --- CALLBACK FUNCTION ---
        def submit_dispatch():
            sn_val = st.session_state.get("k_sn", "")
            oem_val = st.session_state.get("k_oem", "")
            model_val = st.session_state.get("k_model", "")
            conn_val = st.session_state.get("k_conn", "4G")
            uid_val = st.session_state.get("k_uid", "")
            sim_prov_val = st.session_state.get("k_sim_prov", "VI")
            
            # SIM Logic (Dropdown vs Manual)
            sim_select = st.session_state.get("k_sim_select", "")
            sim_new = st.session_state.get("k_sim_new", "")
            sim_num_val = sim_new if sim_select == "Select or Type New..." else sim_select

            partner_select = st.session_state.get("k_partner_select", "")
            client_select = st.session_state.get("k_client_select", "")
            ind_select = st.session_state.get("k_ind_select", "")
            prod_select = st.session_state.get("k_prod", "")
            
            partner_new = st.session_state.get("k_partner_new", "")
            client_new = st.session_state.get("k_client_new", "")
            ind_new = st.session_state.get("k_ind_new", "")
            prod_custom = st.session_state.get("k_custom_prod", "")
            
            final_prod = prod_custom if prod_select == "Custom" else prod_select
            cable_input = st.session_state.get("k_cable", "N/A")
            cable_len_val = cable_input if final_prod == "DWLR" else "N/A"
            final_partner = partner_new if partner_select == "Select or Type New..." else partner_select
            final_client = client_new if client_select == "Select or Type New..." else client_select
            final_ind = ind_new if ind_select == "Select or Type New..." else ind_select
            
            install_d = st.session_state.k_install
            activ_d = st.session_state.k_activ
            validity_d = st.session_state.k_valid
            calc_renew = calculate_renewal(activ_d, validity_d)

            missing = []
            if not sn_val: missing.append("S/N")
            if not final_client: missing.append("End User")
            if not final_prod: missing.append("Product Name")
            if not final_ind: missing.append("Industry")

            if missing:
                st.session_state.msg_type = "error"
                st.session_state.msg_text = f"❌ Missing required fields: {', '.join(missing)}"
                return

            current_prod_df = load_excel(PRODUCT_FILE, PROD_COLS)
            current_client_df = load_excel(CLIENT_FILE, CLIENT_COLS)
            current_sim_df = load_excel(SIM_FILE, SIM_COLS)

            if not current_prod_df.empty and str(sn_val) in current_prod_df["S/N"].astype(str).values:
                st.session_state.msg_type = "warning"
                st.session_state.msg_text = f"⚠️ Warning: Product S/N {sn_val} already exists."
            
            # 1. Save Product
            new_entry = {
                "S/N": sn_val, "OEM S/N": oem_val, "Product Name": final_prod, 
                "Model": model_val, "Connectivity (2G/4G)": conn_val, 
                "Cable Length": cable_len_val, "Installation Date": install_d, 
                "Activation Date": activ_d, "Validity (Months)": validity_d, 
                "Renewal Date": calc_renew, "Device UID": uid_val, 
                "SIM Provider": sim_prov_val, "SIM Number": sim_num_val, 
                "Channel Partner": final_partner, "End User": final_client, 
                "Industry Category": final_ind
            }
            updated_prod_df = pd.concat([current_prod_df, pd.DataFrame([new_entry])], ignore_index=True)
            save_excel(updated_prod_df, PRODUCT_FILE)

            # 2. Auto-Add New Client
            if final_client not in current_client_df["Client Name"].values:
                new_c_row = {"Client Name": final_client, "Contact Person": "", "Phone Number": "", "Email": "", "Address": ""}
                updated_client_df = pd.concat([current_client_df, pd.DataFrame([new_c_row])], ignore_index=True)
                save_excel(updated_client_df, CLIENT_FILE)

            # 3. Update SIM Inventory
            sim_str = str(sim_num_val).strip()
            if sim_str and sim_str.lower() != "n/a":
                if sim_str in current_sim_df["SIM Number"].values:
                    # Update existing SIM to Used
                    idx = current_sim_df[current_sim_df["SIM Number"] == sim_str].index
                    current_sim_df.at[idx[0], "Status"] = "Used"
                    current_sim_df.at[idx[0], "Used In S/N"] = sn_val
                    save_excel(current_sim_df, SIM_FILE)
                else:
                    # Auto-add manual SIM
                    new_sim_row = {
                        "SIM Number": sim_str, "Provider": sim_prov_val, "Status": "Used", 
                        "Plan Details": "Auto-added from Dispatch", "Entry Date": date.today(), "Used In S/N": sn_val
                    }
                    updated_sim_df = pd.concat([current_sim_df, pd.DataFrame([new_sim_row])], ignore_index=True)
                    save_excel(updated_sim_df, SIM_FILE)

            st.session_state.msg_type = "success"
            st.session_state.msg_text = f"✅ Product '{sn_val}' saved & SIM Inventory updated!"

            # Reset State
            keys_to_clear = ["k_sn", "k_oem", "k_model", "k_cable", "k_uid", "k_sim_new", "k_partner_new", "k_client_new", "k_ind_new", "k_custom_prod"]
            for key in keys_to_clear: st.session_state[key] = ""
            st.session_state.k_prod = BASE_PRODUCT_LIST[0]
            st.session_state.k_conn = "4G"
            st.session_state.k_sim_prov = "VI"
            st.session_state.k_partner_select = "Select or Type New..."
            st.session_state.k_client_select = "Select or Type New..."
            st.session_state.k_ind_select = "Select or Type New..."
            st.session_state.k_sim_select = "Select or Type New..."
            st.session_state.k_valid = 12

        # --- UI LAYOUT ---
        with st.container():
            col1, col2 = st.columns([1, 1])
            with col1:
                st.text_input("Product S/N# (Required)", key="k_sn")
                st.text_input("OEM S/N#", key="k_oem")
                prod_select = st.selectbox("Product Name", BASE_PRODUCT_LIST, key="k_prod")
                if prod_select == "Custom":
                    st.text_input("Enter Custom Product Name", placeholder="Type product name...", key="k_custom_prod")
                st.text_input("Model", key="k_model")
                st.selectbox("Connectivity", ["4G", "2G", "NB-IoT", "WiFi", "LoRaWAN", "NA"], key="k_conn")

            with col2:
                current_prod = st.session_state.get("k_prod", BASE_PRODUCT_LIST[0])
                current_custom = st.session_state.get("k_custom_prod", "")
                actual_prod = current_custom if current_prod == "Custom" else current_prod
                
                if actual_prod == "DWLR":
                    st.text_input("Cable Length (Meters)", key="k_cable")
                else:
                    st.text_input("Cable Length", value="N/A", disabled=True)
                
                st.date_input("Installation Date", key="k_install")
                st.date_input("Activation Date", key="k_activ")
                st.number_input("Validity (Months)", min_value=1, key="k_valid")

            st.divider()
            c3, c4, c5 = st.columns(3)
            with c3:
                st.text_input("Device UID", key="k_uid")
                st.selectbox("SIM Provider", ["VI", "AIRTEL", "JIO", "BSNL", "Other", "N/A"], key="k_sim_prov")
                
                # --- SIM DROPDOWN LOGIC ---
                # Get available SIMs for dropdown
                available_sim_list = sim_df[sim_df["Status"] == "Available"]["SIM Number"].astype(str).unique().tolist()
                st.selectbox("SIM Number", ["Select or Type New..."] + available_sim_list, key="k_sim_select")
                
                if st.session_state.get("k_sim_select") == "Select or Type New...":
                    st.text_input("Enter New SIM Number", key="k_sim_new", help="This will be added to stock as 'Used' automatically.")

            with c4:
                existing_partners = list(prod_df["Channel Partner"].dropna().unique())
                clean_partners = [str(p) for p in existing_partners if str(p).strip() != ""]
                st.selectbox("Channel Partner", ["Select or Type New..."] + clean_partners, key="k_partner_select")
                if st.session_state.get("k_partner_select") == "Select or Type New...":
                    st.text_input("Enter New Partner Name", key="k_partner_new")

                client_list = list(client_df["Client Name"].unique())
                client_list.sort()
                st.selectbox("End User (Client)", ["Select or Type New..."] + client_list, key="k_client_select")
                if st.session_state.get("k_client_select") == "Select or Type New...":
                    st.text_input("Enter New Client Name", key="k_client_new")
            with c5:
                existing_inds = list(prod_df["Industry Category"].dropna().unique())
                st.selectbox("Industry Category", ["Select or Type New..."] + existing_inds, key="k_ind_select")
                if st.session_state.get("k_ind_select") == "Select or Type New...":
                    st.text_input("Enter New Industry Category", key="k_ind_new")

            st.button("💾 Save to Database", type="primary", use_container_width=True, on_click=submit_dispatch)

    # ==========================
    # 4. INSTALLATION LIST
    # ==========================
    elif menu == "Installation List":
        st.subheader("🔎 Installation Repository")
        col_search, _ = st.columns([2, 1])
        with col_search:
            search_term = st.text_input("🔍 Search Database", placeholder="Type S/N, Client, or UID...")
        
        display_df = prod_df.copy()
        if search_term:
            mask = display_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
            display_df = display_df[mask]
            st.success(f"Found {len(display_df)} records")

        st.dataframe(display_df, use_container_width=True, height=600, column_config={"Renewal Date": st.column_config.DateColumn("Renewal Date", format="YYYY-MM-DD")})

    # ==========================
    # 5. CLIENT MASTER
    # ==========================
    elif menu == "Client Master":
        st.subheader("👥 Client Master Database")
        col_list, col_form = st.columns([1, 1])
        
        with col_list:
            st.markdown("#### Select Client to Edit")
            client_names = list(client_df["Client Name"].unique())
            client_names.sort()
            selected_client_name = st.selectbox("Search Client", ["➕ Add New Client"] + client_names)
            st.divider()
            st.dataframe(client_df, use_container_width=True, height=400)

        with col_form:
            st.markdown("#### Client Details")
            is_new = (selected_client_name == "➕ Add New Client")
            current_data = {}
            if not is_new:
                record = client_df[client_df["Client Name"] == selected_client_name].iloc[0]
                current_data = record.to_dict()
            
            with st.form("client_form"):
                new_name = st.text_input("Client Name (End User)", value=current_data.get("Client Name", ""))
                contact = st.text_input("Contact Person", value=current_data.get("Contact Person", ""))
                phone = st.text_input("Phone Number", value=current_data.get("Phone Number", ""))
                email = st.text_input("Email ID", value=current_data.get("Email", ""))
                address = st.text_area("Address / Location", value=current_data.get("Address", ""))
                
                submitted = st.form_submit_button("💾 Save Client Details")
                
                if submitted:
                    if not new_name.strip():
                        st.error("Client Name is required.")
                    else:
                        if is_new:
                            if new_name in client_names:
                                st.error("Client already exists!")
                            else:
                                new_row = {
                                    "Client Name": new_name, "Contact Person": contact, 
                                    "Phone Number": phone, "Email": email, "Address": address
                                }
                                client_df = pd.concat([client_df, pd.DataFrame([new_row])], ignore_index=True)
                                if save_excel(client_df, CLIENT_FILE):
                                    st.success(f"Client '{new_name}' added!")
                                    st.rerun()
                        else:
                            idx = client_df[client_df["Client Name"] == selected_client_name].index
                            client_df.at[idx[0], "Client Name"] = new_name
                            client_df.at[idx[0], "Contact Person"] = contact
                            client_df.at[idx[0], "Phone Number"] = phone
                            client_df.at[idx[0], "Email"] = email
                            client_df.at[idx[0], "Address"] = address
                            save_excel(client_df, CLIENT_FILE)
                            
                            if new_name != selected_client_name:
                                count = len(prod_df[prod_df["End User"] == selected_client_name])
                                if count > 0:
                                    prod_df.loc[prod_df["End User"] == selected_client_name, "End User"] = new_name
                                    save_excel(prod_df, PRODUCT_FILE)
                                    st.info(f"Updated {count} records in History.")
                            st.success("Updated successfully!")
                            st.rerun()

    # ==========================
    # 6. CHANNEL PARTNER ANALYTICS
    # ==========================
    elif menu == "Channel Partner Analytics":
        st.subheader("🤝 Channel Partner Performance")
        if not prod_df.empty:
            partner_df = prod_df[prod_df["Channel Partner"].notna() & (prod_df["Channel Partner"] != "")]
            if not partner_df.empty:
                partner_stats = partner_df.groupby("Channel Partner").agg({
                    "S/N": "count", "End User": "nunique", "Product Name": lambda x: ", ".join(sorted(x.unique()))
                }).reset_index()
                partner_stats.columns = ["Channel Partner", "Total Installations", "Unique Clients", "Product Types Sold"]
                partner_stats = partner_stats.sort_values(by="Total Installations", ascending=False)

                col_p1, col_p2 = st.columns([2, 1])
                with col_p1:
                    fig_part = px.bar(partner_stats, x="Channel Partner", y="Total Installations", color="Total Installations", color_continuous_scale="Viridis")
                    st.plotly_chart(fig_part, use_container_width=True)
                with col_p2:
                    st.metric("🏆 Top Performer", partner_stats.iloc[0]["Channel Partner"])
                    st.metric("📈 Max Installs", partner_stats.iloc[0]["Total Installations"])

                st.dataframe(partner_stats, use_container_width=True)
                st.download_button("⬇️ Download Partner Report", convert_df_to_excel(partner_stats), "Partner_Report.xlsx")
            else: st.info("No Channel Partner data found.")
        else: st.info("Database is empty.")

    # ==========================
    # 7. IMPORT/EXPORT DB
    # ==========================
    elif menu == "IMPORT/EXPORT DB":
        st.subheader("💾 Database Management")
        tab1, tab2 = st.tabs(["⬇️ Export Full DB", "⬆️ Import Data"])
        with tab1:
            if not prod_df.empty:
                st.download_button("Download Product DB (Excel)", convert_df_to_excel(prod_df), "Product_DB.xlsx")
                st.download_button("Download Client DB (Excel)", convert_df_to_excel(client_df), "Client_DB.xlsx")
                st.download_button("Download SIM DB (Excel)", convert_df_to_excel(sim_df), "SIM_DB.xlsx")
            else: st.warning("Database is empty.")
        with tab2:
            st.write("Merge data into Product Database")
            uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
            if uploaded_file:
                try:
                    new_data = pd.read_excel(uploaded_file)
                    missing = [c for c in PROD_COLS if c not in new_data.columns]
                    if missing: st.error(f"❌ Missing columns: {missing}")
                    else:
                        st.dataframe(new_data.head())
                        if st.button("Confirm Import"):
                            prod_df = pd.concat([prod_df, new_data], ignore_index=True)
                            save_excel(prod_df, PRODUCT_FILE)
                            st.success("Import Successful!")
                            st.rerun()
                except Exception as e: st.error(f"Error: {e}")

if __name__ == "__main__":
    main()



# v6
# import streamlit as st
# import pandas as pd
# from datetime import datetime, date
# from dateutil.relativedelta import relativedelta
# import plotly.express as px
# import os
# import io

# # --- CONFIGURATION ---
# PRODUCT_FILE = 'product_database.xlsx'
# CLIENT_FILE = 'client_database.xlsx'
# SIM_FILE = 'sim_database.xlsx'

# st.set_page_config(page_title="Product Management System", page_icon="🏭", layout="wide")

# # --- CONSTANTS ---
# BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]

# # Columns for Databases
# PROD_COLS = [
#     "S/N", "OEM S/N", "Product Name", "Model", "Connectivity (2G/4G)", 
#     "Cable Length", "Installation Date", "Activation Date", 
#     "Validity (Months)", "Renewal Date", "Device UID", 
#     "SIM Provider", "SIM Number", "Channel Partner", 
#     "End User", "Industry Category"
# ]

# CLIENT_COLS = ["Client Name", "Contact Person", "Phone Number", "Email", "Address"]

# SIM_COLS = ["SIM Number", "Provider", "Status", "Plan Details", "Entry Date", "Used In S/N"]

# # --- DATA HANDLING ---

# def load_excel(file_path, columns):
#     if not os.path.exists(file_path):
#         df = pd.DataFrame(columns=columns)
#         df.to_excel(file_path, index=False)
#         return df
#     try:
#         df = pd.read_excel(file_path)
#         # Ensure proper columns
#         for col in columns:
#             if col not in df.columns:
#                 df[col] = "" 
#         # specific casting for SIM numbers to string to avoid matching issues
#         if "SIM Number" in df.columns:
#             df["SIM Number"] = df["SIM Number"].astype(str).str.strip()
#         return df
#     except Exception as e:
#         st.error(f"Error loading {file_path}: {e}")
#         return pd.DataFrame(columns=columns)

# def save_excel(df, file_path):
#     try:
#         df.to_excel(file_path, index=False)
#         return True
#     except PermissionError:
#         st.error(f"⚠️ Error: Close '{file_path}' before saving!")
#         return False

# # --- UTILITY FUNCTIONS ---

# def calculate_renewal(activation_date, months):
#     if not activation_date:
#         return None
#     return activation_date + relativedelta(months=int(months))

# def check_expiry_status(renewal_date):
#     if pd.isna(renewal_date):
#         return "Unknown"
#     today = pd.to_datetime(datetime.now().date())
#     renewal = pd.to_datetime(renewal_date)
#     days_left = (renewal - today).days
    
#     if days_left < 0: return "Expired"
#     elif days_left <= 30: return "Expiring Soon"
#     else: return "Active"

# def convert_df_to_excel(df):
#     output = io.BytesIO()
#     with pd.ExcelWriter(output, engine='openpyxl') as writer:
#         df.to_excel(writer, index=False)
#     return output.getvalue()

# # --- MAIN APP ---

# def main():
#     st.title("🏭 Product Management System")
#     st.markdown("Manage installations, clients, SIM stock, and subscriptions.")
#     st.markdown("---")

#     # Load Data
#     prod_df = load_excel(PRODUCT_FILE, PROD_COLS)
#     client_df = load_excel(CLIENT_FILE, CLIENT_COLS)
#     sim_df = load_excel(SIM_FILE, SIM_COLS)
    
#     # Pre-process dates
#     date_cols = ["Installation Date", "Activation Date", "Renewal Date"]
#     for col in date_cols:
#         if col in prod_df.columns:
#             prod_df[col] = pd.to_datetime(prod_df[col], errors='coerce').dt.date

#     # Auto-seed Client DB if empty
#     if client_df.empty and not prod_df.empty:
#         unique_users = prod_df["End User"].dropna().unique()
#         if len(unique_users) > 0:
#             new_entries = [{"Client Name": name} for name in unique_users if str(name).strip() != ""]
#             client_df = pd.concat([client_df, pd.DataFrame(new_entries)], ignore_index=True)
#             client_df.drop_duplicates(subset=["Client Name"], inplace=True)
#             save_excel(client_df, CLIENT_FILE)

#     st.sidebar.header("Navigation")
#     menu = st.sidebar.radio(
#         "Go to:", 
#         ["Dashboard", "SIM Manager", "New Dispatch Entry", "Installation List", "Client Master", "Channel Partner Analytics", "IMPORT/EXPORT DB"]
#     )
#     st.sidebar.markdown("---")
#     st.sidebar.caption(f"📦 Products: {len(prod_df)}")
#     st.sidebar.caption(f"👥 Clients: {len(client_df)}")
#     st.sidebar.caption(f"📶 SIMs: {len(sim_df)}")

#     # Show callback messages
#     if "msg_type" in st.session_state and st.session_state.msg_type:
#         if st.session_state.msg_type == "success":
#             st.success(st.session_state.msg_text)
#         elif st.session_state.msg_type == "error":
#             st.error(st.session_state.msg_text)
#         elif st.session_state.msg_type == "warning":
#             st.warning(st.session_state.msg_text)
#         st.session_state.msg_type = None
#         st.session_state.msg_text = None

#     # ==========================
#     # 1. DASHBOARD
#     # ==========================
#     if menu == "Dashboard":
#         st.subheader("📊 Analytics Overview")
#         if not prod_df.empty:
#             prod_df['Status'] = prod_df['Renewal Date'].apply(check_expiry_status)
#             expired_count = len(prod_df[prod_df['Status'] == "Expired"])
#             expiring_count = len(prod_df[prod_df['Status'] == "Expiring Soon"])
            
#             c1, c2, c3, c4 = st.columns(4)
#             c1.metric("Total Installations", len(prod_df))
#             c2.metric("Active Subscriptions", len(prod_df[prod_df['Status'] == "Active"]))
#             c3.metric("Expiring Soon", expiring_count, delta="Action Needed", delta_color="inverse")
#             c4.metric("Expired", expired_count, delta="Critical", delta_color="inverse")
#             st.divider()

#             col_g1, col_g2 = st.columns(2)
#             with col_g1:
#                 st.markdown("##### 🏭 Industry Distribution")
#                 if "Industry Category" in prod_df.columns and prod_df["Industry Category"].notna().any():
#                     ind_counts = prod_df["Industry Category"].value_counts().reset_index()
#                     ind_counts.columns = ["Category", "Count"]
#                     fig = px.pie(ind_counts, values='Count', names='Category', hole=0.4)
#                     st.plotly_chart(fig, use_container_width=True)
#             with col_g2:
#                 st.markdown("##### 📈 Installation Growth (Monthly)")
#                 if "Installation Date" in prod_df.columns and prod_df["Installation Date"].notna().any():
#                     trend_df = prod_df.copy()
#                     trend_df["Installation Date"] = pd.to_datetime(trend_df["Installation Date"])
#                     trend_data = trend_df.groupby(trend_df["Installation Date"].dt.to_period("M")).size().reset_index(name="Installations")
#                     trend_data["Installation Date"] = trend_data["Installation Date"].astype(str)
#                     fig_trend = px.area(trend_data, x="Installation Date", y="Installations", markers=True, color_discrete_sequence=["#00CC96"])
#                     st.plotly_chart(fig_trend, use_container_width=True)

#             if expired_count > 0 or expiring_count > 0:
#                 st.markdown("### ⚠️ Alert Center")
#                 tab_soon, tab_expired = st.tabs(["⏳ Expiring Soon", "❌ Expired"])
#                 today = pd.to_datetime(date.today())
#                 with tab_soon:
#                     if expiring_count > 0:
#                         df_soon = prod_df[prod_df['Status'] == "Expiring Soon"].copy()
#                         df_soon["Days Left"] = (pd.to_datetime(df_soon["Renewal Date"]) - today).dt.days
#                         st.dataframe(df_soon[["Days Left", "S/N", "End User", "Renewal Date", "Product Name"]].sort_values("Days Left"), use_container_width=True)
#                     else: st.success("No devices expiring soon.")
#                 with tab_expired:
#                     if expired_count > 0:
#                         df_expired = prod_df[prod_df['Status'] == "Expired"].copy()
#                         df_expired["Days Overdue"] = (today - pd.to_datetime(df_expired["Renewal Date"])).dt.days
#                         st.dataframe(df_expired[["Days Overdue", "S/N", "End User", "Renewal Date", "Product Name"]].sort_values("Days Overdue", ascending=False), use_container_width=True)
#                     else: st.success("No expired devices.")
#         else: st.info("Welcome! Go to 'New Dispatch Entry' to add your first product.")

#     # ==========================
#     # 2. SIM MANAGER (NEW)
#     # ==========================
#     elif menu == "SIM Manager":
#         st.subheader("📶 SIM Inventory Manager")
        
#         # Metrics
#         total_sims = len(sim_df)
#         available_sims = len(sim_df[sim_df["Status"] == "Available"])
#         used_sims = len(sim_df[sim_df["Status"] == "Used"])
        
#         m1, m2, m3 = st.columns(3)
#         m1.metric("Total Stock", total_sims)
#         m2.metric("Available", available_sims, delta="Ready to Deploy")
#         m3.metric("Used / Deployed", used_sims, delta_color="inverse")
        
#         st.divider()
        
#         col_form, col_view = st.columns([1, 2])
        
#         with col_form:
#             st.markdown("#### ➕ Add New Stock")
#             with st.form("add_sim_form", clear_on_submit=True):
#                 new_sim_prov = st.selectbox("Provider", ["VI", "AIRTEL", "JIO", "BSNL", "Other"])
#                 new_sim_num = st.text_input("SIM Number (Required)")
#                 new_plan = st.text_input("Plan Details (Optional)")
                
#                 submitted_sim = st.form_submit_button("Add to Stock")
#                 if submitted_sim:
#                     if not new_sim_num:
#                         st.error("SIM Number is required.")
#                     elif str(new_sim_num) in sim_df["SIM Number"].values:
#                         st.error("This SIM Number already exists in stock!")
#                     else:
#                         new_row = {
#                             "SIM Number": str(new_sim_num),
#                             "Provider": new_sim_prov,
#                             "Status": "Available",
#                             "Plan Details": new_plan,
#                             "Entry Date": date.today(),
#                             "Used In S/N": ""
#                         }
#                         sim_df = pd.concat([sim_df, pd.DataFrame([new_row])], ignore_index=True)
#                         save_excel(sim_df, SIM_FILE)
#                         st.success(f"SIM {new_sim_num} added to inventory!")
#                         st.rerun()

#         with col_view:
#             st.markdown("#### 📋 Stock Repository")
#             # Filters
#             filter_status = st.selectbox("Filter by Status", ["All", "Available", "Used"], index=0)
            
#             view_df = sim_df.copy()
#             if filter_status != "All":
#                 view_df = view_df[view_df["Status"] == filter_status]
            
#             st.dataframe(view_df, use_container_width=True, height=400)

#     # ==========================
#     # 3. NEW DISPATCH ENTRY
#     # ==========================
#     elif menu == "New Dispatch Entry":
#         st.subheader("📝 Register New Dispatch")

#         # --- INITIALIZATION ---
#         if "k_valid" not in st.session_state: st.session_state.k_valid = 12
#         if "k_install" not in st.session_state: st.session_state.k_install = date.today()
#         if "k_activ" not in st.session_state: st.session_state.k_activ = date.today()
#         if "k_prod" not in st.session_state: st.session_state.k_prod = BASE_PRODUCT_LIST[0]
#         if "k_conn" not in st.session_state: st.session_state.k_conn = "4G"
#         if "k_sim_prov" not in st.session_state: st.session_state.k_sim_prov = "VI"
#         if "k_partner_select" not in st.session_state: st.session_state.k_partner_select = "Select or Type New..."
#         if "k_client_select" not in st.session_state: st.session_state.k_client_select = "Select or Type New..."
#         if "k_ind_select" not in st.session_state: st.session_state.k_ind_select = "Select or Type New..."
        
#         # --- CALLBACK FUNCTION ---
#         def submit_dispatch():
#             sn_val = st.session_state.get("k_sn", "")
#             oem_val = st.session_state.get("k_oem", "")
#             model_val = st.session_state.get("k_model", "")
#             conn_val = st.session_state.get("k_conn", "4G")
#             uid_val = st.session_state.get("k_uid", "")
#             sim_prov_val = st.session_state.get("k_sim_prov", "VI")
#             sim_num_val = st.session_state.get("k_sim_num", "")
#             partner_select = st.session_state.get("k_partner_select", "")
#             client_select = st.session_state.get("k_client_select", "")
#             ind_select = st.session_state.get("k_ind_select", "")
#             prod_select = st.session_state.get("k_prod", "")
            
#             partner_new = st.session_state.get("k_partner_new", "")
#             client_new = st.session_state.get("k_client_new", "")
#             ind_new = st.session_state.get("k_ind_new", "")
#             prod_custom = st.session_state.get("k_custom_prod", "")
            
#             final_prod = prod_custom if prod_select == "Custom" else prod_select
#             cable_input = st.session_state.get("k_cable", "N/A")
#             cable_len_val = cable_input if final_prod == "DWLR" else "N/A"
#             final_partner = partner_new if partner_select == "Select or Type New..." else partner_select
#             final_client = client_new if client_select == "Select or Type New..." else client_select
#             final_ind = ind_new if ind_select == "Select or Type New..." else ind_select
            
#             install_d = st.session_state.k_install
#             activ_d = st.session_state.k_activ
#             validity_d = st.session_state.k_valid
#             calc_renew = calculate_renewal(activ_d, validity_d)

#             missing = []
#             if not sn_val: missing.append("S/N")
#             if not final_client: missing.append("End User")
#             if not final_prod: missing.append("Product Name")
#             if not final_ind: missing.append("Industry")

#             if missing:
#                 st.session_state.msg_type = "error"
#                 st.session_state.msg_text = f"❌ Missing required fields: {', '.join(missing)}"
#                 return

#             current_prod_df = load_excel(PRODUCT_FILE, PROD_COLS)
#             current_client_df = load_excel(CLIENT_FILE, CLIENT_COLS)
#             current_sim_df = load_excel(SIM_FILE, SIM_COLS)

#             if not current_prod_df.empty and str(sn_val) in current_prod_df["S/N"].astype(str).values:
#                 st.session_state.msg_type = "warning"
#                 st.session_state.msg_text = f"⚠️ Warning: Product S/N {sn_val} already exists."
            
#             # 1. Save Product
#             new_entry = {
#                 "S/N": sn_val, "OEM S/N": oem_val, "Product Name": final_prod, 
#                 "Model": model_val, "Connectivity (2G/4G)": conn_val, 
#                 "Cable Length": cable_len_val, "Installation Date": install_d, 
#                 "Activation Date": activ_d, "Validity (Months)": validity_d, 
#                 "Renewal Date": calc_renew, "Device UID": uid_val, 
#                 "SIM Provider": sim_prov_val, "SIM Number": sim_num_val, 
#                 "Channel Partner": final_partner, "End User": final_client, 
#                 "Industry Category": final_ind
#             }
#             updated_prod_df = pd.concat([current_prod_df, pd.DataFrame([new_entry])], ignore_index=True)
#             save_excel(updated_prod_df, PRODUCT_FILE)

#             # 2. Auto-Add New Client
#             if final_client not in current_client_df["Client Name"].values:
#                 new_c_row = {"Client Name": final_client, "Contact Person": "", "Phone Number": "", "Email": "", "Address": ""}
#                 updated_client_df = pd.concat([current_client_df, pd.DataFrame([new_c_row])], ignore_index=True)
#                 save_excel(updated_client_df, CLIENT_FILE)

#             # 3. Update SIM Inventory (Smart Logic)
#             sim_str = str(sim_num_val).strip()
#             if sim_str:
#                 if sim_str in current_sim_df["SIM Number"].values:
#                     # Update existing SIM to Used
#                     idx = current_sim_df[current_sim_df["SIM Number"] == sim_str].index
#                     current_sim_df.at[idx[0], "Status"] = "Used"
#                     current_sim_df.at[idx[0], "Used In S/N"] = sn_val
#                     save_excel(current_sim_df, SIM_FILE)
#                 else:
#                     # Optional: Auto-add SIM to inventory as Used if not found? 
#                     # For now, let's just add it so inventory matches reality
#                     new_sim_row = {
#                         "SIM Number": sim_str, "Provider": sim_prov_val, "Status": "Used", 
#                         "Plan Details": "Auto-added from Dispatch", "Entry Date": date.today(), "Used In S/N": sn_val
#                     }
#                     updated_sim_df = pd.concat([current_sim_df, pd.DataFrame([new_sim_row])], ignore_index=True)
#                     save_excel(updated_sim_df, SIM_FILE)

#             st.session_state.msg_type = "success"
#             st.session_state.msg_text = f"✅ Product '{sn_val}' saved & SIM Inventory updated!"

#             # Reset State
#             keys_to_clear = ["k_sn", "k_oem", "k_model", "k_cable", "k_uid", "k_sim_num", "k_partner_new", "k_client_new", "k_ind_new", "k_custom_prod"]
#             for key in keys_to_clear: st.session_state[key] = ""
#             st.session_state.k_prod = BASE_PRODUCT_LIST[0]
#             st.session_state.k_conn = "4G"
#             st.session_state.k_sim_prov = "VI"
#             st.session_state.k_partner_select = "Select or Type New..."
#             st.session_state.k_client_select = "Select or Type New..."
#             st.session_state.k_ind_select = "Select or Type New..."
#             st.session_state.k_valid = 12

#         # --- UI LAYOUT ---
#         with st.container():
#             col1, col2 = st.columns([1, 1])
#             with col1:
#                 st.text_input("Product S/N# (Required)", key="k_sn")
#                 st.text_input("OEM S/N#", key="k_oem")
#                 prod_select = st.selectbox("Product Name", BASE_PRODUCT_LIST, key="k_prod")
#                 if prod_select == "Custom":
#                     st.text_input("Enter Custom Product Name", placeholder="Type product name...", key="k_custom_prod")
#                 st.text_input("Model", key="k_model")
#                 st.selectbox("Connectivity", ["4G", "2G", "NB-IoT", "WiFi", "LoRaWAN", "NA"], key="k_conn")

#             with col2:
#                 current_prod = st.session_state.get("k_prod", BASE_PRODUCT_LIST[0])
#                 current_custom = st.session_state.get("k_custom_prod", "")
#                 actual_prod = current_custom if current_prod == "Custom" else current_prod
                
#                 if actual_prod == "DWLR":
#                     st.text_input("Cable Length (Meters)", key="k_cable")
#                 else:
#                     st.text_input("Cable Length", value="N/A", disabled=True)
                
#                 st.date_input("Installation Date", key="k_install")
#                 st.date_input("Activation Date", key="k_activ")
#                 st.number_input("Validity (Months)", min_value=1, key="k_valid")

#             st.divider()
#             c3, c4, c5 = st.columns(3)
#             with c3:
#                 st.text_input("Device UID", key="k_uid")
#                 st.selectbox("SIM Provider", ["VI", "AIRTEL", "JIO", "BSNL", "Other", "N/A"], key="k_sim_prov")
#                 st.text_input("SIM Number", key="k_sim_num", help="If this SIM exists in Stock, it will be marked 'Used' automatically.")
#             with c4:
#                 existing_partners = list(prod_df["Channel Partner"].dropna().unique())
#                 clean_partners = [str(p) for p in existing_partners if str(p).strip() != ""]
#                 st.selectbox("Channel Partner", ["Select or Type New..."] + clean_partners, key="k_partner_select")
#                 if st.session_state.get("k_partner_select") == "Select or Type New...":
#                     st.text_input("Enter New Partner Name", key="k_partner_new")

#                 client_list = list(client_df["Client Name"].unique())
#                 client_list.sort()
#                 st.selectbox("End User (Client)", ["Select or Type New..."] + client_list, key="k_client_select")
#                 if st.session_state.get("k_client_select") == "Select or Type New...":
#                     st.text_input("Enter New Client Name", key="k_client_new")
#             with c5:
#                 existing_inds = list(prod_df["Industry Category"].dropna().unique())
#                 st.selectbox("Industry Category", ["Select or Type New..."] + existing_inds, key="k_ind_select")
#                 if st.session_state.get("k_ind_select") == "Select or Type New...":
#                     st.text_input("Enter New Industry Category", key="k_ind_new")

#             st.button("💾 Save to Database", type="primary", use_container_width=True, on_click=submit_dispatch)

#     # ==========================
#     # 4. INSTALLATION LIST
#     # ==========================
#     elif menu == "Installation List":
#         st.subheader("🔎 Installation Repository")
#         col_search, _ = st.columns([2, 1])
#         with col_search:
#             search_term = st.text_input("🔍 Search Database", placeholder="Type S/N, Client, or UID...")
        
#         display_df = prod_df.copy()
#         if search_term:
#             mask = display_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
#             display_df = display_df[mask]
#             st.success(f"Found {len(display_df)} records")

#         st.dataframe(display_df, use_container_width=True, height=600, column_config={"Renewal Date": st.column_config.DateColumn("Renewal Date", format="YYYY-MM-DD")})

#     # ==========================
#     # 5. CLIENT MASTER
#     # ==========================
#     elif menu == "Client Master":
#         st.subheader("👥 Client Master Database")
#         col_list, col_form = st.columns([1, 1])
        
#         with col_list:
#             st.markdown("#### Select Client to Edit")
#             client_names = list(client_df["Client Name"].unique())
#             client_names.sort()
#             selected_client_name = st.selectbox("Search Client", ["➕ Add New Client"] + client_names)
#             st.divider()
#             st.dataframe(client_df, use_container_width=True, height=400)

#         with col_form:
#             st.markdown("#### Client Details")
#             is_new = (selected_client_name == "➕ Add New Client")
#             current_data = {}
#             if not is_new:
#                 record = client_df[client_df["Client Name"] == selected_client_name].iloc[0]
#                 current_data = record.to_dict()
            
#             with st.form("client_form"):
#                 new_name = st.text_input("Client Name (End User)", value=current_data.get("Client Name", ""))
#                 contact = st.text_input("Contact Person", value=current_data.get("Contact Person", ""))
#                 phone = st.text_input("Phone Number", value=current_data.get("Phone Number", ""))
#                 email = st.text_input("Email ID", value=current_data.get("Email", ""))
#                 address = st.text_area("Address / Location", value=current_data.get("Address", ""))
                
#                 submitted = st.form_submit_button("💾 Save Client Details")
                
#                 if submitted:
#                     if not new_name.strip():
#                         st.error("Client Name is required.")
#                     else:
#                         if is_new:
#                             if new_name in client_names:
#                                 st.error("Client already exists!")
#                             else:
#                                 new_row = {
#                                     "Client Name": new_name, "Contact Person": contact, 
#                                     "Phone Number": phone, "Email": email, "Address": address
#                                 }
#                                 client_df = pd.concat([client_df, pd.DataFrame([new_row])], ignore_index=True)
#                                 if save_excel(client_df, CLIENT_FILE):
#                                     st.success(f"Client '{new_name}' added!")
#                                     st.rerun()
#                         else:
#                             idx = client_df[client_df["Client Name"] == selected_client_name].index
#                             client_df.at[idx[0], "Client Name"] = new_name
#                             client_df.at[idx[0], "Contact Person"] = contact
#                             client_df.at[idx[0], "Phone Number"] = phone
#                             client_df.at[idx[0], "Email"] = email
#                             client_df.at[idx[0], "Address"] = address
#                             save_excel(client_df, CLIENT_FILE)
                            
#                             if new_name != selected_client_name:
#                                 count = len(prod_df[prod_df["End User"] == selected_client_name])
#                                 if count > 0:
#                                     prod_df.loc[prod_df["End User"] == selected_client_name, "End User"] = new_name
#                                     save_excel(prod_df, PRODUCT_FILE)
#                                     st.info(f"Updated {count} records in History.")
#                             st.success("Updated successfully!")
#                             st.rerun()

#     # ==========================
#     # 6. CHANNEL PARTNER ANALYTICS
#     # ==========================
#     elif menu == "Channel Partner Analytics":
#         st.subheader("🤝 Channel Partner Performance")
#         if not prod_df.empty:
#             partner_df = prod_df[prod_df["Channel Partner"].notna() & (prod_df["Channel Partner"] != "")]
#             if not partner_df.empty:
#                 partner_stats = partner_df.groupby("Channel Partner").agg({
#                     "S/N": "count", "End User": "nunique", "Product Name": lambda x: ", ".join(sorted(x.unique()))
#                 }).reset_index()
#                 partner_stats.columns = ["Channel Partner", "Total Installations", "Unique Clients", "Product Types Sold"]
#                 partner_stats = partner_stats.sort_values(by="Total Installations", ascending=False)

#                 col_p1, col_p2 = st.columns([2, 1])
#                 with col_p1:
#                     fig_part = px.bar(partner_stats, x="Channel Partner", y="Total Installations", color="Total Installations", color_continuous_scale="Viridis")
#                     st.plotly_chart(fig_part, use_container_width=True)
#                 with col_p2:
#                     st.metric("🏆 Top Performer", partner_stats.iloc[0]["Channel Partner"])
#                     st.metric("📈 Max Installs", partner_stats.iloc[0]["Total Installations"])

#                 st.dataframe(partner_stats, use_container_width=True)
#                 st.download_button("⬇️ Download Partner Report", convert_df_to_excel(partner_stats), "Partner_Report.xlsx")
#             else: st.info("No Channel Partner data found.")
#         else: st.info("Database is empty.")

#     # ==========================
#     # 7. IMPORT/EXPORT DB
#     # ==========================
#     elif menu == "IMPORT/EXPORT DB":
#         st.subheader("💾 Database Management")
#         tab1, tab2 = st.tabs(["⬇️ Export Full DB", "⬆️ Import Data"])
#         with tab1:
#             if not prod_df.empty:
#                 st.download_button("Download Product DB (Excel)", convert_df_to_excel(prod_df), "Product_DB.xlsx")
#                 st.download_button("Download Client DB (Excel)", convert_df_to_excel(client_df), "Client_DB.xlsx")
#                 st.download_button("Download SIM DB (Excel)", convert_df_to_excel(sim_df), "SIM_DB.xlsx")
#             else: st.warning("Database is empty.")
#         with tab2:
#             st.write("Merge data into Product Database")
#             uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
#             if uploaded_file:
#                 try:
#                     new_data = pd.read_excel(uploaded_file)
#                     missing = [c for c in PROD_COLS if c not in new_data.columns]
#                     if missing: st.error(f"❌ Missing columns: {missing}")
#                     else:
#                         st.dataframe(new_data.head())
#                         if st.button("Confirm Import"):
#                             prod_df = pd.concat([prod_df, new_data], ignore_index=True)
#                             save_excel(prod_df, PRODUCT_FILE)
#                             st.success("Import Successful!")
#                             st.rerun()
#                 except Exception as e: st.error(f"Error: {e}")

# if __name__ == "__main__":
#     main()




# v5.1
# import streamlit as st
# import pandas as pd
# from datetime import datetime, date
# from dateutil.relativedelta import relativedelta
# import plotly.express as px
# import os
# import io

# # --- CONFIGURATION ---
# PRODUCT_FILE = 'product_database.xlsx'
# CLIENT_FILE = 'client_database.xlsx'

# st.set_page_config(page_title="Product Management System", page_icon="🏭", layout="wide")

# # --- CONSTANTS ---
# BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]

# # Columns for Product DB
# PROD_COLS = [
#     "S/N", "OEM S/N", "Product Name", "Model", "Connectivity (2G/4G)", 
#     "Cable Length", "Installation Date", "Activation Date", 
#     "Validity (Months)", "Renewal Date", "Device UID", 
#     "SIM Provider", "SIM Number", "Channel Partner", 
#     "End User", "Industry Category"
# ]

# # Columns for Client Master DB
# CLIENT_COLS = ["Client Name", "Contact Person", "Phone Number", "Email", "Address"]

# # --- DATA HANDLING ---

# def load_products():
#     """Loads the Product Excel file."""
#     if not os.path.exists(PRODUCT_FILE):
#         df = pd.DataFrame(columns=PROD_COLS)
#         df.to_excel(PRODUCT_FILE, index=False)
#         return df
#     try:
#         df = pd.read_excel(PRODUCT_FILE)
#         for col in PROD_COLS:
#             if col not in df.columns:
#                 df[col] = "" 
#         return df
#     except Exception as e:
#         st.error(f"Error loading Product DB: {e}")
#         return pd.DataFrame(columns=PROD_COLS)

# def save_products(df):
#     try:
#         df.to_excel(PRODUCT_FILE, index=False)
#         return True
#     except PermissionError:
#         st.error("⚠️ Error: Close 'product_database.xlsx' before saving!")
#         return False

# def load_clients(product_df=None):
#     if not os.path.exists(CLIENT_FILE):
#         df = pd.DataFrame(columns=CLIENT_COLS)
#         df.to_excel(CLIENT_FILE, index=False)
    
#     try:
#         client_df = pd.read_excel(CLIENT_FILE)
#         for col in CLIENT_COLS:
#             if col not in client_df.columns:
#                 client_df[col] = ""

#         # Auto-Seed Logic
#         if client_df.empty and product_df is not None and not product_df.empty:
#             unique_users = product_df["End User"].dropna().unique()
#             if len(unique_users) > 0:
#                 new_entries = [{"Client Name": name} for name in unique_users if str(name).strip() != ""]
#                 client_df = pd.concat([client_df, pd.DataFrame(new_entries)], ignore_index=True)
#                 client_df.drop_duplicates(subset=["Client Name"], inplace=True)
#                 save_clients(client_df)
        
#         return client_df
#     except Exception as e:
#         st.error(f"Error loading Client DB: {e}")
#         return pd.DataFrame(columns=CLIENT_COLS)

# def save_clients(df):
#     try:
#         df.to_excel(CLIENT_FILE, index=False)
#         return True
#     except PermissionError:
#         st.error("⚠️ Error: Close 'client_database.xlsx' before saving!")
#         return False

# # --- UTILITY FUNCTIONS ---

# def calculate_renewal(activation_date, months):
#     if not activation_date:
#         return None
#     return activation_date + relativedelta(months=int(months))

# def check_expiry_status(renewal_date):
#     if pd.isna(renewal_date):
#         return "Unknown"
#     today = pd.to_datetime(datetime.now().date())
#     renewal = pd.to_datetime(renewal_date)
#     days_left = (renewal - today).days
    
#     if days_left < 0: return "Expired"
#     elif days_left <= 30: return "Expiring Soon"
#     else: return "Active"

# def convert_df_to_excel(df):
#     output = io.BytesIO()
#     with pd.ExcelWriter(output, engine='openpyxl') as writer:
#         df.to_excel(writer, index=False)
#     return output.getvalue()

# # --- MAIN APP ---

# def main():
#     st.title("🏭 Product Management System")
#     st.markdown("Manage installations, clients, and subscriptions.")
#     st.markdown("---")

#     prod_df = load_products()
#     client_df = load_clients(prod_df) 
    
#     date_cols = ["Installation Date", "Activation Date", "Renewal Date"]
#     for col in date_cols:
#         if col in prod_df.columns:
#             prod_df[col] = pd.to_datetime(prod_df[col], errors='coerce').dt.date

#     st.sidebar.header("Navigation")
#     menu = st.sidebar.radio(
#         "Go to:", 
#         ["Dashboard", "Client Master", "New Dispatch Entry", "Installation List", "Channel Partner Analytics", "IMPORT/EXPORT DB"]
#     )
#     st.sidebar.markdown("---")
#     st.sidebar.caption(f"📦 Products: {len(prod_df)}")
#     st.sidebar.caption(f"👥 Clients: {len(client_df)}")

#     if "msg_type" in st.session_state and st.session_state.msg_type:
#         if st.session_state.msg_type == "success":
#             st.success(st.session_state.msg_text)
#         elif st.session_state.msg_type == "error":
#             st.error(st.session_state.msg_text)
#         elif st.session_state.msg_type == "warning":
#             st.warning(st.session_state.msg_text)
#         st.session_state.msg_type = None
#         st.session_state.msg_text = None

#     # ==========================
#     # 1. DASHBOARD
#     # ==========================
#     if menu == "Dashboard":
#         st.subheader("📊 Analytics Overview")
#         if not prod_df.empty:
#             prod_df['Status'] = prod_df['Renewal Date'].apply(check_expiry_status)
#             expired_count = len(prod_df[prod_df['Status'] == "Expired"])
#             expiring_count = len(prod_df[prod_df['Status'] == "Expiring Soon"])
            
#             c1, c2, c3, c4 = st.columns(4)
#             c1.metric("Total Installations", len(prod_df))
#             c2.metric("Active Subscriptions", len(prod_df[prod_df['Status'] == "Active"]))
#             c3.metric("Expiring Soon", expiring_count, delta="Action Needed", delta_color="inverse")
#             c4.metric("Expired", expired_count, delta="Critical", delta_color="inverse")
#             st.divider()

#             col_g1, col_g2 = st.columns(2)
#             with col_g1:
#                 st.markdown("##### 🏭 Industry Distribution")
#                 if "Industry Category" in prod_df.columns and prod_df["Industry Category"].notna().any():
#                     ind_counts = prod_df["Industry Category"].value_counts().reset_index()
#                     ind_counts.columns = ["Category", "Count"]
#                     fig = px.pie(ind_counts, values='Count', names='Category', hole=0.4)
#                     st.plotly_chart(fig, use_container_width=True)
#             with col_g2:
#                 st.markdown("##### 📈 Installation Growth (Monthly)")
#                 if "Installation Date" in prod_df.columns and prod_df["Installation Date"].notna().any():
#                     trend_df = prod_df.copy()
#                     trend_df["Installation Date"] = pd.to_datetime(trend_df["Installation Date"])
#                     trend_data = trend_df.groupby(trend_df["Installation Date"].dt.to_period("M")).size().reset_index(name="Installations")
#                     trend_data["Installation Date"] = trend_data["Installation Date"].astype(str)
#                     fig_trend = px.area(trend_data, x="Installation Date", y="Installations", markers=True, color_discrete_sequence=["#00CC96"])
#                     st.plotly_chart(fig_trend, use_container_width=True)

#             if expired_count > 0 or expiring_count > 0:
#                 st.markdown("### ⚠️ Alert Center")
#                 tab_soon, tab_expired = st.tabs(["⏳ Expiring Soon", "❌ Expired"])
#                 today = pd.to_datetime(date.today())
#                 with tab_soon:
#                     if expiring_count > 0:
#                         df_soon = prod_df[prod_df['Status'] == "Expiring Soon"].copy()
#                         df_soon["Days Left"] = (pd.to_datetime(df_soon["Renewal Date"]) - today).dt.days
#                         st.dataframe(df_soon[["Days Left", "S/N", "End User", "Renewal Date", "Product Name"]].sort_values("Days Left"), use_container_width=True)
#                     else: st.success("No devices expiring soon.")
#                 with tab_expired:
#                     if expired_count > 0:
#                         df_expired = prod_df[prod_df['Status'] == "Expired"].copy()
#                         df_expired["Days Overdue"] = (today - pd.to_datetime(df_expired["Renewal Date"])).dt.days
#                         st.dataframe(df_expired[["Days Overdue", "S/N", "End User", "Renewal Date", "Product Name"]].sort_values("Days Overdue", ascending=False), use_container_width=True)
#                     else: st.success("No expired devices.")
#         else: st.info("Welcome! Go to 'New Dispatch Entry' to add your first product.")

#     # ==========================
#     # 2. CLIENT MASTER
#     # ==========================
#     elif menu == "Client Master":
#         st.subheader("👥 Client Master Database")
#         col_list, col_form = st.columns([1, 1])
        
#         with col_list:
#             st.markdown("#### Select Client to Edit")
#             client_names = list(client_df["Client Name"].unique())
#             client_names.sort()
#             selected_client_name = st.selectbox("Search Client", ["➕ Add New Client"] + client_names)
#             st.divider()
#             st.dataframe(client_df, use_container_width=True, height=400)

#         with col_form:
#             st.markdown("#### Client Details")
#             is_new = (selected_client_name == "➕ Add New Client")
#             current_data = {}
#             if not is_new:
#                 record = client_df[client_df["Client Name"] == selected_client_name].iloc[0]
#                 current_data = record.to_dict()
            
#             with st.form("client_form"):
#                 new_name = st.text_input("Client Name (End User)", value=current_data.get("Client Name", ""))
#                 contact = st.text_input("Contact Person", value=current_data.get("Contact Person", ""))
#                 phone = st.text_input("Phone Number", value=current_data.get("Phone Number", ""))
#                 email = st.text_input("Email ID", value=current_data.get("Email", ""))
#                 address = st.text_area("Address / Location", value=current_data.get("Address", ""))
                
#                 submitted = st.form_submit_button("💾 Save Client Details")
                
#                 if submitted:
#                     if not new_name.strip():
#                         st.error("Client Name is required.")
#                     else:
#                         if is_new:
#                             if new_name in client_names:
#                                 st.error("Client already exists!")
#                             else:
#                                 new_row = {
#                                     "Client Name": new_name, "Contact Person": contact, 
#                                     "Phone Number": phone, "Email": email, "Address": address
#                                 }
#                                 client_df = pd.concat([client_df, pd.DataFrame([new_row])], ignore_index=True)
#                                 if save_clients(client_df):
#                                     st.success(f"Client '{new_name}' added!")
#                                     st.rerun()
#                         else:
#                             idx = client_df[client_df["Client Name"] == selected_client_name].index
#                             client_df.at[idx[0], "Client Name"] = new_name
#                             client_df.at[idx[0], "Contact Person"] = contact
#                             client_df.at[idx[0], "Phone Number"] = phone
#                             client_df.at[idx[0], "Email"] = email
#                             client_df.at[idx[0], "Address"] = address
#                             save_clients(client_df)
                            
#                             if new_name != selected_client_name:
#                                 count = len(prod_df[prod_df["End User"] == selected_client_name])
#                                 if count > 0:
#                                     prod_df.loc[prod_df["End User"] == selected_client_name, "End User"] = new_name
#                                     save_products(prod_df)
#                                     st.info(f"Also updated {count} records in Installation History.")
                                    
#                             st.success("Client details updated successfully!")
#                             st.rerun()

#     # ==========================
#     # 3. NEW DISPATCH ENTRY
#     # ==========================
#     elif menu == "New Dispatch Entry":
#         st.subheader("📝 Register New Dispatch")

#         # --- INITIALIZATION BLOCK ---
#         if "k_valid" not in st.session_state: st.session_state.k_valid = 12
#         if "k_install" not in st.session_state: st.session_state.k_install = date.today()
#         if "k_activ" not in st.session_state: st.session_state.k_activ = date.today()
#         if "k_prod" not in st.session_state: st.session_state.k_prod = BASE_PRODUCT_LIST[0]
#         if "k_conn" not in st.session_state: st.session_state.k_conn = "4G"
#         if "k_sim_prov" not in st.session_state: st.session_state.k_sim_prov = "VI"
#         if "k_partner_select" not in st.session_state: st.session_state.k_partner_select = "Select or Type New..."
#         if "k_client_select" not in st.session_state: st.session_state.k_client_select = "Select or Type New..."
#         if "k_ind_select" not in st.session_state: st.session_state.k_ind_select = "Select or Type New..."
        
#         # --- CALLBACK FUNCTION (FIXED with .get()) ---
#         def submit_dispatch():
#             # Use .get() for optional/conditional fields to avoid AttributeError
#             sn_val = st.session_state.get("k_sn", "")
#             oem_val = st.session_state.get("k_oem", "")
#             model_val = st.session_state.get("k_model", "")
#             conn_val = st.session_state.get("k_conn", "4G")
#             uid_val = st.session_state.get("k_uid", "")
#             sim_prov_val = st.session_state.get("k_sim_prov", "VI")
#             sim_num_val = st.session_state.get("k_sim_num", "")
#             partner_select = st.session_state.get("k_partner_select", "")
#             client_select = st.session_state.get("k_client_select", "")
#             ind_select = st.session_state.get("k_ind_select", "")
#             prod_select = st.session_state.get("k_prod", "")
            
#             # Use .get() specifically for conditional text inputs
#             partner_new = st.session_state.get("k_partner_new", "")
#             client_new = st.session_state.get("k_client_new", "")
#             ind_new = st.session_state.get("k_ind_new", "")
#             prod_custom = st.session_state.get("k_custom_prod", "")
            
#             final_prod = prod_custom if prod_select == "Custom" else prod_select
#             # Cable logic
#             cable_input = st.session_state.get("k_cable", "N/A")
#             cable_len_val = cable_input if final_prod == "DWLR" else "N/A"
            
#             final_partner = partner_new if partner_select == "Select or Type New..." else partner_select
#             final_client = client_new if client_select == "Select or Type New..." else client_select
#             final_ind = ind_new if ind_select == "Select or Type New..." else ind_select
            
#             install_d = st.session_state.k_install
#             activ_d = st.session_state.k_activ
#             validity_d = st.session_state.k_valid
#             calc_renew = calculate_renewal(activ_d, validity_d)

#             missing = []
#             if not sn_val: missing.append("S/N")
#             if not final_client: missing.append("End User")
#             if not final_prod: missing.append("Product Name")
#             if not final_ind: missing.append("Industry")

#             if missing:
#                 st.session_state.msg_type = "error"
#                 st.session_state.msg_text = f"❌ Missing required fields: {', '.join(missing)}"
#                 return

#             current_prod_df = load_products()
#             current_client_df = load_clients(current_prod_df)

#             if not current_prod_df.empty and str(sn_val) in current_prod_df["S/N"].astype(str).values:
#                 st.session_state.msg_type = "warning"
#                 st.session_state.msg_text = f"⚠️ Warning: Product S/N {sn_val} already exists."
            
#             new_entry = {
#                 "S/N": sn_val, "OEM S/N": oem_val, "Product Name": final_prod, 
#                 "Model": model_val, "Connectivity (2G/4G)": conn_val, 
#                 "Cable Length": cable_len_val, "Installation Date": install_d, 
#                 "Activation Date": activ_d, "Validity (Months)": validity_d, 
#                 "Renewal Date": calc_renew, "Device UID": uid_val, 
#                 "SIM Provider": sim_prov_val, "SIM Number": sim_num_val, 
#                 "Channel Partner": final_partner, "End User": final_client, 
#                 "Industry Category": final_ind
#             }
#             updated_prod_df = pd.concat([current_prod_df, pd.DataFrame([new_entry])], ignore_index=True)
#             save_products(updated_prod_df)

#             if final_client not in current_client_df["Client Name"].values:
#                 new_c_row = {"Client Name": final_client, "Contact Person": "", "Phone Number": "", "Email": "", "Address": ""}
#                 updated_client_df = pd.concat([current_client_df, pd.DataFrame([new_c_row])], ignore_index=True)
#                 save_clients(updated_client_df)

#             st.session_state.msg_type = "success"
#             st.session_state.msg_text = f"✅ Product '{sn_val}' saved successfully!"

#             # Reset State (using .get checks to be safe, though direct assign is fine for existing keys)
#             keys_to_clear = ["k_sn", "k_oem", "k_model", "k_cable", "k_uid", "k_sim_num", "k_partner_new", "k_client_new", "k_ind_new", "k_custom_prod"]
#             for key in keys_to_clear: 
#                 if key in st.session_state: st.session_state[key] = ""
                
#             st.session_state.k_prod = BASE_PRODUCT_LIST[0]
#             st.session_state.k_conn = "4G"
#             st.session_state.k_sim_prov = "VI"
#             st.session_state.k_partner_select = "Select or Type New..."
#             st.session_state.k_client_select = "Select or Type New..."
#             st.session_state.k_ind_select = "Select or Type New..."
#             st.session_state.k_valid = 12

#         # --- UI LAYOUT ---
#         with st.container():
#             col1, col2 = st.columns([1, 1])
#             with col1:
#                 st.text_input("Product S/N# (Required)", key="k_sn")
#                 st.text_input("OEM S/N#", key="k_oem")
#                 prod_select = st.selectbox("Product Name", BASE_PRODUCT_LIST, key="k_prod")
#                 if prod_select == "Custom":
#                     st.text_input("Enter Custom Product Name", placeholder="Type product name...", key="k_custom_prod")
#                 st.text_input("Model", key="k_model")
#                 st.selectbox("Connectivity", ["4G", "2G", "NB-IoT", "WiFi", "LoRaWAN", "NA"], key="k_conn")

#             with col2:
#                 current_prod = st.session_state.get("k_prod", BASE_PRODUCT_LIST[0])
#                 current_custom = st.session_state.get("k_custom_prod", "")
#                 actual_prod = current_custom if current_prod == "Custom" else current_prod
                
#                 if actual_prod == "DWLR":
#                     st.text_input("Cable Length (Meters)", key="k_cable")
#                 else:
#                     st.text_input("Cable Length", value="N/A", disabled=True)
                
#                 st.date_input("Installation Date", key="k_install")
#                 st.date_input("Activation Date", key="k_activ")
#                 st.number_input("Validity (Months)", min_value=1, key="k_valid")

#             st.divider()
#             c3, c4, c5 = st.columns(3)
#             with c3:
#                 st.text_input("Device UID", key="k_uid")
#                 st.selectbox("SIM Provider", ["VI", "AIRTEL", "JIO", "BSNL", "Other", "N/A"], key="k_sim_prov")
#                 st.text_input("SIM Number", key="k_sim_num")
#             with c4:
#                 existing_partners = list(prod_df["Channel Partner"].dropna().unique())
#                 clean_partners = [str(p) for p in existing_partners if str(p).strip() != ""]
#                 st.selectbox("Channel Partner", ["Select or Type New..."] + clean_partners, key="k_partner_select")
#                 if st.session_state.get("k_partner_select") == "Select or Type New...":
#                     st.text_input("Enter New Partner Name", key="k_partner_new")

#                 client_list = list(client_df["Client Name"].unique())
#                 client_list.sort()
#                 st.selectbox("End User (Client)", ["Select or Type New..."] + client_list, key="k_client_select")
#                 if st.session_state.get("k_client_select") == "Select or Type New...":
#                     st.text_input("Enter New Client Name", key="k_client_new")
#             with c5:
#                 existing_inds = list(prod_df["Industry Category"].dropna().unique())
#                 st.selectbox("Industry Category", ["Select or Type New..."] + existing_inds, key="k_ind_select")
#                 if st.session_state.get("k_ind_select") == "Select or Type New...":
#                     st.text_input("Enter New Industry Category", key="k_ind_new")

#             st.button("💾 Save to Database", type="primary", use_container_width=True, on_click=submit_dispatch)

#     # ==========================
#     # 4. INSTALLATION LIST
#     # ==========================
#     elif menu == "Installation List":
#         st.subheader("🔎 Installation Repository")
#         col_search, _ = st.columns([2, 1])
#         with col_search:
#             search_term = st.text_input("🔍 Search Database", placeholder="Type S/N, Client, or UID...")
        
#         display_df = prod_df.copy()
#         if search_term:
#             mask = display_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
#             display_df = display_df[mask]
#             st.success(f"Found {len(display_df)} records")

#         st.dataframe(display_df, use_container_width=True, height=600, column_config={"Renewal Date": st.column_config.DateColumn("Renewal Date", format="YYYY-MM-DD")})

#     # ==========================
#     # 5. CHANNEL PARTNER ANALYTICS
#     # ==========================
#     elif menu == "Channel Partner Analytics":
#         st.subheader("🤝 Channel Partner Performance")
#         if not prod_df.empty:
#             partner_df = prod_df[prod_df["Channel Partner"].notna() & (prod_df["Channel Partner"] != "")]
#             if not partner_df.empty:
#                 partner_stats = partner_df.groupby("Channel Partner").agg({
#                     "S/N": "count", "End User": "nunique", "Product Name": lambda x: ", ".join(sorted(x.unique()))
#                 }).reset_index()
#                 partner_stats.columns = ["Channel Partner", "Total Installations", "Unique Clients", "Product Types Sold"]
#                 partner_stats = partner_stats.sort_values(by="Total Installations", ascending=False)

#                 col_p1, col_p2 = st.columns([2, 1])
#                 with col_p1:
#                     fig_part = px.bar(partner_stats, x="Channel Partner", y="Total Installations", color="Total Installations", color_continuous_scale="Viridis")
#                     st.plotly_chart(fig_part, use_container_width=True)
#                 with col_p2:
#                     st.metric("🏆 Top Performer", partner_stats.iloc[0]["Channel Partner"])
#                     st.metric("📈 Max Installs", partner_stats.iloc[0]["Total Installations"])

#                 st.dataframe(partner_stats, use_container_width=True)
#                 st.download_button("⬇️ Download Partner Report", convert_df_to_excel(partner_stats), "Partner_Report.xlsx")
#             else: st.info("No Channel Partner data found.")
#         else: st.info("Database is empty.")

#     # ==========================
#     # 6. IMPORT/EXPORT DB
#     # ==========================
#     elif menu == "IMPORT/EXPORT DB":
#         st.subheader("💾 Database Management")
#         tab1, tab2 = st.tabs(["⬇️ Export Full DB", "⬆️ Import Data"])
#         with tab1:
#             if not prod_df.empty:
#                 st.download_button("Download Product Database (Excel)", convert_df_to_excel(prod_df), "Product_DB.xlsx")
#                 st.download_button("Download Client Database (Excel)", convert_df_to_excel(client_df), "Client_DB.xlsx")
#             else: st.warning("Database is empty.")
#         with tab2:
#             st.write("Merge data into Product Database")
#             uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
#             if uploaded_file:
#                 try:
#                     new_data = pd.read_excel(uploaded_file)
#                     missing = [c for c in PROD_COLS if c not in new_data.columns]
#                     if missing: st.error(f"❌ Missing columns: {missing}")
#                     else:
#                         st.dataframe(new_data.head())
#                         if st.button("Confirm Import"):
#                             prod_df = pd.concat([prod_df, new_data], ignore_index=True)
#                             save_products(prod_df)
#                             st.success("Import Successful!")
#                             st.rerun()
#                 except Exception as e: st.error(f"Error: {e}")

# if __name__ == "__main__":
#     main()




# v5
# import streamlit as st
# import pandas as pd
# from datetime import datetime, date
# from dateutil.relativedelta import relativedelta
# import plotly.express as px
# import os
# import io

# # --- CONFIGURATION ---
# PRODUCT_FILE = 'product_database.xlsx'
# CLIENT_FILE = 'client_database.xlsx'

# st.set_page_config(page_title="Product Management System", page_icon="🏭", layout="wide")

# # --- CONSTANTS ---
# BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]

# # Columns for Product DB
# PROD_COLS = [
#     "S/N", "OEM S/N", "Product Name", "Model", "Connectivity (2G/4G)", 
#     "Cable Length", "Installation Date", "Activation Date", 
#     "Validity (Months)", "Renewal Date", "Device UID", 
#     "SIM Provider", "SIM Number", "Channel Partner", 
#     "End User", "Industry Category"
# ]

# # Columns for Client Master DB
# CLIENT_COLS = ["Client Name", "Contact Person", "Phone Number", "Email", "Address"]

# # --- DATA HANDLING ---

# def load_products():
#     """Loads the Product Excel file."""
#     if not os.path.exists(PRODUCT_FILE):
#         df = pd.DataFrame(columns=PROD_COLS)
#         df.to_excel(PRODUCT_FILE, index=False)
#         return df
#     try:
#         df = pd.read_excel(PRODUCT_FILE)
#         # Ensure columns exist
#         for col in PROD_COLS:
#             if col not in df.columns:
#                 df[col] = "" 
#         return df
#     except Exception as e:
#         st.error(f"Error loading Product DB: {e}")
#         return pd.DataFrame(columns=PROD_COLS)

# def save_products(df):
#     try:
#         df.to_excel(PRODUCT_FILE, index=False)
#         return True
#     except PermissionError:
#         st.error("⚠️ Error: Close 'product_database.xlsx' before saving!")
#         return False

# def load_clients(product_df=None):
#     """
#     Loads Client DB. 
#     Auto-Sync: If Client DB is empty but Product DB has names, it seeds the Client DB.
#     """
#     # Create file if missing
#     if not os.path.exists(CLIENT_FILE):
#         df = pd.DataFrame(columns=CLIENT_COLS)
#         df.to_excel(CLIENT_FILE, index=False)
    
#     try:
#         client_df = pd.read_excel(CLIENT_FILE)
        
#         # Validation: Add missing columns
#         for col in CLIENT_COLS:
#             if col not in client_df.columns:
#                 client_df[col] = ""

#         # --- AUTO-SEED LOGIC ---
#         # If client DB is empty but we have products, import names from products
#         if client_df.empty and product_df is not None and not product_df.empty:
#             unique_users = product_df["End User"].dropna().unique()
#             if len(unique_users) > 0:
#                 new_entries = [{"Client Name": name} for name in unique_users if str(name).strip() != ""]
#                 client_df = pd.concat([client_df, pd.DataFrame(new_entries)], ignore_index=True)
#                 client_df.drop_duplicates(subset=["Client Name"], inplace=True)
#                 save_clients(client_df)
        
#         return client_df
#     except Exception as e:
#         st.error(f"Error loading Client DB: {e}")
#         return pd.DataFrame(columns=CLIENT_COLS)

# def save_clients(df):
#     try:
#         df.to_excel(CLIENT_FILE, index=False)
#         return True
#     except PermissionError:
#         st.error("⚠️ Error: Close 'client_database.xlsx' before saving!")
#         return False

# # --- UTILITY FUNCTIONS ---

# def calculate_renewal(activation_date, months):
#     if not activation_date:
#         return None
#     return activation_date + relativedelta(months=int(months))

# def check_expiry_status(renewal_date):
#     if pd.isna(renewal_date):
#         return "Unknown"
#     today = pd.to_datetime(datetime.now().date())
#     renewal = pd.to_datetime(renewal_date)
#     days_left = (renewal - today).days
    
#     if days_left < 0: return "Expired"
#     elif days_left <= 30: return "Expiring Soon"
#     else: return "Active"

# def convert_df_to_excel(df):
#     output = io.BytesIO()
#     with pd.ExcelWriter(output, engine='openpyxl') as writer:
#         df.to_excel(writer, index=False)
#     return output.getvalue()

# # --- MAIN APP ---

# def main():
#     st.title("🏭 Product Management System")
#     st.markdown("Manage installations, clients, and subscriptions.")
#     st.markdown("---")

#     # Load Data
#     prod_df = load_products()
#     client_df = load_clients(prod_df) # Pass prod_df for auto-seeding
    
#     # Pre-process dates
#     date_cols = ["Installation Date", "Activation Date", "Renewal Date"]
#     for col in date_cols:
#         if col in prod_df.columns:
#             prod_df[col] = pd.to_datetime(prod_df[col], errors='coerce').dt.date

#     # --- SIDEBAR ---
#     st.sidebar.header("Navigation")
#     menu = st.sidebar.radio(
#         "Go to:", 
#         ["Dashboard", "Client Master", "New Dispatch Entry", "Installation List", "Channel Partner Analytics", "IMPORT/EXPORT DB"]
#     )
#     st.sidebar.markdown("---")
#     st.sidebar.caption(f"📦 Products: {len(prod_df)}")
#     st.sidebar.caption(f"👥 Clients: {len(client_df)}")

#     # ==========================
#     # 1. DASHBOARD
#     # ==========================
#     if menu == "Dashboard":
#         st.subheader("📊 Analytics Overview")
#         if not prod_df.empty:
#             prod_df['Status'] = prod_df['Renewal Date'].apply(check_expiry_status)
#             expired_count = len(prod_df[prod_df['Status'] == "Expired"])
#             expiring_count = len(prod_df[prod_df['Status'] == "Expiring Soon"])
            
#             c1, c2, c3, c4 = st.columns(4)
#             c1.metric("Total Installations", len(prod_df))
#             c2.metric("Active Subscriptions", len(prod_df[prod_df['Status'] == "Active"]))
#             c3.metric("Expiring Soon", expiring_count, delta="Action Needed", delta_color="inverse")
#             c4.metric("Expired", expired_count, delta="Critical", delta_color="inverse")
#             st.divider()

#             col_g1, col_g2 = st.columns(2)
#             with col_g1:
#                 st.markdown("##### 🏭 Industry Distribution")
#                 if "Industry Category" in prod_df.columns and prod_df["Industry Category"].notna().any():
#                     ind_counts = prod_df["Industry Category"].value_counts().reset_index()
#                     ind_counts.columns = ["Category", "Count"]
#                     fig = px.pie(ind_counts, values='Count', names='Category', hole=0.4)
#                     st.plotly_chart(fig, use_container_width=True)
#             with col_g2:
#                 st.markdown("##### 📈 Installation Growth (Monthly)")
#                 if "Installation Date" in prod_df.columns and prod_df["Installation Date"].notna().any():
#                     trend_df = prod_df.copy()
#                     trend_df["Installation Date"] = pd.to_datetime(trend_df["Installation Date"])
#                     trend_data = trend_df.groupby(trend_df["Installation Date"].dt.to_period("M")).size().reset_index(name="Installations")
#                     trend_data["Installation Date"] = trend_data["Installation Date"].astype(str)
#                     fig_trend = px.area(trend_data, x="Installation Date", y="Installations", markers=True, color_discrete_sequence=["#00CC96"])
#                     st.plotly_chart(fig_trend, use_container_width=True)

#             if expired_count > 0 or expiring_count > 0:
#                 st.markdown("### ⚠️ Alert Center")
#                 tab_soon, tab_expired = st.tabs(["⏳ Expiring Soon", "❌ Expired"])
#                 today = pd.to_datetime(date.today())
#                 with tab_soon:
#                     if expiring_count > 0:
#                         df_soon = prod_df[prod_df['Status'] == "Expiring Soon"].copy()
#                         df_soon["Days Left"] = (pd.to_datetime(df_soon["Renewal Date"]) - today).dt.days
#                         st.dataframe(df_soon[["Days Left", "S/N", "End User", "Renewal Date", "Product Name"]].sort_values("Days Left"), use_container_width=True)
#                     else: st.success("No devices expiring soon.")
#                 with tab_expired:
#                     if expired_count > 0:
#                         df_expired = prod_df[prod_df['Status'] == "Expired"].copy()
#                         df_expired["Days Overdue"] = (today - pd.to_datetime(df_expired["Renewal Date"])).dt.days
#                         st.dataframe(df_expired[["Days Overdue", "S/N", "End User", "Renewal Date", "Product Name"]].sort_values("Days Overdue", ascending=False), use_container_width=True)
#                     else: st.success("No expired devices.")
#         else: st.info("Welcome! Go to 'New Dispatch Entry' to add your first product.")

#     # ==========================
#     # 2. CLIENT MASTER (NEW)
#     # ==========================
#     elif menu == "Client Master":
#         st.subheader("👥 Client Master Database")
        
#         col_list, col_form = st.columns([1, 1])
        
#         # --- LEFT: List of Clients ---
#         with col_list:
#             st.markdown("#### Select Client to Edit")
            
#             # Prepare list for dropdown
#             client_names = list(client_df["Client Name"].unique())
#             client_names.sort()
            
#             # Selectbox to pick a client (or 'Add New')
#             selected_client_name = st.selectbox("Search Client", ["➕ Add New Client"] + client_names)
            
#             st.divider()
#             st.dataframe(client_df, use_container_width=True, height=400)

#         # --- RIGHT: Edit/Add Form ---
#         with col_form:
#             st.markdown("#### Client Details")
            
#             # Determine form mode
#             is_new = (selected_client_name == "➕ Add New Client")
            
#             # Get existing data if editing
#             current_data = {}
#             if not is_new:
#                 record = client_df[client_df["Client Name"] == selected_client_name].iloc[0]
#                 current_data = record.to_dict()
            
#             with st.form("client_form"):
#                 # Field Inputs
#                 new_name = st.text_input("Client Name (End User)", value=current_data.get("Client Name", ""))
#                 contact = st.text_input("Contact Person", value=current_data.get("Contact Person", ""))
#                 phone = st.text_input("Phone Number", value=current_data.get("Phone Number", ""))
#                 email = st.text_input("Email ID", value=current_data.get("Email", ""))
#                 address = st.text_area("Address / Location", value=current_data.get("Address", ""))
                
#                 submitted = st.form_submit_button("💾 Save Client Details")
                
#                 if submitted:
#                     if not new_name.strip():
#                         st.error("Client Name is required.")
#                     else:
#                         if is_new:
#                             # ADD NEW
#                             if new_name in client_names:
#                                 st.error("Client already exists!")
#                             else:
#                                 new_row = {
#                                     "Client Name": new_name, "Contact Person": contact, 
#                                     "Phone Number": phone, "Email": email, "Address": address
#                                 }
#                                 client_df = pd.concat([client_df, pd.DataFrame([new_row])], ignore_index=True)
#                                 if save_clients(client_df):
#                                     st.success(f"Client '{new_name}' added!")
#                                     st.rerun()
#                         else:
#                             # UPDATE EXISTING
#                             # 1. Update Client DB
#                             idx = client_df[client_df["Client Name"] == selected_client_name].index
#                             client_df.at[idx[0], "Client Name"] = new_name
#                             client_df.at[idx[0], "Contact Person"] = contact
#                             client_df.at[idx[0], "Phone Number"] = phone
#                             client_df.at[idx[0], "Email"] = email
#                             client_df.at[idx[0], "Address"] = address
                            
#                             save_clients(client_df)
                            
#                             # 2. Update Product DB (Rename history if name changed)
#                             if new_name != selected_client_name:
#                                 count = len(prod_df[prod_df["End User"] == selected_client_name])
#                                 if count > 0:
#                                     prod_df.loc[prod_df["End User"] == selected_client_name, "End User"] = new_name
#                                     save_products(prod_df)
#                                     st.info(f"Also updated {count} records in Installation History.")
                                    
#                             st.success("Client details updated successfully!")
#                             st.rerun()

#     # ==========================
#     # 3. NEW DISPATCH ENTRY
#     # ==========================
#     elif menu == "New Dispatch Entry":
#         st.subheader("📝 Register New Dispatch")
        
#         # --- Session State Management for Clearing ---
#         if "form_cleared" not in st.session_state:
#             st.session_state.form_cleared = False

#         with st.container():
#             col1, col2 = st.columns([1, 1])
            
#             with col1:
#                 sn = st.text_input("Product S/N# (Required)", key="k_sn")
#                 oem_sn = st.text_input("OEM S/N#", key="k_oem")
                
#                 prod_select = st.selectbox("Product Name", BASE_PRODUCT_LIST, key="k_prod")
#                 if prod_select == "Custom":
#                     final_product = st.text_input("Enter Custom Product Name", placeholder="Type product name...", key="k_custom_prod")
#                 else:
#                     final_product = prod_select
                
#                 model = st.text_input("Model", key="k_model")
#                 connectivity = st.selectbox("Connectivity", ["4G", "2G", "NB-IoT", "WiFi", "LoRaWAN", "NA"], key="k_conn")

#             with col2:
#                 if final_product == "DWLR":
#                     cable_len = st.text_input("Cable Length (Meters)", key="k_cable")
#                 else:
#                     cable_len = "N/A"
#                     st.text_input("Cable Length", value="N/A", disabled=True)
                
#                 install_date = st.date_input("Installation Date", date.today(), key="k_install")
#                 activation_date = st.date_input("Activation Date", date.today(), key="k_activ")
#                 validity = st.number_input("Validity (Months)", min_value=1, value=12, key="k_valid")
                
#                 calc_renewal = calculate_renewal(activation_date, validity)
#                 st.info(f"📅 Auto-Calculated Renewal: {calc_renewal}")

#             st.divider()
            
#             c3, c4, c5 = st.columns(3)
#             with c3:
#                 device_uid = st.text_input("Device UID", key="k_uid")
#                 sim_prov = st.selectbox("SIM Provider", ["VI", "AIRTEL", "JIO", "BSNL", "Other", "N/A"], key="k_sim_prov")
#                 sim_num = st.text_input("SIM Number", key="k_sim_num")
            
#             with c4:
#                 # PARTNER DROPDOWN
#                 existing_partners = list(prod_df["Channel Partner"].dropna().unique())
#                 clean_partners = [str(p) for p in existing_partners if str(p).strip() != ""]
#                 partner_choice = st.selectbox("Channel Partner", ["Select or Type New..."] + clean_partners, key="k_partner_select")
                
#                 if partner_choice == "Select or Type New...":
#                     final_partner = st.text_input("Enter New Partner Name", key="k_partner_new")
#                 else:
#                     final_partner = partner_choice

#                 # CLIENT (END USER) DROPDOWN - FROM CLIENT MASTER
#                 client_list = list(client_df["Client Name"].unique())
#                 client_list.sort()
                
#                 # We assume the user picks from Master. 
#                 # If they need a new one, they can type it, and we will auto-add it to Master.
#                 end_user_choice = st.selectbox("End User (Client)", ["Select or Type New..."] + client_list, key="k_client_select")
                
#                 if end_user_choice == "Select or Type New...":
#                     final_end_user = st.text_input("Enter New Client Name", key="k_client_new")
#                 else:
#                     final_end_user = end_user_choice
            
#             with c5:
#                 existing_inds = list(prod_df["Industry Category"].dropna().unique())
#                 ind_choice = st.selectbox("Industry Category", ["Select or Type New..."] + existing_inds, key="k_ind_select")
#                 if ind_choice == "Select or Type New...":
#                     final_industry = st.text_input("Enter New Industry Category", key="k_ind_new")
#                 else:
#                     final_industry = ind_choice

#             if st.button("💾 Save to Database", type="primary", use_container_width=True):
#                 # Validations
#                 missing = []
#                 if not sn: missing.append("S/N")
#                 if not final_end_user: missing.append("End User")
#                 if prod_select == "Custom" and not final_product: missing.append("Custom Product Name")
#                 if ind_choice == "Select or Type New..." and not final_industry: missing.append("Industry Category")

#                 if missing:
#                     st.error(f"❌ Required: {', '.join(missing)}")
#                 else:
#                     if not prod_df.empty and str(sn) in prod_df["S/N"].astype(str).values:
#                         st.warning(f"⚠️ Warning: Product S/N {sn} already exists.")
                    
#                     # 1. Save Product
#                     new_entry = {
#                         "S/N": sn, "OEM S/N": oem_sn, "Product Name": final_product, 
#                         "Model": model, "Connectivity (2G/4G)": connectivity, 
#                         "Cable Length": cable_len, "Installation Date": install_date, 
#                         "Activation Date": activation_date, "Validity (Months)": validity, 
#                         "Renewal Date": calc_renewal, "Device UID": device_uid, 
#                         "SIM Provider": sim_prov, "SIM Number": sim_num, 
#                         "Channel Partner": final_partner, "End User": final_end_user, 
#                         "Industry Category": final_industry
#                     }
#                     prod_df = pd.concat([prod_df, pd.DataFrame([new_entry])], ignore_index=True)
#                     save_products(prod_df)

#                     # 2. Check if Client is New -> Add to Client Master automatically
#                     if final_end_user not in client_list:
#                         new_client_row = {"Client Name": final_end_user, "Contact Person": "", "Phone Number": "", "Email": "", "Address": ""}
#                         client_df = pd.concat([client_df, pd.DataFrame([new_client_row])], ignore_index=True)
#                         save_clients(client_df)
#                         st.success(f"New Client '{final_end_user}' added to Client Master!")

#                     st.success(f"✅ Product '{sn}' saved!")
                    
#                     # RESET FORM
#                     keys_to_clear = ["k_sn", "k_oem", "k_model", "k_cable", "k_uid", "k_sim_num", "k_partner_new", "k_client_new", "k_ind_new", "k_custom_prod"]
#                     for key in keys_to_clear:
#                         if key in st.session_state: st.session_state[key] = ""
#                     st.session_state["k_prod"] = BASE_PRODUCT_LIST[0]
#                     st.session_state["k_conn"] = "4G"
#                     st.session_state["k_sim_prov"] = "VI"
#                     st.session_state["k_partner_select"] = "Select or Type New..."
#                     st.session_state["k_client_select"] = "Select or Type New..."
#                     st.session_state["k_ind_select"] = "Select or Type New..."
#                     st.session_state["k_install"] = date.today()
#                     st.session_state["k_activ"] = date.today()
#                     st.session_state["k_valid"] = 12
#                     st.rerun()

#     # ==========================
#     # 4. INSTALLATION LIST
#     # ==========================
#     elif menu == "Installation List":
#         st.subheader("🔎 Installation Repository")
#         col_search, _ = st.columns([2, 1])
#         with col_search:
#             search_term = st.text_input("🔍 Search Database", placeholder="Type S/N, Client, or UID...")
        
#         display_df = prod_df.copy()
#         if search_term:
#             mask = display_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
#             display_df = display_df[mask]
#             st.success(f"Found {len(display_df)} records")

#         st.dataframe(display_df, use_container_width=True, height=600, column_config={"Renewal Date": st.column_config.DateColumn("Renewal Date", format="YYYY-MM-DD")})

#     # ==========================
#     # 5. CHANNEL PARTNER ANALYTICS
#     # ==========================
#     elif menu == "Channel Partner Analytics":
#         st.subheader("🤝 Channel Partner Performance")
#         if not prod_df.empty:
#             partner_df = prod_df[prod_df["Channel Partner"].notna() & (prod_df["Channel Partner"] != "")]
#             if not partner_df.empty:
#                 partner_stats = partner_df.groupby("Channel Partner").agg({
#                     "S/N": "count", "End User": "nunique", "Product Name": lambda x: ", ".join(sorted(x.unique()))
#                 }).reset_index()
#                 partner_stats.columns = ["Channel Partner", "Total Installations", "Unique Clients", "Product Types Sold"]
#                 partner_stats = partner_stats.sort_values(by="Total Installations", ascending=False)

#                 col_p1, col_p2 = st.columns([2, 1])
#                 with col_p1:
#                     fig_part = px.bar(partner_stats, x="Channel Partner", y="Total Installations", color="Total Installations", color_continuous_scale="Viridis")
#                     st.plotly_chart(fig_part, use_container_width=True)
#                 with col_p2:
#                     st.metric("🏆 Top Performer", partner_stats.iloc[0]["Channel Partner"])
#                     st.metric("📈 Max Installs", partner_stats.iloc[0]["Total Installations"])

#                 st.dataframe(partner_stats, use_container_width=True)
#                 st.download_button("⬇️ Download Partner Report", convert_df_to_excel(partner_stats), "Partner_Report.xlsx")
#             else: st.info("No Channel Partner data found.")
#         else: st.info("Database is empty.")

#     # ==========================
#     # 6. IMPORT/EXPORT DB
#     # ==========================
#     elif menu == "IMPORT/EXPORT DB":
#         st.subheader("💾 Database Management")
#         tab1, tab2 = st.tabs(["⬇️ Export Full DB", "⬆️ Import Data"])
#         with tab1:
#             if not prod_df.empty:
#                 st.download_button("Download Product Database (Excel)", convert_df_to_excel(prod_df), "Product_DB.xlsx")
#                 st.download_button("Download Client Database (Excel)", convert_df_to_excel(client_df), "Client_DB.xlsx")
#             else: st.warning("Database is empty.")
#         with tab2:
#             st.write("Merge data into Product Database")
#             uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
#             if uploaded_file:
#                 try:
#                     new_data = pd.read_excel(uploaded_file)
#                     missing = [c for c in PROD_COLS if c not in new_data.columns]
#                     if missing: st.error(f"❌ Missing columns: {missing}")
#                     else:
#                         st.dataframe(new_data.head())
#                         if st.button("Confirm Import"):
#                             prod_df = pd.concat([prod_df, new_data], ignore_index=True)
#                             save_products(prod_df)
#                             st.success("Import Successful!")
#                             st.rerun()
#                 except Exception as e: st.error(f"Error: {e}")

# if __name__ == "__main__":
#     main()



# v4
# import streamlit as st
# import pandas as pd
# from datetime import datetime, date
# from dateutil.relativedelta import relativedelta
# import plotly.express as px
# import os
# import io

# # --- CONFIGURATION ---
# FILE_PATH = 'product_database.xlsx'
# st.set_page_config(page_title="Product Management System", page_icon="🏭", layout="wide")

# # --- CONSTANTS ---
# BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]
# REQUIRED_COLUMNS = [
#     "S/N", "OEM S/N", "Product Name", "Model", "Connectivity (2G/4G)", 
#     "Cable Length", "Installation Date", "Activation Date", 
#     "Validity (Months)", "Renewal Date", "Device UID", 
#     "SIM Provider", "SIM Number", "Channel Partner", 
#     "End User", "Industry Category"
# ]

# # --- DATA HANDLING ---

# def load_data():
#     """Loads the Excel file. Creates it if it doesn't exist."""
#     if not os.path.exists(FILE_PATH):
#         df = pd.DataFrame(columns=REQUIRED_COLUMNS)
#         df.to_excel(FILE_PATH, index=False)
#         return df
#     try:
#         df = pd.read_excel(FILE_PATH)
#         for col in REQUIRED_COLUMNS:
#             if col not in df.columns:
#                 df[col] = "" 
#         return df
#     except Exception as e:
#         st.error(f"Error loading database: {e}")
#         return pd.DataFrame(columns=REQUIRED_COLUMNS)

# def save_data(df):
#     """Saves the dataframe to Excel."""
#     try:
#         df.to_excel(FILE_PATH, index=False)
#         return True
#     except PermissionError:
#         st.error("⚠️ Error: Please close 'product_database.xlsx' before saving!")
#         return False

# # --- UTILITY FUNCTIONS ---

# def calculate_renewal(activation_date, months):
#     if not activation_date:
#         return None
#     return activation_date + relativedelta(months=int(months))

# def check_expiry_status(renewal_date):
#     if pd.isna(renewal_date):
#         return "Unknown"
#     today = pd.to_datetime(datetime.now().date())
#     renewal = pd.to_datetime(renewal_date)
#     days_left = (renewal - today).days
    
#     if days_left < 0: return "Expired"
#     elif days_left <= 30: return "Expiring Soon"
#     else: return "Active"

# def convert_df_to_excel(df):
#     output = io.BytesIO()
#     with pd.ExcelWriter(output, engine='openpyxl') as writer:
#         df.to_excel(writer, index=False)
#     return output.getvalue()

# # --- MAIN APP ---

# def main():
#     st.title("🏭 Product Management System")
#     st.markdown("Manage installations, subscriptions, and industry analytics.")
#     st.markdown("---")

#     df = load_data()
    
#     # Pre-process dates
#     date_cols = ["Installation Date", "Activation Date", "Renewal Date"]
#     for col in date_cols:
#         if col in df.columns:
#             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

#     # --- SIDEBAR ---
#     st.sidebar.header("Navigation")
#     menu = st.sidebar.radio(
#         "Go to:", 
#         ["Dashboard", "New Dispatch Entry", "Installation List", "Client List", "Channel Partner Analytics", "IMPORT/EXPORT DB"]
#     )
#     st.sidebar.markdown("---")
#     st.sidebar.caption(f"📂 Database: `{FILE_PATH}`")
#     st.sidebar.caption(f"🔢 Total Records: {len(df)}")

#     # --- 1. DASHBOARD ---
#     if menu == "Dashboard":
#         st.subheader("📊 Analytics Overview")
        
#         if not df.empty:
#             df['Status'] = df['Renewal Date'].apply(check_expiry_status)
#             expired_count = len(df[df['Status'] == "Expired"])
#             expiring_count = len(df[df['Status'] == "Expiring Soon"])
            
#             c1, c2, c3, c4 = st.columns(4)
#             c1.metric("Total Installations", len(df))
#             c2.metric("Active Subscriptions", len(df[df['Status'] == "Active"]))
#             c3.metric("Expiring Soon", expiring_count, delta="Action Needed", delta_color="inverse")
#             c4.metric("Expired", expired_count, delta="Critical", delta_color="inverse")
            
#             st.divider()

#             col_g1, col_g2 = st.columns(2)
#             with col_g1:
#                 st.markdown("##### 🏭 Industry Distribution")
#                 if "Industry Category" in df.columns and df["Industry Category"].notna().any():
#                     ind_counts = df["Industry Category"].value_counts().reset_index()
#                     ind_counts.columns = ["Category", "Count"]
#                     fig = px.pie(ind_counts, values='Count', names='Category', hole=0.4)
#                     st.plotly_chart(fig, use_container_width=True)
            
#             with col_g2:
#                 st.markdown("##### 📈 Installation Growth (Monthly)")
#                 if "Installation Date" in df.columns and df["Installation Date"].notna().any():
#                     trend_df = df.copy()
#                     trend_df["Installation Date"] = pd.to_datetime(trend_df["Installation Date"])
#                     trend_data = trend_df.groupby(trend_df["Installation Date"].dt.to_period("M")).size().reset_index(name="Installations")
#                     trend_data["Installation Date"] = trend_data["Installation Date"].astype(str)
#                     fig_trend = px.area(trend_data, x="Installation Date", y="Installations", markers=True, color_discrete_sequence=["#00CC96"])
#                     st.plotly_chart(fig_trend, use_container_width=True)

#             if expired_count > 0 or expiring_count > 0:
#                 st.markdown("### ⚠️ Alert Center")
#                 tab_soon, tab_expired = st.tabs(["⏳ Expiring Soon", "❌ Expired"])
#                 today = pd.to_datetime(date.today())

#                 with tab_soon:
#                     if expiring_count > 0:
#                         df_soon = df[df['Status'] == "Expiring Soon"].copy()
#                         df_soon["Days Left"] = (pd.to_datetime(df_soon["Renewal Date"]) - today).dt.days
#                         st.dataframe(df_soon[["Days Left", "S/N", "End User", "Renewal Date", "Product Name"]].sort_values("Days Left"), use_container_width=True)
#                     else:
#                         st.success("No devices expiring soon.")

#                 with tab_expired:
#                     if expired_count > 0:
#                         df_expired = df[df['Status'] == "Expired"].copy()
#                         df_expired["Days Overdue"] = (today - pd.to_datetime(df_expired["Renewal Date"])).dt.days
#                         st.dataframe(df_expired[["Days Overdue", "S/N", "End User", "Renewal Date", "Product Name"]].sort_values("Days Overdue", ascending=False), use_container_width=True)
#                     else:
#                         st.success("No expired devices.")
#         else:
#             st.info("Welcome! Go to 'New Dispatch Entry' to add your first product.")

#     # --- 2. NEW DISPATCH ENTRY ---
#     elif menu == "New Dispatch Entry":
#         st.subheader("📝 Register New Dispatch")
        
#         # We use st.session_state keys for widgets to allow clearing them later
#         with st.container():
#             col1, col2 = st.columns([1, 1])
            
#             with col1:
#                 sn = st.text_input("Product S/N# (Required)", key="k_sn")
#                 oem_sn = st.text_input("OEM S/N#", key="k_oem")
                
#                 prod_select = st.selectbox("Product Name", BASE_PRODUCT_LIST, key="k_prod")
#                 if prod_select == "Custom":
#                     final_product = st.text_input("Enter Custom Product Name", placeholder="Type product name...", key="k_custom_prod")
#                 else:
#                     final_product = prod_select
                
#                 model = st.text_input("Model", key="k_model")
#                 connectivity = st.selectbox("Connectivity", ["4G", "2G", "NB-IoT", "WiFi", "LoRaWAN", "NA"], key="k_conn")

#             with col2:
#                 if final_product == "DWLR":
#                     cable_len = st.text_input("Cable Length (Meters)", key="k_cable")
#                 else:
#                     cable_len = "N/A"
#                     st.text_input("Cable Length", value="N/A", disabled=True)
                
#                 install_date = st.date_input("Installation Date", date.today(), key="k_install")
#                 activation_date = st.date_input("Activation Date", date.today(), key="k_activ")
#                 validity = st.number_input("Validity (Months)", min_value=1, value=12, key="k_valid")
                
#                 calc_renewal = calculate_renewal(activation_date, validity)
#                 st.info(f"📅 Auto-Calculated Renewal: {calc_renewal}")

#             st.divider()
            
#             c3, c4, c5 = st.columns(3)
#             with c3:
#                 device_uid = st.text_input("Device UID", key="k_uid")
#                 sim_prov = st.selectbox("SIM Provider", ["VI", "AIRTEL", "JIO", "BSNL", "Other", "N/A"], key="k_sim_prov")
#                 sim_num = st.text_input("SIM Number", key="k_sim_num")
            
#             with c4:
#                 # --- UPDATED CHANNEL PARTNER LOGIC ---
#                 existing_partners = list(df["Channel Partner"].dropna().unique()) if not df.empty else []
#                 # Ensure we have a clean list
#                 clean_partners = [str(p) for p in existing_partners if str(p).strip() != ""]
                
#                 partner_choice = st.selectbox("Channel Partner", ["Select or Type New..."] + clean_partners, key="k_partner_select")
                
#                 if partner_choice == "Select or Type New...":
#                     final_partner = st.text_input("Enter New Partner Name", key="k_partner_new")
#                 else:
#                     final_partner = partner_choice

#                 end_user = st.text_input("End User Name (Required)", key="k_end_user")
            
#             with c5:
#                 existing_inds = list(df["Industry Category"].dropna().unique()) if not df.empty else []
#                 ind_choice = st.selectbox("Industry Category", ["Select or Type New..."] + existing_inds, key="k_ind_select")
                
#                 if ind_choice == "Select or Type New...":
#                     final_industry = st.text_input("Enter New Industry Category", key="k_ind_new")
#                 else:
#                     final_industry = ind_choice

#             # -- Save Button --
#             if st.button("💾 Save to Database", type="primary", use_container_width=True):
#                 # 1. Validation Logic
#                 missing_fields = []
#                 if not sn: missing_fields.append("S/N")
#                 if not end_user: missing_fields.append("End User")
#                 if prod_select == "Custom" and not final_product: missing_fields.append("Custom Product Name")
#                 if ind_choice == "Select or Type New..." and not final_industry: missing_fields.append("Industry Category")

#                 if missing_fields:
#                     st.error(f"❌ Cannot Save: The following fields are required: {', '.join(missing_fields)}")
#                 else:
#                     if not df.empty and str(sn) in df["S/N"].astype(str).values:
#                         st.warning(f"⚠️ Warning: Product with S/N {sn} already exists in the database.")
                    
#                     new_entry = {
#                         "S/N": sn, "OEM S/N": oem_sn, "Product Name": final_product, 
#                         "Model": model, "Connectivity (2G/4G)": connectivity, 
#                         "Cable Length": cable_len, "Installation Date": install_date, 
#                         "Activation Date": activation_date, "Validity (Months)": validity, 
#                         "Renewal Date": calc_renewal, "Device UID": device_uid, 
#                         "SIM Provider": sim_prov, "SIM Number": sim_num, 
#                         "Channel Partner": final_partner, "End User": end_user, 
#                         "Industry Category": final_industry
#                     }
                    
#                     df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
#                     if save_data(df):
#                         st.success(f"✅ Product '{sn}' saved successfully!")
                        
#                         # --- CLEAR FIELDS LOGIC ---
#                         # Reset all session state keys to default values
#                         keys_to_clear = ["k_sn", "k_oem", "k_model", "k_cable", "k_uid", "k_sim_num", "k_partner_new", "k_end_user", "k_ind_new", "k_custom_prod"]
#                         for key in keys_to_clear:
#                             if key in st.session_state: st.session_state[key] = ""
                            
#                         # Reset Dropdowns to index 0
#                         st.session_state["k_prod"] = BASE_PRODUCT_LIST[0]
#                         st.session_state["k_conn"] = "4G"
#                         st.session_state["k_sim_prov"] = "VI"
#                         st.session_state["k_partner_select"] = "Select or Type New..."
#                         st.session_state["k_ind_select"] = "Select or Type New..."
                        
#                         # Reset Dates/Numbers
#                         st.session_state["k_install"] = date.today()
#                         st.session_state["k_activ"] = date.today()
#                         st.session_state["k_valid"] = 12
                        
#                         st.rerun()

#     # --- 3. INSTALLATION LIST ---
#     elif menu == "Installation List":
#         st.subheader("🔎 Installation Repository")
#         col_search, col_space = st.columns([2, 1])
#         with col_search:
#             search_term = st.text_input("🔍 Search Database", placeholder="Type S/N, Client Name, or UID here...")
        
#         display_df = df.copy()
#         if search_term:
#             mask = display_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
#             display_df = display_df[mask]
#             st.success(f"Found {len(display_df)} matching records")

#         st.dataframe(display_df, use_container_width=True, height=600, column_config={"Renewal Date": st.column_config.DateColumn("Renewal Date", format="YYYY-MM-DD")})

#     # --- 4. CLIENT LIST ---
#     elif menu == "Client List":
#         st.subheader("👥 Client Database")
#         if not df.empty:
#             client_summary = df.groupby("End User").agg({
#                 "S/N": "count",
#                 "Product Name": lambda x: ", ".join(x.unique()),
#                 "Industry Category": lambda x: ", ".join(x.unique()),
#                 "Channel Partner": lambda x: ", ".join([str(i) for i in x.unique() if str(i) != 'nan'])
#             }).reset_index()
#             client_summary.columns = ["Client Name", "Total Devices", "Products Owned", "Industry", "Partners"]
#             st.dataframe(client_summary, use_container_width=True)
            
#             client_excel = convert_df_to_excel(client_summary)
#             st.download_button(label="⬇️ Download Client List", data=client_excel, file_name=f"Client_List_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
#         else:
#             st.info("No clients found yet.")

#     # --- 5. CHANNEL PARTNER ANALYTICS ---
#     elif menu == "Channel Partner Analytics":
#         st.subheader("🤝 Channel Partner Performance")
#         if not df.empty:
#             partner_df = df[df["Channel Partner"].notna() & (df["Channel Partner"] != "")]
#             if not partner_df.empty:
#                 partner_stats = partner_df.groupby("Channel Partner").agg({
#                     "S/N": "count",
#                     "End User": "nunique",
#                     "Product Name": lambda x: ", ".join(sorted(x.unique()))
#                 }).reset_index()
#                 partner_stats.columns = ["Channel Partner", "Total Installations", "Unique Clients", "Product Types Sold"]
#                 partner_stats = partner_stats.sort_values(by="Total Installations", ascending=False)

#                 col_p1, col_p2 = st.columns([2, 1])
#                 with col_p1:
#                     fig_part = px.bar(partner_stats, x="Channel Partner", y="Total Installations", color="Total Installations", text="Total Installations", color_continuous_scale="Viridis")
#                     st.plotly_chart(fig_part, use_container_width=True)
#                 with col_p2:
#                     st.metric("🏆 Top Performer", partner_stats.iloc[0]["Channel Partner"])
#                     st.metric("📈 Max Installs", partner_stats.iloc[0]["Total Installations"])

#                 st.dataframe(partner_stats, use_container_width=True)
#                 partner_excel = convert_df_to_excel(partner_stats)
#                 st.download_button(label="⬇️ Download Partner Report", data=partner_excel, file_name=f"Partner_Report_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
#             else:
#                 st.info("No Channel Partner data found.")
#         else:
#             st.info("Database is empty.")

#     # --- 6. IMPORT/EXPORT DB ---
#     elif menu == "IMPORT/EXPORT DB":
#         st.subheader("💾 Database Management")
#         tab1, tab2 = st.tabs(["⬇️ Export Full DB", "⬆️ Import Data"])
        
#         with tab1:
#             if not df.empty:
#                 excel_data = convert_df_to_excel(df)
#                 st.download_button(label="Download Database (Excel)", data=excel_data, file_name=f"Orcatech_Products_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
#             else:
#                 st.warning("Database is empty.")
                
#         with tab2:
#             uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
#             if uploaded_file:
#                 try:
#                     new_data = pd.read_excel(uploaded_file)
#                     missing_cols = [c for c in REQUIRED_COLUMNS if c not in new_data.columns]
#                     if missing_cols:
#                         st.error(f"❌ Import Failed! Missing columns: {', '.join(missing_cols)}")
#                     else:
#                         st.dataframe(new_data.head())
#                         if st.button("Confirm Import & Merge"):
#                             combined_df = pd.concat([df, new_data], ignore_index=True)
#                             if save_data(combined_df):
#                                 st.success("Import Successful!")
#                                 st.rerun()
#                 except Exception as e:
#                     st.error(f"Error reading file: {e}")

# if __name__ == "__main__":
#     main()




# v3
# import streamlit as st
# import pandas as pd
# from datetime import datetime, date
# from dateutil.relativedelta import relativedelta
# import plotly.express as px
# import os
# import io

# # --- CONFIGURATION ---
# FILE_PATH = 'product_database.xlsx'
# st.set_page_config(page_title="Product Management System", page_icon="🏭", layout="wide")

# # --- CONSTANTS ---
# BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]
# REQUIRED_COLUMNS = [
#     "S/N", "OEM S/N", "Product Name", "Model", "Connectivity (2G/4G)", 
#     "Cable Length", "Installation Date", "Activation Date", 
#     "Validity (Months)", "Renewal Date", "Device UID", 
#     "SIM Provider", "SIM Number", "Channel Partner", 
#     "End User", "Industry Category"
# ]

# # --- DATA HANDLING ---

# def load_data():
#     """Loads the Excel file. Creates it if it doesn't exist."""
#     if not os.path.exists(FILE_PATH):
#         df = pd.DataFrame(columns=REQUIRED_COLUMNS)
#         df.to_excel(FILE_PATH, index=False)
#         return df
#     try:
#         # Ensure all columns exist even if file is old
#         df = pd.read_excel(FILE_PATH)
#         for col in REQUIRED_COLUMNS:
#             if col not in df.columns:
#                 df[col] = "" # Add missing columns
#         return df
#     except Exception as e:
#         st.error(f"Error loading database: {e}")
#         return pd.DataFrame(columns=REQUIRED_COLUMNS)

# def save_data(df):
#     """Saves the dataframe to Excel."""
#     try:
#         df.to_excel(FILE_PATH, index=False)
#         return True
#     except PermissionError:
#         st.error("⚠️ Error: Please close 'product_database.xlsx' before saving!")
#         return False

# # --- UTILITY FUNCTIONS ---

# def calculate_renewal(activation_date, months):
#     if not activation_date:
#         return None
#     return activation_date + relativedelta(months=int(months))

# def check_expiry_status(renewal_date):
#     if pd.isna(renewal_date):
#         return "Unknown"
#     today = pd.to_datetime(datetime.now().date())
#     renewal = pd.to_datetime(renewal_date)
#     days_left = (renewal - today).days
    
#     if days_left < 0: return "Expired"
#     elif days_left <= 30: return "Expiring Soon"
#     else: return "Active"

# def convert_df_to_excel(df):
#     output = io.BytesIO()
#     with pd.ExcelWriter(output, engine='openpyxl') as writer:
#         df.to_excel(writer, index=False)
#     return output.getvalue()

# # --- MAIN APP ---

# def main():
#     # --- UI HEADER ---
#     st.title("🏭 Product Management System")
#     st.markdown("Manage installations, subscriptions, and industry analytics.")
#     st.markdown("---")

#     # Load Data
#     df = load_data()
    
#     # Pre-process dates for display
#     date_cols = ["Installation Date", "Activation Date", "Renewal Date"]
#     for col in date_cols:
#         if col in df.columns:
#             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

#     # --- SIDEBAR NAVIGATION ---
#     st.sidebar.header("Navigation")
    
#     menu = st.sidebar.radio(
#         "Go to:", 
#         ["Dashboard", "New Dispatch Entry", "Installation List", "Client List", "Channel Partner Analytics", "IMPORT/EXPORT DB"]
#     )
    
#     st.sidebar.markdown("---")
#     st.sidebar.caption(f"📂 Database: `{FILE_PATH}`")
#     st.sidebar.caption(f"🔢 Total Records: {len(df)}")

#     # --- 1. DASHBOARD ---
#     if menu == "Dashboard":
#         st.subheader("📊 Analytics Overview")
        
#         if not df.empty:
#             # Subscriptions Logic
#             df['Status'] = df['Renewal Date'].apply(check_expiry_status)
#             expired_count = len(df[df['Status'] == "Expired"])
#             expiring_count = len(df[df['Status'] == "Expiring Soon"])
            
#             # Key Metrics
#             c1, c2, c3, c4 = st.columns(4)
#             c1.metric("Total Installations", len(df))
#             c2.metric("Active Subscriptions", len(df[df['Status'] == "Active"]))
#             c3.metric("Expiring Soon", expiring_count, delta="Action Needed", delta_color="inverse")
#             c4.metric("Expired", expired_count, delta="Critical", delta_color="inverse")
            
#             st.divider()

#             # Charts
#             col_g1, col_g2 = st.columns(2)
            
#             with col_g1:
#                 st.markdown("##### 🏭 Industry Distribution")
#                 if "Industry Category" in df.columns and df["Industry Category"].notna().any():
#                     ind_counts = df["Industry Category"].value_counts().reset_index()
#                     ind_counts.columns = ["Category", "Count"]
#                     fig = px.pie(ind_counts, values='Count', names='Category', hole=0.4)
#                     st.plotly_chart(fig, use_container_width=True)
#                 else:
#                     st.info("No industry data available yet.")

#             with col_g2:
#                 st.markdown("##### 📈 Installation Growth (Monthly)")
                
#                 if "Installation Date" in df.columns and df["Installation Date"].notna().any():
#                     trend_df = df.copy()
#                     trend_df["Installation Date"] = pd.to_datetime(trend_df["Installation Date"])
                    
#                     trend_data = trend_df.groupby(trend_df["Installation Date"].dt.to_period("M")).size().reset_index(name="Installations")
#                     trend_data["Installation Date"] = trend_data["Installation Date"].astype(str)
                    
#                     fig_trend = px.area(
#                         trend_data, 
#                         x="Installation Date", 
#                         y="Installations", 
#                         markers=True,
#                         color_discrete_sequence=["#00CC96"]
#                     )
#                     st.plotly_chart(fig_trend, use_container_width=True)
#                 else:
#                     st.info("No installation dates available to show trends.")

#             # --- FUNCTIONAL ALERT CENTER ---
#             if expired_count > 0 or expiring_count > 0:
#                 st.markdown("### ⚠️ Alert Center")
                
#                 tab_soon, tab_expired = st.tabs(["⏳ Expiring Soon (Action Needed)", "❌ Expired (Critical)"])
                
#                 today = pd.to_datetime(date.today())

#                 # Tab 1: Expiring Soon
#                 with tab_soon:
#                     if expiring_count > 0:
#                         df_soon = df[df['Status'] == "Expiring Soon"].copy()
#                         # Calculate Days Left
#                         df_soon["Days Left"] = (pd.to_datetime(df_soon["Renewal Date"]) - today).dt.days
                        
#                         st.warning(f"These {len(df_soon)} devices will expire within 30 days. Please contact clients for renewal.")
#                         st.dataframe(
#                             df_soon[["Days Left", "S/N", "End User", "Renewal Date", "Product Name", "Channel Partner"]].sort_values("Days Left"),
#                             use_container_width=True
#                         )
#                     else:
#                         st.success("No devices are expiring soon.")

#                 # Tab 2: Expired
#                 with tab_expired:
#                     if expired_count > 0:
#                         df_expired = df[df['Status'] == "Expired"].copy()
#                         # Calculate Days Overdue
#                         df_expired["Days Overdue"] = (today - pd.to_datetime(df_expired["Renewal Date"])).dt.days
                        
#                         st.error(f"These {len(df_expired)} devices have expired. Service may need suspension.")
#                         st.dataframe(
#                             df_expired[["Days Overdue", "S/N", "End User", "Renewal Date", "Product Name"]].sort_values("Days Overdue", ascending=False),
#                             use_container_width=True
#                         )
#                     else:
#                         st.success("No expired devices found.")

#         else:
#             st.info("Welcome! Go to 'New Dispatch Entry' to add your first product.")

#     # --- 2. NEW DISPATCH ENTRY ---
#     elif menu == "New Dispatch Entry":
#         st.subheader("📝 Register New Dispatch")
        
#         with st.container():
#             col1, col2 = st.columns([1, 1])
            
#             # -- Column 1 Inputs --
#             with col1:
#                 sn = st.text_input("Product S/N# (Required)")
#                 oem_sn = st.text_input("OEM S/N#")
                
#                 # Custom Product Logic
#                 prod_select = st.selectbox("Product Name", BASE_PRODUCT_LIST)
#                 if prod_select == "Custom":
#                     final_product = st.text_input("Enter Custom Product Name", placeholder="Type product name...")
#                 else:
#                     final_product = prod_select
                
#                 model = st.text_input("Model")
#                 connectivity = st.selectbox("Connectivity", ["4G", "2G", "NB-IoT", "WiFi", "LoRaWAN", "NA"])

#             # -- Column 2 Inputs --
#             with col2:
#                 # Cable Logic
#                 if final_product == "DWLR":
#                     cable_len = st.text_input("Cable Length (Meters)")
#                 else:
#                     cable_len = "N/A"
#                     st.text_input("Cable Length", value="N/A", disabled=True)
                
#                 install_date = st.date_input("Installation Date", date.today())
#                 activation_date = st.date_input("Activation Date", date.today())
#                 validity = st.number_input("Validity (Months)", min_value=1, value=12)
                
#                 # Auto-calc
#                 calc_renewal = calculate_renewal(activation_date, validity)
#                 st.info(f"📅 Auto-Calculated Renewal: {calc_renewal}")

#             st.divider()
            
#             # -- Subscription & Client Details --
#             c3, c4, c5 = st.columns(3)
#             with c3:
#                 device_uid = st.text_input("Device UID")
#                 sim_prov = st.selectbox("SIM Provider", ["VI", "AIRTEL", "JIO", "BSNL", "Other", "N/A"])
#                 sim_num = st.text_input("SIM Number")
            
#             with c4:
#                 partner = st.text_input("Channel Partner")
#                 end_user = st.text_input("End User Name (Required)")
            
#             with c5:
#                 # Industry Logic: History + Custom
#                 existing_inds = list(df["Industry Category"].dropna().unique()) if not df.empty else []
#                 ind_choice = st.selectbox("Industry Category", ["Select or Type New..."] + existing_inds)
                
#                 if ind_choice == "Select or Type New...":
#                     final_industry = st.text_input("Enter New Industry Category")
#                 else:
#                     final_industry = ind_choice

#             # -- Save Button --
#             if st.button("💾 Save to Database", type="primary", use_container_width=True):
#                 # 1. Validation Logic
#                 missing_fields = []
#                 if not sn: missing_fields.append("S/N")
#                 if not end_user: missing_fields.append("End User")
#                 if prod_select == "Custom" and not final_product: missing_fields.append("Custom Product Name")
#                 if ind_choice == "Select or Type New..." and not final_industry: missing_fields.append("Industry Category")

#                 if missing_fields:
#                     st.error(f"❌ Cannot Save: The following fields are required: {', '.join(missing_fields)}")
#                 else:
#                     # 2. Check Duplicate S/N
#                     if not df.empty and str(sn) in df["S/N"].astype(str).values:
#                         st.warning(f"⚠️ Warning: Product with S/N {sn} already exists in the database.")
                    
#                     # 3. Save
#                     new_entry = {
#                         "S/N": sn, "OEM S/N": oem_sn, "Product Name": final_product, 
#                         "Model": model, "Connectivity (2G/4G)": connectivity, 
#                         "Cable Length": cable_len, "Installation Date": install_date, 
#                         "Activation Date": activation_date, "Validity (Months)": validity, 
#                         "Renewal Date": calc_renewal, "Device UID": device_uid, 
#                         "SIM Provider": sim_prov, "SIM Number": sim_num, 
#                         "Channel Partner": partner, "End User": end_user, 
#                         "Industry Category": final_industry
#                     }
                    
#                     df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
#                     if save_data(df):
#                         st.success(f"✅ Product '{sn}' saved successfully!")
#                         st.rerun()

#     # --- 3. INSTALLATION LIST ---
#     elif menu == "Installation List":
#         st.subheader("🔎 Installation Repository")
        
#         with st.container():
#             st.markdown("#### Filter Options")
#             col_search, col_space = st.columns([2, 1])
#             with col_search:
#                 search_term = st.text_input("🔍 Search Database", placeholder="Type S/N, Client Name, or UID here...")
        
#         st.divider()

#         display_df = df.copy()
#         if search_term:
#             mask = display_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
#             display_df = display_df[mask]
#             st.success(f"Found {len(display_df)} matching records")

#         st.dataframe(
#             display_df, 
#             use_container_width=True, 
#             height=600,
#             column_config={
#                 "Renewal Date": st.column_config.DateColumn("Renewal Date", format="YYYY-MM-DD"),
#             }
#         )

#     # --- 4. CLIENT LIST ---
#     elif menu == "Client List":
#         st.subheader("👥 Client Database")
        
#         if not df.empty:
#             # Summarize by End User
#             client_summary = df.groupby("End User").agg({
#                 "S/N": "count",
#                 "Product Name": lambda x: ", ".join(x.unique()),
#                 "Industry Category": lambda x: ", ".join(x.unique()),
#                 "Channel Partner": lambda x: ", ".join([str(i) for i in x.unique() if str(i) != 'nan'])
#             }).reset_index()
            
#             client_summary.columns = ["Client Name", "Total Devices", "Products Owned", "Industry", "Partners"]
            
#             # Display Table
#             st.dataframe(client_summary, use_container_width=True)
            
#             # Export Button
#             st.markdown("### Export")
#             st.write("Download this client summary list.")
#             client_excel = convert_df_to_excel(client_summary)
            
#             st.download_button(
#                 label="⬇️ Download Client List (Excel)",
#                 data=client_excel,
#                 file_name=f"Orcatech_Client_List_{date.today()}.xlsx",
#                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#             )
#         else:
#             st.info("No clients found yet.")

#     # --- 5. CHANNEL PARTNER ANALYTICS ---
#     elif menu == "Channel Partner Analytics":
#         st.subheader("🤝 Channel Partner Performance")
        
#         if not df.empty:
#             # Drop empty partners for analysis if any
#             partner_df = df[df["Channel Partner"].notna() & (df["Channel Partner"] != "")]
            
#             if not partner_df.empty:
#                 # 1. Calculate Stats
#                 partner_stats = partner_df.groupby("Channel Partner").agg({
#                     "S/N": "count",
#                     "End User": "nunique",
#                     "Product Name": lambda x: ", ".join(sorted(x.unique()))
#                 }).reset_index()
                
#                 partner_stats.columns = ["Channel Partner", "Total Installations", "Unique Clients", "Product Types Sold"]
#                 partner_stats = partner_stats.sort_values(by="Total Installations", ascending=False)

#                 # 2. Charts
#                 col_p1, col_p2 = st.columns([2, 1])
                
#                 with col_p1:
#                     st.markdown("#### Installation Leaderboard")
#                     fig_part = px.bar(
#                         partner_stats, 
#                         x="Channel Partner", 
#                         y="Total Installations", 
#                         color="Total Installations",
#                         text="Total Installations",
#                         color_continuous_scale="Viridis"
#                     )
#                     st.plotly_chart(fig_part, use_container_width=True)
                    
#                 with col_p2:
#                     st.markdown("#### Summary Metrics")
#                     top_partner = partner_stats.iloc[0]["Channel Partner"]
#                     top_count = partner_stats.iloc[0]["Total Installations"]
#                     st.metric("🏆 Top Performer", top_partner)
#                     st.metric("📈 Max Installs", top_count)
#                     st.metric("🤝 Total Active Partners", len(partner_stats))

#                 # 3. Detailed Table
#                 st.divider()
#                 st.markdown("#### Detailed Partner Report")
#                 st.dataframe(partner_stats, use_container_width=True)
                
#                 # 4. Export
#                 st.write("Download detailed partner report.")
#                 partner_excel = convert_df_to_excel(partner_stats)
#                 st.download_button(
#                     label="⬇️ Download Partner Report (Excel)",
#                     data=partner_excel,
#                     file_name=f"Channel_Partner_Report_{date.today()}.xlsx",
#                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#                 )
#             else:
#                 st.info("No Channel Partner data found in the database yet.")
#         else:
#             st.info("Database is empty.")

#     # --- 6. IMPORT/EXPORT DB ---
#     elif menu == "IMPORT/EXPORT DB":
#         st.subheader("💾 Database Management")
        
#         tab1, tab2 = st.tabs(["⬇️ Export Full DB", "⬆️ Import Data"])
        
#         with tab1:
#             st.write("Download your complete database for backup or reporting.")
#             if not df.empty:
#                 excel_data = convert_df_to_excel(df)
#                 st.download_button(
#                     label="Download Database (Excel)",
#                     data=excel_data,
#                     file_name=f"Orcatech_Products_{date.today()}.xlsx",
#                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#                 )
#             else:
#                 st.warning("Database is empty.")
                
#         with tab2:
#             st.write("Upload an Excel file to merge with the current database.")
#             uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
            
#             if uploaded_file:
#                 try:
#                     new_data = pd.read_excel(uploaded_file)
                    
#                     # VALIDATION
#                     missing_cols = [c for c in REQUIRED_COLUMNS if c not in new_data.columns]
                    
#                     if missing_cols:
#                         st.error(f"❌ Import Failed! Missing columns: {', '.join(missing_cols)}")
#                     else:
#                         st.success("✅ Validation Successful!")
#                         st.dataframe(new_data.head())
                        
#                         if st.button("Confirm Import & Merge"):
#                             combined_df = pd.concat([df, new_data], ignore_index=True)
#                             if save_data(combined_df):
#                                 st.success(f"Successfully imported {len(new_data)} records!")
#                                 st.rerun()
                                
#                 except Exception as e:
#                     st.error(f"Error reading file: {e}")

# if __name__ == "__main__":
#     main()



# v2
# import streamlit as st
# import pandas as pd
# from datetime import datetime, date
# from dateutil.relativedelta import relativedelta
# import plotly.express as px
# import os
# import io

# # --- CONFIGURATION ---
# FILE_PATH = 'product_database.xlsx'
# st.set_page_config(page_title="Product Management System", page_icon="🏭", layout="wide")

# # --- CONSTANTS ---
# BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]
# REQUIRED_COLUMNS = [
#     "S/N", "OEM S/N", "Product Name", "Model", "Connectivity (2G/4G)", 
#     "Cable Length", "Installation Date", "Activation Date", 
#     "Validity (Months)", "Renewal Date", "Device UID", 
#     "SIM Provider", "SIM Number", "Channel Partner", 
#     "End User", "Industry Category"
# ]

# # --- DATA HANDLING ---

# def load_data():
#     """Loads the Excel file. Creates it if it doesn't exist."""
#     if not os.path.exists(FILE_PATH):
#         df = pd.DataFrame(columns=REQUIRED_COLUMNS)
#         df.to_excel(FILE_PATH, index=False)
#         return df
#     try:
#         # Ensure all columns exist even if file is old
#         df = pd.read_excel(FILE_PATH)
#         for col in REQUIRED_COLUMNS:
#             if col not in df.columns:
#                 df[col] = "" # Add missing columns
#         return df
#     except Exception as e:
#         st.error(f"Error loading database: {e}")
#         return pd.DataFrame(columns=REQUIRED_COLUMNS)

# def save_data(df):
#     """Saves the dataframe to Excel."""
#     try:
#         df.to_excel(FILE_PATH, index=False)
#         return True
#     except PermissionError:
#         st.error("⚠️ Error: Please close 'product_database.xlsx' before saving!")
#         return False

# # --- UTILITY FUNCTIONS ---

# def calculate_renewal(activation_date, months):
#     if not activation_date:
#         return None
#     return activation_date + relativedelta(months=int(months))

# def check_expiry_status(renewal_date):
#     if pd.isna(renewal_date):
#         return "Unknown"
#     today = pd.to_datetime(datetime.now().date())
#     renewal = pd.to_datetime(renewal_date)
#     days_left = (renewal - today).days
    
#     if days_left < 0: return "Expired"
#     elif days_left <= 30: return "Expiring Soon"
#     else: return "Active"

# def convert_df_to_excel(df):
#     output = io.BytesIO()
#     with pd.ExcelWriter(output, engine='openpyxl') as writer:
#         df.to_excel(writer, index=False)
#     return output.getvalue()

# # --- MAIN APP ---

# def main():
#     # --- UI HEADER ---
#     st.title("🏭 Product Management System")
#     st.markdown("Manage installations, subscriptions, and industry analytics.")
#     st.markdown("---")

#     # Load Data
#     df = load_data()
    
#     # Pre-process dates for display
#     date_cols = ["Installation Date", "Activation Date", "Renewal Date"]
#     for col in date_cols:
#         if col in df.columns:
#             df[col] = pd.to_datetime(df[col], errors='coerce').dt.date

#     # --- SIDEBAR NAVIGATION ---
#     st.sidebar.header("Navigation")
    
#     # UPDATED MENU NAMES HERE
#     menu = st.sidebar.radio(
#         "Go to:", 
#         ["Dashboard", "New Dispatch Entry", "Installation List", "IMPORT/EXPORT DB"]
#     )
    
#     st.sidebar.markdown("---")
#     st.sidebar.caption(f"📂 Database: `{FILE_PATH}`")
#     st.sidebar.caption(f"🔢 Total Records: {len(df)}")

#     # --- 1. DASHBOARD ---
#     if menu == "Dashboard":
#         st.subheader("📊 Analytics Overview")
        
#         if not df.empty:
#             # Subscriptions Logic
#             df['Status'] = df['Renewal Date'].apply(check_expiry_status)
#             expired = len(df[df['Status'] == "Expired"])
#             expiring = len(df[df['Status'] == "Expiring Soon"])
            
#             # Key Metrics
#             c1, c2, c3, c4 = st.columns(4)
#             c1.metric("Total Installations", len(df))
#             c2.metric("Active Subscriptions", len(df[df['Status'] == "Active"]))
#             c3.metric("Expiring Soon", expiring, delta="Action Needed", delta_color="inverse")
#             c4.metric("Expired", expired, delta="Critical", delta_color="inverse")
            
#             st.divider()

#             # Charts
#             col_g1, col_g2 = st.columns(2)
            
#             with col_g1:
#                 st.markdown("##### 🏭 Industry Distribution")
#                 if "Industry Category" in df.columns and df["Industry Category"].notna().any():
#                     ind_counts = df["Industry Category"].value_counts().reset_index()
#                     ind_counts.columns = ["Category", "Count"]
#                     fig = px.pie(ind_counts, values='Count', names='Category', hole=0.4)
#                     st.plotly_chart(fig, use_container_width=True)
#                 else:
#                     st.info("No industry data available yet.")

#             with col_g2:
#                 st.markdown("##### 📡 Connectivity Types")
#                 if "Connectivity (2G/4G)" in df.columns:
#                     conn_counts = df["Connectivity (2G/4G)"].value_counts()
#                     st.bar_chart(conn_counts)

#             # Expired Table
#             if expired > 0 or expiring > 0:
#                 st.error("⚠️ Devices Requiring Attention")
#                 critical_df = df[df['Status'].isin(["Expired", "Expiring Soon"])]
#                 st.dataframe(
#                     critical_df[["S/N", "End User", "Renewal Date", "Status"]].style.applymap(
#                         lambda x: 'color: red' if x == 'Expired' else 'color: orange', subset=['Status']
#                     ),
#                     use_container_width=True
#                 )
#         else:
#             st.info("Welcome! Go to 'New Dispatch Entry' to add your first product.")

#     # --- 2. NEW DISPATCH ENTRY ---
#     elif menu == "New Dispatch Entry":
#         st.subheader("📝 Register New Dispatch")
        
#         with st.container():
#             col1, col2 = st.columns([1, 1])
            
#             # -- Column 1 Inputs --
#             with col1:
#                 sn = st.text_input("Product S/N# (Required)")
#                 oem_sn = st.text_input("OEM S/N#")
                
#                 # Custom Product Logic
#                 prod_select = st.selectbox("Product Name", BASE_PRODUCT_LIST)
#                 if prod_select == "Custom":
#                     final_product = st.text_input("Enter Custom Product Name", placeholder="Type product name...")
#                 else:
#                     final_product = prod_select
                
#                 model = st.text_input("Model")
#                 connectivity = st.selectbox("Connectivity", ["4G", "2G", "NB-IoT", "WiFi", "LoRaWAN"])

#             # -- Column 2 Inputs --
#             with col2:
#                 # Cable Logic
#                 if final_product == "DWLR":
#                     cable_len = st.text_input("Cable Length (Meters)")
#                 else:
#                     cable_len = "N/A"
#                     st.text_input("Cable Length", value="N/A", disabled=True)
                
#                 install_date = st.date_input("Installation Date", date.today())
#                 activation_date = st.date_input("Activation Date", date.today())
#                 validity = st.number_input("Validity (Months)", min_value=1, value=12)
                
#                 # Auto-calc
#                 calc_renewal = calculate_renewal(activation_date, validity)
#                 st.info(f"📅 Auto-Calculated Renewal: {calc_renewal}")

#             st.divider()
            
#             # -- Subscription & Client Details --
#             c3, c4, c5 = st.columns(3)
#             with c3:
#                 device_uid = st.text_input("Device UID")
#                 sim_prov = st.selectbox("SIM Provider", ["VI", "AIRTEL", "JIO", "BSNL", "Other"])
#                 sim_num = st.text_input("SIM Number")
            
#             with c4:
#                 partner = st.text_input("Channel Partner")
#                 end_user = st.text_input("End User Name (Required)")
            
#             with c5:
#                 # Industry Logic: History + Custom
#                 existing_inds = list(df["Industry Category"].dropna().unique()) if not df.empty else []
#                 ind_choice = st.selectbox("Industry Category", ["Select or Type New..."] + existing_inds)
                
#                 if ind_choice == "Select or Type New...":
#                     final_industry = st.text_input("Enter New Industry Category")
#                 else:
#                     final_industry = ind_choice

#             # -- Save Button --
#             if st.button("💾 Save to Database", type="primary", use_container_width=True):
#                 # 1. Validation Logic
#                 missing_fields = []
#                 if not sn: missing_fields.append("S/N")
#                 if not end_user: missing_fields.append("End User")
#                 if prod_select == "Custom" and not final_product: missing_fields.append("Custom Product Name")
#                 if ind_choice == "Select or Type New..." and not final_industry: missing_fields.append("Industry Category")

#                 if missing_fields:
#                     st.error(f"❌ Cannot Save: The following fields are required: {', '.join(missing_fields)}")
#                 else:
#                     # 2. Check Duplicate S/N
#                     if not df.empty and str(sn) in df["S/N"].astype(str).values:
#                         st.warning(f"⚠️ Warning: Product with S/N {sn} already exists in the database.")
                    
#                     # 3. Save
#                     new_entry = {
#                         "S/N": sn, "OEM S/N": oem_sn, "Product Name": final_product, 
#                         "Model": model, "Connectivity (2G/4G)": connectivity, 
#                         "Cable Length": cable_len, "Installation Date": install_date, 
#                         "Activation Date": activation_date, "Validity (Months)": validity, 
#                         "Renewal Date": calc_renewal, "Device UID": device_uid, 
#                         "SIM Provider": sim_prov, "SIM Number": sim_num, 
#                         "Channel Partner": partner, "End User": end_user, 
#                         "Industry Category": final_industry
#                     }
                    
#                     df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
#                     if save_data(df):
#                         st.success(f"✅ Product '{sn}' saved successfully!")
#                         st.rerun() # Refresh to update suggestions immediately

#     # --- 3. INSTALLATION LIST (Formerly Product List) ---
#     elif menu == "Installation List":
#         st.subheader("🔎 Installation Repository")
        
#         # --- IMPROVED SEARCH BAR VISIBILITY ---
#         with st.container():
#             st.markdown("#### Filter Options")
#             col_search, col_space = st.columns([2, 1])
#             with col_search:
#                 # Placed inside a column with an icon to make it standout
#                 search_term = st.text_input("🔍 Search Database", placeholder="Type S/N, Client Name, or UID here...")
        
#         st.divider()

#         display_df = df.copy()
#         if search_term:
#             # Simple text filter across all columns
#             mask = display_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
#             display_df = display_df[mask]
#             st.success(f"Found {len(display_df)} matching records")

#         st.dataframe(
#             display_df, 
#             use_container_width=True, 
#             height=600,
#             column_config={
#                 "Renewal Date": st.column_config.DateColumn("Renewal Date", format="YYYY-MM-DD"),
#             }
#         )

#     # --- 4. IMPORT/EXPORT DB ---
#     elif menu == "IMPORT/EXPORT DB":
#         st.subheader("💾 Database Management")
        
#         tab1, tab2 = st.tabs(["⬇️ Export Data", "⬆️ Import Data"])
        
#         with tab1:
#             st.write("Download your complete database for backup or reporting.")
#             if not df.empty:
#                 excel_data = convert_df_to_excel(df)
#                 st.download_button(
#                     label="Download Database (Excel)",
#                     data=excel_data,
#                     file_name=f"Orcatech_Products_{date.today()}.xlsx",
#                     mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#                 )
#             else:
#                 st.warning("Database is empty.")
                
#         with tab2:
#             st.write("Upload an Excel file to merge with the current database.")
#             uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
            
#             if uploaded_file:
#                 try:
#                     new_data = pd.read_excel(uploaded_file)
                    
#                     # VALIDATION: Check Columns
#                     missing_cols = [c for c in REQUIRED_COLUMNS if c not in new_data.columns]
                    
#                     if missing_cols:
#                         st.error(f"❌ Import Failed! The uploaded file is missing these columns: {', '.join(missing_cols)}")
#                         st.info(f"Required Columns: {', '.join(REQUIRED_COLUMNS)}")
#                     else:
#                         st.success("✅ Validation Successful! Columns match.")
#                         st.write("Preview of data to be imported:")
#                         st.dataframe(new_data.head())
                        
#                         if st.button("Confirm Import & Merge"):
#                             # Combine and remove duplicates based on S/N if desired, or just append
#                             # Here we simply append
#                             combined_df = pd.concat([df, new_data], ignore_index=True)
#                             if save_data(combined_df):
#                                 st.success(f"Successfully imported {len(new_data)} records!")
#                                 st.rerun()
                                
#                 except Exception as e:
#                     st.error(f"Error reading file: {e}")

# if __name__ == "__main__":
#     main()


# V1
# import streamlit as st
# import pandas as pd
# from datetime import datetime, date
# from dateutil.relativedelta import relativedelta
# import plotly.express as px
# import os

# # --- CONFIGURATION ---
# FILE_PATH = 'product_database.xlsx'
# st.set_page_config(page_title="Orcatech Product Manager", page_icon="🔋", layout="wide")

# # --- LISTS & CONSTANTS ---
# PRODUCT_LIST = ["DWLR", "Telemetry Unit", "Rain Gauge", "Water Flow Meter", "Custom IoT Node"]
# SIM_PROVIDERS = ["VI", "AIRTEL", "JIO", "OTHER"]
# INDUSTRY_CATS = ["Agriculture", "Industrial Automation", "Water Management", "Smart City", "Energy", "Other"]

# # --- DATA HANDLING FUNCTIONS ---

# def load_data():
#     """Loads the Excel file. Creates it if it doesn't exist."""
#     if not os.path.exists(FILE_PATH):
#         columns = [
#             "S/N", "OEM S/N", "Product Name", "Model", "Connectivity (2G/4G)", 
#             "Cable Length", "Installation Date", "Activation Date", 
#             "Validity (Months)", "Renewal Date", "Device UID", 
#             "SIM Provider", "SIM Number", "Channel Partner", 
#             "End User", "Industry Category"
#         ]
#         df = pd.DataFrame(columns=columns)
#         df.to_excel(FILE_PATH, index=False)
#         return df
    
#     try:
#         return pd.read_excel(FILE_PATH)
#     except Exception as e:
#         st.error(f"Error loading Excel file: {e}")
#         return pd.DataFrame()

# def save_data(df):
#     """Saves the dataframe to Excel."""
#     try:
#         df.to_excel(FILE_PATH, index=False)
#         return True
#     except PermissionError:
#         st.error("Error: Please close the Excel file before saving!")
#         return False

# # --- UTILITY FUNCTIONS ---

# def calculate_renewal(activation_date, months):
#     if not activation_date:
#         return None
#     # Use relativedelta to accurately add months
#     return activation_date + relativedelta(months=int(months))

# def check_expiry_status(renewal_date):
#     if pd.isna(renewal_date):
#         return "Unknown"
#     today = pd.to_datetime(datetime.now().date())
#     renewal = pd.to_datetime(renewal_date)
    
#     days_left = (renewal - today).days
    
#     if days_left < 0:
#         return "Expired"
#     elif days_left <= 30:
#         return "Expiring Soon"
#     else:
#         return "Active"

# # --- MAIN APP LOGIC ---

# def main():
#     st.title("🔋 Product Lifecycle Management System")
    
#     # Load Data
#     df = load_data()
    
#     # Ensure date columns are datetime objects
#     date_cols = ["Installation Date", "Activation Date", "Renewal Date"]
#     for col in date_cols:
#         if col in df.columns:
#             df[col] = pd.to_datetime(df[col]).dt.date

#     # Sidebar Navigation
#     menu = ["Dashboard & Analytics", "New Product Dispatch", "Product Repository", "Client List"]
#     choice = st.sidebar.selectbox("Navigation", menu)
    
#     st.sidebar.markdown("---")
#     st.sidebar.info(f"Database Source: Local Excel File\n`{FILE_PATH}`")

#     # --- 1. DASHBOARD & ANALYTICS ---
#     if choice == "Dashboard & Analytics":
#         st.header("📊 Overview & Subscription Status")
        
#         if not df.empty:
#             # Metrics
#             total_devices = len(df)
            
#             # Logic for active/expired
#             # We convert renewal date to datetime for comparison
#             df['Status'] = df['Renewal Date'].apply(check_expiry_status)
            
#             expired_count = len(df[df['Status'] == "Expired"])
#             expiring_soon_count = len(df[df['Status'] == "Expiring Soon"])
            
#             c1, c2, c3 = st.columns(3)
#             c1.metric("Total Deployed Devices", total_devices)
#             c2.metric("Expired Subscriptions", expired_count, delta_color="inverse")
#             c3.metric("Expiring (<30 Days)", expiring_soon_count, delta_color="off")
            
#             st.markdown("---")
            
#             # Analytics Charts
#             col_chart1, col_chart2 = st.columns(2)
            
#             with col_chart1:
#                 st.subheader("Industry Distribution")
#                 if "Industry Category" in df.columns:
#                     ind_counts = df["Industry Category"].value_counts().reset_index()
#                     ind_counts.columns = ["Category", "Count"]
#                     fig_ind = px.pie(ind_counts, values='Count', names='Category', hole=0.4)
#                     st.plotly_chart(fig_ind, use_container_width=True)

#             with col_chart2:
#                 st.subheader("Subscription Health")
#                 status_counts = df['Status'].value_counts().reset_index()
#                 status_counts.columns = ["Status", "Count"]
#                 # Custom colors
#                 color_map = {"Active": "green", "Expired": "red", "Expiring Soon": "orange", "Unknown": "grey"}
#                 fig_stat = px.bar(status_counts, x="Status", y="Count", color="Status", color_discrete_map=color_map)
#                 st.plotly_chart(fig_stat, use_container_width=True)
            
#             # Expired Table
#             st.subheader("⚠️ Critical: Expired / Expiring Products")
#             critical_df = df[df['Status'].isin(["Expired", "Expiring Soon"])]
#             if not critical_df.empty:
#                 st.dataframe(critical_df[["S/N", "Product Name", "End User", "Renewal Date", "Status"]], use_container_width=True)
#             else:
#                 st.success("No critical subscriptions found.")

#         else:
#             st.info("No data available. Go to 'New Product Dispatch' to add entries.")

#     # --- 2. NEW PRODUCT DISPATCH ---
#     elif choice == "New Product Dispatch":
#         st.header("📝 New Product Entry")
        
#         with st.form("entry_form", clear_on_submit=True):
#             col1, col2, col3 = st.columns(3)
            
#             with col1:
#                 sn = st.text_input("S/N#")
#                 oem_sn = st.text_input("OEM S/N#")
#                 product_name = st.selectbox("Product Name", PRODUCT_LIST)
#                 model = st.text_input("Model")
#                 connectivity = st.selectbox("Connectivity", ["4G", "2G", "NB-IoT", "WiFi-Only"])
            
#             with col2:
#                 # Conditional Logic for Cable Length
#                 cable_len = "N/A"
#                 if product_name == "DWLR":
#                     cable_len = st.text_input("Cable Length (Meters)")
#                 else:
#                     st.text_input("Cable Length", value="N/A", disabled=True)
                
#                 install_date = st.date_input("Installation Date", date.today())
#                 activation_date = st.date_input("Product Activation Date", date.today())
#                 validity = st.number_input("Validity Period (Months)", min_value=1, value=12)
                
#                 # Preview Renewal Date
#                 calc_renewal = calculate_renewal(activation_date, validity)
#                 st.caption(f"Calculated Renewal Date: **{calc_renewal}**")
            
#             with col3:
#                 device_uid = st.text_input("Device UID")
#                 sim_provider = st.selectbox("SIM Provider", SIM_PROVIDERS)
#                 sim_num = st.text_input("SIM Number")
                
#             st.markdown("---")
#             col4, col5, col6 = st.columns(3)
#             with col4:
#                 channel_partner = st.text_input("Channel Partner Name (Optional)")
#             with col5:
#                 end_user = st.text_input("End User Name")
#             with col6:
#                 industry = st.selectbox("Industry Category", INDUSTRY_CATS)
            
#             submitted = st.form_submit_button("💾 Save Product")
            
#             if submitted:
#                 if not sn or not end_user:
#                     st.error("Serial Number and End User are required!")
#                 else:
#                     new_data = {
#                         "S/N": sn, "OEM S/N": oem_sn, "Product Name": product_name, 
#                         "Model": model, "Connectivity (2G/4G)": connectivity, 
#                         "Cable Length": cable_len, "Installation Date": install_date, 
#                         "Activation Date": activation_date, "Validity (Months)": validity, 
#                         "Renewal Date": calc_renewal, "Device UID": device_uid, 
#                         "SIM Provider": sim_provider, "SIM Number": sim_num, 
#                         "Channel Partner": channel_partner, "End User": end_user, 
#                         "Industry Category": industry
#                     }
                    
#                     df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
#                     if save_data(df):
#                         st.success(f"Product {sn} added successfully!")

#     # --- 3. PRODUCT REPOSITORY ---
#     elif choice == "Product Repository":
#         st.header("🔎 Device Manager")
#         st.markdown("Use the filters below to find specific devices.")
        
#         # Streamlit Dataframe Editor allows filtering/sorting natively
#         # We configure columns to be sortable and filterable
        
#         st.dataframe(
#             df, 
#             use_container_width=True, 
#             height=600,
#             column_config={
#                 "Renewal Date": st.column_config.DateColumn("Renewal Date", format="YYYY-MM-DD"),
#                 "Installation Date": st.column_config.DateColumn("Installation Date", format="YYYY-MM-DD"),
#             }
#         )
        
#         st.caption("Note: You can click column headers to sort, and hover over headers to filter.")

#     # --- 4. CLIENT LIST ---
#     elif choice == "Client List":
#         st.header("👥 Client Database")
        
#         if not df.empty:
#             unique_clients = df["End User"].unique()
#             st.write(f"Total Unique Clients: **{len(unique_clients)}**")
            
#             # Create a summary table
#             client_summary = df.groupby("End User").agg({
#                 "S/N": "count",
#                 "Product Name": lambda x: ", ".join(x.unique()),
#                 "Industry Category": "first"
#             }).reset_index()
            
#             client_summary.columns = ["Client Name", "Total Devices", "Product Types", "Industry"]
#             st.dataframe(client_summary, use_container_width=True)
#         else:
#             st.info("No clients found.")

# if __name__ == "__main__":
#     main()