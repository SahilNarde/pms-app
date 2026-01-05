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
import uuid
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from zoneinfo import ZoneInfo

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

# --- DEFAULTS ---
DEFAULT_RATE = 4200.00
DEFAULT_SUBJECT = "Telemetry Subscription Renewal Due"
DEFAULT_EMAIL_BODY = """Dear Sir,
I hope you're doing well.
This is a gentle reminder that your telemetry subscription with Orcatech Enterprises is due for renewal for the upcoming year. We appreciate your continued trust in our services and look forward to supporting your operations with uninterrupted telemetry coverage.
Please find the renewal details in the attachment.
To ensure seamless service continuity, we recommend completing the renewal process before the due date. If you have any questions or need assistance with the renewal, feel free to reach out.
Thank you for your continued partnership.

*NOTE: Please do not reply to this email. As this mail is system generated. For communication mail on sales@orcatech.co.in

Warm regards,
ORCATECH ENTERPRISES"""

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

# --- PERMISSION CONSTANTS ---
NAV_TABS = ["Dashboard", "SIM Manager", "New Dispatch Entry", "Subscription Manager", "Installation List", "Client Master", "Channel Partner Analytics", "Email Logs", "IMPORT/EXPORT DB"]
FUNC_PERMS = ["ACCESS: Generate Quote", "ACCESS: Direct Renewal"]
ALL_OPTS = NAV_TABS + FUNC_PERMS

st.set_page_config(page_title="Product Management System", page_icon="🏭", layout="wide")

