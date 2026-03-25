import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V19.5", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border-left: 5px solid #ff4b4b; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        [data-testid="stMetricValue"] { font-size: 2rem; color: #2c3e50; font-weight: 700; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
        p, th, td { font-size: 16px !important; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V19.5")

# ==========================================
# 2. DATA ENGINE
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
        st.session_state['projects_master'] = pd.DataFrame(sh.worksheet('Projects').get_all_records())
        p_m = st.session_state['projects_master']['Project'].unique().tolist() if not st.session_state['projects_master'].empty else []
        p_l = df['Project'].unique().tolist() if not df.empty else []
        st.session_state['projects_list'] = sorted(list(set(p_m + p_l)))
        return df
    except Exception as e:
        st.error(f"⚠️ Load Error: {e}"); return pd.DataFrame(columns=cols)

def safe_save_to_sheet(df_to_save):
    if df_to_save.empty: return False
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = df_to_save.copy()
            for col in ['Start_Date', 'End_Date', 'Revised_End']:
                if col in save_df.columns:
                    save_df[col] = pd.to_datetime(save_df[col], errors='coerce').dt.strftime('%Y-%m-%d').replace('NaT', '')
            save_df = save_df.replace([np.nan, pd.NA], "")
            data_list = save_df.values.tolist()
            ws_logs.batch_clear([f"A2:K{ws_logs.row_count}"])
            ws_logs.update(range_name="A2", values=data_list)
            return True
        except Exception as e:
            st.error(f"Update Error: {e}"); return False
    return False

if 'data' not in st.session_state: load_data()

# ==========================================
# 3. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ AII Control Panel")
    if st.button("🔄 Sync & Refresh Data", use_container_width=True):
        st.cache_data.clear(); load_data(); st.rerun()
    st.divider()
    with st.expander("👤 จัดการทีมงาน"):
        new_name = st.text_input("ชื่อพนักงานใหม่", key="side_add_n")
        if st.button("➕ บันทึกพนักงาน", use_container_width=True):
            if new_name:
                sh = connect_gsheet(); sh.worksheet('Employees').append_row([new_name]); load_data(); st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียนงาน", "📊 แผนผังงาน & สรุปผล"])

# --- TAB 0: ลงทะเบียน ---
with tabs[0]:
    st.subheader("📝 มอบหมายงานใหม่")
    p_opts = st.session_state.get('projects_list', [])
    sel_p_reg = st.selectbox("📁 1. เลือกโปรเจกต์", p_opts, key="main_reg_p")
    df_all = st.session_state.get('data', pd.DataFrame())
    f_mt = df_all[df_all['Project'] == sel_p_reg]['Main_Task'].unique().tolist() if not df_all.empty else []
    
    with st.form("reg_form_v19_5", clear_on_submit=True):
        sel_mt = st.selectbox("📑 2. เลือกงานรอง", ["-- สร้างงานรองใหม่ --"] + f_mt)
        new_mt = st.text_input("✨ หรือพิมพ์ชื่อเฟสใหม่")
        final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        stk = st.text_input("📌 3. ชื่องานย่อย (Sub-task)")
        ems = st.multiselect("👥 5. ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2); ds, de = c1.date_input("วันเริ่ม"), c2.date_input("วันจบ")
        if st.form_submit_button("💾 บันทึกงาน (ต่อท้ายชีต)", use_container_width=True):
            if final_mt and stk and ems:
                sh = connect_gsheet(); ws = sh.worksheet('Logs')
                new_rows = [[e, sel_p_reg, final_mt, stk, "", ds.strftime('%Y-%m-%d'), de.strftime('%Y-%m-%d'), "", 0, "", "⏳ กำลังทำ"] for e in ems]
                ws.append_rows(new_rows); st.success("✅ บันทึกสำเร็จ!"); load_data(); st.rerun()

# --- TAB 1: Gantt Chart & Dashboard ---
with tabs[1]:
    if not df_all.empty:
        sel_g = st.selectbox("📂 เลือกโปรเจกต์ที่ต้องการวิเคราะห์:", p_opts, key="g_view_p")
        df_p = df_all[df_all['Project'] == sel_g].copy().sort_values('Start_Date')
        
        if not df_p.empty:
            # --- 🚀 DASHBOARD SECTION ---
            st.divider()
            col_graph, col_metric = st.columns([1, 1])
            
            # 1. คำนวณ % ตามจริง (Average of Sub-tasks)
            # เราใช้ groupby Sub_Task ก่อนเพื่อไม่ให้จำนวนพนักงานมีผลต่อ % รวม (กรณี 1 งานทำหลายคน)
            sub_task_progress = df_p.groupby('Sub_Task')['Progress'].mean()
            overall_prog = sub_task_progress.mean()
            
            # 2. กราฟวงกลมแสดงความก้าวหน้า
            with col_graph:
                fig_pie = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = overall_prog,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "📊 ความก้าวหน้าโปรเจกต์ (%)", 'font': {'size': 18}},
                    gauge = {
                        'axis': {'range': [None, 100], 'tickwidth': 1},
                        'bar': {'color': "#ff4b4b"},
                        'steps': [
                            {'range': [0, 50], 'color': "#f8d7da"},
                            {'range': [50, 90], 'color': "#fff3cd"},
                            {'range': [90, 100], 'color': "#d4edda"}],
                        'threshold': {
                            'line': {'color': "black", 'width': 4},
                            'thickness': 0.75,
                            'value': 100}}))
                fig_pie.update_layout(height=300, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, use_container_width=True)
            
            # 3. ข้อมูลสรุปรายพนักงานในโปรเจกต์
            with col_metric:
                st.write("👥 **สรุปรายบุคคล (ในโปรเจกต์นี้)**")
                emp_prog = df_p.groupby('Employee')['Progress'].mean().reset_index()
                st.dataframe(emp_prog.style.highlight_max(axis=0, color='#d4edda'), hide_index=True, use_container_width=True)

            st.divider()
            
            # --- GANTT CHART SECTION ---
            df_p['Actual_End'] = df_p['Revised_End'].fillna(df_p['End_Date'])
            fig = px.timeline(df_p, x_start="Start_Date", x_end="Actual_End", y="Sub_Task", 
                              color="Main_Task", text="Employee", template="plotly_white",
                              title=f"📅 แผนผังงาน: {sel_g}")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)
            
            # --- QUICK UPDATE SECTION ---
            st.subheader("⚡ อัปเดตงานย่อย")
            st_opts = df_p['Sub_Task'].unique().tolist()
            sel_stk = st.selectbox("🎯 เลือกงานย่อย", st_opts)
            row_idx = df_all[(df_all['Project'] == sel_g) & (df_all['Sub_Task'] == sel_stk)].index
            if not row_idx.empty:
                curr_p = int(df_all.loc[row_idx[0], 'Progress'])
                with st.container(border=True):
                    c1, c2 = st.columns([1, 2])
                    up_p = c1.slider("%", 0, 100, curr_p)
                    up_i = c2.text_input("Issue", value=str(df_all.loc[row_idx[0], 'Issue']))
                    if st.button("💾 บันทึก", use_container_width=True, type="primary"):
                        df_all.loc[row_idx, 'Progress'] = up_p
                        df_all.loc[row_idx, 'Issue'] = up_i
                        df_all.loc[row_idx, 'Status'] = "✅ เสร็จสมบูรณ์" if up_p == 100 else "⏳ กำลังทำ"
                        if safe_save_to_sheet(df_all):
                            st.success("อัปเดตแล้ว!"); load_data(); st.rerun()
        else:
            st.info("ยังไม่มีข้อมูลงานในโปรเจกต์นี้")