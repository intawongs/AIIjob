import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, date
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V19.3", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border-left: 5px solid #ff4b4b; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        [data-testid="stMetricValue"] { font-size: 2rem; color: #2c3e50; font-weight: 700; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
        p, th, td { font-size: 16px !important; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V19.3")

# ==========================================
# 2. DATA ENGINE (The Iron Core)
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
        st.error(f"❌ Connection Error: {e}")
        return None

def load_data():
    cols = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Dependency', 'Start_Date', 'End_Date', 'Revised_End', 'Progress', 'Issue', 'Status']
    sh = connect_gsheet()
    if not sh: return pd.DataFrame(columns=cols)
    try:
        ws_logs = sh.worksheet('Logs')
        data = ws_logs.get_all_records()
        df = pd.DataFrame(data) if data else pd.DataFrame(columns=cols)
        
        for col in cols:
            if col not in df.columns: df[col] = ""
            
        for col in ['Start_Date', 'End_Date', 'Revised_End']:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        df['Progress'] = pd.to_numeric(df['Progress'], errors='coerce').fillna(0)
            
        st.session_state['data'] = df
        st.session_state['employees'] = sh.worksheet('Employees').col_values(1)[1:]
        
        df_m = pd.DataFrame(sh.worksheet('Projects').get_all_records())
        st.session_state['projects_master'] = df_m
        
        p_m = df_m['Project'].unique().tolist() if not df_m.empty else []
        p_l = df['Project'].unique().tolist() if not df.empty else []
        st.session_state['projects_list'] = sorted(list(set(p_m + p_l)))
        return df
    except Exception as e:
        st.error(f"⚠️ Load Error: {e}"); return pd.DataFrame(columns=cols)

if 'data' not in st.session_state: load_data()

# ==========================================
# 3. SIDEBAR (Full Management)
# ==========================================
with st.sidebar:
    st.header("⚙️ AII Control Panel")
    if st.button("🔄 Sync & Refresh Data", use_container_width=True):
        st.cache_data.clear(); load_data(); st.rerun()
    st.divider()
    
    # --- จัดการพนักงาน ---
    with st.expander("👤 จัดการทีมงาน"):
        new_name = st.text_input("ชื่อพนักงานใหม่", key="side_add_n")
        if st.button("➕ บันทึกพนักงาน", use_container_width=True):
            if new_name:
                sh = connect_gsheet(); sh.worksheet('Employees').append_row([new_name])
                st.success(f"เพิ่ม {new_name} แล้ว"); load_data(); st.rerun()
        st.write("---")
        emp_list = st.session_state.get('employees', [])
        if emp_list:
            to_del = st.selectbox("เลือกคนที่จะลบ", emp_list, key="side_del_n")
            if st.button("🗑️ ลบพนักงาน", use_container_width=True):
                sh = connect_gsheet(); ws = sh.worksheet('Employees')
                vals = ws.col_values(1)
                if to_del in vals:
                    ws.delete_rows(vals.index(to_del) + 1)
                    st.warning(f"ลบ {to_del} แล้ว"); load_data(); st.rerun()

    # --- จัดการโปรเจกต์ Baseline ---
    with st.expander("📂 จัดการ Baseline โปรเจกต์"):
        with st.form("side_add_p_form"):
            np = st.text_input("ชื่อโปรเจกต์ใหม่")
            c1, c2 = st.columns(2); ps = c1.date_input("เริ่ม"); pe = c2.date_input("จบ")
            if st.form_submit_button("➕ บันทึก Baseline"):
                if np:
                    sh = connect_gsheet(); sh.worksheet('Projects').append_row([np, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')])
                    st.success(f"บันทึก {np} แล้ว"); load_data(); st.rerun()
        st.write("---")
        m_projs = st.session_state.get('projects_master', pd.DataFrame())
        if not m_projs.empty:
            p_to_del = st.selectbox("เลือกโปรเจกต์ที่จะลบ", m_projs['Project'].tolist(), key="side_del_p")
            if st.button("🗑️ ลบ Baseline นี้", use_container_width=True):
                sh = connect_gsheet(); ws = sh.worksheet('Projects')
                all_p = ws.col_values(1)
                if p_to_del in all_p:
                    ws.delete_rows(all_p.index(p_to_del) + 1)
                    st.warning(f"ลบโปรเจกต์ {p_to_del} แล้ว"); load_data(); st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียนงาน", "📊 แผนผังงาน (Gantt)"])

# --- TAB 0: ลงทะเบียน (Append Mode - ปลอดภัยที่สุด) ---
with tabs[0]:
    st.subheader("📝 มอบหมายงานใหม่")
    p_opts = st.session_state.get('projects_list', [])
    sel_p_reg = st.selectbox("📁 1. เลือกโปรเจกต์", p_opts, key="main_reg_p")
    df_curr = st.session_state.get('data', pd.DataFrame())
    
    f_mt = df_curr[df_curr['Project'] == sel_p_reg]['Main_Task'].unique().tolist() if not df_curr.empty else []
    
    with st.form("reg_form_v19_3", clear_on_submit=True):
        sel_mt = st.selectbox("📑 2. เลือกงานรอง", ["-- สร้างงานรองใหม่ --"] + f_mt)
        new_mt = st.text_input("✨ หรือพิมพ์ชื่อเฟสใหม่")
        final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        
        stk = st.text_input("📌 3. ชื่องานย่อย (Sub-task)")
        
        # ดึงรายชื่อพนักงานจาก Session
        ems = st.multiselect("👥 5. ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2); ds, de = c1.date_input("วันเริ่ม"), c2.date_input("วันจบ")
        
        if st.form_submit_button("💾 บันทึกงาน (ต่อท้ายชีต)", use_container_width=True):
            if final_mt and stk and ems:
                sh = connect_gsheet(); ws = sh.worksheet('Logs')
                # บันทึกแบบต่อท้าย (รักษาหัวตาราง 100%)
                new_rows = [[e, sel_p_reg, final_mt, stk, "", ds.strftime('%Y-%m-%d'), de.strftime('%Y-%m-%d'), "", 0, "", "⏳ กำลังทำ"] for e in ems]
                ws.append_rows(new_rows)
                st.success(f"✅ บันทึกสำเร็จ! เพิ่มงาน '{stk}' ต่อท้ายชีตเรียบร้อย")
                load_data(); st.rerun()

# --- TAB 1: Gantt Chart ---
with tabs[1]:
    if not df_curr.empty:
        sel_g = st.selectbox("📂 เลือกโปรเจกต์แสดง Gantt:", p_opts, key="g_view_p_v19")
        df_p = df_curr[df_curr['Project'] == sel_g].copy().sort_values('Start_Date')
        
        if not df_p.empty:
            df_p['Actual_End'] = df_p['Revised_End'].fillna(df_p['End_Date'])
            p_pct = df_p['Progress'].mean(); st.metric(f"🚀 {sel_g} Progress", f"{p_pct:.1f}%")
            
            fig = px.timeline(df_p, x_start="Start_Date", x_end="Actual_End", y="Sub_Task", 
                              color="Main_Task", text="Employee", template="plotly_white")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)