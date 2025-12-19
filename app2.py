import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker", layout="wide")
st.title("🌌 AII Project Tracker (Online)")

# ==========================================
# 2. GOOGLE SHEETS CONNECTION
# ==========================================
def connect_gsheet():
    """เชื่อมต่อ Google Sheets แบบ Native GSpread Auth"""
    try:
        # กรณีรันบน Streamlit Cloud (ใช้ Secrets)
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            
            # แก้บั๊ก Private Key (\n) ที่บางที Streamlit อ่านผิด
            if "\\n" in creds_dict["private_key"]:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            
            client = gspread.service_account_from_dict(creds_dict)
            
        # กรณีรันในเครื่อง (Local - ใช้ไฟล์ json)
        else:
            client = gspread.service_account(filename='credentials.json')

        # เปิด Sheet
        sh = client.open("Chronos_Data") 
        return sh
        
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        if "SpreadsheetNotFound" in str(e):
            st.warning("👉 บอทหาไฟล์ 'Chronos_Data' ไม่เจอ! อย่าลืมกด Share ไฟล์ให้ Email ของบอทด้วย")
        return None

# ==========================================
# 3. DATABASE LOGIC (LOAD & SAVE)
# ==========================================
def load_data():
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            ws_emps = sh.worksheet('Employees')
            ws_projs = sh.worksheet('Projects')

            # ดึงข้อมูลดิบ
            data_logs = ws_logs.get_all_records()
            data_emps = ws_emps.get_all_records()
            data_projs = ws_projs.get_all_records()

            # สร้าง DataFrame
            df_logs = pd.DataFrame(data_logs)
            df_emps = pd.DataFrame(data_emps)
            df_projs = pd.DataFrame(data_projs)

            # [FIX] บังคับสร้างคอลัมน์ให้ครบ แม้ Sheet จะว่างเปล่า
            expected_cols = [
                'Employee', 'Main_Task', 'Sub_Task', 
                'Start_Date', 'End_Date', 
                'Output', 'Issue', 'Dependency', 'Progress',
                'Score', 'Status'
            ]
            
            # ถ้า DataFrame ว่าง หรือไม่มีคอลัมน์ ให้สร้างขึ้นมา
            if df_logs.empty:
                df_logs = pd.DataFrame(columns=expected_cols)
            else:
                for col in expected_cols:
                    if col not in df_logs.columns:
                        df_logs[col] = None

            # [FIX] จัดการ Format ข้อมูล (Date & NaN)
            if not df_logs.empty:
                for col in ['Start_Date', 'End_Date']:
                    df_logs[col] = pd.to_datetime(df_logs[col], errors='coerce').dt.date

                # Fill Default Values
                df_logs['Progress'] = df_logs['Progress'].fillna(0)
                df_logs['Score'] = df_logs['Score'].fillna(0)
                df_logs['Issue'] = df_logs['Issue'].fillna("").astype(str)
                df_logs['Output'] = df_logs['Output'].fillna("").astype(str)
                df_logs['Status'] = df_logs['Status'].fillna("⏳ กำลังดำเนินการ")

            # เตรียม List สำหรับ Dropdown
            emp_list = df_emps['Name'].tolist() if not df_emps.empty and 'Name' in df_emps.columns else []
            proj_list = df_projs['Project'].tolist() if not df_projs.empty and 'Project' in df_projs.columns else []

            return df_logs, emp_list, proj_list

        except Exception as e:
            st.error(f"Error reading data: {e}")
            # คืนค่าตารางเปล่าเพื่อกันแอปพัง
            return pd.DataFrame(columns=['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']), [], []
            
    return pd.DataFrame(), [], []

