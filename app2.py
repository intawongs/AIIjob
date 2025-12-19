import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread
import time

# ---------------------------------------------------------
# 1. การตั้งค่า (CONFIGURATION)
# ---------------------------------------------------------
st.set_page_config(page_title="ระบบติดตามงาน AII", layout="wide")
st.title("🌌 ระบบติดตามงาน AII (AII Project Tracker)")

# ==========================================
# 2. เชื่อมต่อ GOOGLE SHEETS
# ==========================================
def connect_gsheet():
    """เชื่อมต่อ Google Sheets แบบ Native GSpread Auth"""
    try:
        if "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
            if "\\n" in creds_dict["private_key"]:
                creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
            client = gspread.service_account_from_dict(creds_dict)
        else:
            client = gspread.service_account(filename='credentials.json')

        sh = client.open("Chronos_Data") 
        return sh
    except Exception as e:
        st.error(f"❌ ไม่สามารถเชื่อมต่อ Google Sheets: {e}")
        return None

# ==========================================
# 3. ระบบจัดการข้อมูล (LOAD & SAVE)
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
            df_emps = pd.DataFrame(data_emps)
            df_projs = pd.DataFrame(data_projs)

            # คอลัมน์ที่ต้องมี (ภาษาอังกฤษไว้เก็บข้อมูล แต่แสดงผลไทย)
            expected_cols = ['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']
            if df_logs.empty:
                df_logs = pd.DataFrame(columns=expected_cols)
            else:
                for col in expected_cols:
                    if col not in df_logs.columns: df_logs[col] = None

            if not df_logs.empty:
                for col in ['Start_Date', 'End_Date']:
                    df_logs[col] = pd.to_datetime(df_logs[col], errors='coerce').dt.date
                df_logs['Progress'] = df_logs['Progress'].fillna(0)
                df_logs['Score'] = df_logs['Score'].fillna(0)
                df_logs['Issue'] = df_logs['Issue'].fillna("").astype(str)
                df_logs['Output'] = df_logs['Output'].fillna("").astype(str)
                df_logs['Status'] = df_logs['Status'].fillna("⏳ กำลังดำเนินการ")

            emp_list = df_emps['Name'].tolist() if not df_emps.empty and 'Name' in df_emps.columns else []
            proj_list = df_projs['Project'].tolist() if not df_projs.empty and 'Project' in df_projs.columns else []

            return df_logs, emp_list, proj_list
        except Exception as e:
            st.error(f"เกิดข้อผิดพลาดในการอ่านข้อมูล: {e}")
            return pd.DataFrame(columns=['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']), [], []
    return pd.DataFrame(), [], []

