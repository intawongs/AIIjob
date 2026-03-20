import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(page_title="ระบบติดตามงาน AII", layout="wide", initial_sidebar_state="auto")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        button[data-baseweb="tab"] { border-radius: 5px; margin: 0 2px; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 Project Tracker (AII)")

# ==========================================
# 2. CONNECT GOOGLE SHEETS
# ==========================================
def connect_gsheet():
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "\\n" in creds_dict["private_key"]:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            client = gspread.service_account_from_dict(creds_dict)
        else:
            client = gspread.service_account(filename='credentials.json')
        return client.open("Chronos_Data") 
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

# ==========================================
# 3. DATABASE LOGIC (Load & Save)
# ==========================================
def load_data():
    expected_logs = ['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            ws_emps = sh.worksheet('Employees')
            ws_projs = sh.worksheet('Projects')

            df_logs = pd.DataFrame(ws_logs.get_all_records())
            df_projs = pd.DataFrame(ws_projs.get_all_records())
            df_emps = pd.DataFrame(ws_emps.get_all_records())

            if df_logs.empty: df_logs = pd.DataFrame(columns=expected_logs)
            else:
                for col in expected_logs:
                    if col not in df_logs.columns: df_logs[col] = None
            
            # จัดการวันที่
            if not df_logs.empty:
                for col in ['Start_Date', 'End_Date']:
                    df_logs[col] = pd.to_datetime(df_logs[col], errors='coerce').dt.date
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)

            # อัปเดต Session State
            st.session_state['projects_master'] = df_projs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects'] = df_projs['Project'].dropna().tolist() if not df_projs.empty and 'Project' in df_projs.columns else []

            return df_logs, st.session_state['employees'], st.session_state['projects']
        except Exception as e:
            return pd.DataFrame(columns=expected_logs), [], []
    return pd.DataFrame(), [], []

def save_data(df_to_save):
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = df_to_save.copy().fillna("")
            save_df['Start_Date'] = save_df['Start_Date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (date, datetime)) else str(x))
            save_df['End_Date'] = save_df['End_Date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (date, datetime)) else str(x))
            cols = ['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=[cols] + save_df[cols].values.tolist())
            return True
        except Exception as e:
            st.error(f"Save Error: {e}")
            return False

# ==========================================
# 4. INITIALIZE
# ==========================================
if 'data' not in st.session_state:
    logs, emps, projs = load_data()
    st.session_state.update({"data": logs, "employees": emps, "projects": projs})

# ==========================================
# 6. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    if st.button("🔄 รีเฟรชข้อมูล", use_container_width=True):
        st.cache_data.clear()
        logs, emps, projs = load_data()
        st.session_state.update({"data": logs, "employees": emps, "projects": projs})
        st.rerun()

    sel_emps_filter = st.multiselect("กรองพนักงาน (แผนผัง):", st.session_state['employees'], default=st.session_state['employees'])

    with st.expander("📂 จัดการโปรเจกต์ (Baseline)"):
        new_p_name = st.text_input("ชื่อโปรเจกต์หลัก", key="new_p_side")
        c1, c2 = st.columns(2)
        p_start = c1.date_input("วันเริ่ม")
        p_end = c2.date_input("วันจบ", value=date.today() + timedelta(days=30))
        if st.button("➕ บันทึกโปรเจกต์", use_container_width=True):
            if new_p_name:
                sh = connect_gsheet()
                sh.worksheet('Projects').append_row([new_p_name, p_start.strftime('%Y-%m-%d'), p_end.strftime('%Y-%m-%d')])
                st.toast(f"💾 บันทึกโปรเจกต์ {new_p_name} แล้ว", icon="✅")
                st.rerun()

# ==========================================
# 7. MAIN UI
# ==========================================
tab1, tab2, tab3 = st.tabs(["📝 ลงทะเบียน", "📊 แผนผัง & Dashboard", "🛠️ อัปเดต"])

with tab1: # ลงทะเบียนงานย่อย
    # ดึงรายชื่อโปรเจกต์
    p_opt = st.session_state['projects']
    
    with st.form("sub_task_form", clear_on_submit=True): # ใช้ Form เพื่อให้ล้างค่าได้ง่าย
        p = st.selectbox("เลือกโปรเจกต์", p_opt if p_opt else ["-- ไม่มีข้อมูล --"])
        sub = st.text_input("ชื่องานย่อย")
        emps_multi = st.multiselect("ผู้รับผิดชอบ", st.session_state['employees'])
        c1, c2 = st.columns(2)
        d_start = c1.date_input("วันที่เริ่ม", value=date.today())
        d_end = c2.date_input("วันที่จบ", value=date.today() + timedelta(days=7))
        
        submitted = st.form_submit_button("💾 บันทึกงานย่อย", type="primary", use_container_width=True)
        
        if submitted:
            if sub and emps_multi and p != "-- ไม่มีข้อมูล --":
                # เตรียมข้อมูลใหม่
                new_rows = []
                for e in emps_multi:
                    new_rows.append({
                        'Employee': e, 'Main_Task': p, 'Sub_Task': sub, 
                        'Start_Date': d_start, 'End_Date': d_end, 
                        'Progress': 0, 'Status': '⏳ กำลังดำเนินการ'
                    })
                
                # โหลดข้อมูลล่าสุดมาต่อท้ายเพื่อป้องกันข้อมูลหาย
                latest_logs, _, _ = load_data()
                updated_df = pd.concat([latest_logs, pd.DataFrame(new_rows)], ignore_index=True)
                
                # บันทึก
                if save_data(updated_df):
                    st.session_state['data'] = updated_df
                    st.toast(f"✅ บันทึกงาน '{sub}' เรียบร้อยแล้ว!", icon="💾")
                    st.rerun() # รีเฟรชหน้าเพื่อล้างค่าและแสดงผลใหม่
            else:
                st.warning("⚠️ กรุณากรอกข้อมูลให้ครบถ้วน")

with tab2: # แผนผัง & Dashboard
    df_all = st.session_state['data']
    if not df_all.empty and st.session_state['projects']:
        sel_p = st.selectbox("📂 ดูภาพรวมโปรเจกต์:", st.session_state['projects'])
        
        # กรองข้อมูลงานย่อย
        df_plot = df_all[(df_all['Main_Task'] == sel_p) & (df_all['Employee'].isin(sel_emps_filter))].copy()
        
        if not df_plot.empty:
            df_plot['S'], df_plot['E'] = pd.to_datetime(df_plot['Start_Date']), pd.to_datetime(df_plot['End_Date']) + pd.Timedelta(days=1)
            fig = px.timeline(df_plot, x_start="S", x_end="E", y="Sub_Task", color="Employee", text="Progress")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📭 ยังไม่มีข้อมูลงานย่อย")

with tab3: # อัปเดตงาน
    st.write("เลือกงานจากตารางเพื่ออัปเดต")
    st.dataframe(st.session_state['data'][['Sub_Task', 'Employee', 'Progress']], use_container_width=True)