def save_data():
    """ฟังก์ชันบันทึกข้อมูลแบบ Atomic Write (เขียนทับรวดเดียว เพื่อแก้ปัญหาลบไม่หาย)"""
    sh = connect_gsheet()
    if sh:
        # --- PART 1: LOGS (งาน) ---
        try:
            ws_logs = sh.worksheet('Logs')
            
            # เตรียมข้อมูล DataFrame
            save_df = st.session_state['data'].copy()
            
            # จัดการวันที่ให้เป็น String เพื่อส่งไป GSheet
            save_df['Start_Date'] = save_df['Start_Date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (date, datetime)) else "")
            save_df['End_Date'] = save_df['End_Date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (date, datetime)) else "")
            
            # เตรียม Header
            cols_to_save = [
                'Employee', 'Main_Task', 'Sub_Task', 
                'Start_Date', 'End_Date', 
                'Output', 'Issue', 'Dependency', 'Progress',
                'Score', 'Status'
            ]
            
            # เช็คคอลัมน์ให้ครบ
            for c in cols_to_save:
                if c not in save_df.columns: save_df[c] = ""
            
            # รวม Header + Data เป็นก้อนเดียว (List of Lists)
            all_values = [cols_to_save] # ใส่ Header เป็นแถวแรก
            if not save_df.empty:
                # เพิ่มข้อมูลต่อท้าย
                all_values.extend(save_df[cols_to_save].values.tolist())
            
            # สั่ง Clear และ Update ในคำสั่งเดียว
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=all_values)
                
        except Exception as e:
            print(f"Error saving LOGS: {e}")

        # --- PART 2: EMPLOYEES (พนักงาน) ---
        try:
            ws_emps = sh.worksheet('Employees')
            
            # เตรียมข้อมูล [Header] + [Data]
            emp_final_data = [['Name']] # แถวแรกคือหัวตาราง
            for name in st.session_state['employees']:
                emp_final_data.append([name])
            
            # เขียนทับเลย
            ws_emps.clear()
            ws_emps.update(range_name="A1", values=emp_final_data)
            
        except Exception as e:
            st.error(f"❌ Error saving Employees: {e}")

        # --- PART 3: PROJECTS (โปรเจกต์) ---
        try:
            ws_projs = sh.worksheet('Projects')
            
            # เตรียมข้อมูล [Header] + [Data]
            proj_final_data = [['Project']] # แถวแรกคือหัวตาราง
            for proj in st.session_state['projects']:
                proj_final_data.append([proj])
                
            # เขียนทับเลย
            ws_projs.clear()
            ws_projs.update(range_name="A1", values=proj_final_data)
            
        except Exception as e:
            st.error(f"❌ Error saving Projects: {e}")

def update_db(key, list_name):
    val = st.session_state.get(key)
    if val and val not in st.session_state[list_name]:
        st.session_state[list_name].append(val)
        save_data()

def delete_db(key, list_name):
    val = st.session_state.get(key)
    if val and val in st.session_state[list_name]:
        
        # 1. ลบจากหน่วยความจำ
        st.session_state[list_name].remove(val)
        
        # 2. ลบงานที่เกี่ยวข้อง (Cascading Delete)
        if list_name == 'projects':
            df = st.session_state['data']
            st.session_state['data'] = df[df['Main_Task'] != val].reset_index(drop=True)
            st.toast(f"🗑️ ลบโปรเจกต์ '{val}' และงานที่เกี่ยวข้องแล้ว", icon="🗑️")
        elif list_name == 'employees':
             df = st.session_state['data']
             st.session_state['data'] = df[df['Employee'] != val].reset_index(drop=True)
             st.toast(f"👤 ลบพนักงาน '{val}' และงานของเขาแล้ว", icon="🗑️")
        
        # 3. บันทึกลง GSheet ทันที (เขียนทับใหม่หมด)
        save_data()
        
        # 4. เคลียร์ Cache เพื่อให้โหลดใหม่ถูกต้อง
        st.cache_data.clear()

# ==========================================
# 4. INITIALIZE STATE
# ==========================================
if 'data' not in st.session_state:
    logs, emps, projs = load_data()
    
    if logs is not None:
        st.session_state['data'] = logs
        st.session_state['employees'] = emps
        st.session_state['projects'] = projs
    else:
        st.session_state['employees'] = []
        st.session_state['projects'] = []
        st.session_state['data'] = pd.DataFrame(columns=[
            'Employee', 'Main_Task', 'Sub_Task', 
            'Start_Date', 'End_Date', 
            'Output', 'Issue', 'Dependency', 'Progress',
            'Score', 'Status'
        ])

# Init Helper Variables
keys = ['k_d_start', 'k_d_end', 'k_prog', 'k_sub', 'k_out', 'k_issue', 'k_emps_multi']
defaults = [datetime.now(), datetime.now(), 0, "", "", "", []]
for k, v in zip(keys, defaults):
    if k not in st.session_state: st.session_state[k] = v

# ==========================================
# 5. HELPER: SCORE & STATUS
# ==========================================
def calculate_status_and_score(df):
    if df.empty: return df
    today = date.today()
    
    def get_details(row):
        try:
            s_date = row['Start_Date']
            e_date = row['End_Date']
            
            # Ensure date objects
            if isinstance(s_date, str) and s_date: s_date = datetime.strptime(s_date, '%Y-%m-%d').date()
            if isinstance(e_date, str) and e_date: e_date = datetime.strptime(e_date, '%Y-%m-%d').date()
            
            # Check Valid Date
            if not isinstance(s_date, date) or not isinstance(e_date, date):
                return "❓ วันที่ระบุไม่ครบ", 0

            is_completed = row['Progress'] == 100
            
            if is_completed: 
                return "✅ เสร็จสิ้น", 100
            elif today < s_date: 
                return "🔜 ยังไม่ถึงกำหนดเริ่ม", None
            elif today > e_date: 
                return "🔥 ล่าช้า (Late)", row['Progress']
            else: 
                return "⏳ กำลังดำเนินการ", 100
        except:
            return "Error", 0
            
    result = df.apply(get_details, axis=1, result_type='expand')
    df['Status'] = result[0]
    df['Score'] = result[1]
    return df

st.session_state['data'] = calculate_status_and_score(st.session_state['data'])

# ==========================================
# 6. DIALOG FUNCTION (POP-UP)
# ==========================================
@st.dialog("📝 อัพเดตงาน / บันทึกปัญหา")
def update_task_dialog(index, row_data):
    st.write(f"**งาน:** {row_data['Sub_Task']} | **ผู้รับผิดชอบ:** {row_data['Employee']}")
    st.markdown("---")
    
    new_prog = st.slider("ความคืบหน้าปัจจุบัน (%)", 0, 100, int(row_data['Progress']))
    new_output = st.text_input("ผลลัพธ์ / ลิงก์งาน (Output)", value=str(row_data['Output']))
    
    st.markdown("---")
    st.subheader("📒 บันทึกสิ่งที่ทำ / ปัญหา (Log Book)")
    
    current_issue_log = str(row_data['Issue'])
    mode = st.radio("โหมดบันทึก:", ["➕ เพิ่มบันทึกใหม่ (Append)", "✏️ แก้ไขประวัติทั้งหมด (Edit All)"], horizontal=True)

    final_log_to_save = current_issue_log
    
    if "เพิ่มบันทึกใหม่" in mode:
        if current_issue_log:
            with st.expander("ดูประวัติบันทึกย้อนหลัง", expanded=False):
                st.info(current_issue_log)
        st.caption(f"📅 บันทึกของวันที่: {datetime.now().strftime('%d/%m/%Y')}")
        new_log_entry = st.text_area("พิมพ์สิ่งที่ทำวันนี้:", height=100)
    else:
        st.warning("⚠️ โหมดแก้ไข: แก้ไขข้อความทั้งหมดได้โดยตรง")
        full_log_edit = st.text_area("แก้ไขประวัติทั้งหมด:", value=current_issue_log, height=200)

    col1, col2 = st.columns(2)
    if col1.button("บันทึกข้อมูล", type="primary", use_container_width=True):
        if "เพิ่มบันทึกใหม่" in mode:
            if new_log_entry.strip():
                timestamp = datetime.now().strftime("%d/%m")
                final_log_to_save += f"\n- [{timestamp}] {new_log_entry.strip()}"
        else:
            final_log_to_save = full_log_edit
            
        st.session_state['data'].at[index, 'Progress'] = new_prog
        st.session_state['data'].at[index, 'Output'] = new_output
        st.session_state['data'].at[index, 'Issue'] = final_log_to_save.strip()
        
        save_data()
        st.rerun()
        
    if col2.button("ยกเลิก", use_container_width=True):
        st.rerun()

# ==========================================
# 7. CALLBACKS
# ==========================================
def auto_update_date():
    proj = st.session_state.get('k_proj_sel')
    dep = st.session_state.get('k_dep_sel')
    if proj and dep and dep != "- เริ่มต้นใหม่ (ไม่รอใคร) -":
        df = st.session_state['data']
        row = df[(df['Main_Task'] == proj) & (df['Sub_Task'] == dep)]
        if not row.empty:
            end_date = row.iloc[0]['End_Date']
            if isinstance(end_date, str):
                try: end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                except: end_date = date.today()
            
            if isinstance(end_date, (date, datetime)):
                new_start = end_date + timedelta(days=1)
                st.session_state.k_d_start = new_start
                st.session_state.k_d_end = new_start
                st.toast(f"⚡ ปรับวันเริ่มเป็น {new_start.strftime('%d/%m/%Y')} (ต่อจาก {dep})", icon="📅")

def submit_work_log():
    c_emps_list = st.session_state.k_emps_multi 
    c_proj = st.session_state.k_proj_sel
    c_sub = st.session_state.k_sub
    c_dep = st.session_state.k_dep_sel
    c_out = st.session_state.k_out
    c_issue = st.session_state.k_issue
    c_start = st.session_state.k_d_start
    c_end = st.session_state.k_d_end
    c_prog = st.session_state.k_prog

    if c_end >= c_start and c_sub and c_emps_list:
        new_rows = []
        for emp in c_emps_list:
            row = {
                'Employee': emp, 'Main_Task': c_proj, 'Sub_Task': c_sub, 
                'Start_Date': c_start, 'End_Date': c_end, 
                'Output': c_out, 'Issue': c_issue, 'Dependency': c_dep, 'Progress': c_prog
            }
            new_rows.append(row)
        new_df = pd.DataFrame(new_rows)
        new_df = calculate_status_and_score(new_df) 
        st.session_state['data'] = pd.concat([st.session_state['data'], new_df], ignore_index=True)
        save_data()
        
        st.session_state.k_sub = ""
        st.session_state.k_out = ""
        st.session_state.k_issue = ""
        st.session_state.k_prog = 0
        st.session_state.k_emps_multi = []
        st.toast(f"✅ บันทึกงานให้ {len(c_emps_list)} คนเรียบร้อย", icon="💾")
    else:
        st.toast("❌ ข้อมูลไม่ครบ", icon="⚠️")

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.title("⚙️ ตั้งค่า")
    
    # ปุ่มรีเฟรชข้อมูล
    if st.button("🔄 รีเฟรชข้อมูลล่าสุด", use_container_width=True):
        st.cache_data.clear()
        logs, emps, projs = load_data()
        if logs is not None:
            st.session_state['data'] = logs
            st.session_state['employees'] = emps
            st.session_state['projects'] = projs
            st.toast("อัพเดตข้อมูลล่าสุดแล้ว!", icon="✅")
            st.rerun()

    # Alert System
    df_alert = st.session_state['data']
    if not df_alert.empty and 'Status' in df_alert.columns:
        late_tasks = df_alert[df_alert['Status'].str.contains("ล่าช้า", na=False)]
        if not late_tasks.empty:
            st.error(f"⚠️ มีงานล่าช้า {len(late_tasks)} งาน!")
            with st.expander("ดูรายการ"):
                st.dataframe(late_tasks[['Employee', 'Sub_Task', 'End_Date']], hide_index=True)
        else: st.success("✨ งานทุกอย่างเป็นไปตามกำหนด")
    
    st.markdown("---")
    all_emps = st.session_state['employees']
    selected_emps = st.multiselect("เลือกพนักงาน:", options=all_emps, default=all_emps)
    st.markdown("---")

    with st.expander("👤 จัดการรายชื่อพนักงาน", expanded=False):
        st.text_input("เพิ่มชื่อ", key='new_emp', on_change=update_db, args=('new_emp', 'employees'))
        if st.session_state['employees']:
            st.selectbox("ลบชื่อ", st.session_state['employees'], key='del_emp')
            st.button("ลบคน", on_click=delete_db, args=('del_emp', 'employees'))

    with st.expander("📂 จัดการงานหลัก (Projects)", expanded=False):
        st.text_input("เพิ่มงาน", key='new_proj', on_change=update_db, args=('new_proj', 'projects'))
        if st.session_state['projects']:
            st.selectbox("ลบงาน", st.session_state['projects'], key='del_proj')
            st.button("ลบงาน", on_click=delete_db, args=('del_proj', 'projects'))

# ==========================================
# MAIN APP
# ==========================================
menu = st.radio("", ["📝 ลงทะเบียนงาน", "📊 Gantt Chart (ติดตามงาน)", "🛠️ อัพเดตความก้าวหน้า", "🏆 ประเมินผลงาน"], horizontal=True)
st.divider()

if menu == "📝 ลงทะเบียนงาน":
    col_left, col_right = st.columns([1, 1.5]) 
    with col_left:
        st.subheader("1. รายละเอียดงาน")
        proj = st.selectbox("โปรเจกต์หลัก", st.session_state['projects'] or ["No Data"], key="k_proj_sel")
        st.text_input("ชื่องานย่อย", key="k_sub", placeholder="เช่น ออกแบบ UX/UI")
        
        df_curr = st.session_state['data']
        dep_options = ["- เริ่มต้นใหม่ (ไม่รอใคร) -"]
        if not df_curr.empty and proj != "No Data":
            proj_tasks = df_curr[df_curr['Main_Task'] == proj].sort_values(by='End_Date', ascending=False)
            dep_options += proj_tasks['Sub_Task'].unique().tolist()
        st.selectbox("⏳ รอต่อจากงานไหน?", dep_options, key="k_dep_sel", on_change=auto_update_date)

    with col_right:
        st.subheader("2. มอบหมายและเวลา")
        st.multiselect("👥 ผู้รับผิดชอบ", st.session_state['employees'], key="k_emps_multi")
        c1, c2 = st.columns(2)
        with c1: st.date_input("เริ่มวันที่", key="k_d_start")
        with c2: st.date_input("ถึงวันที่", key="k_d_end")
        st.slider("ความคืบหน้า (%)", 0, 100, key="k_prog")
        st.text_area("📦 ผลลัพธ์", key="k_out", height=68)
        st.text_area("หมายเหตุ", key="k_issue", height=68, placeholder="ปล่อยว่างได้ ค่อยไปอัพเดตทีหลัง")
        st.button("บันทึกข้อมูล", on_click=submit_work_log, type="primary", use_container_width=True)

elif menu == "📊 Gantt Chart (ติดตามงาน)":
    st.caption("แผนภาพติดตามความคืบหน้า")
    df = calculate_status_and_score(st.session_state['data'].copy())
    if not df.empty: df = df[df['Employee'].isin(selected_emps)]
    
    if not df.empty:
        try:
            # Prepare Data for Chart
            df['Start'] = pd.to_datetime(df['Start_Date'], errors='coerce')
            df['End'] = pd.to_datetime(df['End_Date'], errors='coerce')
            df = df.dropna(subset=['Start', 'End'])

            df['Visual_End'] = df['End'] + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            
            def get_status_icon(p):
                if p == 100: return "✅"
                elif p == 0: return "⚪"
                else: return "🚧"
            
            df['Status_Icon'] = df['Progress'].apply(get_status_icon)
            df['Label_Text'] = df['Progress'].astype(str) + "%"
            
            view_mode = st.radio("รูปแบบ:", ["👤 รวมตามพนักงาน", "📝 แยกตามชื่องาน"], horizontal=True)
            
            # Zoom Logic
            if not df['Start'].isnull().all() and not df['End'].isnull().all():
                start_view = df['Start'].min() - timedelta(days=5)
                end_view = df['End'].max() + timedelta(days=5)
            else:
                start_view, end_view = datetime.now() - timedelta(days=7), datetime.now() + timedelta(days=14)
            
            # Plot
            df_chart = df.copy()
            if not df_chart.empty:
                df_chart['Dependency'] = df_chart['Dependency'].fillna("-")
                
                if "รวมตามพนักงาน" in view_mode:
                    y_axis, height_calc, opacity_val = "Employee", 120 + (len(df_chart['Employee'].unique()) * 50), 0.8
                else:
                    df_chart['Task_Display'] = df_chart['Status_Icon'] + " " + df_chart['Sub_Task']
                    y_axis, height_calc, opacity_val = "Task_Display", 150 + (len(df_chart) * 40), 1.0

                fig = px.timeline(
                    df_chart, x_start="Start", x_end="Visual_End", y=y_axis, color="Main_Task",
                    text="Label_Text", 
                    hover_data={"Sub_Task": True, "Output": True, "Progress": True, "Score": True, "Status": True, "Visual_End": False, "Start": False}, 
                    height=height_calc, template="plotly_white", opacity=opacity_val
                )
                
                fig.update_traces(textposition='inside', insidetextanchor='middle', textfont_size=11)
                fig.update_yaxes(autorange="reversed", title="")
                fig.update_xaxes(range=[start_view, end_view], tickformat="%d/%m", tickangle=-45, side="top", gridcolor="#eee")
                fig.update_layout(bargap=0.2, margin=dict(t=100, b=50), legend=dict(orientation="h", y=-0.2, x=0, xanchor="left", title=None))
                fig.add_vline(x=datetime.now().timestamp() * 1000, line_width=2, line_dash="dash", line_color="red", annotation_text="Today")
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Detail Table
                def highlight_late(row): return ['background-color: #ffcccc'] * len(row) if "ล่าช้า" in str(row['Status']) else [''] * len(row)
                st.write("### 📋 รายละเอียด")
                st.dataframe(
                    df_chart[['Employee', 'Main_Task', 'Sub_Task', 'Progress', 'Status', 'Score', 'End_Date']].style.apply(highlight_late, axis=1),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "Progress": st.column_config.ProgressColumn("Prog.", format="%d%%", min_value=0, max_value=100),
                        "Score": st.column_config.NumberColumn("Score", format="%d"),
                        "End_Date": st.column_config.DateColumn("Due")
                    }
                )
            else: st.info("ไม่พบข้อมูล")
        except Exception as e: st.error(f"Error: {e}")
    else: st.info("ไม่มีข้อมูล")

