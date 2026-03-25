import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, date
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V19.2", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border-left: 5px solid #ff4b4b; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        [data-testid="stMetricValue"] { font-size: 2rem; color: #2c3e50; font-weight: 700; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
        p, th, td { font-size: 16px !important; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V19.2")

# ==========================================
# 2. DATA ENGINE (The Core System)
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
    # 11 คอลัมน์ที่ต้องรักษาไว้ใน Sheet 'Logs'
    cols = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Dependency', 'Start_Date', 'End_Date', 'Revised_End', 'Progress', 'Issue', 'Status']
    sh = connect_gsheet()
    if not sh: return pd.DataFrame(columns=cols)
    try:
        ws_logs = sh.worksheet('Logs')
        data = ws_logs.get_all_records()
        df = pd.DataFrame(data) if data else pd.DataFrame(columns=cols)
        
        # ตรวจสอบคอลัมน์ (ซ่อมถ้าหาย)
        for col in cols:
            if col not in df.columns: df[col] = ""
            
        # จัดการประเภทข้อมูล
        for col in ['Start_Date', 'End_Date', 'Revised_End']:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        df['Progress'] = pd.to_numeric(df['Progress'], errors='coerce').fillna(0)
            
        st.session_state['data'] = df
        st.session_state['employees'] = sh.worksheet('Employees').col_values(1)[1:]
        st.session_state['projects_master'] = pd.DataFrame(sh.worksheet('Projects').get_all_records())
        
        # รวมโปรเจกต์
        p_m = st.session_state['projects_master']['Project'].unique().tolist() if not st.session_state['projects_master'].empty else []
        p_l = df['Project'].unique().tolist() if not df.empty else []
        st.session_state['projects_list'] = sorted(list(set(p_m + p_l)))
        return df
    except Exception as e:
        st.error(f"⚠️ Load Error: {e}"); return pd.DataFrame(columns=cols)

if 'data' not in st.session_state: load_data()

# ==========================================
# 3. SIDEBAR (Sync Only)
# ==========================================
with st.sidebar:
    st.header("⚙️ AII Control Panel")
    if st.button("🔄 Sync & Refresh Data", use_container_width=True):
        st.cache_data.clear(); load_data(); st.rerun()
    st.divider()
    st.info("ระบบ V19.2 เน้นความเสถียรของข้อมูล (2 Tabs)")

# ==========================================
# 4. MAIN INTERFACE (2 Tabs Only)
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียนงาน", "📊 แผนผังงาน (Gantt)"])

# --- TAB 0: ลงทะเบียน (Append Only - ปลอดภัยที่สุด) ---
with tabs[0]:
    st.subheader("📝 มอบหมายงานใหม่")
    p_opts = st.session_state.get('projects_list', [])
    sel_p_reg = st.selectbox("📁 1. เลือกโปรเจกต์", p_opts, key="reg_p_v19")
    df_curr = st.session_state.get('data', pd.DataFrame())
    
    f_mt = df_curr[df_curr['Project'] == sel_p_reg]['Main_Task'].unique().tolist() if not df_curr.empty else []
    
    with st.form("reg_form_v19_2", clear_on_submit=True):
        sel_mt = st.selectbox("📑 2. เลือกงานรอง", ["-- สร้างงานรองใหม่ --"] + f_mt)
        new_mt = st.text_input("✨ หรือพิมพ์ชื่อเฟสใหม่")
        final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        
        stk = st.text_input("📌 3. ชื่องานย่อย (Sub-task)")
        
        # ดึงรายชื่อพนักงานจาก Session State
        emp_list = st.session_state.get('employees', [])
        ems_selected = st.multiselect("👥 5. ผู้รับผิดชอบ", emp_list)
        
        c1, c2 = st.columns(2); ds, de = c1.date_input("วันเริ่ม"), c2.date_input("วันจบ")
        
        if st.form_submit_button("💾 บันทึกงาน (ต่อท้ายชีต)", use_container_width=True):
            if final_mt and stk and ems_selected:
                sh = connect_gsheet()
                ws_logs = sh.worksheet('Logs')
                # 🔥 บันทึกแบบต่อท้าย (รักษาของเดิม 100% ไม่ล้างคอลัมน์)
                new_rows = [[e, sel_p_reg, final_mt, stk, "", ds.strftime('%Y-%m-%d'), de.strftime('%Y-%m-%d'), "", 0, "", "⏳ กำลังทำ"] for e in ems_selected]
                ws_logs.append_rows(new_rows)
                st.success(f"✅ บันทึกสำเร็จ! เพิ่มงาน '{stk}' ต่อท้ายชีตเรียบร้อย")
                load_data(); st.rerun()
            else:
                st.warning("⚠️ กรุณากรอกข้อมูลให้ครบ (งานรอง, งานย่อย, ผู้รับผิดชอบ)")

# --- TAB 1: Gantt Chart ---
with tabs[1]:
    if not df_curr.empty:
        sel_g = st.selectbox("📂 เลือกโปรเจกต์แสดง Gantt:", p_opts, key="g_view_p")
        df_p = df_curr[df_curr['Project'] == sel_g].copy().sort_values('Start_Date')
        
        if not df_p.empty:
            # ใช้ Revised_End ถ้ามี ถ้าไม่มีใช้ End_Date
            df_p['Actual_End'] = df_p['Revised_End'].fillna(df_p['End_Date'])
            
            p_pct = df_p['Progress'].mean(); st.metric(f"🚀 {sel_g} Overall Progress", f"{p_pct:.1f}%")
            
            # วาด Gantt Chart
            fig = px.timeline(df_p, x_start="Start_Date", x_end="Actual_End", y="Sub_Task", 
                              color="Main_Task", text="Employee", template="plotly_white",
                              title=f"Timeline: {sel_g}")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"ยังไม่มีข้อมูลงานในโปรเจกต์ {sel_g}")