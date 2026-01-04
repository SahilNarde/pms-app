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
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

# --- CONFIGURATION ---
SHEET_NAME = "PMS DB"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
LOGO_FILENAME = "FINAL LOGO.png"

# --- COMPANY DETAILS ---
COMPANY_INFO = {
    "name": "Orcatech Enterprises",
    "address": "Flat No. 102, Mayureshwar Heights, S.No. 24/4,\nJadhavrao Industrial Estate, Nanded City,\nSinhagad Road, Pune 411041",
    "contact": "sales@orcatech.co.in | Mobile: 9325665554",  # <--- UPDATED HERE
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

    # Add Totals
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
        ('GRID', (0, 0), (-1, -5), 1, colors.black), 
        ('LINEBELOW', (0, -4), (-1, -1), 1, colors.grey), 
        ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
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
    elements.append(Paragraph(bank_info, styles['Normal']))
    
    # 5. Professional Footer
    elements.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle('Footer', parent=styles['Italic'], fontSize=9, textColor=colors.darkgrey, alignment=TA_CENTER)
    footer_text = "This is a computer-generated document and does not require a physical signature."
    elements.append(Paragraph(footer_text, footer_style))
    
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
        
        # Ensure safe DataFrames
        if "S/N" not in prod_df.columns: prod_df = pd.DataFrame(columns=["S/N", "End User", "Renewal Date", "Industry Category", "Installation Date", "Activation Date", "Validity (Months)", "Channel Partner"])
        if "Client Name" not in client_df.columns: client_df = pd.DataFrame(columns=["Client Name", "Email"])
        if "SIM Number" not in sim_df.columns: sim_df = pd.DataFrame(columns=["SIM Number", "Status", "Provider"])
    except: st.error("DB Error"); return

    st.sidebar.caption(f"📦 Products: {len(prod_df)}")
    st.sidebar.caption(f"👥 Clients: {len(client_df)}")

    # CONSTANTS
    BASE_PRODUCT_LIST = ["DWLR", "FM", "OCFM", "ARG", "LM", "LC", "Custom"]

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

    # --- RESTRUCTURED SUBSCRIPTION MANAGER ---
    elif menu == "Subscription Manager":
        st.subheader("🔄 Subscription & Quotation Manager")
        
        if prod_df.empty:
            st.info("No product data available.")
        else:
            prod_df['Status_Calc'] = prod_df['Renewal Date'].apply(check_expiry_status)
            exp_df = prod_df[prod_df['Status_Calc'].isin(["Expiring Soon", "Expired"])].copy()
            
            if exp_df.empty:
                st.success("✅ Good news! No devices need renewal.")
            else:
                # --- TABS FOR SINGLE VS BULK ---
                tab_single, tab_bulk = st.tabs(["📱 Individual Device Renewal", "🏢 Bulk / Client Renewal"])
                
                # --- TAB 1: INDIVIDUAL ---
                with tab_single:
                    st.markdown("##### Manage Specific Device")
                    # List format: "S/N | Client | Status"
                    exp_df['Label'] = exp_df['S/N'] + " | " + exp_df['End User'] + " (" + exp_df['Status_Calc'] + ")"
                    selected_label = st.selectbox("Select Device", exp_df['Label'].tolist())
                    
                    selected_sn = selected_label.split(" | ")[0]
                    row = exp_df[exp_df['S/N'] == selected_sn].iloc[0]
                    
                    c_i1, c_i2, c_i3 = st.columns(3)
                    c_i1.info(f"**Product:** {row.get('Product Name')}")
                    c_i2.info(f"**Client:** {row.get('End User')}")
                    c_i3.error(f"**Expires:** {row.get('Renewal Date')}")
                    
                    # 1. Quote
                    with st.expander("📄 Generate Quote", expanded=True):
                        with st.form("single_quote"):
                            sq1, sq2 = st.columns(2)
                            s_rate = sq1.number_input("Amount (INR)", value=2500.0, step=100.0)
                            s_valid = sq2.date_input("Valid Until", date.today() + relativedelta(days=15))
                            if st.form_submit_button("Generate & Preview"):
                                device_list = [{"sn": selected_sn, "product": row.get('Product Name'), "model": row.get('Model', '-'), "renewal": row.get('Renewal Date')}]
                                st.session_state['single_quote'] = {"client": row.get('End User'), "devices": device_list, "rate": s_rate, "valid": s_valid}
                                st.success("Quote Ready! See Email section.")

                    # 2. Email
                    if 'single_quote' in st.session_state:
                        with st.expander("📧 Email Quote", expanded=True):
                            sq_data = st.session_state['single_quote']
                            client_name = sq_data['client']
                            client_email = ""
                            if not client_df.empty:
                                match = client_df[client_df["Client Name"] == client_name]
                                if not match.empty: client_email = match.iloc[0].get("Email", "")
                            
                            se_to = st.text_input("To Email", value=client_email, key="se_to")
                            if st.button("Send Email", key="se_btn"):
                                with st.spinner("Sending..."):
                                    pdf = create_quotation_pdf(client_name, sq_data['devices'], sq_data['rate'], sq_data['valid'])
                                    if send_email_with_attachment(se_to, f"Renewal Quote - {selected_sn}", "Please find quote attached.", pdf, f"Quote_{selected_sn}.pdf"):
                                        st.success("Sent!")
                                        del st.session_state['single_quote']

                    # 3. Update DB
                    with st.expander("📅 Update Renewal Date (Finalize)", expanded=True):
                        with st.form("single_renew"):
                            rn1, rn2 = st.columns(2)
                            new_st = rn1.date_input("New Start Date", date.today())
                            new_dur = rn2.number_input("Months", value=12)
                            if st.form_submit_button("Update Database"):
                                new_end = calculate_renewal(new_st, new_dur)
                                if update_product_subscription(selected_sn, str(new_st), new_dur, str(new_end)):
                                    st.success(f"Updated {selected_sn}!"); st.rerun()

                # --- TAB 2: BULK / CLIENT ---
                with tab_bulk:
                    st.markdown("##### Manage All Devices for a Company")
                    clients_list = get_clean_list(exp_df, "End User")
                    sel_client = st.selectbox("Select Company", clients_list)
                    
                    client_devs = exp_df[exp_df["End User"] == sel_client]
                    st.dataframe(client_devs[["S/N", "Product Name", "Renewal Date", "Status_Calc"]], use_container_width=True)
                    st.info(f"Total Devices: {len(client_devs)}")
                    
                    # 1. Quote
                    with st.expander("📄 Generate Bulk Quote", expanded=True):
                        with st.form("bulk_quote"):
                            bq1, bq2 = st.columns(2)
                            b_rate = bq1.number_input("Rate Per Device (INR)", value=2500.0, step=100.0)
                            b_valid = bq2.date_input("Quote Valid Until", date.today() + relativedelta(days=15))
                            if st.form_submit_button("Generate Bulk Quote"):
                                d_list = []
                                for _, r in client_devs.iterrows():
                                    d_list.append({"sn": r['S/N'], "product": r.get('Product Name'), "model": r.get('Model', '-'), "renewal": r.get('Renewal Date')})
                                st.session_state['bulk_quote'] = {"client": sel_client, "devices": d_list, "rate": b_rate, "valid": b_valid}
                                st.success(f"Quote generated for {len(d_list)} devices.")

                    # 2. Email
                    if 'bulk_quote' in st.session_state:
                        with st.expander("📧 Email Bulk Quote", expanded=True):
                            bq_data = st.session_state['bulk_quote']
                            c_mail = ""
                            if not client_df.empty:
                                m = client_df[client_df["Client Name"] == sel_client]
                                if not m.empty: c_mail = m.iloc[0].get("Email", "")
                            
                            be_to = st.text_input("To Email", value=c_mail, key="be_to")
                            if st.button("Send Bulk Email", key="be_btn"):
                                with st.spinner("Sending..."):
                                    pdf = create_quotation_pdf(sel_client, bq_data['devices'], bq_data['rate'], bq_data['valid'])
                                    if send_email_with_attachment(be_to, f"Bulk Renewal Quote - {sel_client}", f"Please find attached the renewal quote for {len(bq_data['devices'])} devices.", pdf, f"Quote_{sel_client}.pdf"):
                                        st.success("Sent!")
                                        del st.session_state['bulk_quote']

                    # 3. Update DB
                    with st.expander("📅 Bulk Update Renewal (Finalize)", expanded=True):
                        with st.form("bulk_renew"):
                            br1, br2 = st.columns(2)
                            b_start = br1.date_input("New Start Date", date.today())
                            b_dur = br2.number_input("Months", value=12)
                            if st.form_submit_button("Update ALL Devices"):
                                b_end = calculate_renewal(b_start, b_dur)
                                cnt = 0
                                for sn in client_devs['S/N'].tolist():
                                    if update_product_subscription(sn, str(b_start), b_dur, str(b_end)): cnt += 1
                                st.success(f"Successfully updated {cnt} devices!"); st.rerun()

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
