import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Management V6", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #007bff; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V6")

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
    expected_logs = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Start_Date', 'End_Date', 'Progress', 'Issue', 'Status']
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            ws_emps = sh.worksheet('Employees')
            ws_projs = sh.worksheet('Projects')

            df_logs = pd.DataFrame(ws_logs.get_all_records())
            df_projs = pd.DataFrame(ws_projs.get_all_records())
            df_emps = pd.DataFrame(ws_emps.get_all_records())

            for col in expected_logs:
                if col not in df_logs.columns: df_logs[col] = ""
            
            if not df_logs.empty:
                df_logs['Start_Date'] = pd.to_datetime(df_logs['Start_Date'], errors='coerce')
                df_logs['End_Date'] = pd.to_datetime(df_logs['End_Date'], errors='coerce')
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)

            st.session_state['data'] = df_logs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects_master'] = df_projs
            st.session_state['projects_list'] = df_projs['Project'].dropna().unique().tolist() if not df_projs.empty else []
            return df_logs
        except Exception as e:
            st.error(f"Load Error: {e}")
            return pd.DataFrame(columns=expected_logs)
    return pd.DataFrame()

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

if 'data' not in st.session_state:
    load_data()

# ==========================================
# 3. SIDEBAR
# ==========================================
with st.sidebar:
    st.header("⚙️ ระบบหลังบ้าน")
    if st.button("🔄 รีเฟรชข้อมูล (Sync Now)", use_container_width=True):
        st.cache_data.clear()
        load_data()
        st.rerun()
    
    st.divider()
    with st.expander("👤 รายชื่อทีมงาน"):
        st.write(st.session_state.get('employees', []))
        n_emp = st.text_input("เพิ่มชื่อเล่นพนักงาน")
        if st.button("บันทึกพนักงาน"):
            sh = connect_gsheet(); sh.worksheet('Employees').append_row([n_emp]); st.rerun()

    with st.expander("📂 กำหนดโปรเจกต์ (Baseline)"):
        n_p = st.text_input("ชื่อโปรเจกต์ใหม่")
        c1, c2 = st.columns(2)
        ps = c1.date_input("วันเริ่มงาน", key="p_start"); pe = c2.date_input("วันจบงาน", key="p_end")
        if st.button("บันทึกโปรเจกต์"):
            sh = connect_gsheet(); sh.worksheet('Projects').append_row([n_p, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')]); st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผังงาน (Gantt)", "🛠️ แก้ไข/ลบข้อมูล", "🏆 อันดับผลงาน", "📑 รายงาน"])

# --- TAB 0: ลงทะเบียนงาน ---
with tabs[0]:
    st.subheader("📝 มอบหมายงาน (3 ระดับ)")
    df_curr = st.session_state.get('data', pd.DataFrame())
    with st.form("reg_form_v6", clear_on_submit=True):
        p = st.selectbox("📁 1. เลือกโปรเจกต์", st.session_state.get('projects_list', []))
        
        # ค้นหา Main Task เก่า
        existing_mt = ["-- สร้างงานรองใหม่ --"]
        if not df_curr.empty and p:
            mt_list = df_curr[df_curr['Project'] == p]['Main_Task'].unique().tolist()
            existing_mt.extend(mt_list)
        
        sel_mt = st.selectbox("📑 2. เลือกงานรอง (Main Task)", existing_mt)
        new_mt = st.text_input("✨ หรือพิมพ์งานรองใหม่ที่นี่")
        final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        
        stk = st.text_input("📌 3. ชื่องานย่อย (Sub-task)")
        ems = st.multiselect("👥 4. พนักงานผู้รับผิดชอบ", st.session_state.get('employees', []))
        
        c1, c2 = st.columns(2)
        ds, de = c1.date_input("วันเริ่ม"), c2.date_input("วันจบ")
        
        if st.form_submit_button("💾 บันทึกงานสู่ระบบ", use_container_width=True):
            if final_mt and stk and ems:
                latest = st.session_state['data']
                new_rows = [{'Employee': e, 'Project': p, 'Main_Task': final_mt, 'Sub_Task': stk, 'Start_Date': pd.to_datetime(ds), 'End_Date': pd.to_datetime(de), 'Progress': 0, 'Status': '⏳ กำลังทำ'} for e in ems]
                updated = pd.concat([latest, pd.DataFrame(new_rows)], ignore_index=True)
                if save_data(updated):
                    st.success("✅ บันทึกสำเร็จ"); st.rerun()

# --- TAB 1: แผนผังงาน (Ultimate Gantt) ---
with tabs[1]:
    df_all = st.session_state.get('data', pd.DataFrame())
    if not df_all.empty:
        # 1. เลือกโปรเจกต์
        available_p = df_all['Project'].unique().tolist()
        sel_p = st.selectbox("📂 ดูแผนผังโปรเจกต์:", available_p, key="p_gantt_v9")
        
        df_proj = df_all[df_all['Project'] == sel_p].copy()
        
        # --- Baseline Logic ---
        master = st.session_state.get('projects_master', pd.DataFrame())
        if not master.empty and sel_p in master['Project'].values:
            p_info = master[master['Project'] == sel_p].iloc[0]
            p_s, p_e = pd.to_datetime(p_info['Start_Date']), pd.to_datetime(p_info['End_Date']) + pd.Timedelta(days=1)
        else:
            p_s, p_e = df_proj['Start_Date'].min(), df_proj['End_Date'].max() + pd.Timedelta(days=1)

        p_pct = df_proj['Progress'].mean()
        st.metric(f"📊 Overall: {sel_p}", f"{p_pct:.1f}%")

        # --- ส่วนวาดกราฟ (Gantt) ---
        plot_data = []
        # ระดับ Project
        p_label = f"🏢 {sel_p}"
        plot_data.append({'Task': p_label, 'Start': p_s, 'End': p_e, 'Type': 'P_Plan', 'Label': '', 'Width': 0.8, 'Color': '#E5E7E9', 'Pos': 'inside'})
        p_act_e = p_s + ((p_e - p_s) * (p_pct / 100))
        plot_data.append({'Task': p_label, 'Start': p_s, 'End': p_act_e, 'Type': 'P_Act', 'Label': f"{int(p_pct)}%", 'Width': 0.8, 'Color': '#2C3E50', 'Pos': 'inside'})

        main_tasks = df_proj['Main_Task'].unique()
        colors = px.colors.qualitative.Prism 
        
        for idx, mt in enumerate(main_tasks):
            df_mt_group = df_proj[df_proj['Main_Task'] == mt]
            group_col = colors[idx % len(colors)]
            mt_s, mt_e, mt_pct = df_mt_group['Start_Date'].min(), df_mt_group['End_Date'].max()+pd.Timedelta(days=1), df_mt_group['Progress'].mean()
            
            mt_lab = f"📑 {mt}"
            plot_data.append({'Task': mt_lab, 'Start': mt_s, 'End': mt_e, 'Type': f'M_P_{idx}', 'Label': '', 'Width': 0.5, 'Color': '#F2F3F4', 'Pos': 'outside'})
            plot_data.append({'Task': mt_lab, 'Start': mt_s, 'End': mt_s+(mt_e-mt_s)*(mt_pct/100), 'Type': f'M_A_{idx}', 'Label': f"{int(mt_pct)}%", 'Width': 0.5, 'Color': group_col, 'Pos': 'outside'})
            
            df_stk_list = df_mt_group.groupby('Sub_Task').agg({'Start_Date': 'min', 'End_Date': 'max', 'Progress': 'mean'}).reset_index().sort_values('Start_Date')
            for s_idx, srow in df_stk_list.iterrows():
                ss, se, st_pct = srow['Start_Date'], srow['End_Date']+pd.Timedelta(days=1), srow['Progress']
                st_lab = f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└ {srow['Sub_Task']}"
                plot_data.append({'Task': st_lab, 'Start': ss, 'End': se, 'Type': f'S_P_{idx}_{s_idx}', 'Label': '', 'Width': 0.3, 'Color': '#FBFCFC', 'Pos': 'outside'})
                plot_data.append({'Task': st_lab, 'Start': ss, 'End': ss+(se-ss)*(st_pct/100), 'Type': f'S_A_{idx}_{s_idx}', 'Label': f"{int(st_pct)}%", 'Width': 0.3, 'Color': group_col, 'Pos': 'outside'})

        df_p = pd.DataFrame(plot_data)
        fig = px.timeline(df_p, x_start="Start", x_end="End", y="Task", color="Type", text="Label", height=len(df_p)*25+150)
        for i, row in df_p.iterrows():
            f_col = "white" if row['Pos'] == 'inside' else "black"
            fig.update_traces(marker_color=row['Color'], selector={'name': row['Type']}, patch={"width": row['Width'], "textposition": row['Pos'], "textfont": {"size": 13, "family": "Arial Black", "color": f_col}})
        fig.update_yaxes(categoryorder="array", categoryarray=df_p['Task'].unique()[::-1], title="")
        fig.update_layout(showlegend=False, margin=dict(r=120))
        st.plotly_chart(fig, use_container_width=True)

        # --- 🔥 ส่วนที่ดึงกลับมา: ตารางแสดงรายละเอียดคนทำ ---
        st.markdown("---")
        st.subheader("🔍 ตรวจสอบรายละเอียดงานและผู้รับผิดชอบ")
        st.caption("💡 คลิกเลือกแถวในตารางด้านล่าง เพื่อดูรายชื่อพนักงานและบันทึกปัญหา (Issue)")
        
        # สรุปข้อมูลงานย่อย (ไม่ซ้ำแถวคน) เพื่อให้เลือกง่าย
        df_summary = df_proj.groupby(['Sub_Task', 'Main_Task']).agg({
            'Progress': 'mean',
            'Start_Date': 'min',
            'End_Date': 'max'
        }).reset_index()

        # ตาราง Interactive สำหรับการคลิก
        event = st.dataframe(
            df_summary[['Sub_Task', 'Main_Task', 'Progress']], 
            use_container_width=True, 
            hide_index=True, 
            on_select="rerun", 
            selection_mode="single-row"
        )

        # เมื่อมีการคลิกเลือกแถว
        if event.selection.rows:
            idx = event.selection.rows[0]
            selected_sub = df_summary.iloc[idx]['Sub_Task']
            selected_main = df_summary.iloc[idx]['Main_Task']
            
            # ดึงรายชื่อพนักงานทุกคนที่อยู่ใน Sub_Task นี้
            team_info = df_proj[(df_proj['Sub_Task'] == selected_sub) & (df_proj['Main_Task'] == selected_main)]
            
            with st.expander(f"👥 รายชื่อทีมงานสำหรับ: {selected_sub}", expanded=True):
                for _, row in team_info.iterrows():
                    c1, c2 = st.columns([1, 3])
                    c1.write(f"👤 **{row['Employee']}**")
                    c2.progress(int(row['Progress'])/100)
                    if row['Issue']:
                        st.warning(f"🚩 **Issue:** {row['Issue']}")

# --- TAB 2: แก้ไข/ลบข้อมูล (Full Admin) ---
# --- TAB 2: จัดการข้อมูล (ฉบับ Smart Status Check) ---
with tabs[2]:
    st.subheader("🛠️ ระบบจัดการงาน AII (Smart Status Control)")
    df_raw = st.session_state.get('data', pd.DataFrame()).copy()
    
    if not df_raw.empty:
        st.info("💡 แก้ไข Progress เป็น 100 เพื่อให้ระบบเปลี่ยนสถานะเป็น 'เสร็จสิ้น' อัตโนมัติ")
        
        # เพิ่มคอลัมน์เลือกหน้าสุด
        if "Select" not in df_raw.columns:
            df_raw.insert(0, "Select", False)
            
        edited_df = st.data_editor(
            df_raw,
            column_config={
                "Select": st.column_config.CheckboxColumn("เลือก", default=False),
                "Progress": st.column_config.NumberColumn("Progress (%)", min_value=0, max_value=100),
                "Status": st.column_config.SelectboxColumn("สถานะ", options=["⏳ กำลังทำ", "✅ เสร็จสมบูรณ์", "⚠️ ติดปัญหา"])
            },
            hide_index=True,
            use_container_width=True,
            key="admin_editor_v8"
        )

        selected_rows = edited_df[edited_df["Select"] == True]
        
        c1, c2 = st.columns(2)
        
        # --- 💾 ปุ่มบันทึกการแก้ไข (พร้อมระบบเช็ค 100%) ---
        if c1.button("💾 ยืนยันการอัปเดตข้อมูล", type="primary", use_container_width=True):
            # 🔥 Logic พิเศษ: ถ้า Progress = 100 ให้ปรับ Status เป็น "เสร็จสมบูรณ์" อัตโนมัติ
            def auto_status(row):
                if row['Progress'] == 100:
                    return "✅ เสร็จสมบูรณ์"
                elif row['Progress'] > 0:
                    return "⏳ กำลังทำ"
                return row['Status']

            # สั่งรัน Logic เปลี่ยนสถานะกับทุกแถวที่แก้ไข
            edited_df['Status'] = edited_df.apply(auto_status, axis=1)
            
            final_df = edited_df.drop(columns=["Select"])
            if save_data(final_df):
                st.success("✅ อัปเดตข้อมูลและสถานะเรียบร้อยแล้ว!")
                st.session_state['data'] = final_df
                st.rerun()

        # --- 🗑️ ปุ่มลบ (ต้องเลือกก่อน) ---
        if c2.button("🗑️ ยืนยันการลบงานที่เลือก", use_container_width=True):
            if not selected_rows.empty:
                # เช็ค Progress ก่อนลบตามที่คุณวรายุต้องการ
                if any(selected_rows['Progress'] == 100):
                    st.error("❌ ห้ามลบงานที่เสร็จ 100% แล้ว (โปรดแก้ Progress ลงก่อนถ้าต้องการลบจริงๆ)")
                else:
                    remaining_df = edited_df[edited_df["Select"] == False].drop(columns=["Select"])
                    if save_data(remaining_df):
                        st.warning(f"🗑️ ลบงานออกไป {len(selected_rows)} รายการแล้ว")
                        st.session_state['data'] = remaining_df
                        st.rerun()
            else:
                st.error("❌ กรุณา 'ติ๊กเลือก' งานที่จะลบก่อนครับ")

# --- TAB 3: อันดับผลงาน ---
with tabs[3]:
    st.subheader("🏆 Leaderboard")
    if not df_all.empty:
        ld = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        st.plotly_chart(px.bar(ld, x='Employee', y='Progress', color='Progress', text_auto='.1f', title="Success Rate (%)"), use_container_width=True)

# --- TAB 4: รายงาน ---
with tabs[4]:
    st.subheader("📑 รายงานสรุป")
    if not df_all.empty:
        st.dataframe(df_all.groupby(['Project', 'Main_Task'])['Progress'].mean().reset_index(), use_container_width=True)
        st.download_button("📥 โหลดรายงาน (CSV)", data=df_all.to_csv(index=False).encode('utf-8-sig'), file_name=f"AII_Report_{date.today()}.csv")