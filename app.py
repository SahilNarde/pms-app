import streamlit as st
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import io
import os
import smtplib
import base64
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# --- PDF LIBRARIES ---
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

# --- CONFIGURATION ---
SHEET_NAME = "PMS DB"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
LOGO_FILENAME = "FINAL LOGO.png"

# --- COMPANY DETAILS ---
COMPANY_INFO = {
    "name": "Orcatech Enterprises",
    "address": "Flat No. 102, Mayureshwar Heights, S.No. 24/4,\nJadhavrao Industrial Estate, Nanded City,\nSinhagad Road, Pune 411041",
    "contact": "sales@orcatech.co.in | Mobile: 9325665554",
    "gst": "27AWIPN2502N1ZB",
    "bank_name": "Bank of Maharashtra",
    "acc_name": "ORCATECH ENTERPRISES",
    "acc_no": "60493663515",
    "ifsc": "MAHB0001745",
    "branch": "NANDED PHATA"
}

st.set_page_config(page_title="Product Management System", page_icon="🏭", layout="wide")

# --- CUSTOM CSS FOR LAYOUT ---
st.markdown(
    """
    <style>
        /* Reduce sidebar padding */
        [data-testid="stSidebar"] .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
        /* Align user badge to the right */
        div[data-testid="column"] {
            align-items: center;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

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
        return None

# --- UI HELPER FUNCTIONS ---
def img_to_bytes(img_path):
    img_bytes = Path(img_path).read_bytes()
    encoded = base64.b64encode(img_bytes).decode()
    return encoded

def render_centered_logo(img_path, width_px):
    if os.path.exists(img_path):
        img_base64 = img_to_bytes(img_path)
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 20px;">
                <img src="data:image/png;base64,{img_base64}" alt="Logo" style="width:{width_px}px; max-width: 100%; height: auto;">
            </div>
            """,
            unsafe_allow_html=True
        )

