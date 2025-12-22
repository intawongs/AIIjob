import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. การตั้งค่า (CONFIGURATION)
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

st.title("🌌 Project Tracker")

# ==========================================
# 2. เชื่อมต่อ GOOGLE SHEETS
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
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            ws_emps = sh.worksheet('Employees')
            ws_projs = sh.worksheet('Projects')

            data_logs = ws_logs.get_all_records()
            data_emps = ws_emps.get_all_records()
            data_projs = ws_projs.get_all_records()

            df_logs = pd.DataFrame(data_logs)
            expected_cols = ['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']
            
            if df_logs.empty: df_logs = pd.DataFrame(columns=expected_cols)
            else:
                for col in expected_cols:
                    if col not in df_logs.columns: df_logs[col] = None

            if not df_logs.empty:
                for col in ['Start_Date', 'End_Date']:
                    df_logs[col] = pd.to_datetime(df_logs[col], errors='coerce').dt.date
                
                # Force String conversion for text fields
                df_logs['Issue'] = df_logs['Issue'].astype(str).replace('nan', '')
                df_logs['Output'] = df_logs['Output'].astype(str).replace('nan', '')
                
                df_logs['Progress'] = df_logs['Progress'].fillna(0)
                df_logs['Score'] = df_logs['Score'].fillna(0)
                df_logs['Status'] = df_logs['Status'].fillna("⏳ กำลังดำเนินการ")

            emp_list = pd.DataFrame(data_emps)['Name'].tolist() if data_emps else []
            proj_list = pd.DataFrame(data_projs)['Project'].tolist() if data_projs else []

            return df_logs, emp_list, proj_list
        except: return pd.DataFrame(columns=expected_cols), [], []
    return pd.DataFrame(), [], []

