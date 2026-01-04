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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# --- PDF LIBRARIES ---
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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

# --- PDF GENERATOR (PLATYPUS ENGINE) ---
def create_quotation_pdf(client_name, device_list, rate_per_device, valid_until):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()

    # 1. Header & Logo
    # Create a table for the header (Logo Left, Company Info Right)
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
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # 2. Title & Client Info
    elements.append(Paragraph("QUOTATION", styles['Title']))
    elements.append(Spacer(1, 0.2*inch))

    client_info = f"""<b>Bill To:</b><br/>{client_name}<br/><br/>
    <b>Date:</b> {date.today().strftime('%d-%b-%Y')}<br/>
    <b>Valid Until:</b> {valid_until.strftime('%d-%b-%Y')}"""
    elements.append(Paragraph(client_info, styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))

    # 3. Items Table
    # Headers
    data = [['S/N', 'Product / Model', 'Description', 'Amount (INR)']]
    
    subtotal = 0
    for device in device_list:
        desc = f"Subscription Renewal\n(Exp: {device['renewal']})"
        row = [
            device['sn'],
            f"{device['product']}\n{device['model']}",
            desc,
            f"{rate_per_device:,.2f}"
        ]
        data.append(row)
        subtotal += rate_per_device

    # Taxes
    cgst = subtotal * 0.09
    sgst = subtotal * 0.09
    total = subtotal + cgst + sgst

    # Add Totals to Table
    data.append(['', '', 'Subtotal', f"{subtotal:,.2f}"])
    data.append(['', '', 'CGST (9%)', f"{cgst:,.2f}"])
    data.append(['', '', 'SGST (9%)', f"{sgst:,.2f}"])
    data.append(['', '', 'GRAND TOTAL', f"{total:,.2f}"])

    # Table Styling
    table = Table(data, colWidths=[1.5*inch, 2*inch, 2*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -5), 1, colors.black), # Grid for items
        ('LINEBELOW', (0, -4), (-1, -1), 1, colors.grey), # Lines for totals
        ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'), # Bold Grand Total
        ('BACKGROUND', (-2, -1), (-1, -1), colors.whitesmoke),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))

    # 4. Bank Details
    bank_info = f"""<b>Bank Details for Payment:</b><br/>
    Account Name: {COMPANY_INFO['acc_name']}<br/>
    Bank Name: {COMPANY_INFO['bank_name']}<br/>
    Account No: {COMPANY_INFO['acc_no']}<br/>
    IFSC Code: {COMPANY_INFO['ifsc']}<br/>
    Branch: {COMPANY_INFO['branch']}"""
    
    # Draw Bank info in a box
    elements.append(Paragraph(bank_info, styles['Normal']))
    
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

def calculate_renewal(activation_date, months):
    if not activation_date: return None
    try: return (pd.to_datetime(activation_date).date() + relativedelta(months=int(months)))
    except: return None

def check_expiry_status(renewal_date):
    try:
        days = (pd.to_datetime(renewal_date).date() - datetime.now().date()).days
        return "Expired" if days < 0 else ("Expiring Soon" if days <= 30 else "Active")
    except: return "Unknown"