# --- CUSTOM CSS ---
st.markdown(
    """
    <style>
        [data-testid="stSidebar"] .block-container { padding-top: 1rem; padding-bottom: 1rem; }
        div[data-testid="column"] { align-items: center; }
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
        try:
            return sh.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            if tab_name == "Renewal Requests":
                return sh.add_worksheet(title="Renewal Requests", rows=100, cols=10)
            elif tab_name == "Email Logs":
                # UPDATED: Added 'Client Name' to headers
                ws = sh.add_worksheet(title="Email Logs", rows=100, cols=10)
                ws.append_row(["Date", "Time", "Sender", "To Email", "Client Name", "Subject", "Type", "Status"])
                return ws
            return None
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
    
    elements.append(Paragraph("QUOTATION", styles['Title']))
    elements.append(Spacer(1, 0.2*inch))

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

    bank_info = f"""<b>Bank Details for Payment:</b><br/>
    Account Name: {COMPANY_INFO['acc_name']}<br/>
    Bank Name: {COMPANY_INFO['bank_name']}<br/>
    Account No: {COMPANY_INFO['acc_no']}<br/>
    IFSC Code: {COMPANY_INFO['ifsc']}<br/>
    Branch: {COMPANY_INFO['branch']}"""
    elements.append(Paragraph(bank_info, styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))

    disc_style = ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=8, textColor=colors.red)
    disc_text = "<b>Disclaimer:</b> Orcatech Enterprises shall not be held liable for any data loss or unavailability of historical records occurring after the subscription expiry date. Please ensure timely renewal to maintain continuous data retention."
    elements.append(Paragraph(disc_text, disc_style))
    
    elements.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle('Footer', parent=styles['Italic'], fontSize=9, textColor=colors.darkgrey, alignment=TA_CENTER)
    elements.append(Paragraph("This is a computer-generated document and does not require a physical signature.", footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- EMAIL LOGGING ---
def log_email(to_email, client_name, subject, email_type="Single"):
    try:
        ws = get_worksheet(SHEET_NAME, "Email Logs")
        if ws:
            ist = ZoneInfo("Asia/Kolkata")
            now = datetime.now(ist)
            # Date, Time, Sender, To Email, Client Name, Subject, Type, Status
            ws.append_row([
                str(now.date()),
                now.strftime("%H:%M:%S"),
                st.session_state.get('user_name', 'System'),
                to_email,
                client_name,
                subject,
                email_type,
                "Sent"
            ])
    except Exception:
        pass

# --- EMAIL FUNCTION ---
def format_email_body_html(text):
    """Converts plain text to HTML with specific formatting."""
    html = text.replace("\n", "<br>")
    
    target_text = "*NOTE: Please do not reply to this email. As this mail is system generated. For communication mail on"
    if target_text in html:
        html = html.replace(target_text, f"<strong style='color:red;'>{target_text}</strong>")
    
    html = html.replace("sales@orcatech.co.in", "<a href='mailto:sales@orcatech.co.in' style='color:blue; text-decoration:underline;'>sales@orcatech.co.in</a>")
    
    return f"<html><body style='font-family: Arial, sans-serif;'>{html}</body></html>"

def send_email_with_attachment(to_email, client_name, subject, body, pdf_buffer, filename="Quotation.pdf", email_type="Single"):
    try:
        email_conf = st.secrets["email"]
        msg = MIMEMultipart()
        msg['From'] = email_conf["sender_email"]
        msg['To'] = to_email
        msg['Subject'] = subject
        
        html_body = format_email_body_html(body)
        msg.attach(MIMEText(html_body, 'html'))
        
        if pdf_buffer:
            part = MIMEApplication(pdf_buffer.read(), Name=filename)
            part['Content-Disposition'] = f'attachment; filename="{filename}"'
            msg.attach(part)
            
        server = smtplib.SMTP(email_conf["smtp_server"], email_conf["smtp_port"])
        server.starttls()
        server.login(email_conf["sender_email"], email_conf["app_password"])
        server.sendmail(email_conf["sender_email"], to_email, msg.as_string())
        server.quit()
        
        # Log with client name
        log_email(to_email, client_name, subject, email_type)
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
            if h.strip() not in df.columns: df[h.strip()] = ""
        clean_headers = [h.strip() for h in sheet_headers]
        ws.append_rows(df[clean_headers].astype(str).values.tolist())
        load_data.clear()
        return True
    except Exception: return False

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

def submit_renewal_request(sn_list, new_start, duration, requested_by):
    req_id = str(uuid.uuid4())[:8]
    data = {
        "Request ID": req_id,
        "S/N List": ",".join(sn_list),
        "New Start Date": str(new_start),
        "Duration": str(duration),
        "Requested By": requested_by,
        "Request Date": str(date.today()),
        "Status": "Pending"
    }
    return append_to_sheet("Renewal Requests", data)

def approve_request(req_id, sn_list_str, new_start, duration):
    sn_list = sn_list_str.split(",")
    new_end = calculate_renewal(new_start, duration)
    success_count = 0
    for sn in sn_list:
        if update_product_subscription(sn.strip(), str(new_start), duration, str(new_end)):
            success_count += 1
            
    ws = get_worksheet(SHEET_NAME, "Renewal Requests")
    if ws:
        cell = ws.find(req_id)
        if cell:
            headers = ws.row_values(1)
            ws.update_cell(cell.row, headers.index("Status")+1, "Approved")
            load_data.clear()
            return success_count
    return 0

def reject_request(req_id):
    ws = get_worksheet(SHEET_NAME, "Renewal Requests")
    if ws:
        cell = ws.find(req_id)
        if cell:
            headers = ws.row_values(1)
            ws.update_cell(cell.row, headers.index("Status")+1, "Rejected")
            load_data.clear()
            return True
    return False

def calculate_renewal(activation_date, months):
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
    if not user_match.empty:
        row = user_match.iloc[0]
        perms = row.get("Permissions", "")
        return {'name': row['Name'], 'role': row.get('Role', 'User'), 'permissions': [p.strip() for p in perms.split(",") if p.strip()] if perms else []}
    return None

def create_new_user(username, password, name, role, permissions):
    ws = get_worksheet(SHEET_NAME, "Credentials")
    if not ws: return False
    if ws.find(username): return False
    ws.append_row([username, password, name, role, ",".join(permissions)])
    return True

# --- MAIN APP ---
def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_name = ""
        st.session_state.user_role = ""
        st.session_state.user_perms = []

    if not st.session_state.logged_in:
        c1, c2, c3 = st.columns([1, 3, 1])
        with c2:
            st.write(""); st.write("") 
            c_logo, c_form = st.columns([1, 1.5], gap="large")
            with c_logo:
                st.write(""); st.write("")
                render_centered_logo(LOGO_FILENAME, 350)
            with c_form:
                st.markdown("## 🔒 System Login")
                with st.form("login_form"):
                    user = st.text_input("Username")
                    pwd = st.text_input("Password", type="password")
                    if st.form_submit_button("Login"):
                        user_data = check_login(user, pwd)
                        if user_data:
                            st.session_state.logged_in = True
                            st.session_state.user_name = user_data['name']
                            st.session_state.user_role = user_data['role']
                            st.session_state.user_perms = user_data['permissions']
                            st.rerun()
                        else: st.error("Invalid Credentials")
        return

    with st.sidebar:
        render_centered_logo(LOGO_FILENAME, 120)
        st.markdown("---")
        
        if st.session_state.user_role == "Admin":
            available_options = NAV_TABS + ["🔔 Approvals", "👤 User Manager"]
        else:
            available_options = [tab for tab in NAV_TABS if tab in st.session_state.user_perms]
            if not available_options: available_options = ["Dashboard"]

        menu = st.sidebar.radio("Go to:", available_options)
        
        st.markdown("---")
        if st.button("🔄 Refresh Data"): load_data.clear(); st.rerun()
        if st.button("🚪 Logout", type="primary", use_container_width=True):
            st.session_state.logged_in = False; st.rerun()

        st.markdown("### 📊 Database Stats")
        stats_placeholder = st.empty()

    c_title, c_user = st.columns([3, 1])
    with c_title: st.title("🏭 PMS (Cloud)")
    with c_user:
        badge = "👑 Admin" if st.session_state.user_role == "Admin" else "👤 User"
        st.success(f"{badge}: **{st.session_state.user_name}**")
    st.markdown("---")

    try:
        prod_df = load_data("Products")
        client_df = load_data("Clients")
        sim_df = load_data("Sims")
        req_df = load_data("Renewal Requests") if st.session_state.user_role == "Admin" else pd.DataFrame()
        email_df = load_data("Email Logs")

        if prod_df.empty or "S/N" not in prod_df.columns:
            prod_df = pd.DataFrame(columns=["S/N", "End User", "Product Name", "Model", "Renewal Date", "Industry Category", "Installation Date", "Activation Date", "Validity (Months)", "Channel Partner", "Device UID", "Connectivity (2G/4G)", "Cable Length", "SIM Number", "SIM Provider"])
        if client_df.empty or "Client Name" not in client_df.columns:
            client_df = pd.DataFrame(columns=["Client Name", "Email", "Phone Number", "Contact Person", "Address"])
        if sim_df.empty or "SIM Number" not in sim_df.columns:
            sim_df = pd.DataFrame(columns=["SIM Number", "Status", "Provider", "Plan Details", "Entry Date", "Used In S/N"])

        with stats_placeholder.container():
            st.caption(f"📦 Products: {len(prod_df)}")
            st.caption(f"👥 Clients: {len(client_df)}")
            st.caption(f"📶 SIMs: {len(sim_df)}")

    except Exception:
        st.error("Connection Error. Data could not be loaded."); return

    BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]

    # --- PERMISSION CHECKS ---
    can_generate_quote = "ACCESS: Generate Quote" in st.session_state.user_perms or st.session_state.user_role == "Admin"
    can_direct_renew = "ACCESS: Direct Renewal" in st.session_state.user_perms or st.session_state.user_role == "Admin"

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
            c1, c2 = st.columns(2)
            with c1:
                df_pie = prod_df[~prod_df["Industry Category"].isin(['', 'nan'])]
                st.plotly_chart(px.pie(df_pie, names='Industry Category', title="Industry Distribution", hole=0.4), use_container_width=True)
            with c2:
                df_trend = prod_df.dropna(subset=["Installation Date"])
                if not df_trend.empty:
                    df_trend["Installation Date"] = pd.to_datetime(df_trend["Installation Date"], errors='coerce')
                    trend = df_trend.groupby(df_trend["Installation Date"].dt.to_period("M")).size().reset_index(name="Count")
                    trend["Month"] = trend["Installation Date"].astype(str)
                    st.plotly_chart(px.area(trend, x="Month", y="Count", title="Monthly Installations"), use_container_width=True)
            
            st.markdown("### ⚠️ Alert Center")
            t1, t2 = st.tabs(["⏳ Expiring Soon", "❌ Expired"])
            with t1: st.dataframe(prod_df[prod_df['Status_Calc']=="Expiring Soon"], use_container_width=True)
            with t2: st.dataframe(prod_df[prod_df['Status_Calc']=="Expired"], use_container_width=True)

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
        # --- FIXED LAYOUT ---
        st.markdown("### 🛠️ Device & Network")
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            sn = st.text_input("Product S/N (Required)", key="sn_in")
            oem = st.text_input("OEM S/N", key="oem_in")
        with c2:
            prod = st.selectbox("Product Name", BASE_PRODUCT_LIST, key="prod_in")
            model = st.text_input("Model", key="model_in")
        with c3:
            conn = st.selectbox("Connectivity", ["4G", "2G", "NB-IoT", "WiFi", "LoRaWAN"], key="conn_in")
            cable = st.text_input("Cable Length", key="cable_in")
        with c4:
            uid = st.text_input("Device UID", key="uid_in")
            avail_sims = get_clean_list(sim_df[sim_df["Status"] == "Available"], "SIM Number")
            sim_opts = ["None"] + avail_sims + ["➕ Add New..."]
            sim_sel = st.selectbox("SIM Card", sim_opts, key="sim_sel")
            sim_man = ""
            sim_prov = "VI"
            if sim_sel == "➕ Add New...":
                sim_man = st.text_input("New SIM Number", key="sim_man_in")
                sim_prov = st.selectbox("Provider", ["VI", "AIRTEL", "JIO", "BSNL"], key="sim_prov_in")
            elif sim_sel != "None":
                sim_man = sim_sel

        st.divider()
        st.markdown("### 👥 Client & Partner")
        col_p, col_c, col_i, col_d = st.columns(4)
        
        with col_p:
            p_opts = ["Select..."] + get_clean_list(prod_df, "Channel Partner") + ["➕ Create..."]
            p_sel = st.selectbox("Channel Partner", p_opts, key="p_sel")
            partner = st.text_input("New Partner Name", key="p_new") if p_sel == "➕ Create..." else (p_sel if p_sel != "Select..." else "")

        with col_c:
            c_opts = ["Select..."] + get_clean_list(client_df, "Client Name") + ["➕ Create..."]
            c_sel = st.selectbox("Client", c_opts, key="c_sel")
            client = st.text_input("New Client Name", key="c_new") if c_sel == "➕ Create..." else (c_sel if c_sel != "Select..." else "")

        with col_i:
            i_opts = ["Select..."] + get_clean_list(prod_df, "Industry Category") + ["➕ Create..."]
            i_sel = st.selectbox("Industry", i_opts, key="i_sel")
            industry = st.text_input("New Industry", key="i_new") if i_sel == "➕ Create..." else (i_sel if i_sel != "Select..." else "")

        with col_d:
            install_d = st.date_input("Installation Date", key="d_inst")
            valid = st.number_input("Validity", 1, 60, 12, key="d_valid")
            activ_d = st.date_input("Activation Date", key="d_activ")

        st.markdown("---")
        if st.button("💾 Save Dispatch Entry", type="primary", use_container_width=True):
            if not sn or not client:
                st.error("S/N and Client Required!")
            elif sn in prod_df["S/N"].values:
                st.error("S/N Exists!")
            else:
                renew_date = calculate_renewal(activ_d, valid)
                new_prod = {
                    "S/N": sn, "OEM S/N": oem, "Product Name": prod, "Model": model, "Connectivity (2G/4G)": conn,
                    "Cable Length": cable, "Installation Date": str(install_d), "Activation Date": str(activ_d),
                    "Validity (Months)": valid, "Renewal Date": str(renew_date),
                    "Device UID": uid, "SIM Number": sim_man, "SIM Provider": sim_prov,
                    "Channel Partner": partner, "End User": client, "Industry Category": industry
                }
                if append_to_sheet("Products", new_prod):
                    if c_sel == "➕ Create...": append_to_sheet("Clients", {"Client Name": client})
                    if sim_man:
                        if sim_man in sim_df["SIM Number"].values: update_sim_status(sim_man, "Used", sn)
                        else: append_to_sheet("Sims", {"SIM Number": sim_man, "Provider": sim_prov, "Status": "Used", "Used In S/N": sn})
                    st.success("Saved!"); st.rerun()

    elif menu == "Subscription Manager":
        st.subheader("🔄 Subscription & Quotation Manager")
        if not prod_df.empty:
            prod_df['Status_Calc'] = prod_df['Renewal Date'].apply(check_expiry_status)
            exp_df = prod_df[prod_df['Status_Calc'].isin(["Expiring Soon", "Expired"])].copy()
            
            if exp_df.empty: st.success("No devices need renewal.")
            else:
                tab_s, tab_b = st.tabs(["📱 Individual", "🏢 Bulk"])
                
                # --- INDIVIDUAL ---
                with tab_s:
                    exp_df['Label'] = exp_df['S/N'] + " | " + exp_df['End User']
                    sel_lbl = st.selectbox("Select Device", exp_df['Label'].tolist())
                    sel_sn = sel_lbl.split(" | ")[0]
                    row = exp_df[exp_df['S/N'] == sel_sn].iloc[0]
                    
                    st.info(f"Product: {row['Product Name']} | Expires: {row['Renewal Date']}")
                    
                    # QUOTE PERMISSION CHECK
                    if can_generate_quote:
                        with st.expander("📄 Generate Quote"):
                            with st.form("sq"):
                                rate = st.number_input("Amount", value=DEFAULT_RATE)
                                valid = st.date_input("Valid Until", date.today()+relativedelta(days=15))
                                if st.form_submit_button("Generate"):
                                    c_det = {"Client Name": row['End User']}
                                    if not client_df.empty:
                                        m = client_df[client_df["Client Name"] == row['End User']]
                                        if not m.empty: c_det = m.iloc[0].to_dict()
                                    st.session_state['sq_data'] = {"c": c_det, "d": [{"sn": sel_sn, "product": row['Product Name'], "model": row.get('Model',''), "renewal": row['Renewal Date']}], "r": rate, "v": valid}
                                    st.success("Ready!")
                        
                        if 'sq_data' in st.session_state:
                            with st.expander("📧 Email"):
                                q = st.session_state['sq_data']
                                to = st.text_input("To", q['c'].get('Email',''), key="se_to")
                                sub = st.text_input("Subj", value=DEFAULT_SUBJECT, key="se_sub")
                                body = st.text_area("Msg", value=DEFAULT_EMAIL_BODY, height=350, key="se_msg")
                                if st.button("Send", key="se_btn"):
                                    pdf = create_quotation_pdf(q['c'], q['d'], q['r'], q['v'])
                                    if send_email_with_attachment(to, q['c'].get('Client Name', 'Unknown'), sub, body, pdf, "Quote.pdf", email_type="Single"):
                                        st.success("Sent!"); del st.session_state['sq_data']
                    
                    # RENEWAL PERMISSION CHECK
                    st.write("---")
                    st.markdown("### 📅 Update Subscription")
                    with st.form("sr"):
                        new_st = st.date_input("New Start", date.today())
                        dur = st.number_input("Months", 12)
                        
                        if can_direct_renew:
                            if st.form_submit_button("✅ Update Database"):
                                end = calculate_renewal(new_st, dur)
                                if update_product_subscription(sel_sn, str(new_st), dur, str(end)): st.success("Updated!"); st.rerun()
                        else:
                            if st.form_submit_button("✋ Request Renewal"):
                                if submit_renewal_request([sel_sn], new_st, dur, st.session_state.user_name):
                                    st.success("Request Submitted to Admin!"); st.rerun()

                # --- BULK ---
                with tab_b:
                    cl_list = get_clean_list(exp_df, "End User")
                    sel_cl = st.selectbox("Select Client", cl_list)
                    devs = exp_df[exp_df["End User"] == sel_cl]
                    st.dataframe(devs[["S/N", "Product Name", "Renewal Date"]])
                    
                    if can_generate_quote:
                        with st.expander("📄 Generate Bulk Quote"):
                            with st.form("bq"):
                                rate = st.number_input("Rate/Device", value=DEFAULT_RATE)
                                valid = st.date_input("Valid Until", date.today()+relativedelta(days=15))
                                if st.form_submit_button("Generate"):
                                    c_det = {"Client Name": sel_cl}
                                    if not client_df.empty:
                                        m = client_df[client_df["Client Name"] == sel_cl]
                                        if not m.empty: c_det = m.iloc[0].to_dict()
                                    d_list = []
                                    for _, r in devs.iterrows(): d_list.append({"sn": r['S/N'], "product": r['Product Name'], "model": r.get('Model',''), "renewal": r['Renewal Date']})
                                    st.session_state['bq_data'] = {"c": c_det, "d": d_list, "r": rate, "v": valid}
                                    st.success("Ready!")
                        
                        if 'bq_data' in st.session_state:
                            with st.expander("📧 Email Bulk"):
                                q = st.session_state['bq_data']
                                to = st.text_input("To", q['c'].get('Email',''), key="b_to")
                                sub = st.text_input("Subj", value=DEFAULT_SUBJECT, key="b_sub")
                                body = st.text_area("Msg", value=DEFAULT_EMAIL_BODY, height=350, key="b_msg")
                                if st.button("Send Bulk", key="b_btn"):
                                    pdf = create_quotation_pdf(q['c'], q['d'], q['r'], q['v'])
                                    if send_email_with_attachment(to, q['c'].get('Client Name', 'Unknown'), sub, body, pdf, "Quote.pdf", email_type="Bulk"):
                                        st.success("Sent!"); del st.session_state['bq_data']

                    st.write("---")
                    st.markdown("### 📅 Bulk Renewal")
                    with st.form("br"):
                        b_st = st.date_input("New Start", date.today())
                        b_dur = st.number_input("Months", 12)
                        
                        if can_direct_renew:
                            if st.form_submit_button("✅ Update ALL Devices"):
                                end = calculate_renewal(b_st, b_dur)
                                cnt = 0
                                for sn in devs['S/N']: 
                                    if update_product_subscription(sn, str(b_st), b_dur, str(end)): cnt+=1
                                st.success(f"Updated {cnt} devices!"); st.rerun()
                        else:
                            if st.form_submit_button("✋ Request Bulk Renewal"):
                                sn_list = devs['S/N'].tolist()
                                if submit_renewal_request(sn_list, b_st, b_dur, st.session_state.user_name):
                                    st.success(f"Request for {len(sn_list)} devices submitted!"); st.rerun()

    elif menu == "Installation List":
        st.subheader("🔎 Installation Repository")
        search = st.text_input("Search")
        if search: st.dataframe(prod_df[prod_df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)], use_container_width=True)
        else: st.dataframe(prod_df, use_container_width=True)

    elif menu == "Client Master":
        st.subheader("👥 Client Master")
        search_c = st.text_input("Search Clients")
        if search_c: st.dataframe(client_df[client_df.astype(str).apply(lambda x: x.str.contains(search_c, case=False)).any(axis=1)], use_container_width=True)
        else: st.dataframe(client_df, use_container_width=True)
        
        cl_list = get_clean_list(client_df, "Client Name")
        if cl_list:
            with st.expander("Edit Client"):
                c_edit = st.selectbox("Select", cl_list)
                row = client_df[client_df["Client Name"] == c_edit].iloc[0]
                with st.form("ec"):
                    nm = st.text_input("Name", row["Client Name"])
                    em = st.text_input("Email", row.get("Email",""))
                    ph = st.text_input("Phone", row.get("Phone Number",""))
                    ad = st.text_input("Address", row.get("Address",""))
                    if st.form_submit_button("Update"):
                        if update_client_details(c_edit, {"Client Name": nm, "Email": em, "Phone Number": ph, "Address": ad}): st.success("Updated!"); st.rerun()

    elif menu == "Channel Partner Analytics":
        st.subheader("🤝 Partner Performance")
        if not prod_df.empty and "Channel Partner" in prod_df.columns:
            pc = prod_df["Channel Partner"].value_counts().reset_index()
            pc.columns = ["Partner", "Installations"]
            c1, c2 = st.columns([1, 2])
            with c1: st.dataframe(pc, use_container_width=True, hide_index=True)
            with c2: st.plotly_chart(px.bar(pc, x="Partner", y="Installations", color="Installations", text_auto=True), use_container_width=True)
            
            sel_p = st.selectbox("Drill-Down", sorted(prod_df["Channel Partner"].unique()))
            if sel_p: st.dataframe(prod_df[prod_df["Channel Partner"] == sel_p], use_container_width=True)

    elif menu == "IMPORT/EXPORT DB":
        st.subheader("💾 Backup")
        st.download_button("Download DB", convert_all_to_excel({"Products": prod_df, "Clients": client_df, "Sims": sim_df}), "Backup.xlsx")
        st.divider()
        up = st.file_uploader("Bulk Import", type=['xlsx'])
        if up:
            try:
                nd = pd.read_excel(up)
                st.dataframe(nd.head())
                if st.button("Upload"): 
                    if bulk_append_to_sheet("Products", nd): st.success("Done!"); st.rerun()
            except Exception as e: st.error(str(e))

    elif menu == "Email Logs":
        st.subheader("📨 Email History Log")
        search_term = st.text_input("🔍 Search Logs", placeholder="Subject, Recipient, or Date...")
        
        if not email_df.empty:
            if st.session_state.user_role != "Admin":
                filtered_df = email_df[email_df["Sender"] == st.session_state.user_name]
            else:
                filtered_df = email_df
            
            if search_term:
                filtered_df = filtered_df[filtered_df.astype(str).apply(lambda x: x.str.contains(search_term, case=False)).any(axis=1)]
            
            st.dataframe(filtered_df, use_container_width=True)
        else:
            st.info("No email logs found.")

    # --- ADMIN EXCLUSIVE TABS ---
    elif menu == "🔔 Approvals" and st.session_state.user_role == "Admin":
        st.subheader("🔔 Pending Renewal Requests")
        if not req_df.empty:
            pending = req_df[req_df["Status"] == "Pending"]
            if pending.empty: st.info("No pending requests.")
            else:
                for _, row in pending.iterrows():
                    with st.expander(f"Request from {row['Requested By']} ({row['Request Date']})"):
                        st.write(f"**Devices:** {row['S/N List']}")
                        st.write(f"**New Start:** {row['New Start Date']} | **Duration:** {row['Duration']} Months")
                        c_a, c_r = st.columns(2)
                        if c_a.button("✅ Approve", key=f"app_{row['Request ID']}"):
                            cnt = approve_request(row['Request ID'], row['S/N List'], row['New Start Date'], int(row['Duration']))
                            st.success(f"Approved! {cnt} devices updated."); st.rerun()
                        if c_r.button("❌ Reject", key=f"rej_{row['Request ID']}"):
                            reject_request(row['Request ID'])
                            st.warning("Rejected."); st.rerun()
        else: st.info("No requests found.")

    elif menu == "👤 User Manager" and st.session_state.user_role == "Admin":
        st.subheader("👤 User Manager")
        ws = get_worksheet(SHEET_NAME, "Credentials")
        if ws: st.dataframe(pd.DataFrame(ws.get_all_records()), use_container_width=True)
        st.divider()
        st.markdown("### ➕ Create User")
        with st.form("nu"):
            c1, c2 = st.columns(2)
            u = c1.text_input("Username")
            p = c2.text_input("Password", type="password")
            n = c1.text_input("Name")
            r = c2.selectbox("Role", ["User", "Admin"])
            perms = st.multiselect("Permissions", ALL_OPTS)
            if st.form_submit_button("Create"):
                if create_new_user(u, p, n, r, perms): st.success("Created!"); st.rerun()
                else: st.error("Failed/Exists")

if __name__ == "__main__":
    main()
