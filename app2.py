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
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.title("🌌 Project Tracker (AII)")

THAI_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
THAI_COLS = {
    "Employee": "พนักงาน", "Main_Task": "โปรเจกต์", "Sub_Task": "ชื่องาน",
    "Progress": "ความคืบหน้า", "Status": "สถานะ", "End_Date": "กำหนดส่ง"
}

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
    expected_cols = ['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']
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
                df_logs = pd.DataFrame(columns=expected_cols)
            else:
                for col in expected_cols:
                    if col not in df_logs.columns: df_logs[col] = None

            if not df_logs.empty:
                for col in ['Start_Date', 'End_Date']:
                    df_logs[col] = pd.to_datetime(df_logs[col], errors='coerce').dt.date
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)

            # เก็บค่าลง Session State ให้ชัวร์
            st.session_state['projects_master'] = df_projs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects'] = df_projs['Project'].tolist() if not df_projs.empty else []

            return df_logs, st.session_state['employees'], st.session_state['projects']
        except Exception as e:
            return pd.DataFrame(columns=expected_cols), [], []
    return pd.DataFrame(columns=expected_cols), [], []

def save_data(df_to_save=None):
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = df_to_save.copy() if df_to_save is not None else st.session_state['data'].copy()
            save_df = save_df.fillna("") 
            save_df['Start_Date'] = save_df['Start_Date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (date, datetime)) else str(x))
            save_df['End_Date'] = save_df['End_Date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (date, datetime)) else str(x))
            cols = ['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=[cols] + save_df[cols].values.tolist())
        except Exception as e: st.error(f"Save Error: {e}")

# ==========================================
# 4. INITIALIZE
# ==========================================
if 'data' not in st.session_state:
    logs, emps, projs = load_data()
    st.session_state.update({"data": logs, "employees": emps, "projects": projs})

def calculate_status_and_score(df):
    if df.empty: return df
    today = date.today()
    def get_details(row):
        try:
            s, e = row['Start_Date'], row['End_Date']
            if isinstance(s, str) and s: s = datetime.strptime(s, '%Y-%m-%d').date()
            if isinstance(e, str) and e: e = datetime.strptime(e, '%Y-%m-%d').date()
            if not isinstance(s, date) or not isinstance(e, date): return "❓ วันที่ระบุไม่ครบ", 0
            if row['Progress'] == 100: return "✅ เสร็จสิ้น", 100
            elif today < s: return "🔜 ยังไม่ถึงกำหนดเริ่ม", None
            elif today > e: return "🔥 ล่าช้า (Late)", row['Progress']
            else: return "⏳ กำลังดำเนินการ", 100
        except: return "Error", 0
    res = df.apply(get_details, axis=1, result_type='expand')
    df['Status'], df['Score'] = res[0], res[1]
    return df

@st.dialog("📝 จัดการงาน")
def update_task_dialog(index, row_data):
    st.caption(f"{row_data['Sub_Task']} ({row_data['Employee']})")
    new_prog = st.slider("ความคืบหน้า (%)", 0, 100, int(row_data['Progress']))
    new_output = st.text_input("ผลลัพธ์ / ลิงก์", value=str(row_data['Output']))
    current_log = str(row_data['Issue']).replace('nan', '')
    mode = st.radio("Log Book:", ["➕ เพิ่มบันทึก", "✏️ แก้ไขทั้งหมด"], horizontal=True)
    if "เพิ่มบันทึก" in mode:
        if current_log: st.info(current_log)
        new_entry = st.text_area("บันทึกวันนี้:")
    else: full_edit = st.text_area("แก้ไขประวัติ:", value=current_log, height=150)

    c1, c2 = st.columns(2)
    if c1.button("💾 บันทึก", type="primary", use_container_width=True):
        final_log = current_log
        if "เพิ่มบันทึก" in mode and new_entry.strip():
            ts = datetime.now().strftime("%d/%m")
            final_log += f"\n- [{ts}] {new_entry.strip()}"
        elif "แก้ไข" in mode: final_log = full_edit
        st.session_state['data'].at[index, 'Progress'] = new_prog
        st.session_state['data'].at[index, 'Output'] = new_output
        st.session_state['data'].at[index, 'Issue'] = final_log.strip()
        save_data()
        st.toast("✅ บันทึกแล้ว", icon="💾")
        st.rerun()
    if c2.button("ยกเลิก", use_container_width=True): st.rerun()

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

    sel_emps = st.multiselect("กรองพนักงาน (แผนผัง):", st.session_state['employees'], default=st.session_state['employees'])

    with st.expander("👤 จัดการคน"):
        new_emp = st.text_input("ชื่อพนักงานใหม่", key="new_emp_side")
        if st.button("➕ เพิ่มชื่อ"):
            if new_emp:
                sh = connect_gsheet()
                sh.worksheet('Employees').append_row([new_emp])
                st.toast(f"✅ เพิ่ม {new_emp} แล้ว", icon="👤")
                st.rerun()

    with st.expander("📂 จัดการโปรเจกต์ (Baseline)"):
        new_p_name = st.text_input("ชื่อโปรเจกต์ใหม่", key="new_p_side")
        c1, c2 = st.columns(2)
        p_start = c1.date_input("วันเริ่ม")
        p_end = c2.date_input("วันจบ", value=datetime.now() + timedelta(days=30))
        if st.button("➕ บันทึกโปรเจกต์", use_container_width=True):
            if new_p_name:
                sh = connect_gsheet()
                sh.worksheet('Projects').append_row([new_p_name, p_start.strftime('%Y-%m-%d'), p_end.strftime('%Y-%m-%d')])
                st.toast(f"💾 บันทึก {new_p_name} แล้ว", icon="✅")
                st.rerun()

# ==========================================
# 7. MAIN UI
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 ลงทะเบียน", "📊 แผนผัง & Dashboard", "🛠️ อัพเดต", "🏆 ผลงาน", "📑 รายงาน"])

with tab1: # ลงทะเบียนงานย่อย
    # ดึงชื่อโปรเจกต์จาก Master List เสมอ
    p = st.selectbox("เลือกโปรเจกต์", st.session_state['projects'] or ["ไม่มีข้อมูล"], key="p_reg")
    sub = st.text_input("ชื่องานย่อย", key="sub_reg")
    emps_multi = st.multiselect("ผู้รับผิดชอบ", st.session_state['employees'], key="emps_reg")
    c1, c2 = st.columns(2)
    d_start = c1.date_input("วันที่เริ่ม", key="start_reg")
    d_end = c2.date_input("วันที่จบ", key="end_reg")
    if st.button("💾 บันทึกงานย่อย", type="primary", use_container_width=True):
        if sub and emps_multi and p != "ไม่มีข้อมูล":
            latest_logs, _, _ = load_data()
            new_rows = [{'Employee': e, 'Main_Task': p, 'Sub_Task': sub, 'Start_Date': d_start, 'End_Date': d_end, 'Progress': 0, 'Status': "⏳ กำลังดำเนินการ"} for e in emps_multi]
            updated_df = pd.concat([latest_logs, pd.DataFrame(new_rows)], ignore_index=True)
            st.session_state['data'] = calculate_status_and_score(updated_df)
            save_data(df_to_save=st.session_state['data'])
            st.toast(f"✅ บันทึกงาน {sub} เรียบร้อย", icon="💾")
            st.rerun()

with tab2: # Dashboard & Gantt Chart
    # ดึงชื่อโปรเจกต์จาก Master List
    master_projs = st.session_state['projects']
    if master_projs:
        sel_p = st.selectbox("📂 เลือกโปรเจกต์:", master_projs, key="p_dash")
        
        master_df = st.session_state.get('projects_master', pd.DataFrame())
        if not master_df.empty and sel_p in master_df['Project'].values:
            p_info = master_df[master_df['Project'] == sel_p].iloc[0]
            p_s, p_e = pd.to_datetime(p_info['Start_Date']), pd.to_datetime(p_info['End_Date'])
            
            # Dashboard Calculation
            today = date.today()
            total_days = (p_e.date() - p_s.date()).days
            passed = (today - p_s.date()).days
            planned_pct = max(0, min(100, (passed / total_days) * 100)) if total_days > 0 else 0
            
            # Actual Progress จากงานย่อย
            df_all = st.session_state['data']
            actual_pct = df_all[df_all['Main_Task'] == sel_p]['Progress'].mean() if not df_all.empty else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("ทำจริง (Actual)", f"{actual_pct:.1f}%", f"{actual_pct-planned_pct:.1f}%")
            c2.metric("แผนงาน (Planned)", f"{planned_pct:.1f}%")
            c3.metric("วันคงเหลือ", f"{(p_e.date() - today).days} วัน")
            st.progress(actual_pct/100)

            # Gantt Chart
            df_sub = df_all[(df_all['Main_Task'] == sel_p) & (df_all['Employee'].isin(sel_emps))].copy() if not df_all.empty else pd.DataFrame()
            
            # สร้าง Summary Bar จาก Baseline
            summary_row = pd.DataFrame([{
                'Sub_Task': f"🎯 Baseline: {sel_p}", 'Employee': 'OVERALL', 
                'Start': p_s, 'End_V': p_e + pd.Timedelta(days=1), 'Progress': actual_pct, 'Type': "🏢 โปรเจกต์หลัก"
            }])

            if not df_sub.empty:
                df_sub['Start'], df_sub['End_V'] = pd.to_datetime(df_sub['Start_Date']), pd.to_datetime(df_sub['End_Date']) + pd.Timedelta(days=1)
                df_sub['Type'] = "📌 งานย่อย"
                df_plot = pd.concat([summary_row, df_sub], ignore_index=True)
            else:
                df_plot = summary_row

            fig = px.timeline(df_plot, x_start="Start", x_end="End_V", y="Sub_Task", color="Type", text="Progress", height=400,
                             color_discrete_map={"🏢 โปรเจกต์หลัก": "#333333", "📌 งานย่อย": "#636EFA"})
            fig.update_yaxes(autorange="reversed", title="")
            fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="dot", line_color="red")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📭 ยังไม่มีโปรเจกต์ กรุณาเพิ่มที่ Sidebar")

with tab3: # อัพเดต
    df = calculate_status_and_score(st.session_state['data'])
    if not df.empty:
        event = st.dataframe(df[['Sub_Task', 'Main_Task', 'Employee', 'Progress', 'Status']], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True)
        if event.selection.rows:
            idx = event.selection.rows[0]
            if st.button(f"✏️ แก้ไข: {df.iloc[idx]['Sub_Task']}", type="primary", use_container_width=True):
                update_task_dialog(idx, df.iloc[idx])

with tab4: # ผลงาน
    df = st.session_state['data']
    if not df.empty:
        sum_df = df.groupby('Employee').agg(Total=('Sub_Task','count'), Avg=('Progress','mean')).reset_index().sort_values('Avg', ascending=False)
        for i, row in sum_df.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([1, 4])
                c1.title("🥇" if i==0 else "🥈" if i==1 else "🥉" if i==2 else f"#{i+1}")
                c2.metric(row['Employee'], f"{row['Avg']:.1f}% (จาก {row['Total']} งาน)")

with tab5: # รายงาน
    st.header("📑 Monthly Summary")
    st.info("กรุณาใช้ข้อมูลจากหน้า Dashboard เพื่อสรุปผล")