def save_data():
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = st.session_state['data'].copy()
            
            # Prepare Data
            save_df = save_df.fillna("") 
            save_df['Issue'] = save_df['Issue'].astype(str)
            save_df['Output'] = save_df['Output'].astype(str)
            save_df['Start_Date'] = save_df['Start_Date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (date, datetime)) else "")
            save_df['End_Date'] = save_df['End_Date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (date, datetime)) else "")
            
            cols = ['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']
            for c in cols: 
                if c not in save_df.columns: save_df[c] = ""
            
            all_values = [cols]
            if not save_df.empty: all_values.extend(save_df[cols].values.tolist())
            
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=all_values)
        except Exception as e: print(f"Log Error: {e}")

        try:
            ws_emps = sh.worksheet('Employees')
            ws_emps.clear()
            ws_emps.update(range_name="A1", values=[['Name']] + [[x] for x in st.session_state['employees']])
        except: pass

        try:
            ws_projs = sh.worksheet('Projects')
            ws_projs.clear()
            ws_projs.update(range_name="A1", values=[['Project']] + [[x] for x in st.session_state['projects']])
        except: pass

def update_db(key, list_name):
    val = st.session_state.get(key)
    if val and val not in st.session_state[list_name]:
        st.session_state[list_name].append(val)
        save_data()
        st.session_state[key] = ""
        st.toast(f"✅ เพิ่ม '{val}' เรียบร้อย", icon="💾")

def delete_db(key, list_name):
    val = st.session_state.get(key)
    if val and val in st.session_state[list_name]:
        st.session_state[list_name].remove(val)
        if list_name == 'projects':
            df = st.session_state['data']
            st.session_state['data'] = df[df['Main_Task'] != val].reset_index(drop=True)
        elif list_name == 'employees':
             df = st.session_state['data']
             st.session_state['data'] = df[df['Employee'] != val].reset_index(drop=True)
        save_data()
        st.cache_data.clear()
        st.toast(f"🗑️ ลบ '{val}' แล้ว", icon="🗑️")

# ==========================================
# 4. INITIALIZE
# ==========================================
if 'data' not in st.session_state:
    logs, emps, projs = load_data()
    if logs is not None:
        st.session_state['data'] = logs
        st.session_state['employees'] = emps
        st.session_state['projects'] = projs
    else:
        st.session_state['data'] = pd.DataFrame()
        st.session_state['employees'] = []
        st.session_state['projects'] = []

keys = ['k_d_start', 'k_d_end', 'k_prog', 'k_sub', 'k_out', 'k_issue', 'k_emps_multi']
defaults = [datetime.now(), datetime.now(), 0, "", "", "", []]
for k, v in zip(keys, defaults):
    if k not in st.session_state: st.session_state[k] = v

# ==========================================
# 5. HELPER
# ==========================================
def calculate_status_and_score(df):
    if df.empty: return df
    today = date.today()
    def get_details(row):
        try:
            s = row['Start_Date']
            e = row['End_Date']
            if isinstance(s, str) and s: s = datetime.strptime(s, '%Y-%m-%d').date()
            if isinstance(e, str) and e: e = datetime.strptime(e, '%Y-%m-%d').date()
            if not isinstance(s, date) or not isinstance(e, date): return "❓ วันที่ระบุไม่ครบ", 0
            
            if row['Progress'] == 100: return "✅ เสร็จสิ้น", 100
            elif today < s: return "🔜 ยังไม่ถึงกำหนดเริ่ม", None
            elif today > e: return "🔥 ล่าช้า (Late)", row['Progress']
            else: return "⏳ กำลังดำเนินการ", 100
        except: return "Error", 0
    res = df.apply(get_details, axis=1, result_type='expand')
    df['Status'] = res[0]
    df['Score'] = res[1]
    return df

st.session_state['data'] = calculate_status_and_score(st.session_state['data'])

THAI_COLS = {
    "Employee": "พนักงาน", "Main_Task": "โปรเจกต์", "Sub_Task": "ชื่องาน",
    "Progress": "ความคืบหน้า", "Status": "สถานะ", "End_Date": "กำหนดส่ง",
    "Issue": "บันทึก", "Score": "คะแนน", "Total": "งานทั้งหมด",
    "Avg": "คะแนนเฉลี่ย", "OnTime%": "ส่งตรงเวลา (%)", "Grade": "เกรด", "Late": "งานล่าช้า"
}

# ==========================================
# 6. DIALOG
# ==========================================
@st.dialog("📝 จัดการงาน")
def update_task_dialog(index, row_data):
    st.caption(f"{row_data['Sub_Task']} ({row_data['Employee']})")
    
    new_prog = st.slider("ความคืบหน้า (%)", 0, 100, int(row_data['Progress']))
    new_output = st.text_input("ผลลัพธ์ / ลิงก์", value=str(row_data['Output']))
    
    st.markdown("---")
    
    # Handle Issue
    issue_val = str(row_data['Issue'])
    if issue_val == "nan" or issue_val == "None": issue_val = ""
    
    current_log = issue_val
    mode = st.radio("Log Book:", ["➕ เพิ่มบันทึก", "✏️ แก้ไขทั้งหมด"], horizontal=True)
    
    final_log = current_log
    if "เพิ่มบันทึก" in mode:
        if current_log: st.info(current_log)
        new_entry = st.text_area("บันทึกวันนี้:", height=80)
    else:
        full_edit = st.text_area("แก้ไขประวัติ:", value=current_log, height=150)

    st.markdown("---")
    
    c1, c2 = st.columns(2)
    if c1.button("💾 บันทึก", type="primary", use_container_width=True):
        if "เพิ่มบันทึก" in mode and new_entry.strip():
            ts = datetime.now().strftime("%d/%m")
            final_log += f"\n- [{ts}] {new_entry.strip()}"
        elif "แก้ไข" in mode: final_log = full_edit
        
        st.session_state['data'].at[index, 'Progress'] = new_prog
        st.session_state['data'].at[index, 'Output'] = new_output
        st.session_state['data'].at[index, 'Issue'] = final_log.strip()
        save_data()
        st.toast("บันทึกแล้ว", icon="💾")
        st.rerun()
            
    if c2.button("ยกเลิก", use_container_width=True): st.rerun()
    if st.button("🗑️ ลบงานนี้", type="secondary", use_container_width=True):
        st.session_state['data'] = st.session_state['data'].drop(index).reset_index(drop=True)
        save_data() 
        st.toast("ลบงานแล้ว", icon="🗑️")
        st.rerun()

# ==========================================
# 7. MAIN UI
# ==========================================
def auto_update_date():
    p, d = st.session_state.get('k_proj_sel'), st.session_state.get('k_dep_sel')
    if p and d and d != "- เริ่มต้นใหม่ (ไม่รอใคร) -":
        df = st.session_state['data']
        row = df[(df['Main_Task'] == p) & (df['Sub_Task'] == d)]
        if not row.empty:
            ed = row.iloc[0]['End_Date']
            if isinstance(ed, str): ed = datetime.strptime(ed, '%Y-%m-%d').date()
            if isinstance(ed, (date, datetime)):
                st.session_state.k_d_start = ed + timedelta(days=1)
                st.session_state.k_d_end = ed + timedelta(days=1)

def submit_work():
    emps = st.session_state.k_emps_multi
    if st.session_state.k_d_end >= st.session_state.k_d_start and st.session_state.k_sub and emps:
        new_rows = []
        for emp in emps:
            new_rows.append({
                'Employee': emp, 'Main_Task': st.session_state.k_proj_sel, 
                'Sub_Task': st.session_state.k_sub, 'Start_Date': st.session_state.k_d_start, 
                'End_Date': st.session_state.k_d_end, 'Output': st.session_state.k_out, 
                'Issue': st.session_state.k_issue, 'Dependency': st.session_state.k_dep_sel, 
                'Progress': st.session_state.k_prog
            })
        st.session_state['data'] = pd.concat([st.session_state['data'], calculate_status_and_score(pd.DataFrame(new_rows))], ignore_index=True)
        save_data()
        st.session_state.k_sub = ""
        st.session_state.k_out = ""
        st.session_state.k_issue = ""
        st.session_state.k_prog = 0
        st.session_state.k_emps_multi = []
        st.toast(f"✅ เพิ่มงานเรียบร้อย ({len(emps)} คน)", icon="💾")
    else: st.toast("❌ ข้อมูลไม่ครบ", icon="⚠️")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ ตั้งค่า")
    if st.button("🔄 รีเฟรชข้อมูล", use_container_width=True):
        st.cache_data.clear()
        logs, emps, projs = load_data()
        if logs is not None:
            st.session_state['data'] = logs
            st.session_state['employees'] = emps
            st.session_state['projects'] = projs
            st.rerun()

    st.divider()
    all_emps = st.session_state['employees']
    sel_emps = st.multiselect("กรองชื่อ:", all_emps, default=all_emps)
    
    with st.expander("👤 จัดการคน"):
        st.text_input("เพิ่มชื่อ", key='new_emp', on_change=update_db, args=('new_emp', 'employees'))
        if st.session_state['employees']:
            st.selectbox("ลบชื่อ", st.session_state['employees'], key='del_emp')
            st.button("ลบคน", on_click=delete_db, args=('del_emp', 'employees'))
            
    with st.expander("📂 จัดการงาน"):
        st.text_input("เพิ่มงาน", key='new_proj', on_change=update_db, args=('new_proj', 'projects'))
        if st.session_state['projects']:
            st.selectbox("ลบงาน", st.session_state['projects'], key='del_proj')
            st.button("ลบงาน", on_click=delete_db, args=('del_proj', 'projects'))

# --- MAIN TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📝 ลงทะเบียน", "📊 แผนผัง", "🛠️ อัพเดต", "🏆 ผลงาน"])

with tab1:
    with st.container():
        p = st.selectbox("โปรเจกต์", st.session_state['projects'] or ["ไม่มีข้อมูล"], key="k_proj_sel")
        st.text_input("ชื่องาน", key="k_sub", placeholder="เช่น ออกแบบ UX/UI")
        
        df = st.session_state['data']
        dep_opt = ["- เริ่มใหม่ -"]
        if not df.empty and p != "ไม่มีข้อมูล":
            dep_opt += df[df['Main_Task'] == p].sort_values('End_Date', ascending=False)['Sub_Task'].unique().tolist()
        st.selectbox("รอต่องานไหน?", dep_opt, key="k_dep_sel", on_change=auto_update_date)
        
        st.multiselect("ผู้รับผิดชอบ", st.session_state['employees'], key="k_emps_multi")
        
        c1, c2 = st.columns(2)
        with c1: st.date_input("เริ่ม", key="k_d_start")
        with c2: st.date_input("ถึง", key="k_d_end")
        
        st.slider("ความคืบหน้า", 0, 100, key="k_prog")
        
        with st.expander("เพิ่มเติม (ผลลัพธ์/Log)"):
            st.text_area("ผลลัพธ์", key="k_out", height=68)
            st.text_area("Log Book", key="k_issue", height=68)
            
        st.button("บันทึกข้อมูล", on_click=submit_work, type="primary", use_container_width=True)

with tab2:
    df = calculate_status_and_score(st.session_state['data'].copy())
    if not df.empty: df = df[df['Employee'].isin(sel_emps)]
    
    if not df.empty:
        df['Start'] = pd.to_datetime(df['Start_Date'], errors='coerce')
        df['End'] = pd.to_datetime(df['End_Date'], errors='coerce')
        df = df.dropna(subset=['Start', 'End'])
        df['Visual_End'] = df['End'] + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        df['Label'] = df['Progress'].astype(str) + "%"
        
        chart_height = 300 + (len(df) * 30)
        
        # -----------------------------------------------
        # [แก้ไข] เพิ่มการแยกกลุ่มและสีที่ชัดเจน
        # -----------------------------------------------
        fig = px.timeline(
            df, 
            x_start="Start", 
            x_end="Visual_End", 
            y="Sub_Task", 
            color="Employee", 
            text="Label", 
            height=chart_height,
            color_discrete_sequence=px.colors.qualitative.Bold, # เปลี่ยนชุดสีให้ชัด
            opacity=0.9
        )
        fig.update_yaxes(autorange="reversed", title="")
        fig.update_layout(
            barmode='group', # สำคัญมาก! ทำให้แท่งกราฟไม่ทับกัน
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", y=-0.2)
        )
        fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="dash", line_color="red")
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("ดูตารางรายละเอียด"):
            def highlight(row): return ['background-color: #ffcccc'] * len(row) if "ล่าช้า" in str(row['Status']) else [''] * len(row)
            st.dataframe(
                df[['Sub_Task', 'Employee', 'Progress', 'Status', 'End_Date']].style.apply(highlight, axis=1), 
                use_container_width=True, hide_index=True,
                column_config={
                    "Sub_Task": st.column_config.TextColumn(THAI_COLS["Sub_Task"]),
                    "Employee": st.column_config.TextColumn(THAI_COLS["Employee"]),
                    "Progress": st.column_config.ProgressColumn(THAI_COLS["Progress"], format="%d%%"),
                    "End_Date": st.column_config.DateColumn(THAI_COLS["End_Date"])
                }
            )
    else: st.info("ไม่มีข้อมูล")

