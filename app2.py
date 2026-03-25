import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, date
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING (Premium Look)
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V19.0", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border-left: 5px solid #ff4b4b; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        [data-testid="stMetricValue"] { font-size: 2rem; color: #2c3e50; font-weight: 700; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
        p, th, td { font-size: 16px !important; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V19.0")

# ==========================================
# 2. DATA ENGINE (The Iron Guard)
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
    # 11 คอลัมน์ที่ต้องมีใน Sheet 'Logs'
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
            
        # จัดการ Format วันที่และตัวเลข
        for col in ['Start_Date', 'End_Date', 'Revised_End']:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        df['Progress'] = pd.to_numeric(df['Progress'], errors='coerce').fillna(0)
            
        st.session_state['data'] = df
        st.session_state['employees'] = sh.worksheet('Employees').col_values(1)[1:]
        
        # โหลดโปรเจกต์ Master
        df_m = pd.DataFrame(sh.worksheet('Projects').get_all_records())
        st.session_state['projects_master'] = df_m
        
        p_m = df_m['Project'].unique().tolist() if not df_m.empty else []
        p_l = df['Project'].unique().tolist() if not df.empty else []
        st.session_state['projects_list'] = sorted(list(set(p_m + p_l)))
        
        return df
    except Exception as e:
        st.error(f"⚠️ Load Error: {e}"); return pd.DataFrame(columns=cols)

def safe_save_to_sheet(df_to_save):
    """ฟังก์ชันเซฟที่ปลอดภัยที่สุด: กำจัด NaN และรักษาหัวตาราง"""
    if df_to_save.empty:
        st.warning("⚠️ ข้อมูลว่างเปล่า ระบบระงับการบันทึก")
        return False
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = df_to_save.copy()
            
            # 1. แปลงวันที่เป็น String (กัน NaT Error)
            for col in ['Start_Date', 'End_Date', 'Revised_End']:
                if col in save_df.columns:
                    save_df[col] = pd.to_datetime(save_df[col], errors='coerce').dt.strftime('%Y-%m-%d').replace('NaT', '')
            
            # 2. 🔥 กำจัด NaN/None (แก้ปัญหา JSON float Error)
            save_df = save_df.replace([np.nan, pd.NA], "")
            data_list = save_df.values.tolist()
            
            # 3. ล้างเฉพาะแถว 2 ลงไป (รักษาหัวตาราง A1)
            ws_logs.batch_clear([f"A2:K{ws_logs.row_count}"])
            ws_logs.update(range_name="A2", values=data_list)
            return True
        except Exception as e:
            st.error(f"Save Error: {e}"); return False
    return False

if 'data' not in st.session_state: load_data()

# ==========================================
# 3. SIDEBAR (Full Management)
# ==========================================
with st.sidebar:
    st.header("⚙️ AII Control Panel")
    if st.button("🔄 Sync & Refresh Data", use_container_width=True):
        st.cache_data.clear(); load_data(); st.rerun()
    st.divider()
    
    with st.expander("👤 รายชื่อทีมงาน (เพิ่ม/ลบ)"):
        n_e = st.text_input("เพิ่มชื่อพนักงาน")
        if st.button("➕ บันทึกพนักงาน"):
            if n_e:
                sh = connect_gsheet(); sh.worksheet('Employees').append_row([n_e])
                load_data(); st.rerun()
        st.write("---")
        emps = st.session_state.get('employees', [])
        if ems:
            del_e = st.selectbox("เลือกคนที่จะลบ", ems)
            if st.button("🗑️ ลบพนักงาน"):
                sh = connect_gsheet(); ws = sh.worksheet('Employees')
                vals = ws.col_values(1)
                if del_e in vals: ws.delete_rows(vals.index(del_e) + 1); load_data(); st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 Gantt Chart", "🏆 ผลงานทีม", "📑 รายงานสรุป", "🛠️ Admin"])

# --- TAB 0: ลงทะเบียน (Append Only) ---
with tabs[0]:
    st.subheader("📝 มอบหมายงานใหม่")
    p_opts = st.session_state.get('projects_list', [])
    sel_p_reg = st.selectbox("📁 1. เลือกโปรเจกต์", p_opts)
    df_curr = st.session_state.get('data', pd.DataFrame())
    
    f_mt = df_curr[df_curr['Project'] == sel_p_reg]['Main_Task'].unique().tolist() if not df_curr.empty else []
    
    with st.form("reg_form_v19", clear_on_submit=True):
        sel_mt = st.selectbox("📑 2. เลือกงานรอง", ["-- สร้างงานรองใหม่ --"] + f_mt)
        new_mt = st.text_input("✨ หรือพิมพ์ชื่อเฟสใหม่")
        final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        stk = st.text_input("📌 3. ชื่องานย่อย (Sub-task)")
        
        ems = st.multiselect("👥 5. ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2); ds, de = c1.date_input("วันเริ่ม"), c2.date_input("วันจบ")
        
        if st.form_submit_button("💾 บันทึกงาน (ต่อท้าย)", use_container_width=True):
            if final_mt and stk and ems:
                sh = connect_gsheet(); ws = sh.worksheet('Logs')
                # บันทึกแบบต่อท้าย (รักษาของเดิม 100%)
                new_rows = [[e, sel_p_reg, final_mt, stk, "", ds.strftime('%Y-%m-%d'), de.strftime('%Y-%m-%d'), "", 0, "", "⏳ กำลังทำ"] for e in ems]
                ws.append_rows(new_rows)
                st.success("✅ บันทึกสำเร็จ!"); load_data(); st.rerun()

# --- TAB 1: Gantt Chart ---
with tabs[1]:
    if not df_curr.empty:
        sel_g = st.selectbox("เลือกโปรเจกต์แสดง Gantt:", p_opts, key="g_v19")
        df_p = df_curr[df_curr['Project'] == sel_g].copy().sort_values('Start_Date')
        
        if not df_p.empty:
            df_p['Actual_End'] = df_p['Revised_End'].fillna(df_p['End_Date'])
            p_pct = df_p['Progress'].mean(); st.metric(f"🚀 {sel_g} Progress", f"{p_pct:.1f}%")
            
            fig = px.timeline(df_p, x_start="Start_Date", x_end="Actual_End", y="Sub_Task", color="Main_Task", text="Employee", template="plotly_white")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)

# --- TAB 2: ผลงานทีม (Premium Leaderboard) ---
with tabs[2]:
    st.subheader("🏆 Leaderboard")
    if not df_curr.empty:
        col1, col2 = st.columns([1, 2])
        ld = df_curr.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        col1.dataframe(ld.style.highlight_max(subset=['Progress'], color='#d4edda'), hide_index=True)
        col2.plotly_chart(px.bar(ld, x='Progress', y='Employee', orientation='h', color='Progress', color_continuous_scale='RdYlGn'), use_container_width=True)

# --- TAB 3: รายงานสรุป (With Search) ---
with tabs[3]:
    st.subheader("📑 รายงานสถานะงาน")
    q = st.text_input("🔍 ค้นหา (ชื่อคน, โปรเจกต์, งาน)...")
    df_disp = df_curr.copy()
    if q:
        df_disp = df_disp[df_disp.apply(lambda r: r.astype(str).str.contains(q, case=False).any(), axis=1)]
    
    st.dataframe(df_disp.style.applymap(lambda v: 'background-color: #d4edda' if v == '✅ เสร็จสมบูรณ์' else '', subset=['Status']), use_container_width=True)

# --- TAB 4: Admin (Safe Save) ---
with tabs[4]:
    st.subheader("🛠️ แก้ไขข้อมูลดิบ")
    df_raw = st.session_state.get('data', pd.DataFrame()).copy()
    if not df_raw.empty:
        df_raw.insert(0, "เลือก", False)
        edited = st.data_editor(df_raw, hide_index=True, use_container_width=True, 
                               column_config={"เลือก": st.column_config.CheckboxColumn("ลบ?"),
                                              "Revised_End": st.column_config.DateColumn("เลื่อนจบ")})
        c1, c2 = st.columns(2)
        if c1.button("💾 บันทึกการแก้ไข", type="primary", use_container_width=True):
            final = edited[edited["เลือก"] == False].drop(columns=["เลือก"])
            final.loc[final['Progress'] == 100, 'Status'] = "✅ เสร็จสมบูรณ์"
            if safe_save_to_sheet(final):
                st.success("อัปเดตเรียบร้อย"); load_data(); st.rerun()
        if c2.button("🗑️ ยืนยันลบรายการ", use_container_width=True):
            final_rem = edited[edited["เลือก"] == False].drop(columns=["เลือก"])
            if safe_save_to_sheet(final_rem): load_data(); st.rerun()