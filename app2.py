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

# ค่าคงที่
THAI_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]

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
# 3. DATABASE LOGIC
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

            if df_logs.empty: 
                df_logs = pd.DataFrame(columns=expected_logs)
            else:
                for col in expected_cols: # check columns exist
                    if col not in df_logs.columns: df_logs[col] = None
            
            # บังคับ format วันที่
            if not df_logs.empty:
                df_logs['Start_Date'] = pd.to_datetime(df_logs['Start_Date'], errors='coerce')
                df_logs['End_Date'] = pd.to_datetime(df_logs['End_Date'], errors='coerce')
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)

            st.session_state['projects_master'] = df_projs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects'] = df_projs['Project'].dropna().tolist() if not df_projs.empty else []

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
            save_df['Start_Date'] = save_df['Start_Date'].dt.strftime('%Y-%m-%d')
            save_df['End_Date'] = save_df['End_Date'].dt.strftime('%Y-%m-%d')
            
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
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผัง & Dashboard", "🛠️ อัพเดต", "🏆 ผลงาน", "📑 รายงาน"])

with tabs[0]: # ลงทะเบียน
    with st.form("sub_task_form", clear_on_submit=True):
        p = st.selectbox("เลือกโปรเจกต์", st.session_state['projects'] if st.session_state['projects'] else ["-- ไม่มีข้อมูล --"])
        sub = st.text_input("ชื่องานย่อย")
        emps_multi = st.multiselect("ผู้รับผิดชอบ", st.session_state['employees'])
        c1, c2 = st.columns(2)
        d_start = c1.date_input("วันที่เริ่ม", value=date.today())
        d_end = c2.date_input("วันที่จบ", value=date.today() + timedelta(days=7))
        
        submitted = st.form_submit_button("💾 บันทึกงานย่อย", type="primary", use_container_width=True)
        
        if submitted:
            if sub and emps_multi and p != "-- ไม่มีข้อมูล --":
                latest_logs, _, _ = load_data()
                new_data = []
                for e in emps_multi:
                    new_data.append({
                        'Employee': e, 'Main_Task': p, 'Sub_Task': sub, 
                        'Start_Date': pd.to_datetime(d_start), 
                        'End_Date': pd.to_datetime(d_end), 
                        'Progress': 0, 'Status': '⏳ กำลังดำเนินการ'
                    })
                updated_df = pd.concat([latest_logs, pd.DataFrame(new_data)], ignore_index=True)
                if save_data(updated_df):
                    st.session_state['data'] = updated_df
                    st.toast(f"✅ บันทึกงาน '{sub}' เรียบร้อย!", icon="💾")
                    st.rerun()

with tabs[1]: # แผนผัง & Dashboard
    df_all = st.session_state['data']
    if not df_all.empty and st.session_state['projects']:
        sel_p = st.selectbox("📂 ดูโปรเจกต์:", st.session_state['projects'])
        
        # 1. Dashboard Baseline
        master = st.session_state.get('projects_master', pd.DataFrame())
        if not master.empty and sel_p in master['Project'].values:
            p_info = master[master['Project'] == sel_p].iloc[0]
            p_s, p_e = pd.to_datetime(p_info['Start_Date']), pd.to_datetime(p_info['End_Date'])
            today = pd.Timestamp(date.today())
            
            total_days = (p_e - p_s).days
            passed = (today - p_s).days
            planned_pct = max(0, min(100, (passed / total_days) * 100)) if total_days > 0 else 0
            actual_pct = df_all[df_all['Main_Task'] == sel_p]['Progress'].mean()
            
            c1, c2, c3 = st.columns(3)
            c1.metric("ทำจริง (Actual)", f"{actual_pct:.1f}%", f"{actual_pct-planned_pct:.1f}%")
            c2.metric("แผนงาน (Planned)", f"{planned_pct:.1f}%")
            c3.metric("วันคงเหลือ", f"{(p_e.date() - today.date()).days} วัน")
            st.progress(actual_pct/100)

            # 2. Gantt Chart (Summary + Sub-tasks)
            df_sub = df_all[(df_all['Main_Task'] == sel_p) & (df_all['Employee'].isin(sel_emps_filter))].copy()
            df_sub['Start'], df_sub['End_V'] = df_sub['Start_Date'], df_sub['End_Date'] + pd.Timedelta(days=1)
            df_sub['Type'] = "📌 งานย่อย"

            summary_row = pd.DataFrame([{
                'Sub_Task': f"🎯 ภาพรวม: {sel_p}", 'Employee': 'OVERALL', 
                'Start': p_s, 'End_V': p_e + pd.Timedelta(days=1), 'Progress': actual_pct, 'Type': "🏢 โปรเจกต์หลัก"
            }])

            df_plot = pd.concat([summary_row, df_sub], ignore_index=True)
            fig = px.timeline(df_plot, x_start="Start", x_end="End_V", y="Sub_Task", color="Type", text="Progress", height=450,
                             color_discrete_map={"🏢 โปรเจกต์หลัก": "#333333", "📌 งานย่อย": "#636EFA"})
            fig.update_yaxes(autorange="reversed")
            fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="dot", line_color="red")
            st.plotly_chart(fig, use_container_width=True)

with tabs[2]: # อัปเดต
    st.subheader("🛠️ แก้ไขสถานะงานย่อย")
    st.dataframe(st.session_state['data'][['Sub_Task', 'Employee', 'Progress', 'Main_Task']], use_container_width=True)

with tabs[3]: # ผลงาน
    st.subheader("🏆 อันดับความคืบหน้าพนักงาน")
    df_perf = st.session_state['data']
    if not df_perf.empty:
        sum_df = df_perf.groupby('Employee').agg(Total=('Sub_Task','count'), Avg=('Progress','mean')).reset_index().sort_values('Avg', ascending=False)
        for i, row in sum_df.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([1, 4])
                c1.title("🥇" if i==0 else "🥈" if i==1 else "🥉" if i==2 else f"#{i+1}")
                c2.metric(row['Employee'], f"{row['Avg']:.1f}%", f"จาก {row['Total']} งาน")

with tabs[4]: # รายงาน
    st.subheader("📑 สรุปรายงานรายโปรเจกต์")
    df_rep = st.session_state['data']
    if not df_rep.empty:
        proj_group = df_rep.groupby('Main_Task').agg(Progress=('Progress', 'mean'), Tasks=('Sub_Task', 'count')).reset_index()
        st.table(proj_group)
        if st.button("📥 เตรียมส่งรายงาน"):
            st.toast("เตรียมข้อมูลรายงานเรียบร้อย (ตัวอย่าง)")