with tab3:
    st.info("👆 คลิกเลือกงานในตาราง -> จะมีปุ่ม 'แก้ไข' โผล่มาด้านล่าง")
    df = calculate_status_and_score(st.session_state['data'])
    if not df.empty:
        event = st.dataframe(
            df[['Sub_Task', 'Employee', 'Issue', 'Progress', 'Status']], 
            use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True,
            column_config={
                "Sub_Task": st.column_config.TextColumn(THAI_COLS["Sub_Task"]),
                "Employee": st.column_config.TextColumn(THAI_COLS["Employee"]),
                "Issue": st.column_config.TextColumn(THAI_COLS["Issue"], width="medium"),
                "Progress": st.column_config.ProgressColumn(THAI_COLS["Progress"], format="%d%%"),
                "Status": st.column_config.TextColumn(THAI_COLS["Status"])
            }
        )
        if event.selection.rows:
            idx = event.selection.rows[0]
            selected_task_name = df.iloc[idx]['Sub_Task']
            if st.button(f"✏️ แก้ไขงาน: {selected_task_name}", type="primary", use_container_width=True):
                update_task_dialog(idx, df.iloc[idx])
    else: st.info("ไม่มีงาน")

with tab4:
    df = calculate_status_and_score(st.session_state['data'].copy())
    if not df.empty:
        df['Year'] = pd.to_datetime(df['End_Date'], errors='coerce').dt.year
        yrs = df['Year'].dropna().unique().tolist()
        if yrs:
            sy = st.selectbox("ปีงบประมาณ", sorted(yrs, reverse=True))
            dfy = df[df['Year'] == sy]
            if not dfy.empty:
                sum_df = dfy.groupby('Employee').agg(
                    Total=('Sub_Task','count'), 
                    Avg=('Score','mean'), 
                    Late=('Status', lambda x: x.str.contains('ล่าช้า').sum())
                ).reset_index()
                
                sum_df['Avg'] = sum_df['Avg'].fillna(0)
                sum_df['OnTime%'] = ((sum_df['Total'] - sum_df['Late']) / sum_df['Total']) * 100
                
                if not sum_df.empty:
                    best = sum_df.sort_values(by='Avg', ascending=False).iloc[0]
                    st.success(f"🥇 **{best['Employee']}** ({best['Avg']:.1f})")
                
                for _, row in sum_df.iterrows():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns(3)
                        c1.metric(row['Employee'], f"{row['Avg']:.1f}")
                        c2.metric("งาน", row['Total'])
                        c3.metric("ตรงเวลา", f"{row['OnTime%']:.0f}%")

            else: st.info("ไม่มีงานปีนี้")
        else: st.info("ไม่มีข้อมูลปี")
    else: st.info("ไม่มีข้อมูล")