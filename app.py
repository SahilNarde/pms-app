import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# --- PDF GENERATION LIBRARIES ---
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch

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

# --- PDF GENERATOR ---
def create_quotation_pdf(client_name, product_name, sn, description, amount, valid_until):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # -- Header --
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 50, "QUOTATION")
    
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, f"Date: {date.today()}")
    c.drawString(50, height - 85, f"Valid Until: {valid_until}")

    # -- Company Info (Your Company) --
    c.setFont("Helvetica-Bold", 12)
    c.drawString(400, height - 50, "Orcatech Enterprises") # Replace with your Company Name
    c.setFont("Helvetica", 10)
    c.drawString(400, height - 65, "123 Tech Park, Pune")
    c.drawString(400, height - 80, "support@orcatech.com")

    c.line(50, height - 100, width - 50, height - 100)

    # -- Client Details --
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 130, "Bill To:")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 145, client_name)

    # -- Table Header --
    y = height - 200
    c.setFillColor(colors.lightgrey)
    c.rect(50, y, width - 100, 20, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(60, y + 6, "Description")
    c.drawString(450, y + 6, "Amount (INR)")

    # -- Line Item --
    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(60, y, f"{product_name} (S/N: {sn})")
    c.drawString(60, y - 15, description) # Sub-description
    c.drawString(450, y, f"{amount:,.2f}")

    # -- Total --
    y -= 50
    c.line(50, y, width - 50, y)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y - 20, "Total:")
    c.drawString(450, y - 20, f"INR {amount:,.2f}")

    # -- Footer --
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 50, "This is a computer-generated quotation. No signature required.")
    
    c.save()
    buffer.seek(0)
    return buffer

# --- EMAIL FUNCTION (WITH ATTACHMENT) ---
def send_email_with_attachment(to_email, subject, body, pdf_buffer, filename="Quotation.pdf"):
    try:
        email_conf = st.secrets["email"]
        smtp_server = email_conf["smtp_server"]
        smtp_port = email_conf["smtp_port"]
        sender_email = email_conf["sender_email"]
        password = email_conf["app_password"]

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Attach PDF
        if pdf_buffer:
            part = MIMEApplication(pdf_buffer.read(), Name=filename)
            part['Content-Disposition'] = f'attachment; filename="{filename}"'
            msg.attach(part)

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# --- DATA HANDLING ---
@st.cache_data(ttl=60)
def load_data(tab_name):
    ws = get_worksheet(SHEET_NAME, tab_name)
    if not ws: return pd.DataFrame()
    try:
        data = ws.get_all_values()
        if not data: return pd.DataFrame()
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        df.columns = df.columns.astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Error reading {tab_name}: {e}")
        return pd.DataFrame()

def get_clean_list(df, column_name):
    if df.empty or column_name not in df.columns: return []
    series = df[column_name].astype(str)
    values = series.unique().tolist()
    clean_values = [v.strip() for v in values if v and str(v).lower() not in ["", "nan", "none", "null"] and v.strip() != ""]
    return sorted(list(set(clean_values)))

def append_to_sheet(tab_name, data_dict):
    ws = get_worksheet(SHEET_NAME, tab_name)
    if not ws: return False
    try:
        raw_headers = ws.row_values(1)
        if not raw_headers:
            headers = list(data_dict.keys())
            ws.append_row(headers)
            raw_headers = headers
        row_values = []
        for h in raw_headers:
            val = data_dict.get(h.strip(), "")
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
        for h in sheet_headers:
            h_clean = h.strip()
            if h_clean not in df.columns: df[h_clean] = ""
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
                status_col = headers.index("Status") + 1
                used_col = headers.index("Used In S/N") + 1
                ws.update_cell(cell.row, status_col, new_status)
                ws.update_cell(cell.row, used_col, used_in_sn)
                load_data.clear()
            except ValueError: pass
    except Exception as e:
        st.warning(f"Could not update SIM status: {e}")

def update_product_subscription(sn, new_activ, new_val, new_renew):
    ws = get_worksheet(SHEET_NAME, "Products")
    if not ws: return False
    try:
        cell = ws.find(sn)
        if cell:
            headers = ws.row_values(1)
            try:
                activ_col = headers.index("Activation Date") + 1
                valid_col = headers.index("Validity (Months)") + 1
                renew_col = headers.index("Renewal Date") + 1
                ws.update_cell(cell.row, activ_col, str(new_activ))
                ws.update_cell(cell.row, valid_col, str(new_val))
                ws.update_cell(cell.row, renew_col, str(new_renew))
                load_data.clear()
                return True
            except ValueError:
                st.error("Could not find Date columns in Sheet headers.")
                return False
    except Exception as e:
        st.error(f"Update failed: {e}")
        return False
    return False