elif menu == "🛠️ อัพเดตความก้าวหน้า":
    st.caption("คลิกที่แถวงานที่ต้องการอัพเดต -> แล้วกดปุ่มแก้ไขด้านล่าง")
    df_display = calculate_status_and_score(st.session_state['data'])
    
    if not df_display.empty:
        event = st.dataframe(
            df_display[['Employee', 'Main_Task', 'Sub_Task', 'Progress', 'Status', 'End_Date', 'Issue']], 
            use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row",
            column_config={
                "Progress": st.column_config.ProgressColumn("Prog.", format="%d%%", min_value=0, max_value=100),
                "Issue": st.column_config.TextColumn("Last Issue (ย่อ)", width="medium")
            }
        )

        if event.selection.rows:
            idx = event.selection.rows[0]
            row_data = df_display.iloc[idx]
            st.info(f"👉 คุณเลือกงาน: **{row_data['Sub_Task']}** (โดย {row_data['Employee']})")
            if st.button("📝 อัพเดต & บันทึก Log", type="primary"): 
                update_task_dialog(idx, row_data)
        else: st.info("👆 กรุณาคลิกเลือกงานในตารางข้างบน เพื่อทำการอัพเดต")
    else: st.info("ยังไม่มีข้อมูลงานในระบบ")