def save_data():
    """บันทึกข้อมูลแบบ Atomic Write (เขียนทับรวดเดียว)"""
    sh = connect_gsheet()
    if sh:
        # บันทึกงาน (LOGS)
        try:
            ws_logs = sh.worksheet('Logs')
            save_df = st.session_state['data'].copy()
            save_df['Start_Date'] = save_df['Start_Date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (date, datetime)) else "")
            save_df['End_Date'] = save_df['End_Date'].apply(lambda x: x.strftime('%Y-%m-%d') if isinstance(x, (date, datetime)) else "")
            
            cols = ['Employee', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Output', 'Issue', 'Dependency', 'Progress', 'Score', 'Status']
            for c in cols: 
                if c not in save_df.columns: save_df[c] = ""
            
            all_values = [cols]
            if not save_df.empty: all_values.extend(save_df[cols].values.tolist())
            
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=all_values)
        except Exception as e: print(f"Log Save Error: {e}")

        # บันทึกพนักงาน (EMPLOYEES)
        try:
            ws_emps = sh.worksheet('Employees')
            emp_data = [['Name']] + [[x] for x in st.session_state['employees']]
            ws_emps.clear()
            ws_emps.update(range_name="A1", values=emp_data)
        except: pass

        # บันทึกโปรเจกต์ (PROJECTS)
        try:
            ws_projs = sh.worksheet('Projects')
            proj_data = [['Project']] + [[x] for x in st.session_state['projects']]
            ws_projs.clear()
            ws_projs.update(range_name="A1", values=proj_data)
        except: pass

def update_db(key, list_name):
    val = st.session_state.get(key)
    if val and val not in st.session_state[list_name]:
        st.session_state[list_name].append(val)
        save_data()
        st.session_state[key] = "" # ล้างช่องกรอกข้อมูล
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
# 4. ตั้งค่าเริ่มต้น (INITIALIZE STATE)
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
# 5. ฟังก์ชันช่วยคำนวณ (HELPER)
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

# ตัวแปรสำหรับตั้งชื่อหัวตารางภาษาไทย
THAI_COLS = {
    "Employee": "พนักงาน",
    "Main_Task": "โปรเจกต์",
    "Sub_Task": "ชื่องาน",
    "Progress": "ความคืบหน้า",
    "Status": "สถานะ",
    "End_Date": "กำหนดส่ง",
    "Issue": "บันทึกล่าสุด",
    "Score": "คะแนน",
    "Total": "งานทั้งหมด",
    "Avg": "คะแนนเฉลี่ย",
    "OnTime%": "ส่งตรงเวลา (%)",
    "Grade": "เกรด",
    "Late": "งานล่าช้า"
}

# ==========================================
# 6. หน้าต่างแก้ไขงาน (DIALOG)
# ==========================================
@st.dialog("📝 จัดการงาน (แก้ไข / ลบ)")
def update_task_dialog(index, row_data):
    st.write(f"**งาน:** {row_data['Sub_Task']}")
    st.write(f"**ผู้รับผิดชอบ:** {row_data['Employee']}")
    st.markdown("---")
    
    new_prog = st.slider("ความคืบหน้า (%)", 0, 100, int(row_data['Progress']))
    new_output = st.text_input("ผลลัพธ์ / ลิงก์งาน", value=str(row_data['Output']))
    
    st.markdown("---")
    st.caption("สมุดบันทึก (Log Book)")
    current_log = str(row_data['Issue'])
    mode = st.radio("โหมดบันทึก:", ["➕ เพิ่มบันทึกใหม่", "✏️ แก้ไขประวัติทั้งหมด"], horizontal=True)
    
    final_log = current_log
    if "เพิ่มบันทึก" in mode:
        if current_log: st.info(current_log)
        new_entry = st.text_area("บันทึกวันนี้:", height=80, placeholder="พิมพ์สิ่งที่ทำไปวันนี้...")
    else:
        full_edit = st.text_area("แก้ไขประวัติทั้งหมด:", value=current_log, height=150)

    st.markdown("---")
    
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("💾 บันทึกการแก้ไข", type="primary", use_container_width=True):
            if "เพิ่มบันทึก" in mode:
                if new_entry.strip():
                    ts = datetime.now().strftime("%d/%m")
                    final_log += f"\n- [{ts}] {new_entry.strip()}"
            else: final_log = full_edit
            
            st.session_state['data'].at[index, 'Progress'] = new_prog
            st.session_state['data'].at[index, 'Output'] = new_output
            st.session_state['data'].at[index, 'Issue'] = final_log.strip()
            save_data()
            st.toast("บันทึกข้อมูลเรียบร้อย", icon="💾")
            st.rerun()
            
    with c2:
        if st.button("ยกเลิก", use_container_width=True):
            st.rerun()

    if st.button("🗑️ ลบงานนี้ทิ้ง", type="secondary", use_container_width=True):
        st.session_state['data'] = st.session_state['data'].drop(index).reset_index(drop=True)
        save_data() 
        st.toast("🗑️ ลบงานเรียบร้อยแล้ว", icon="🗑️")
        st.rerun()

# ==========================================
# 7. ส่วนแสดงผลหลัก (UI MAIN)
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
        
        # Clear Inputs
        st.session_state.k_sub = ""
        st.session_state.k_out = ""
        st.session_state.k_issue = ""
        st.session_state.k_prog = 0
        st.session_state.k_emps_multi = []
        st.toast(f"✅ บันทึกงานให้ {len(emps)} คนเรียบร้อย", icon="💾")
    else: st.toast("❌ ข้อมูลไม่ครบ กรุณาตรวจสอบอีกครั้ง", icon="⚠️")

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ ตั้งค่า")
    if st.button("🔄 รีเฟรชข้อมูลล่าสุด", use_container_width=True):
        st.cache_data.clear()
        logs, emps, projs = load_data()
        if logs is not None:
            st.session_state['data'] = logs
            st.session_state['employees'] = emps
            st.session_state['projects'] = projs
            st.rerun()

    st.markdown("---")
    all_emps = st.session_state['employees']
    sel_emps = st.multiselect("กรองชื่อพนักงาน:", all_emps, default=all_emps)
    st.markdown("---")
    
    with st.expander("👤 จัดการพนักงาน"):
        st.text_input("เพิ่มชื่อ", key='new_emp', on_change=update_db, args=('new_emp', 'employees'))
        if st.session_state['employees']:
            st.selectbox("ลบชื่อ", st.session_state['employees'], key='del_emp')
            st.button("ลบรายชื่อ", on_click=delete_db, args=('del_emp', 'employees'))
            
    with st.expander("📂 จัดการโปรเจกต์"):
        st.text_input("เพิ่มงาน", key='new_proj', on_change=update_db, args=('new_proj', 'projects'))
        if st.session_state['projects']:
            st.selectbox("ลบงาน", st.session_state['projects'], key='del_proj')
            st.button("ลบโปรเจกต์", on_click=delete_db, args=('del_proj', 'projects'))

# --- MAIN MENU ---
menu = st.radio("", ["📝 ลงทะเบียนงาน", "📊 แผนผังงาน (Gantt Chart)", "🛠️ อัพเดตความก้าวหน้า", "🏆 ประเมินผลงาน"], horizontal=True)
st.divider()

if menu == "📝 ลงทะเบียนงาน":
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("1. รายละเอียดงาน")
        p = st.selectbox("โปรเจกต์", st.session_state['projects'] or ["ไม่มีข้อมูล"], key="k_proj_sel")
        st.text_input("ชื่องาน", key="k_sub", placeholder="เช่น ออกแบบ UX/UI")
        df = st.session_state['data']
        dep_opt = ["- เริ่มต้นใหม่ (ไม่รอใคร) -"]
        if not df.empty and p != "ไม่มีข้อมูล":
            dep_opt += df[df['Main_Task'] == p].sort_values('End_Date', ascending=False)['Sub_Task'].unique().tolist()
        st.selectbox("รอต่องานไหน?", dep_opt, key="k_dep_sel", on_change=auto_update_date)
    with c2:
        st.subheader("2. มอบหมาย")
        st.multiselect("ผู้รับผิดชอบ", st.session_state['employees'], key="k_emps_multi")
        c2a, c2b = st.columns(2)
        with c2a: st.date_input("เริ่มวันที่", key="k_d_start")
        with c2b: st.date_input("ถึงวันที่", key="k_d_end")
        st.slider("ความคืบหน้า (%)", 0, 100, key="k_prog")
        st.text_area("ผลลัพธ์ / ลิงก์งาน", key="k_out", height=68)
        st.text_area("บันทึกช่วยจำ (Log Book)", key="k_issue", height=68)
        st.button("บันทึกข้อมูล", on_click=submit_work, type="primary", use_container_width=True)

elif menu == "📊 แผนผังงาน (Gantt Chart)":
    df = calculate_status_and_score(st.session_state['data'].copy())
    if not df.empty: df = df[df['Employee'].isin(sel_emps)]
    if not df.empty:
        df['Start'] = pd.to_datetime(df['Start_Date'], errors='coerce')
        df['End'] = pd.to_datetime(df['End_Date'], errors='coerce')
        df = df.dropna(subset=['Start', 'End'])
        df['Visual_End'] = df['End'] + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        df['Label'] = df['Progress'].astype(str) + "%"
        
        mode = st.radio("มุมมอง:", ["ดูตามพนักงาน", "ดูตามงาน"], horizontal=True)
        y_ax = "Employee" if "พนักงาน" in mode else "Sub_Task"
        
        fig = px.timeline(df, x_start="Start", x_end="Visual_End", y=y_ax, color="Main_Task", text="Label", height=400 + (len(df)*20))
        fig.update_yaxes(autorange="reversed", title="")
        fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="dash", line_color="red", annotation_text="วันนี้")
        st.plotly_chart(fig, use_container_width=True)
        
        def highlight(row): return ['background-color: #ffcccc'] * len(row) if "ล่าช้า" in str(row['Status']) else [''] * len(row)
        st.write("### 📋 รายละเอียด")
        st.dataframe(
            df[['Employee', 'Main_Task', 'Sub_Task', 'Progress', 'Status', 'End_Date']].style.apply(highlight, axis=1), 
            use_container_width=True,
            column_config={
                "Employee": st.column_config.TextColumn(THAI_COLS["Employee"]),
                "Main_Task": st.column_config.TextColumn(THAI_COLS["Main_Task"]),
                "Sub_Task": st.column_config.TextColumn(THAI_COLS["Sub_Task"]),
                "Progress": st.column_config.ProgressColumn(THAI_COLS["Progress"], format="%d%%", min_value=0, max_value=100),
                "Status": st.column_config.TextColumn(THAI_COLS["Status"]),
                "End_Date": st.column_config.DateColumn(THAI_COLS["End_Date"]),
            }
        )
    else: st.info("ยังไม่มีข้อมูล")