def update_client_details(original_name, updated_data):
    ws = get_worksheet(SHEET_NAME, "Clients")
    if not ws: return False
    try:
        cell = ws.find(original_name)
        if cell:
            headers = ws.row_values(1)
            for key, value in updated_data.items():
                if key in headers:
                    col_index = headers.index(key) + 1
                    ws.update_cell(cell.row, col_index, str(value))
            load_data.clear()
            return True
        else:
            st.error("Client not found.")
            return False
    except Exception as e:
        st.error(f"Update failed: {e}")
        return False

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
    df.columns = df.columns.str.strip()
    if 'Username' not in df.columns or 'Password' not in df.columns: return None
    user_match = df[(df['Username'].str.strip() == username.strip()) & (df['Password'].str.strip() == password.strip())]
    if not user_match.empty: return user_match.iloc[0]['Name']
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

    try:
        prod_df = load_data("Products")
        client_df = load_data("Clients")
        sim_df = load_data("Sims")
        
        if "S/N" not in prod_df.columns: prod_df = pd.DataFrame(columns=["S/N", "End User", "Renewal Date", "Industry Category", "Installation Date", "Activation Date", "Validity (Months)", "Channel Partner"])
        required_client_cols = ["Client Name", "Email", "Phone Number", "Contact Person", "Address"]
        for col in required_client_cols:
            if col not in client_df.columns: client_df[col] = ""
        if "SIM Number" not in sim_df.columns: sim_df = pd.DataFrame(columns=["SIM Number", "Status", "Provider"])
    except Exception as e:
        st.error("⚠️ Data connection error. Please refresh.")
        return

    st.sidebar.caption(f"📦 Products: {len(prod_df)}")
    st.sidebar.caption(f"👥 Clients: {len(client_df)}")
    st.sidebar.caption(f"📶 SIMs: {len(sim_df)}")

    menu = st.sidebar.radio("Go to:", 
        ["Dashboard", "SIM Manager", "New Dispatch Entry", "Subscription Manager", "Installation List", "Client Master", "Channel Partner Analytics", "IMPORT/EXPORT DB"])

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
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                if "Industry Category" in prod_df.columns:
                    df_pie = prod_df.copy()
                    df_pie["Industry Category"] = df_pie["Industry Category"].replace(['', 'nan', 'None', 'NaN'], 'Uncategorized')
                    df_pie["Industry Category"] = df_pie["Industry Category"].astype(str).str.strip()
                    df_pie["Industry Category"] = df_pie["Industry Category"].replace('', 'Uncategorized')
                    ind_counts = df_pie['Industry Category'].value_counts().reset_index()
                    ind_counts.columns = ['Industry Category', 'Count']
                    fig_pie = px.pie(ind_counts, values='Count', names='Industry Category', title="Industry Distribution", hole=0.4)
                    st.plotly_chart(fig_pie, use_container_width=True)
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
            st.markdown("### ⚠️ Alert Center")
            tab_soon, tab_expired = st.tabs(["⏳ Expiring Soon", "❌ Expired"])
            with tab_soon:
                df_soon = prod_df[prod_df['Status_Calc'] == "Expiring Soon"]
                if not df_soon.empty:
                    st.dataframe(df_soon[["S/N", "End User", "Renewal Date", "Status_Calc"]], use_container_width=True)
                else: st.success("No subscriptions expiring soon.")
            with tab_expired:
                df_expired = prod_df[prod_df['Status_Calc'] == "Expired"]
                if not df_expired.empty:
                    st.dataframe(df_expired[["S/N", "End User", "Renewal Date", "Status_Calc"]], use_container_width=True)
                else: st.success("No expired subscriptions.")
        else: st.info("Database empty. Add entries.")

    # 2. SIM MANAGER
    elif menu == "SIM Manager":
        st.subheader("📶 SIM Inventory")
        with st.form("add_sim"):
            s_prov = st.selectbox("Provider", ["VI", "AIRTEL", "JIO", "BSNL"])
            s_num = st.text_input("SIM Number")
            s_plan = st.text_input("Plan")
            if st.form_submit_button("Add SIM"):
                sim_list = sim_df["SIM Number"].values if "SIM Number" in sim_df.columns else []
                if str(s_num) in sim_list: st.error("SIM Exists!")
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
        final_sim_num, final_sim_prov = "", "VI"
        if sim_sel == "➕ Add New SIM...":
            c_s1, c_s2 = st.columns(2)
            with c_s1: final_sim_num = st.text_input("Enter New SIM Number")
            with c_s2: final_sim_prov = st.selectbox("Provider", ["VI", "AIRTEL", "JIO", "BSNL", "Other"])
        elif sim_sel != "None":
            final_sim_num = sim_sel
            if not sim_df.empty:
                match = sim_df[sim_df["SIM Number"] == final_sim_num]
                if not match.empty and "Provider" in match.columns: final_sim_prov = match.iloc[0]["Provider"]
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
            if not sn or not final_client: st.error("S/N and Client are required!")
            elif sn in (prod_df["S/N"].values if "S/N" in prod_df.columns else []): st.error("S/N already exists!")
            else:
                renew_date = calculate_renewal(activ_d, valid)
                new_prod = {
                    "S/N": sn, "OEM S/N": oem, "Product Name": prod, "Model": model,
                    "Connectivity (2G/4G)": conn, "Cable Length": cable, "Installation Date": str(install_d),
                    "Activation Date": str(activ_d), "Validity (Months)": valid, "Renewal Date": str(renew_date),
                    "Device UID": uid, "SIM Number": final_sim_num, "SIM Provider": final_sim_prov,
                    "Channel Partner": final_partner, "End User": final_client, "Industry Category": final_ind
                }
                if append_to_sheet("Products", new_prod):
                    if c_sel == "➕ Create New..." and final_client: append_to_sheet("Clients", {"Client Name": final_client})
                    if final_sim_num:
                        sim_db_list = sim_df["SIM Number"].values if "SIM Number" in sim_df.columns else []
                        if final_sim_num in sim_db_list: update_sim_status(final_sim_num, "Used", sn)
                        else: append_to_sheet("Sims", {"SIM Number": final_sim_num, "Provider": final_sim_prov, "Status": "Used", "Used In S/N": sn, "Entry Date": str(date.today())})
                    st.success("✅ Dispatch Saved Successfully!"); st.balloons(); st.rerun()

    # 4. SUBSCRIPTION MANAGER (UPDATED WITH QUOTATION)
    elif menu == "Subscription Manager":
        st.subheader("🔄 Subscription Renewal Manager")
        if not prod_df.empty and "Renewal Date" in prod_df.columns:
            prod_df['Status_Calc'] = prod_df['Renewal Date'].apply(check_expiry_status)
            renew_candidates = prod_df[prod_df['Status_Calc'].isin(["Expiring Soon", "Expired"])].copy()
            if renew_candidates.empty:
                st.success("✅ Good news! No devices need renewal at this time.")
            else:
                renew_candidates['Label'] = renew_candidates['S/N'] + " | " + renew_candidates['End User'] + " (" + renew_candidates['Status_Calc'] + ")"
                selected_label = st.selectbox("Select Device to Renew", renew_candidates['Label'].tolist())
                selected_sn = selected_label.split(" | ")[0]
                row = renew_candidates[renew_candidates['S/N'] == selected_sn].iloc[0]
                
                st.divider()
                st.markdown(f"**Current Status:** :red[{row['Status_Calc']}]")
                c_info1, c_info2, c_info3 = st.columns(3)
                c_info1.info(f"**Product:** {row.get('Product Name', 'N/A')}")
                c_info2.info(f"**Current Expiry:** {row.get('Renewal Date', 'N/A')}")
                c_info3.info(f"**Client:** {row.get('End User', 'N/A')}")

                # --- 1. GENERATE QUOTATION ---
                st.markdown("### 📄 Generate Quotation")
                with st.form("quote_form"):
                    cq1, cq2 = st.columns(2)
                    quote_amount = cq1.number_input("Subscription Amount (INR)", min_value=0.0, step=100.0)
                    quote_desc = cq2.text_input("Line Item Description", value=f"Subscription Renewal for {row.get('Product Name', 'Device')} (12 Months)")
                    quote_validity = st.date_input("Quote Valid Until", value=date.today() + relativedelta(days=15))
                    
                    submitted_quote = st.form_submit_button("📜 Generate Quote Preview")
                    if submitted_quote:
                        st.session_state['generated_quote'] = {
                            'amount': quote_amount,
                            'desc': quote_desc,
                            'valid': quote_validity
                        }
                        st.success("Quote details saved! Review and send below.")

                # --- 2. REVIEW & SEND ---
                if 'generated_quote' in st.session_state:
                    st.divider()
                    st.markdown("### 📧 Review & Email")
                    
                    # Fetch Client Email
                    client_name = row.get('End User', 'Client')
                    client_email = ""
                    if "Email" in client_df.columns:
                        match_client = client_df[client_df["Client Name"] == client_name]
                        if not match_client.empty: client_email = match_client.iloc[0]["Email"]

                    q_data = st.session_state['generated_quote']
                    
                    ce1, ce2 = st.columns(2)
                    email_to = ce1.text_input("Recipient Email", value=client_email)
                    email_subject = ce2.text_input("Subject", value=f"Quotation for Subscription Renewal - {selected_sn}")
                    email_body = st.text_area("Email Message", value=f"Dear {client_name},\n\nPlease find attached the quotation for the subscription renewal of your device ({selected_sn}).\n\nTotal Amount: INR {q_data['amount']:,.2f}\n\nRegards,\nOrcatech Enterprises")

                    if st.button("📨 Send Quotation Email", type="primary"):
                        if not email_to: st.error("Email required!")
                        elif "email" not in st.secrets: st.error("Configure email secrets!")
                        else:
                            with st.spinner("Generating PDF & Sending..."):
                                pdf_bytes = create_quotation_pdf(client_name, row.get('Product Name', 'Device'), selected_sn, q_data['desc'], q_data['amount'], q_data['valid'])
                                if send_email_with_attachment(email_to, email_subject, email_body, pdf_bytes, filename=f"Quote_{selected_sn}.pdf"):
                                    st.success(f"Quotation sent to {email_to}!")
                                    del st.session_state['generated_quote'] # Clear state

                # --- 3. RENEW (FINAL STEP) ---
                st.divider()
                st.markdown("### 📅 Finalize Renewal (Update Database)")
                with st.form("renew_db_form"):
                    cr1, cr2 = st.columns(2)
                    new_install_d = cr1.date_input("New Activation Date", date.today())
                    new_validity = cr2.number_input("Validity (Months)", min_value=1, value=12, step=1)
                    new_end_date = calculate_renewal(new_install_d, new_validity)
                    st.write(f"**New Expiry Date:** :green[{new_end_date}]")
                    
                    if st.form_submit_button("✅ Confirm Renewal in DB"):
                        if update_product_subscription(selected_sn, str(new_install_d), new_validity, str(new_end_date)):
                            st.success(f"Database updated for {selected_sn}!"); st.balloons(); st.rerun()
                        else: st.error("Update failed.")
        else: st.info("No product data available.")

    # 5. INSTALLATION LIST
    elif menu == "Installation List":
        st.subheader("🔎 Installation Repository")
        search_term = st.text_input("🔍 Search Database", placeholder="Type S/N, Client, or UID...")
        if search_term:
            mask = prod_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)
            display_df = prod_df[mask]
            st.info(f"Found {len(display_df)} records matching '{search_term}'")
        else: display_df = prod_df
        st.dataframe(display_df, use_container_width=True)

    # 6. CLIENT MASTER
    elif menu == "Client Master":
        st.subheader("👥 Client Master Database")
        st.dataframe(client_df, use_container_width=True)
        st.divider()
        st.markdown("### ✏️ Edit Client Details")
        avail_clients = get_clean_list(client_df, "Client Name")
        if avail_clients:
            client_to_edit = st.selectbox("Select Client to Edit", avail_clients)
            current_row = client_df[client_df["Client Name"] == client_to_edit].iloc[0]
            with st.form("edit_client_form"):
                new_name = st.text_input("Client Name (Editing this will NOT update Products)", value=current_row["Client Name"])
                c_edit1, c_edit2 = st.columns(2)
                new_email = c_edit1.text_input("Email", value=current_row.get("Email", ""))
                new_phone = c_edit2.text_input("Phone Number", value=current_row.get("Phone Number", ""))
                c_edit3, c_edit4 = st.columns(2)
                new_contact = c_edit3.text_input("Contact Person", value=current_row.get("Contact Person", ""))
                new_address = c_edit4.text_input("Address", value=current_row.get("Address", ""))
                if st.form_submit_button("💾 Update Client Details"):
                    update_payload = {"Client Name": new_name, "Email": new_email, "Phone Number": new_phone, "Contact Person": new_contact, "Address": new_address}
                    if update_client_details(client_to_edit, update_payload):
                        st.success("Client updated successfully!"); st.rerun()
        else: st.info("No clients found to edit.")
    
    # 7. PARTNER ANALYTICS
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
                with c2: st.metric("🏆 Top Performer", partner_stats.iloc[0]["Channel Partner"])
                st.dataframe(partner_stats, use_container_width=True)
            else: st.info("No Channel Partner data.")
        else: st.info("No Data.")

    # 8. IMPORT/EXPORT
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
            uploaded_file = st.file_uploader("Choose Excel File", type=['xlsx'])
            if uploaded_file:
                try:
                    new_data = pd.read_excel(uploaded_file)
                    st.dataframe(new_data.head(), use_container_width=True)
                    if st.button("Confirm Bulk Upload"):
                        with st.spinner("Uploading..."):
                            if bulk_append_to_sheet("Products", new_data):
                                st.success(f"✅ Uploaded {len(new_data)} rows!"); st.rerun()
                except Exception as e: st.error(f"Error reading file: {e}")

if __name__ == "__main__":
    main()
