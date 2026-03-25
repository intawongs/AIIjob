import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V18.0", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #ffffff; padding: 20px; border-radius: 12px; border-left: 5px solid #ff4b4b; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        [data-testid="stMetricValue"] { font-size: 2.2rem; color: #2c3e50; font-weight: 700; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.2rem; height: 50px; }
        p, th, td { font-size: 16px !important; font-weight: 500; }
        .status-pill { padding: 4px 10px; border-radius: 15px; font-size: 14px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V18.0")

# ==========================================
# 2. DATA ENGINE (Ironclad System)
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
        
        # ป้องกันคอลัมน์หาย
        for col in cols:
            if col not in df.columns: df[col] = ""
            
        # แปลงวันที่และตัวเลข
        for col in ['Start_Date', 'End_Date', 'Revised_End']:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        df['Progress'] = pd.to_numeric(df['Progress'], errors='coerce').fillna(0)
            
        st.session_state['data'] = df
        st.session_state['employees'] = sh.worksheet('Employees').col_values(1)[1:]
        st.session_state['projects_master'] = pd.DataFrame(sh.worksheet('Projects').get_all_records())
        return df
    except Exception as e:
        st.error(f"⚠️ Load Error: {e}")
        return pd.DataFrame(columns=cols)

def safe_save_to_sheet(df_to_save):
    """เซฟแบบรักษาหัวตาราง โดยการเขียนทับตั้งแต่แถวที่ 2"""
    if df_to_save.empty:
        st.warning("⚠️ ข้อมูลว่างเปล่า ระบบระงับการบันทึกเพื่อความปลอดภัย")
        return False
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = df_to_save.copy().fillna("")
            for col in ['Start_Date', 'End_Date', 'Revised_End']:
                if col in save_df.columns:
                    save_df[col] = pd.to_datetime(save_df[col], errors='coerce').dt.strftime('%Y-%m-%d').replace('NaT', '')
            
            # ล้างเฉพาะข้อมูล (A2 ถึงปลายชีต) รักษา A1 ไว้
            ws_logs.batch_clear([f"A2:K{ws_logs.row_count}"])
            ws_logs.update(range_name="A2", values=save_df.values.tolist())
            return True
        except Exception as e:
            st.error(f"Save Error: {e}")
            return False
    return False

if 'data' not in st.session_state: load_data()

# ==========================================
# 3. SIDEBAR (Management)
# ==========================================
with st.sidebar:
    st.header("⚙️ AII Control Panel")
    if st.button("🔄 Sync & Refresh Data", use_container_width=True):
        st.cache_data.clear(); load_data(); st.rerun()
    st.divider()
    
    with st.expander("👤 พนักงาน & 📂 Baseline"):
        st.subheader("เพิ่มคน")
        ne = st.text_input("ชื่อเล่น")
        if st.button("บันทึกชื่อ"):
            sh = connect_gsheet(); sh.worksheet('Employees').append_row([ne]); load_data(); st.rerun()
        st.write("---")
        st.subheader("เพิ่มโปรเจกต์")
        with st.form("add_p"):
            np = st.text_input("ชื่อโปรเจกต์")
            ps = st.date_input("เริ่ม"); pe = st.date_input("จบ")
            if st.form_submit_button("บันทึกโปรเจกต์"):
                sh = connect_gsheet(); sh.worksheet('Projects').append_row([np, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')])
                load_data(); st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 Gantt Chart", "🏆 ผลงานทีม", "📑 รายงานสรุป", "🛠️ Admin"])

# --- TAB 0: ลงทะเบียน (Append Only) ---
with tabs[0]:
    st.subheader("📝 มอบหมายงานใหม่")
    p_master = st.session_state.get('projects_master', pd.DataFrame())
    p_list = p_master['Project'].tolist() if not p_master.empty else []
    sel_p = st.selectbox("📁 เลือกโปรเจกต์", p_list)
    df_all = st.session_state.get('data', pd.DataFrame())
    f_mt = df_all[df_all['Project'] == sel_p]['Main_Task'].unique().tolist() if not df_all.empty else []

    with st.form("reg_v18", clear_on_submit=True):
        mt_sel = st.selectbox("📑 งานรอง", ["-- สร้างใหม่ --"] + f_mt)
        mt_new = st.text_input("หรือพิมพ์งานรองใหม่")
        final_mt = mt_new if mt_sel == "-- สร้างใหม่ --" else mt_sel
        stk = st.text_input("📌 งานย่อย (Sub-task)")
        ems = st.multiselect("👥 ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2); ds, de = c1.date_input("เริ่ม"), c2.date_input("จบ")
        
        if st.form_submit_button("💾 บันทึกงานใหม่", use_container_width=True):
            if final_mt and stk and ems:
                sh = connect_gsheet(); ws = sh.worksheet('Logs')
                new_data = [[e, sel_p, final_mt, stk, "", ds.strftime('%Y-%m-%d'), de.strftime('%Y-%m-%d'), "", 0, "", "⏳ กำลังทำ"] for e in ems]
                ws.append_rows(new_data)
                st.success("✅ บันทึกสำเร็จ (ต่อท้ายชีตเดิม)"); load_data(); st.rerun()

# --- TAB 1: Gantt Chart ---
with tabs[1]:
    if not df_all.empty:
        sel_g = st.selectbox("ดูความคืบหน้าโปรเจกต์", p_list, key="g_v18")
        df_p = df_all[df_all['Project'] == sel_g].copy()
        if not df_p.empty:
            df_p['Actual_End'] = df_p['Revised_End'].fillna(df_p['End_Date'])
            fig = px.timeline(df_p, x_start="Start_Date", x_end="Actual_End", y="Sub_Task", color="Main_Task", text="Employee", template="plotly_white")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)

# --- TAB 2: ผลงานทีม (Leaderboard - สวยๆ) ---
with tabs[2]:
    st.subheader("🏆 Leaderboard: AII Star Performers")
    if not df_all.empty:
        col1, col2, col3 = st.columns(3)
        total_tasks = len(df_all)
        avg_prog = df_all['Progress'].mean()
        done_tasks = len(df_all[df_all['Progress'] == 100])
        
        col1.metric("📊 งานทั้งหมด", f"{total_tasks} รายการ")
        col2.metric("🎯 ความคืบหน้าเฉลี่ย", f"{avg_prog:.1f}%")
        col3.metric("✅ เสร็จสมบูรณ์", f"{done_tasks} รายการ")
        
        st.write("---")
        ld = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        fig_ld = px.bar(ld, x='Progress', y='Employee', orientation='h', color='Progress', 
                        color_continuous_scale='RdYlGn', text_auto='.1f',
                        title="อันดับพนักงานตาม % ความคืบหน้าเฉลี่ย")
        fig_ld.update_layout(yaxis={'categoryorder':'total ascending'}, height=400)
        st.plotly_chart(fig_ld, use_container_width=True)

# --- TAB 3: รายงานสรุป (Report - สวยๆ) ---
with tabs[3]:
    st.subheader("📑 รายงานสถานะงานละเอียด")
    if not df_all.empty:
        # ระบบค้นหาและกรอง
        c1, c2 = st.columns([2, 1])
        q = c1.text_input("🔍 ค้นหา (ชื่อคน, ชื่อโปรเจกต์, งานรอง)...")
        status_filter = c2.multiselect("กรองสถานะ", df_all['Status'].unique())
        
        df_display = df_all.copy()
        if q:
            df_display = df_display[df_display.apply(lambda row: row.astype(str).str.contains(q, case=False).any(), axis=1)]
        if status_filter:
            df_display = df_display[df_display['Status'].isin(status_filter)]
            
        # ฟังก์ชันใส่สีตาราง
        def highlight_status(val):
            if val == '✅ เสร็จสมบูรณ์': return 'background-color: #d4edda; color: #155724'
            if val == '⏳ กำลังทำ': return 'background-color: #fff3cd; color: #856404'
            return ''

        st.dataframe(df_display.style.applymap(highlight_status, subset=['Status']), use_container_width=True)
        st.download_button("📥 Export CSV", df_display.to_csv(index=False).encode('utf-8-sig'), f"AII_Report_{date.today()}.csv")

# --- TAB 4: Admin (แก้ไขแบบปลอดภัย) ---
with tabs[4]:
    st.subheader("🛠️ แก้ไขข้อมูลดิบ")
    df_adm = st.session_state.get('data', pd.DataFrame()).copy()
    if not df_adm.empty:
        df_adm.insert(0, "ลบรายการ", False)
        edited = st.data_editor(df_adm, hide_index=True, use_container_width=True, 
                               column_config={"ลบรายการ": st.column_config.CheckboxColumn("ลบ?"),
                                              "Revised_End": st.column_config.DateColumn("เลื่อนจบ")})
        if st.button("💾 ยืนยันบันทึกการแก้ไข", type="primary", use_container_width=True):
            final = edited[edited["ลบรายการ"] == False].drop(columns=["ลบรายการ"])
            final.loc[final['Progress'] == 100, 'Status'] = "✅ เสร็จสมบูรณ์"
            if safe_save_to_sheet(final):
                st.success("อัปเดตเรียบร้อย"); load_data(); st.rerun()