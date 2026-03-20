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
                df_logs['Start_Date'] = pd.to_datetime(df_logs['Start_Date'], errors='coerce')
                df_logs['End_Date'] = pd.to_datetime(df_logs['End_Date'], errors='coerce')
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)
                df_logs['Issue'] = df_logs['Issue'].astype(str).replace('nan', '')

            st.session_state['projects_master'] = df_projs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects'] = df_projs['Project'].dropna().unique().tolist() if not df_projs.empty else []

            return df_logs, st.session_state['employees'], st.session_state['projects']
        except Exception as e:
            return pd.DataFrame(columns=expected_cols), [], []
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
        except: return False

# ==========================================
# 4. DIALOGS
# ==========================================
@st.dialog("👤 รายละเอียดผู้รับผิดชอบ")
def show_task_info(task_name, project_name):
    df = st.session_state['data']
    team = df[(df['Main_Task'] == project_name) & (df['Sub_Task'] == task_name)]
    
    st.subheader(f"📌 {task_name}")
    st.caption(f"📁 โปรเจกต์: {project_name}")
    st.divider()
    
    if team.empty:
        st.write("ไม่พบข้อมูลผู้รับผิดชอบ")
    else:
        for _, row in team.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([1, 4])
                c1.markdown("### 👤")
                c2.markdown(f"**{row['Employee']}**")
                c2.progress(int(row['Progress'])/100)
                c2.write(f"ความคืบหน้า: {int(row['Progress'])}%")
                if row['Issue'] and row['Issue'] != "":
                    st.info(f"📝 **บันทึก:** {row['Issue']}")
    
    if st.button("ปิดหน้าต่าง", use_container_width=True):
        st.rerun()

@st.dialog("📝 อัปเดตงาน (Sync ทีม)")
def update_task_dialog(index, row_data):
    df = st.session_state['data']
    task_name, project_name = row_data['Sub_Task'], row_data['Main_Task']
    team = df[(df['Main_Task'] == project_name) & (df['Sub_Task'] == task_name)]['Employee'].unique().tolist()
    
    st.markdown(f"📁 **โปรเจกต์:** {project_name}  \n📌 **งาน:** {task_name}  \n👥 **ทีมงาน:** {', '.join(team)}")
    new_prog = st.slider("ความคืบหน้า (%)", 0, 100, int(row_data['Progress']))
    new_issue = st.text_area("บันทึกวันนี้", value=str(row_data['Issue']))
    sync_all = st.checkbox("🔄 อัปเดตให้ทุกคนพร้อมกัน", value=True)
    
    c1, c2 = st.columns(2)
    if c1.button("💾 บันทึก", type="primary", use_container_width=True):
        if sync_all:
            mask = (df['Main_Task'] == project_name) & (df['Sub_Task'] == task_name)
            df.loc[mask, 'Progress'] = new_prog
            df.loc[mask, 'Issue'] = new_issue
        else:
            df.at[index, 'Progress'] = new_prog
            df.at[index, 'Issue'] = new_issue
        if save_data(df):
            st.toast("✅ อัปเดตเรียบร้อย", icon="🚀")
            st.rerun()
    if c2.button("ยกเลิก", use_container_width=True): st.rerun()

# ==========================================
# 5. INITIALIZE
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
        new_p_name = st.text_input("ชื่อโปรเจกต์ใหม่")
        c1, c2 = st.columns(2)
        p_start, p_end = c1.date_input("วันเริ่ม"), c2.date_input("วันจบ", value=date.today() + timedelta(days=30))
        if st.button("➕ บันทึกโปรเจกต์", use_container_width=True):
            if new_p_name:
                sh = connect_gsheet()
                sh.worksheet('Projects').append_row([new_p_name, p_start.strftime('%Y-%m-%d'), p_end.strftime('%Y-%m-%d')])
                st.toast(f"💾 บันทึก {new_p_name} แล้ว"); st.rerun()

# ==========================================
# 7. MAIN UI
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผัง & Popup", "🛠️ อัพเดต", "🏆 ผลงาน", "📑 รายงาน"])

with tabs[0]: # ลงทะเบียน
    with st.form("task_reg", clear_on_submit=True):
        p = st.selectbox("โปรเจกต์", st.session_state['projects'])
        sub = st.text_input("ชื่องานย่อย")
        emps_multi = st.multiselect("ผู้รับผิดชอบ", st.session_state['employees'])
        c1, c2 = st.columns(2)
        d_s, d_e = c1.date_input("เริ่ม", value=date.today()), c2.date_input("จบ", value=date.today()+timedelta(days=7))
        if st.form_submit_button("💾 บันทึกงาน", use_container_width=True):
            latest_logs, _, _ = load_data()
            new_rows = [{'Employee': e, 'Main_Task': p, 'Sub_Task': sub, 'Start_Date': pd.to_datetime(d_s), 'End_Date': pd.to_datetime(d_e), 'Progress': 0} for e in emps_multi]
            updated = pd.concat([latest_logs, pd.DataFrame(new_rows)], ignore_index=True)
            if save_data(updated):
                st.session_state['data'] = updated
                st.toast(f"✅ เพิ่มงาน '{sub}' สำเร็จ"); st.rerun()