def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False)
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
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
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
        st.info(f"👤 User: **{st.session_state.user_name}**")
        if st.button("🔄 Refresh Data"): load_data.clear(); st.rerun()
        if st.button("🚪 Logout"): st.session_state.logged_in = False; st.rerun()
        st.markdown("---")

    st.title("🏭 Product Management System (Cloud)")
    st.markdown("---")

    try:
        prod_df = load_data("Products")
        client_df = load_data("Clients")
        sim_df = load_data("Sims")
    except: st.error("DB Error"); return

    st.sidebar.caption(f"📦 Products: {len(prod_df)}")
    st.sidebar.caption(f"👥 Clients: {len(client_df)}")

    menu = st.sidebar.radio("Go to:", ["Dashboard", "SIM Manager", "New Dispatch Entry", "Subscription Manager", "Installation List", "Client Master", "Channel Partner Analytics", "IMPORT/EXPORT DB"])

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
            
            # --- GRAPHS ---
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

            # Alerts
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
        with st.form("dispatch_form"):
            c1, c2 = st.columns(2)
            sn = c1.text_input("S/N (Required)")
            prod = c1.selectbox("Product", BASE_PRODUCT_LIST)
            client = c2.text_input("Client Name")
            install_d = c2.date_input("Installation Date")
            if st.form_submit_button("Save Dispatch"):
                if not sn or not client: st.error("Missing Data")
                else:
                    new_prod = {"S/N": sn, "Product Name": prod, "End User": client, "Installation Date": str(install_d), "Renewal Date": str(calculate_renewal(install_d, 12))}
                    if append_to_sheet("Products", new_prod):
                        append_to_sheet("Clients", {"Client Name": client})
                        st.success("Saved!"); st.rerun()

    # --- UPDATED SUBSCRIPTION & QUOTATION MANAGER ---
    elif menu == "Subscription Manager":
        st.subheader("🔄 Subscription & Quotation Manager")
        
        if not prod_df.empty:
            prod_df['Status_Calc'] = prod_df['Renewal Date'].apply(check_expiry_status)
            
            # Filter Expiring/Expired Data
            exp_df = prod_df[prod_df['Status_Calc'].isin(["Expiring Soon", "Expired"])].copy()
            
            if exp_df.empty:
                st.success("✅ No devices need renewal.")
            else:
                # 1. Select Client
                clients_with_expiry = get_clean_list(exp_df, "End User")
                selected_client = st.selectbox("Select Client (Company)", clients_with_expiry)
                
                # 2. Get Devices for Client
                client_devices = exp_df[exp_df["End User"] == selected_client]
                st.info(f"Found {len(client_devices)} expiring devices for **{selected_client}**")
                st.dataframe(client_devices[["S/N", "Product Name", "Model", "Renewal Date", "Status_Calc"]], use_container_width=True)
                
                st.divider()
                
                # 3. Quotation Generator
                st.markdown("### 📄 Create Quotation")
                with st.form("quote_gen_form"):
                    c_q1, c_q2 = st.columns(2)
                    rate_per_device = c_q1.number_input("Subscription Rate Per Device (INR)", min_value=0.0, value=2500.0, step=100.0)
                    valid_until = c_q2.date_input("Quotation Valid Until", value=date.today() + relativedelta(days=15))
                    
                    if st.form_submit_button("📜 Generate Quotation & Preview"):
                        # Prepare data for PDF
                        device_list = []
                        for _, row in client_devices.iterrows():
                            device_list.append({
                                "sn": row['S/N'],
                                "product": row.get('Product Name', 'Device'),
                                "model": row.get('Model', ''),
                                "renewal": row.get('Renewal Date', '')
                            })
                        
                        st.session_state['quote_data'] = {
                            "client": selected_client,
                            "devices": device_list,
                            "rate": rate_per_device,
                            "valid": valid_until
                        }
                        st.success("Quotation Generated! Review below.")

                # 4. Review & Send
                if 'quote_data' in st.session_state:
                    q = st.session_state['quote_data']
                    total_amt = q['rate'] * len(q['devices']) * 1.18 # Rough calc for preview
                    
                    st.markdown("#### 📧 Email to Client")
                    c_e1, c_e2 = st.columns(2)
                    
                    # Try fetch email
                    client_email = ""
                    if not client_df.empty:
                        match = client_df[client_df["Client Name"] == selected_client]
                        if not match.empty: client_email = match.iloc[0].get("Email", "")
                    
                    email_to = c_e1.text_input("Recipient Email", value=client_email)
                    email_sub = c_e2.text_input("Subject", value=f"Quotation for Subscription Renewal - {selected_client}")
                    email_body = st.text_area("Message", value=f"Dear {selected_client},\n\nPlease find attached the quotation for the subscription renewal of your {len(q['devices'])} devices.\n\nKindly process the payment to ensure uninterrupted services.\n\nRegards,\nOrcatech Enterprises")
                    
                    if st.button("📨 Send Quotation Now", type="primary"):
                        if not email_to: st.error("Email required!")
                        elif "email" not in st.secrets: st.error("Secrets not configured!")
                        else:
                            with st.spinner("Generating PDF and Sending..."):
                                pdf_buffer = create_quotation_pdf(q['client'], q['devices'], q['rate'], q['valid'])
                                if send_email_with_attachment(email_to, email_sub, email_body, pdf_buffer, f"Quote_{selected_client}.pdf"):
                                    st.success(f"Quotation sent successfully to {email_to}!")
                                    del st.session_state['quote_data'] # Reset

                st.divider()
                st.markdown("### 📅 Bulk Renewal (After Payment)")
                with st.expander("Update All These Devices"):
                    with st.form("bulk_renew_form"):
                        new_start = st.date_input("New Start Date", date.today())
                        months = st.number_input("Months", value=12)
                        if st.form_submit_button("✅ Renew All Listed Devices"):
                            new_end = calculate_renewal(new_start, months)
                            success_count = 0
                            for sn in client_devices['S/N'].tolist():
                                if update_product_subscription(sn, str(new_start), months, str(new_end)):
                                    success_count += 1
                            st.success(f"Updated {success_count} devices successfully!")
                            st.rerun()

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
            c_edit = st.selectbox("Edit Client", clients)
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
        st.subheader("🤝 Partner Stats")
        if not prod_df.empty and "Channel Partner" in prod_df.columns:
            Stats = prod_df["Channel Partner"].value_counts().reset_index()
            Stats.columns = ["Partner", "Count"]
            st.plotly_chart(px.bar(Stats, x="Partner", y="Count"), use_container_width=True)

    elif menu == "IMPORT/EXPORT DB":
        st.subheader("💾 Backup")
        st.download_button("Download Data", convert_df_to_excel(prod_df), "Backup.xlsx")

if __name__ == "__main__":
    main()

