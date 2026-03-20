import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker - 3 Layers", layout="wide", initial_sidebar_state="auto")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        button[data-baseweb="tab"] { border-radius: 5px; margin: 0 2px; }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Tracker (3 Layers Edition)")

# ==========================================
# 2. CONNECTION & DATA LOGIC
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
    expected_logs = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Progress', 'Issue']
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            ws_emps = sh.worksheet('Employees')
            ws_projs = sh.worksheet('Projects')

            df_logs = pd.DataFrame(ws_logs.get_all_records())
            df_projs = pd.DataFrame(ws_projs.get_all_records())
            df_emps = pd.DataFrame(ws_emps.get_all_records())

            # 🛠️ Defensive: สร้างคอลัมน์ถ้าหาไม่เจอ ป้องกัน KeyError
            for col in expected_logs:
                if col not in df_logs.columns: df_logs[col] = ""
            
            if not df_logs.empty:
                df_logs['Start_Date'] = pd.to_datetime(df_logs['Start_Date'], errors='coerce')
                df_logs['End_Date'] = pd.to_datetime(df_logs['End_Date'], errors='coerce')
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)
                df_logs['Issue'] = df_logs['Issue'].astype(str).replace('nan', '')

            st.session_state['projects_master'] = df_projs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects_list'] = df_projs['Project'].dropna().unique().tolist() if not df_projs.empty else []

            return df_logs, st.session_state['employees'], st.session_state['projects_list']
        except Exception as e:
            st.error(f"Load Error: {e}")
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
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=[save_df.columns.values.tolist()] + save_df.values.tolist())
            return True
        except: return False

# ==========================================
# 3. DIALOGS
# ==========================================
@st.dialog("👤 ทีมงาน & บันทึก")
def show_task_info(task_name, main_task, project_name):
    df = st.session_state['data']
    team = df[(df['Project'] == project_name) & (df['Main_Task'] == main_task) & (df['Sub_Task'] == task_name)]
    st.subheader(f"📌 {task_name}")
    st.divider()
    for _, row in team.iterrows():
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            c1.markdown("### 👤")
            c2.markdown(f"**{row['Employee']}**")
            c2.progress(int(row['Progress'])/100)
            c2.caption(f"Progress: {int(row['Progress'])}%")
            if row['Issue']: st.info(f"📝 {row['Issue']}")

@st.dialog("📝 อัปเดตงานยกทีม")
def update_task_dialog(index, row_data):
    df = st.session_state['data']
    task_name, main_task, project = row_data['Sub_Task'], row_data['Main_Task'], row_data['Project']
    team = df[(df['Project'] == project) & (df['Main_Task'] == main_task) & (df['Sub_Task'] == task_name)]['Employee'].unique().tolist()
    
    st.markdown(f"🏢 **{project}** > 📑 **{main_task}**")
    st.subheader(f"📌 {task_name}")
    new_prog = st.slider("ความคืบหน้า (%)", 0, 100, int(row_data['Progress']))
    new_issue = st.text_area("บันทึกเพิ่มเติม", value=str(row_data['Issue']))
    sync_all = st.checkbox("🔄 อัปเดตทุกคนในกลุ่มงานนี้", value=True)
    
    if st.button("💾 บันทึก", type="primary", use_container_width=True):
        if sync_all:
            mask = (df['Project'] == project) & (df['Main_Task'] == main_task) & (df['Sub_Task'] == task_name)
            df.loc[mask, 'Progress'] = new_prog
            df.loc[mask, 'Issue'] = new_issue
        else:
            df.at[index, 'Progress'] = new_prog
            df.at[index, 'Issue'] = new_issue
        if save_data(df):
            st.toast("✅ อัปเดตสำเร็จ!"); st.rerun()

# ==========================================
# 4. INITIALIZE
# ==========================================
if 'data' not in st.session_state:
    logs, emps, projs = load_data()
    st.session_state.update({"data": logs, "employees": emps, "projects_list": projs})