with tabs[1]: # แผนผัง (Interactive Popup)
    df_all = st.session_state['data']
    if not df_all.empty and st.session_state['projects']:
        sel_p = st.selectbox("📂 เลือกโปรเจกต์:", st.session_state['projects'], key="dash_p")
        master = st.session_state.get('projects_master', pd.DataFrame())
        
        if not master.empty and sel_p in master['Project'].values:
            p_info = master[master['Project'] == sel_p].iloc[0]
            p_s, p_e = pd.to_datetime(p_info['Start_Date']), pd.to_datetime(p_info['End_Date'])
            actual_pct = df_all[df_all['Main_Task'] == sel_p]['Progress'].mean()
            st.metric(f"Progress รวม: {sel_p}", f"{actual_pct:.1f}%")

            df_sub = df_all[(df_all['Main_Task'] == sel_p) & (df_all['Employee'].isin(sel_emps_filter))].copy()
            if not df_sub.empty:
                df_sub['Start'], df_sub['End_V'] = df_sub['Start_Date'], df_sub['End_Date'] + pd.Timedelta(days=1)
                df_sub['Type'] = "📌 งานย่อย"
                df_sub['Label'] = df_sub['Progress'].astype(int).astype(str) + "%"

                summary_row = pd.DataFrame([{
                    'Sub_Task': f"🏢 Baseline: {sel_p}", 'Employee': 'ALL', 'Start': p_s, 'End_V': p_e + pd.Timedelta(days=1), 
                    'Progress': actual_pct, 'Type': "🏢 โปรเจกต์หลัก", 'Label': f"{int(actual_pct)}%"
                }])

                df_plot = pd.concat([summary_row, df_sub], ignore_index=True)
                
                # --- สร้างกราฟ ---
                fig = px.timeline(
                    df_plot, x_start="Start", x_end="End_V", y="Sub_Task", color="Type", text="Label", height=450,
                    color_discrete_map={"🏢 โปรเจกต์หลัก": "#333333", "📌 งานย่อย": "#636EFA"},
                    custom_data=["Sub_Task"] # ส่งชื่องานเข้าไปในกราฟเพื่อใช้ดักจับ
                )
                fig.update_traces(patch={"width": 0.7}, selector={"name": "🏢 โปรเจกต์หลัก"})
                fig.update_traces(patch={"width": 0.35}, selector={"name": "📌 งานย่อย"})
                fig.update_yaxes(autorange="reversed")
                fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="dot", line_color="red")
                
                st.info("💡 คลิกที่แท่งงานย่อยในกราฟ เพื่อดูรายชื่อคนทำงาน")
                
                # 🔥 จุดที่แก้ไข: ใช้ selection_mode="points" และจับเหตุการณ์
                selected_point = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points")
                
                # ตรวจสอบการคลิก
                if selected_point and "selection" in selected_point and "points" in selected_point["selection"]:
                    points = selected_point["selection"]["points"]
                    if points:
                        # ดึงชื่อ Task จาก custom_data ที่เราใส่ไว้ในตอนสร้าง fig
                        t_name = points[0].get("y") 
                        if t_name and "Baseline" not in t_name:
                            show_task_info(t_name, sel_p)

with tabs[2]: # อัปเดต
    st.subheader("🛠️ คลิกเลือกแถวงานเพื่ออัปเดตยกทีม")
    df_upd = st.session_state['data'].copy()
    if not df_upd.empty:
        event = st.dataframe(df_upd[['Sub_Task', 'Main_Task', 'Employee', 'Progress', 'Issue']], 
                            use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if event.selection.rows:
            idx = event.selection.rows[0]
            if st.button(f"✏️ แก้ไขงาน: {df_upd.iloc[idx]['Sub_Task']}", type="primary", use_container_width=True):
                update_task_dialog(idx, df_upd.iloc[idx])

with tabs[3]: # ผลงาน
    if not df_all.empty:
        sum_df = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        for i, row in sum_df.iterrows():
            st.metric(f"#{i+1} {row['Employee']}", f"{row['Progress']:.1f}%")

with tabs[4]: # รายงาน
    if not df_all.empty:
        st.table(df_all.groupby('Main_Task')['Progress'].mean().reset_index())