elif menu == "🛠️ อัพเดตความก้าวหน้า":
    st.info("💡 คลิกเลือกงานในตาราง -> กดปุ่มแก้ไขด้านล่าง (มีปุ่มลบงานในนั้น)")
    df = calculate_status_and_score(st.session_state['data'])
    if not df.empty:
        event = st.dataframe(
            df[['Employee', 'Sub_Task', 'Progress', 'Status', 'End_Date']], 
            use_container_width=True, on_select="rerun", selection_mode="single-row",
            column_config={
                "Employee": st.column_config.TextColumn(THAI_COLS["Employee"]),
                "Sub_Task": st.column_config.TextColumn(THAI_COLS["Sub_Task"]),
                "Progress": st.column_config.ProgressColumn(THAI_COLS["Progress"], format="%d%%", min_value=0, max_value=100),
                "Status": st.column_config.TextColumn(THAI_COLS["Status"]),
                "End_Date": st.column_config.DateColumn(THAI_COLS["End_Date"]),
            }
        )
        if event.selection.rows:
            idx = event.selection.rows[0]
            if st.button(f"✏️ แก้ไข / ลบ: {df.iloc[idx]['Sub_Task']}", type="primary"):
                update_task_dialog(idx, df.iloc[idx])
    else:
        st.info("ยังไม่มีข้อมูลงานในระบบ")