# ==========================================
# 5. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ ตั้งค่าระบบ")
    if st.button("🔄 รีเฟรชข้อมูล", use_container_width=True):
        st.cache_data.clear()
        logs, emps, projs = load_data()
        st.session_state.update({"data": logs, "employees": emps, "projects_list": projs})
        st.rerun()

    sel_emps_filter = st.multiselect("กรองพนักงาน:", st.session_state['employees'], default=st.session_state['employees'])

    with st.expander("👤 จัดการรายชื่อพนักงาน"):
        new_emp = st.text_input("ชื่อพนักงานใหม่")
        if st.button("➕ เพิ่มชื่อ", use_container_width=True):
            if new_emp:
                sh = connect_gsheet()
                sh.worksheet('Employees').append_row([new_emp])
                st.toast("เพิ่มชื่อสำเร็จ"); st.rerun()

    with st.expander("📂 เพิ่มโปรเจกต์ใหม่ (Baseline)"):
        new_p = st.text_input("ชื่อโปรเจกต์")
        c1, c2 = st.columns(2)
        ps, pe = c1.date_input("เริ่ม"), c2.date_input("จบ", value=date.today()+timedelta(days=30))
        if st.button("➕ บันทึกโปรเจกต์", use_container_width=True):
            if new_p:
                sh = connect_gsheet()
                sh.worksheet('Projects').append_row([new_p, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')])
                st.toast("บันทึกโปรเจกต์สำเร็จ"); st.rerun()

# ==========================================
# 6. MAIN UI
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผัง 3 ระดับ", "🛠️ อัปเดต", "🏆 ผลงาน", "📑 รายงาน"])

with tabs[0]: # ลงทะเบียน 3 ระดับ
    with st.form("reg_form_3l", clear_on_submit=True):
        p = st.selectbox("1. เลือกโปรเจกต์ (Project)", st.session_state['projects_list'])
        mt = st.text_input("2. งานรอง/เฟส (Main Task)")
        stk = st.text_input("3. งานย่อย (Sub-task)")
        emps_multi = st.multiselect("ผู้รับผิดชอบ", st.session_state['employees'])
        c1, c2 = st.columns(2)
        d_s, d_e = c1.date_input("เริ่มงาน"), c2.date_input("จบงาน")
        if st.form_submit_button("💾 บันทึกงาน", use_container_width=True):
            if p and mt and stk and emps_multi:
                latest, _, _ = load_data()
                new_data = [{'Employee': e, 'Project': p, 'Main_Task': mt, 'Sub_Task': stk, 'Start_Date': pd.to_datetime(d_s), 'End_Date': pd.to_datetime(d_e), 'Progress': 0} for e in emps_multi]
                updated = pd.concat([latest, pd.DataFrame(new_data)], ignore_index=True)
                if save_data(updated):
                    st.session_state['data'] = updated
                    st.toast("✅ บันทึกสำเร็จ"); st.rerun()

with tabs[1]: # แผนผัง 3 ระดับ
    df_all = st.session_state['data']
    if not df_all.empty and st.session_state['projects_list']:
        sel_p = st.selectbox("📂 เลือกโปรเจกต์ดูแผนผัง:", st.session_state['projects_list'], key="dash_p_3l")
        master = st.session_state.get('projects_master', pd.DataFrame())
        
        if not master.empty and sel_p in master['Project'].values:
            p_info = master[master['Project'] == sel_p].iloc[0]
            p_s, p_e = pd.to_datetime(p_info['Start_Date']), pd.to_datetime(p_info['End_Date']) + pd.Timedelta(days=1)
            
            df_proj = df_all[df_all['Project'] == sel_p].copy()
            actual_p_pct = df_proj['Progress'].mean()
            st.metric(f"📊 Overall Progress: {sel_p}", f"{actual_p_pct:.1f}%")

            plot_data = []
            # Level 1: Project
            label_p = f"🏢 {sel_p}"
            plot_data.append({'Task': label_p, 'Start': p_s, 'End': p_e, 'Type': 'P_Planned', 'Label': '', 'Sort_Key': pd.Timestamp.min})
            p_act_end = p_s + ((p_e - p_s) * (actual_p_pct / 100))
            plot_data.append({'Task': label_p, 'Start': p_s, 'End': p_act_end, 'Type': 'P_Actual', 'Label': f"{int(actual_p_pct)}%", 'Sort_Key': pd.Timestamp.min})

            # Level 2 & 3
            df_mt = df_proj.groupby('Main_Task').agg({'Start_Date': 'min', 'End_Date': 'max', 'Progress': 'mean'}).reset_index().sort_values('Start_Date')
            for _, row in df_mt.iterrows():
                ms, me = row['Start_Date'], row['End_Date'] + pd.Timedelta(days=1)
                mt_label = f"📑 {row['Main_Task']}"
                plot_data.append({'Task': mt_label, 'Start': ms, 'End': me, 'Type': 'M_Planned', 'Label': '', 'Sort_Key': ms})
                m_act_end = ms + ((me - ms) * (row['Progress'] / 100))
                plot_data.append({'Task': mt_label, 'Start': ms, 'End': m_act_end, 'Type': 'M_Actual', 'Label': f"{int(row['Progress'])}%", 'Sort_Key': ms})

                df_stk = df_proj[df_proj['Main_Task'] == row['Main_Task']].groupby('Sub_Task').agg({'Start_Date': 'min', 'End_Date': 'max', 'Progress': 'mean'}).reset_index().sort_values('Start_Date')
                for _, srow in df_stk.iterrows():
                    ss, se = srow['Start_Date'], srow['End_Date'] + pd.Timedelta(days=1)
                    st_label = f"   └ {srow['Sub_Task']}"
                    plot_data.append({'Task': st_label, 'Start': ss, 'End': se, 'Type': 'S_Planned', 'Label': '', 'Sort_Key': ss})
                    s_act_end = ss + ((se - ss) * (srow['Progress'] / 100))
                    plot_data.append({'Task': st_label, 'Start': ss, 'End': s_act_end, 'Type': 'S_Actual', 'Label': f"{int(srow['Progress'])}%", 'Sort_Key': ss})

            df_p = pd.DataFrame(plot_data)
            fig = px.timeline(df_p, x_start="Start", x_end="End", y="Task", color="Type", text="Label", height=600,
                             color_discrete_map={
                                 "P_Planned": "#E5E7E9", "P_Actual": "#2C3E50",
                                 "M_Planned": "#D6EAF8", "M_Actual": "#2E86C1",
                                 "S_Planned": "#D4EFDF", "S_Actual": "#28B463"
                             })
            fig.update_yaxes(categoryorder="array", categoryarray=df_p['Task'].unique()[::-1], title="")
            fig.update_traces(textfont=dict(size=14, color="white", family="Arial Black"), textposition='inside')
            # Set Widths
            fig.update_traces(patch={"width": 0.85}, selector={"name": "P_Planned"})
            fig.update_traces(patch={"width": 0.85}, selector={"name": "P_Actual"})
            fig.update_traces(patch={"width": 0.60}, selector={"name": "M_Planned"})
            fig.update_traces(patch={"width": 0.60}, selector={"name": "M_Actual"})
            fig.update_traces(patch={"width": 0.35}, selector={"name": "S_Planned"})
            fig.update_traces(patch={"width": 0.35}, selector={"name": "S_Actual"})
            fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="dot", line_color="red")
            st.plotly_chart(fig, use_container_width=True)

            # Interactive Details
            st.markdown("---")
            st.markdown("🔍 **คลิกเลือกงานย่อยเพื่อดูผู้รับผิดชอบ**")
            ev = st.dataframe(df_proj[['Sub_Task', 'Main_Task', 'Progress']].drop_duplicates(), use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            if ev.selection.rows:
                sel_row = df_proj[['Sub_Task', 'Main_Task']].drop_duplicates().iloc[ev.selection.rows[0]]
                show_task_info(sel_row['Sub_Task'], sel_row['Main_Task'], sel_p)

with tabs[2]: # อัปเดตยกทีม
    st.subheader("🛠️ แก้ไขงานย่อย")
    df_u = st.session_state['data'].copy()
    if not df_u.empty:
        ev2 = st.dataframe(df_u[['Sub_Task', 'Main_Task', 'Project', 'Employee', 'Progress']], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if ev2.selection.rows:
            idx = ev2.selection.rows[0]
            if st.button(f"✏️ อัปเดต: {df_u.iloc[idx]['Sub_Task']}", type="primary", use_container_width=True):
                update_task_dialog(idx, df_u.iloc[idx])

with tabs[3]: # ผลงาน
    if not df_all.empty:
        perf = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        for i, r in perf.iterrows():
            st.metric(f"#{i+1} {r['Employee']}", f"{r['Progress']:.1f}%")

with tabs[4]: # รายงาน
    if not df_all.empty:
        st.table(df_all.groupby(['Project', 'Main_Task'])['Progress'].mean().reset_index())