elif menu == "🏆 ประเมินผลงาน":
    st.subheader("🏆 รายงานผลการปฏิบัติงาน")
    df_perf = calculate_status_and_score(st.session_state['data'].copy())
    if not df_perf.empty:
        df_perf['Year'] = pd.to_datetime(df_perf['End_Date'], errors='coerce').dt.year
        valid_years = df_perf['Year'].dropna().unique().tolist()
        if valid_years:
            years = sorted(valid_years, reverse=True)
            sel_year = st.selectbox("ปีงบประมาณ:", years)
            df_year = df_perf[df_perf['Year'] == sel_year]
            
            if not df_year.empty:
                summary = df_year.groupby('Employee').agg(
                    Total=('Sub_Task', 'count'), 
                    Avg=('Score', 'mean'), 
                    Late=('Status', lambda x: x.str.contains('ล่าช้า').sum())
                ).reset_index()
                
                summary['Avg'] = summary['Avg'].fillna(0)
                summary['OnTime%'] = ((summary['Total'] - summary['Late']) / summary['Total']) * 100
                summary['Grade'] = summary['Avg'].apply(lambda x: "A 🌟" if x>=90 else "B 👍" if x>=80 else "C 👌" if x>=70 else "D ⚠️")
                
                if not summary.empty:
                    best = summary.sort_values(by='Avg', ascending=False).iloc[0]
                    st.success(f"🥇 **Top Performer {sel_year}: {best['Employee']}** (Score: {best['Avg']:.1f})")
                
                c1, c2 = st.columns([2, 1])
                with c1: 
                    fig = px.bar(summary, x='Employee', y='Avg', color='Avg', color_continuous_scale='RdYlGn', text_auto='.1f')
                    fig.update_layout(yaxis_title="Average Score")
                    st.plotly_chart(fig, use_container_width=True)
                with c2: 
                    st.dataframe(
                        summary[['Employee', 'Total', 'Avg', 'OnTime%', 'Grade']], 
                        use_container_width=True, hide_index=True,
                        column_config={"Avg": st.column_config.NumberColumn(format="%.1f"), "OnTime%": st.column_config.ProgressColumn(format="%d%%", min_value=0, max_value=100)}
                    )
            else: st.info(f"ไม่มีงานในปี {sel_year}")
        else: st.info("ไม่มีข้อมูลปี (ตรวจสอบวันที่สิ้นสุดของงาน)")
    else: st.info("ไม่มีข้อมูล")