elif menu == "🏆 ประเมินผลงาน":
    df = calculate_status_and_score(st.session_state['data'].copy())
    if not df.empty:
        df['Year'] = pd.to_datetime(df['End_Date'], errors='coerce').dt.year
        yrs = df['Year'].dropna().unique().tolist()
        if yrs:
            sy = st.selectbox("เลือกปีงบประมาณ:", sorted(yrs, reverse=True))
            dfy = df[df['Year'] == sy]
            if not dfy.empty:
                sum_df = dfy.groupby('Employee').agg(Total=('Sub_Task','count'), Avg=('Score','mean'), Late=('Status', lambda x: x.str.contains('ล่าช้า').sum())).reset_index()
                sum_df['Avg'] = sum_df['Avg'].fillna(0)
                sum_df['OnTime%'] = ((sum_df['Total'] - sum_df['Late']) / sum_df['Total']) * 100
                sum_df['Grade'] = sum_df['Avg'].apply(lambda x: "A" if x>=90 else "B" if x>=80 else "C" if x>=70 else "D")
                
                # Winner
                if not sum_df.empty:
                    best = sum_df.sort_values(by='Avg', ascending=False).iloc[0]
                    st.success(f"🥇 **สุดยอดพนักงานปี {sy}: {best['Employee']}** (คะแนน: {best['Avg']:.1f})")

                c1, c2 = st.columns([2, 1])
                with c1:
                    fig = px.bar(sum_df, x='Employee', y='Avg', color='Avg', color_continuous_scale='RdYlGn', text_auto='.1f')
                    fig.update_layout(yaxis_title="คะแนนเฉลี่ย")
                    st.plotly_chart(fig, use_container_width=True)
                with c2:
                    st.dataframe(
                        sum_df, 
                        use_container_width=True, hide_index=True,
                        column_config={
                            "Employee": st.column_config.TextColumn(THAI_COLS["Employee"]),
                            "Total": st.column_config.NumberColumn(THAI_COLS["Total"]),
                            "Avg": st.column_config.NumberColumn(THAI_COLS["Avg"], format="%.1f"),
                            "Late": st.column_config.NumberColumn(THAI_COLS["Late"]),
                            "OnTime%": st.column_config.ProgressColumn(THAI_COLS["OnTime%"], format="%d%%", min_value=0, max_value=100),
                            "Grade": st.column_config.TextColumn(THAI_COLS["Grade"]),
                        }
                    )
            else: st.info("ไม่มีข้อมูลสำหรับปีนี้")
        else: st.info("ไม่พบปีที่มีข้อมูล (กรุณาตรวจสอบวันที่สิ้นสุดของงาน)")
    else: st.info("ยังไม่มีข้อมูล")