# --- PDF GENERATOR ---
def create_quotation_pdf(client_name, device_list, rate_per_device, valid_until):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()

    # 1. Header
    logo = []
    if os.path.exists(LOGO_FILENAME):
        img = Image(LOGO_FILENAME, width=2*inch, height=1*inch)
        img.hAlign = 'LEFT'
        logo.append(img)
    
    comp_details = f"""<font size=12><b>{COMPANY_INFO['name']}</b></font><br/>
    <font size=9>{COMPANY_INFO['address'].replace(chr(10), '<br/>')}<br/>
    <b>GSTIN:</b> {COMPANY_INFO['gst']}<br/>
    <b>Contact:</b> {COMPANY_INFO['contact']}</font>"""
    
    header_data = [[logo if logo else "", Paragraph(comp_details, styles['Normal'])]]
    header_table = Table(header_data, colWidths=[2.5*inch, 4.5*inch])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (1,0), (1,0), 'RIGHT')]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # 2. Title
    elements.append(Paragraph("QUOTATION", styles['Title']))
    elements.append(Spacer(1, 0.2*inch))

    # 3. Bill To
    if isinstance(client_name, dict):
        c_name = client_name.get('Client Name', '')
        c_person = client_name.get('Contact Person', '')
        c_addr = client_name.get('Address', '').replace('\n', '<br/>')
        c_phone = client_name.get('Phone Number', '')
        c_email = client_name.get('Email', '')
    else:
        c_name = str(client_name)
        c_person, c_addr, c_phone, c_email = "", "", "", ""

    bill_to = f"<b>Bill To:</b><br/><font size=12><b>{c_name}</b></font><br/>"
    if c_person: bill_to += f"Attn: {c_person}<br/>"
    if c_addr: bill_to += f"{c_addr}<br/>"
    if c_phone or c_email: bill_to += f"Ph: {c_phone} | Email: {c_email}<br/>"
    
    date_info = f"<br/><b>Date:</b> {date.today().strftime('%d-%b-%Y')}<br/><b>Valid Until:</b> {valid_until.strftime('%d-%b-%Y')}"
    elements.append(Paragraph(bill_to + date_info, styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))

    # 4. Table
    data = [['S/N', 'Product / Model', 'Description', 'Amount (INR)']]
    subtotal = 0
    for d in device_list:
        row = [d['sn'], f"{d['product']}\n{d['model']}", f"Subscription Renewal\n(Exp: {d['renewal']})", f"{rate_per_device:,.2f}"]
        data.append(row)
        subtotal += rate_per_device

    cgst = subtotal * 0.09
    sgst = subtotal * 0.09
    total = subtotal + cgst + sgst

    data.append(['', '', 'Subtotal', f"{subtotal:,.2f}"])
    data.append(['', '', 'CGST (9%)', f"{cgst:,.2f}"])
    data.append(['', '', 'SGST (9%)', f"{sgst:,.2f}"])
    data.append(['', '', 'GRAND TOTAL', f"{total:,.2f}"])

    table = Table(data, colWidths=[1.5*inch, 2*inch, 2*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('GRID', (0,0), (-1,-5), 1, colors.black),
        ('LINEBELOW', (0,-4), (-1,-1), 1, colors.grey),
        ('FONTNAME', (-2,-1), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (-2,-1), (-1,-1), colors.whitesmoke),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))

    # 5. Bank Info
    bank_info = f"""<b>Bank Details for Payment:</b><br/>
    Account Name: {COMPANY_INFO['acc_name']}<br/>
    Bank Name: {COMPANY_INFO['bank_name']}<br/>
    Account No: {COMPANY_INFO['acc_no']}<br/>
    IFSC Code: {COMPANY_INFO['ifsc']}<br/>
    Branch: {COMPANY_INFO['branch']}"""
    elements.append(Paragraph(bank_info, styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))

    # 6. Disclaimer
    disc_style = ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=8, textColor=colors.red)
    disc_text = "<b>Disclaimer:</b> Orcatech Enterprises shall not be held liable for any data loss or unavailability of historical records occurring after the subscription expiry date. Please ensure timely renewal to maintain continuous data retention."
    elements.append(Paragraph(disc_text, disc_style))
    
    # 7. Footer
    elements.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle('Footer', parent=styles['Italic'], fontSize=9, textColor=colors.darkgrey, alignment=TA_CENTER)
    elements.append(Paragraph("This is a computer-generated document and does not require a physical signature.", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- EMAIL FUNCTION ---
def send_email_with_attachment(to_email, subject, body, pdf_buffer, filename="Quotation.pdf"):
    try:
        email_conf = st.secrets["email"]
        msg = MIMEMultipart()
        msg['From'] = email_conf["sender_email"]
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        if pdf_buffer:
            part = MIMEApplication(pdf_buffer.read(), Name=filename)
            part['Content-Disposition'] = f'attachment; filename="{filename}"'
            msg.attach(part)
        server = smtplib.SMTP(email_conf["smtp_server"], email_conf["smtp_port"])
        server.starttls()
        server.login(email_conf["sender_email"], email_conf["app_password"])
        server.sendmail(email_conf["sender_email"], to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Email Error: {e}")
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
    except Exception: return pd.DataFrame()

def get_clean_list(df, column_name):
    if df.empty or column_name not in df.columns: return []
    series = df[column_name].astype(str)
    values = series.unique().tolist()
    return sorted([v.strip() for v in values if v and str(v).lower() not in ["", "nan", "none"] and v.strip() != ""])

def append_to_sheet(tab_name, data_dict):
    ws = get_worksheet(SHEET_NAME, tab_name)
    if not ws: return False
    try:
        raw_headers = ws.row_values(1)
        if not raw_headers:
            ws.append_row(list(data_dict.keys()))
            raw_headers = list(data_dict.keys())
        ws.append_row([str(data_dict.get(h.strip(), "")) for h in raw_headers])
        load_data.clear()
        return True
    except Exception: return False

def bulk_append_to_sheet(tab_name, df):
    ws = get_worksheet(SHEET_NAME, tab_name)
    if not ws: return False
    try:
        sheet_headers = ws.row_values(1)
        if not sheet_headers: return False
        
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
        st.error(f"Bulk Upload Failed: {e}")
        return False

def update_sim_status(sim_number, new_status, used_in_sn):
    ws = get_worksheet(SHEET_NAME, "Sims")
    if not ws: return
    try:
        cell = ws.find(sim_number)
        if cell:
            headers = ws.row_values(1)
            ws.update_cell(cell.row, headers.index("Status")+1, new_status)
            ws.update_cell(cell.row, headers.index("Used In S/N")+1, used_in_sn)
            load_data.clear()
    except Exception: pass

def update_product_subscription(sn, new_activ, new_val, new_renew):
    ws = get_worksheet(SHEET_NAME, "Products")
    if not ws: return False
    try:
        cell = ws.find(sn)
        if cell:
            headers = ws.row_values(1)
            ws.update_cell(cell.row, headers.index("Activation Date")+1, str(new_activ))
            ws.update_cell(cell.row, headers.index("Validity (Months)")+1, str(new_val))
            ws.update_cell(cell.row, headers.index("Renewal Date")+1, str(new_renew))
            load_data.clear()
            return True
    except Exception: return False
    return False

def update_client_details(original_name, updated_data):
    ws = get_worksheet(SHEET_NAME, "Clients")
    if not ws: return False
    try:
        cell = ws.find(original_name)
        if cell:
            headers = ws.row_values(1)
            for key, value in updated_data.items():
                if key in headers: ws.update_cell(cell.row, headers.index(key)+1, str(value))
            load_data.clear()
            return True
    except Exception: return False
    return False

def calculate_renewal(activation_date, months):
    if not activation_date: return None
    try: return (pd.to_datetime(activation_date).date() + relativedelta(months=int(months)))
    except: return None

def check_expiry_status(renewal_date):
    try:
        days = (pd.to_datetime(renewal_date).date() - datetime.now().date()).days
        return "Expired" if days < 0 else ("Expiring Soon" if days <= 30 else "Active")
    except: return "Unknown"

def convert_all_to_excel(dfs_dict):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in dfs_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()

def check_login(username, password):
    ws = get_worksheet(SHEET_NAME, "Credentials")
    if not ws: return None
    data = ws.get_all_values()
    if not data: return None
    df = pd.DataFrame(data[1:], columns=[h.strip() for h in data[0]])
    user_match = df[(df['Username'].str.strip() == username.strip()) & (df['Password'].str.strip() == password.strip())]
    return user_match.iloc[0]['Name'] if not user_match.empty else None

# --- MAIN APP ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_name = ""

    if not st.session_state.logged_in:
        # Use wider middle column to hold side-by-side layout
        c1, c2, c3 = st.columns([1, 3, 1])
        with c2:
            st.write("") # Spacer
            st.write("") 
            # --- SPLIT LAYOUT: LOGO LEFT | FORM RIGHT ---
            c_logo, c_form = st.columns([1, 1.5], gap="large")
            
            with c_logo:
                # Vertical spacer to align logo with form
                st.write("")
                st.write("")
                if os.path.exists(LOGO_FILENAME):
                    st.image(LOGO_FILENAME, use_container_width=True)
            
            with c_form:
                st.markdown("## 🔒 System Login")
                with st.form("login_form"):
                    user = st.text_input("Username")
                    pwd = st.text_input("Password", type="password")
                    if st.form_submit_button("Login"):
                        name = check_login(user, pwd)
                        if name:
                            st.session_state.logged_in = True
                            st.session_state.user_name = name
                            st.rerun()
                        else: st.error("Invalid Credentials")
        return

    with st.sidebar:
        # --- LOGO ON SIDEBAR (CENTERED) ---
        render_centered_logo(LOGO_FILENAME, 120)
        st.markdown("---")
        
        # NAVIGATION MENU
        menu = st.sidebar.radio("Go to:", ["Dashboard", "SIM Manager", "New Dispatch Entry", "Subscription Manager", "Installation List", "Client Master", "Channel Partner Analytics", "IMPORT/EXPORT DB"])
        
        # --- BOTTOM SECTION ---
        st.markdown("---")
        # Refresh button (small)
        if st.button("🔄 Refresh Data"): 
            load_data.clear()
            st.rerun()
            
        # Logout button
        if st.button("🚪 Logout", type="primary", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

        st.markdown("### 📊 Database Stats")
        # Placeholder for stats
        stats_placeholder = st.empty()

    # --- TOP HEADER (USER INFO RIGHT) ---
    c_title, c_user = st.columns([3, 1])
    with c_title:
        st.title("🏭 PMS (Cloud)")
    with c_user:
        # User Name top right
        st.success(f"👤 **{st.session_state.user_name}**")
        
    st.markdown("---")

    # --- LOAD DATA ---
    try:
        prod_df = load_data("Products")
        client_df = load_data("Clients")
        sim_df = load_data("Sims")
        
        if prod_df.empty or "S/N" not in prod_df.columns:
            prod_df = pd.DataFrame(columns=["S/N", "End User", "Product Name", "Model", "Renewal Date", "Industry Category", "Installation Date", "Activation Date", "Validity (Months)", "Channel Partner", "Device UID", "Connectivity (2G/4G)", "Cable Length", "SIM Number", "SIM Provider"])
        if client_df.empty or "Client Name" not in client_df.columns:
            client_df = pd.DataFrame(columns=["Client Name", "Email", "Phone Number", "Contact Person", "Address"])
        if sim_df.empty or "SIM Number" not in sim_df.columns:
            sim_df = pd.DataFrame(columns=["SIM Number", "Status", "Provider", "Plan Details", "Entry Date", "Used In S/N"])

        # Populate Stats
        with stats_placeholder.container():
            st.caption(f"📦 Products: {len(prod_df)}")
            st.caption(f"👥 Clients: {len(client_df)}")
            st.caption(f"📶 SIMs: {len(sim_df)}")

    except Exception:
        st.error("Connection Error. Data could not be loaded.")
        return

    BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]

    if menu == "Dashboard":
        st.subheader("📊 Analytics Overview")
        if not prod_df.empty:
            prod_df['Status_Calc'] = prod_df['Renewal Date'].apply(check_expiry_status)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total", len(prod_df))
            c2.metric("Active", len(prod_df[prod_df['Status_Calc'] == "Active"]))
            c3.metric("Expiring", len(prod_df[prod_df['Status_Calc'] == "Expiring Soon"]))
            c4.metric("Expired", len(prod_df[prod_df['Status_Calc'] == "Expired"]))
            st.divider()
            
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                if "Industry Category" in prod_df.columns:
                    df_pie = prod_df[~prod_df["Industry Category"].isin(['', 'nan', 'None'])]
                    if not df_pie.empty:
                        fig = px.pie(df_pie, names='Industry Category', title="Industry Distribution", hole=0.4)
                        st.plotly_chart(fig, use_container_width=True)
            with col_g2:
                if "Installation Date" in prod_df.columns:
                    df_trend = prod_df.copy()
                    df_trend["Installation Date"] = pd.to_datetime(df_trend["Installation Date"], errors='coerce')
                    df_trend = df_trend.dropna(subset=["Installation Date"])
                    if not df_trend.empty:
                        trend = df_trend.groupby(df_trend["Installation Date"].dt.to_period("M")).size().reset_index(name="Count")
                        trend["Month"] = trend["Installation Date"].astype(str)
                        st.plotly_chart(px.area(trend, x="Month", y="Count", title="Monthly Installations", markers=True), use_container_width=True)
            
            st.markdown("### ⚠️ Alert Center")
            t1, t2 = st.tabs(["⏳ Expiring Soon", "❌ Expired"])
            with t1: st.dataframe(prod_df[prod_df['Status_Calc']=="Expiring Soon"], use_container_width=True)
            with t2: st.dataframe(prod_df[prod_df['Status_Calc']=="Expired"], use_container_width=True)
        else: st.info("Database empty.")

    elif menu == "SIM Manager":
        st.subheader("📶 SIM Inventory")
        with st.form("add_sim"):
            s_prov = st.selectbox("Provider", ["VI", "AIRTEL", "JIO", "BSNL"])
            s_num = st.text_input("SIM Number")
            if st.form_submit_button("Add SIM"):
                if str(s_num) in sim_df["SIM Number"].values: st.error("Exists")
                elif append_to_sheet("Sims", {"SIM Number": s_num, "Provider": s_prov, "Status": "Available"}): st.success("Added"); st.rerun()
        st.dataframe(sim_df, use_container_width=True)

    elif menu == "New Dispatch Entry":
        st.subheader("📝 New Dispatch")
        st.markdown("### 🛠️ Device & Network")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            sn = st.text_input("Product S/N (Required)")
            oem = c1.text_input("OEM S/N")
        with c2:
            prod = st.selectbox("Product Name", BASE_PRODUCT_LIST)
            model = st.text_input("Model")
        with c3:
            conn = st.selectbox("Connectivity", ["4G", "2G", "NB-IoT", "WiFi", "LoRaWAN"])
            cable = st.text_input("Cable Length")
        with c4:
            uid = st.text_input("Device UID")
            avail_sims = get_clean_list(sim_df[sim_df["Status"] == "Available"], "SIM Number")
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
                if not match.empty: final_sim_prov = match.iloc[0]["Provider"]

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
            elif sn in prod_df["S/N"].values: st.error("S/N already exists!")
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
                        if final_sim_num in sim_df["SIM Number"].values: update_sim_status(final_sim_num, "Used", sn)
                        else: append_to_sheet("Sims", {"SIM Number": final_sim_num, "Provider": final_sim_prov, "Status": "Used", "Used In S/N": sn})
                    st.success("✅ Dispatch Saved Successfully!"); st.balloons(); st.rerun()

    elif menu == "Subscription Manager":
        st.subheader("🔄 Subscription & Quotation Manager")
        if not prod_df.empty and 'Renewal Date' in prod_df.columns:
            prod_df['Status_Calc'] = prod_df['Renewal Date'].apply(check_expiry_status)
            exp_df = prod_df[prod_df['Status_Calc'].isin(["Expiring Soon", "Expired"])].copy()
            if exp_df.empty: st.success("✅ Good news! No devices need renewal.")
            else:
                tab_single, tab_bulk = st.tabs(["📱 Individual Renewal", "🏢 Bulk Renewal"])
                with tab_single:
                    exp_df['Label'] = exp_df['S/N'] + " | " + exp_df['End User']
                    selected_label = st.selectbox("Select Device", exp_df['Label'].tolist())
                    selected_sn = selected_label.split(" | ")[0]
                    row = exp_df[exp_df['S/N'] == selected_sn].iloc[0]
                    st.info(f"Product: {row.get('Product Name')} | Client: {row.get('End User')} | Expires: {row.get('Renewal Date')}")
                    
                    with st.expander("📄 Generate Quote"):
                        with st.form("single_quote"):
                            s_rate = st.number_input("Amount (INR)", value=2500.0)
                            s_valid = st.date_input("Valid Until", date.today() + relativedelta(days=15))
                            if st.form_submit_button("Generate"):
                                c_det = {"Client Name": row.get('End User')}
                                if not client_df.empty:
                                    c_match = client_df[client_df["Client Name"] == row.get('End User')]
                                    if not c_match.empty: c_det = c_match.iloc[0].to_dict()
                                d_list = [{"sn": selected_sn, "product": row.get('Product Name'), "model": row.get('Model', '-'), "renewal": row.get('Renewal Date')}]
                                st.session_state['sq_data'] = {"client": c_det, "devices": d_list, "rate": s_rate, "valid": s_valid}
                                st.success("Ready to Email!")

                    if 'sq_data' in st.session_state:
                        with st.expander("📧 Email Quote", expanded=True):
                            sq = st.session_state['sq_data']
                            se_to = st.text_input("To Email", value=sq['client'].get('Email', ''), key="se_to")
                            se_sub = st.text_input("Subject", value=f"Renewal Quote - {selected_sn}", key="se_sub")
                            se_body = st.text_area("Message", value=f"Dear {sq['client'].get('Client Name', 'Client')},\n\nPlease find the renewal quote attached.\n\nRegards,\nOrcatech", height=100, key="se_body")
                            
                            if st.button("Send Email", key="se_btn"):
                                pdf = create_quotation_pdf(sq['client'], sq['devices'], sq['rate'], sq['valid'])
                                if send_email_with_attachment(se_to, se_sub, se_body, pdf, "Quote.pdf"):
                                    st.success("Sent!")
                                    del st.session_state['sq_data']

                    with st.expander("📅 Update Renewal Date"):
                        with st.form("single_renew"):
                            new_st = st.date_input("New Start", date.today())
                            new_dur = st.number_input("Months", value=12)
                            if st.form_submit_button("Update DB"):
                                new_end = calculate_renewal(new_st, new_dur)
                                if update_product_subscription(selected_sn, str(new_st), new_dur, str(new_end)):
                                    st.success("Updated!"); st.rerun()

                with tab_bulk:
                    clients_list = get_clean_list(exp_df, "End User")
                    sel_client = st.selectbox("Select Company", clients_list)
                    client_devs = exp_df[exp_df["End User"] == sel_client]
                    st.dataframe(client_devs[["S/N", "Product Name", "Renewal Date", "Status_Calc"]], use_container_width=True)
                    
                    with st.expander("📄 Generate Bulk Quote"):
                        with st.form("bulk_quote"):
                            b_rate = st.number_input("Rate Per Device", value=2500.0)
                            b_valid = st.date_input("Valid Until", date.today() + relativedelta(days=15))
                            if st.form_submit_button("Generate"):
                                c_det = {"Client Name": sel_client}
                                if not client_df.empty:
                                    c_match = client_df[client_df["Client Name"] == sel_client]
                                    if not c_match.empty: c_det = c_match.iloc[0].to_dict()
                                d_list = []
                                for _, r in client_devs.iterrows():
                                    d_list.append({"sn": r['S/N'], "product": r.get('Product Name'), "model": r.get('Model', '-'), "renewal": r.get('Renewal Date')})
                                st.session_state['bq_data'] = {"client": c_det, "devices": d_list, "rate": b_rate, "valid": b_valid}
                                st.success("Ready to Email!")

                    if 'bq_data' in st.session_state:
                        with st.expander("📧 Email Bulk Quote", expanded=True):
                            bq = st.session_state['bq_data']
                            be_to = st.text_input("To Email", value=bq['client'].get('Email', ''), key="be_to")
                            be_sub = st.text_input("Subject", value=f"Bulk Renewal Quote - {sel_client}", key="be_sub")
                            be_body = st.text_area("Message", value=f"Dear {sel_client},\n\nPlease find the bulk renewal quote attached.\n\nRegards,\nOrcatech", height=100, key="be_body")
                            
                            if st.button("Send Bulk Email", key="be_btn"):
                                pdf = create_quotation_pdf(bq['client'], bq['devices'], bq['rate'], bq['valid'])
                                if send_email_with_attachment(be_to, be_sub, be_body, pdf, "Quote.pdf"):
                                    st.success("Sent!")
                                    del st.session_state['bq_data']

                    with st.expander("📅 Bulk Update Renewal"):
                        with st.form("bulk_renew"):
                            b_start = st.date_input("New Start", date.today())
                            b_dur = st.number_input("Months", value=12)
                            if st.form_submit_button("Update ALL"):
                                b_end = calculate_renewal(b_start, b_dur)
                                cnt = 0
                                for sn in client_devs['S/N'].tolist():
                                    if update_product_subscription(sn, str(b_start), b_dur, str(b_end)): cnt += 1
                                st.success(f"Updated {cnt} devices!"); st.rerun()
        else: st.info("No product data available.")

    elif menu == "Installation List":
        st.subheader("🔎 Installation Repository")
        search = st.text_input("Search")
        if search: st.dataframe(prod_df[prod_df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)], use_container_width=True)
        else: st.dataframe(prod_df, use_container_width=True)

    elif menu == "Client Master":
        st.subheader("👥 Client Master")
        st.dataframe(client_df, use_container_width=True)
        clients = get_clean_list(client_df, "Client Name")
        if clients:
            with st.expander("Edit Client Details"):
                c_edit = st.selectbox("Select Client", clients)
                row = client_df[client_df["Client Name"] == c_edit].iloc[0]
                with st.form("edit_c"):
                    nm = st.text_input("Name", value=row["Client Name"])
                    em = st.text_input("Email", value=row.get("Email", ""))
                    ph = st.text_input("Phone", value=row.get("Phone Number", ""))
                    ad = st.text_input("Address", value=row.get("Address", ""))
                    if st.form_submit_button("Update"):
                        if update_client_details(c_edit, {"Client Name": nm, "Email": em, "Phone Number": ph, "Address": ad}):
                            st.success("Updated!"); st.rerun()

    elif menu == "Channel Partner Analytics":
        st.subheader("🤝 Partner Performance")
        if not prod_df.empty and "Channel Partner" in prod_df.columns:
            partner_counts = prod_df["Channel Partner"].value_counts().reset_index()
            partner_counts.columns = ["Partner Name", "Total Installations"]
            
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown("#### 🏆 Leaderboard")
                st.dataframe(partner_counts, use_container_width=True, hide_index=True)
            with c2:
                st.markdown("#### 📊 Installation Volume")
                fig = px.bar(partner_counts, x="Partner Name", y="Total Installations", 
                             title="Total Installations by Partner",
                             text_auto=True,
                             color="Total Installations",
                             color_continuous_scale="Viridis")
                st.plotly_chart(fig, use_container_width=True)

            st.divider()
            st.markdown("#### 🔍 Partner Drill-Down")
            sel_partner = st.selectbox("Select Partner", sorted(prod_df["Channel Partner"].unique()))
            if sel_partner:
                specific = prod_df[prod_df["Channel Partner"] == sel_partner]
                st.dataframe(specific, use_container_width=True)
        else: st.info("No Partner Data")

    elif menu == "IMPORT/EXPORT DB":
        st.subheader("💾 Backup")
        all_data = {"Products": prod_df, "Clients": client_df, "Sims": sim_df}
        st.download_button("Download Full Database (Excel)", convert_all_to_excel(all_data), "PMS_Full_Backup.xlsx")
        
        st.divider()
        st.markdown("### ⚠️ Bulk Import (Appends to Products)")
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
