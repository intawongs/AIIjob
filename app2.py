import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V12.1", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #007bff; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V12.1")

# ==========================================
# 2. DATA ENGINE (Google Sheets)
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
    # รายชื่อคอลัมน์ทั้งหมดที่ระบบต้องใช้
    expected_logs = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Dependency', 'Start_Date', 'End_Date', 'Progress', 'Issue', 'Status']
    sh = connect_gsheet()
    if sh:
        try:
            ws_logs = sh.worksheet('Logs')
            ws_emps = sh.worksheet('Employees')
            ws_projs = sh.worksheet('Projects')

            df_logs = pd.DataFrame(ws_logs.get_all_records())
            df_projs = pd.DataFrame(ws_projs.get_all_records())
            df_emps = pd.DataFrame(ws_emps.get_all_records())

            # 🔥 ป้องกัน KeyError: ถ้าไม่มีคอลัมน์ใน Sheets ให้สร้างคอลัมน์ว่างใน DataFrame ทันที
            for col in expected_logs:
                if col not in df_logs.columns:
                    df_logs[col] = "" 

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
            # กรองเอาคอลัมน์ Action ต่างๆ ออกก่อนเซฟ (ถ้ามี)
            cols_to_keep = ['Employee', 'Project', 'Main_Task', 'Sub_Task', 'Dependency', 'Start_Date', 'End_Date', 'Progress', 'Issue', 'Status']
            save_df = save_df[cols_to_keep]
            
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
    st.header("⚙️ ระบบ AII")
    if st.button("🔄 Sync ข้อมูลล่าสุด", use_container_width=True):
        st.cache_data.clear()
        load_data()
        st.rerun()
    st.divider()
    with st.expander("👤 รายชื่อทีมงาน"):
        n_emp = st.text_input("ชื่อเล่นพนักงาน")
        if st.button("เพิ่มพนักงาน"):
            sh = connect_gsheet(); sh.worksheet('Employees').append_row([n_emp]); st.rerun()
    with st.expander("📂 Baseline โปรเจกต์"):
        n_p = st.text_input("ชื่อโปรเจกต์")
        c1, c2 = st.columns(2)
        ps = c1.date_input("เริ่มงาน"); pe = c2.date_input("จบงาน")
        if st.button("บันทึกโปรเจกต์"):
            sh = connect_gsheet(); sh.worksheet('Projects').append_row([n_p, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')]); st.rerun()

# ==========================================
# 4. MAIN TABS
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 แผนผังงาน (Gantt)", "🛠️ แก้ไข/ลบข้อมูล", "🏆 อันดับผลงาน", "📑 รายงาน"])

# --- TAB 0: ลงทะเบียน (พร้อม Dependency) ---
with tabs[0]:
    st.subheader("📝 มอบหมายงานใหม่")
    df_curr = st.session_state.get('data', pd.DataFrame())
    with st.form("reg_form_v12_1", clear_on_submit=True):
        p = st.selectbox("📁 1. เลือกโปรเจกต์", st.session_state.get('projects_list', []))
        
        # เลือก Main Task
        existing_mt = ["-- สร้างงานรองใหม่ --"]
        if not df_curr.empty and p:
            mt_list = df_curr[df_curr['Project'] == p]['Main_Task'].unique().tolist()
            existing_mt.extend(mt_list)
        sel_mt = st.selectbox("📑 2. เลือกงานรอง (Main Task)", existing_mt)
        new_mt = st.text_input("✨ หรือพิมพ์ชื่อเฟส/งานรองใหม่")
        final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        
        stk = st.text_input("📌 3. ชื่องานย่อย (Sub-task)")
        
        # 🔗 Dependency selection
        existing_stk = ["-- เริ่มได้ทันที --"]
        if not df_curr.empty and p:
            stk_list = df_curr[df_curr['Project'] == p]['Sub_Task'].unique().tolist()
            existing_stk.extend(stk_list)
        sel_dep = st.selectbox("🔗 4. งานย่อยที่ต้องเสร็จก่อน (Dependency)", existing_stk)
        final_dep = "" if sel_dep == "-- เริ่มได้ทันที --" else sel_dep

        ems = st.multiselect("👥 5. ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2)
        ds, de = c1.date_input("📅 วันเริ่ม"), c2.date_input("🏁 วันจบ")
        
        if st.form_submit_button("💾 บันทึกลงระบบ AII", use_container_width=True):
            if final_mt and stk and ems:
                latest = st.session_state['data']
                new_data = [{'Employee': e, 'Project': p, 'Main_Task': final_mt, 'Sub_Task': stk, 'Dependency': final_dep, 'Start_Date': pd.to_datetime(ds), 'End_Date': pd.to_datetime(de), 'Progress': 0, 'Status': '⏳ กำลังทำ'} for e in ems]
                updated = pd.concat([latest, pd.DataFrame(new_data)], ignore_index=True)
                if save_data(updated):
                    st.success(f"✅ บันทึกงาน '{stk}' เรียบร้อย"); st.rerun()

# --- TAB 1: แผนผังงาน (Ultimate Gantt V12.1) ---
with tabs[1]:
    df_all = st.session_state.get('data', pd.DataFrame())
    if not df_all.empty:
        sel_p = st.selectbox("📂 โปรเจกต์ที่ต้องการดู:", df_all['Project'].unique().tolist(), key="p_gantt_v12_1")
        df_proj = df_all[df_all['Project'] == sel_p].copy()
        
        # Baseline check
        master = st.session_state.get('projects_master', pd.DataFrame())
        if not master.empty and sel_p in master['Project'].values:
            p_info = master[master['Project'] == sel_p].iloc[0]
            p_s, p_e = pd.to_datetime(p_info['Start_Date']), pd.to_datetime(p_info['End_Date']) + pd.Timedelta(days=1)
        else:
            p_s, p_e = df_proj['Start_Date'].min(), df_proj['End_Date'].max() + pd.Timedelta(days=1)
        
        p_pct = df_proj['Progress'].mean()
        st.metric(f"🚀 Overall Progress: {sel_p}", f"{p_pct:.1f}%")

        plot_data = []
        # Level 1: Project (Layer 1: Shadow, Layer 2: Actual)
        p_lab = f"🏢 {sel_p}"
        plot_data.append({'Task': p_lab, 'Start': p_s, 'End': p_e, 'Type': 'P_Plan', 'Label': '', 'Width': 0.8, 'Color': '#E5E8E8', 'Pos': 'inside'})
        plot_data.append({'Task': p_lab, 'Start': p_s, 'End': p_s+((p_e-p_s)*(p_pct/100)), 'Type': 'P_Act', 'Label': f"{int(p_pct)}%", 'Width': 0.8, 'Color': '#2C3E50', 'Pos': 'inside'})
        
        # Level 2 & 3
        main_tasks = df_proj['Main_Task'].unique()
        colors = px.colors.qualitative.Prism
        for idx, mt in enumerate(main_tasks):
            df_mt_group = df_proj[df_proj['Main_Task'] == mt]
            group_col = colors[idx % len(colors)]
            mt_s, mt_e, mt_pct = df_mt_group['Start_Date'].min(), df_mt_group['End_Date'].max()+pd.Timedelta(days=1), df_mt_group['Progress'].mean()
            
            mt_lab = f"📑 {mt}"
            plot_data.append({'Task': mt_lab, 'Start': mt_s, 'End': mt_e, 'Type': f'M_P_{idx}', 'Label': '', 'Width': 0.55, 'Color': '#F2F3F4', 'Pos': 'outside'})
            plot_data.append({'Task': mt_lab, 'Start': mt_s, 'End': mt_s+((mt_e-mt_s)*(mt_pct/100)), 'Type': f'M_A_{idx}', 'Label': f"{int(mt_pct)}%", 'Width': 0.55, 'Color': group_col, 'Pos': 'outside'})
            
            # Sub Task grouping with Dependency check
            df_stk_list = df_mt_group.groupby(['Sub_Task', 'Dependency']).agg({'Start_Date': 'min', 'End_Date': 'max', 'Progress': 'mean'}).reset_index().sort_values('Start_Date')
            for s_idx, srow in df_stk_list.iterrows():
                ss, se, st_pct = srow['Start_Date'], srow['End_Date']+pd.Timedelta(days=1), srow['Progress']
                dep_info = f" (รอ: {srow['Dependency']})" if srow['Dependency'] else ""
                st_lab = f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└ {srow['Sub_Task']}{dep_info}"
                
                plot_data.append({'Task': st_lab, 'Start': ss, 'End': se, 'Type': f'S_P_{idx}_{s_idx}', 'Label': '', 'Width': 0.35, 'Color': '#FDFEFE', 'Pos': 'outside'})
                plot_data.append({'Task': st_lab, 'Start': ss, 'End': ss+((se-ss)*(st_pct/100)), 'Type': f'S_A_{idx}_{s_idx}', 'Label': f"{int(st_pct)}%", 'Width': 0.35, 'Color': group_col, 'Pos': 'outside'})

        df_p = pd.DataFrame(plot_data)
        fig = px.timeline(df_p, x_start="Start", x_end="End", y="Task", color="Type", text="Label", height=len(df_p)*28 + 150)
        for i, row in df_p.iterrows():
            f_col = "white" if row['Pos'] == 'inside' else "black"
            fig.update_traces(marker_color=row['Color'], selector={'name': row['Type']}, patch={"width": row['Width'], "textposition": row['Pos'], "textfont": {"size": 15, "family": "Arial Black", "color": f_col}})
        
        fig.update_yaxes(categoryorder="array", categoryarray=df_p['Task'].unique()[::-1], tickfont=dict(size=16, family="Arial Black", color="black"), title="")
        fig.update_layout(showlegend=False, margin=dict(r=150, l=250), barmode='overlay')
        fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="solid", line_color="red", line_width=2)
        st.plotly_chart(fig, use_container_width=True)

        # Interactive Table Under Gantt
        st.markdown("---")
        st.subheader("🔍 รายละเอียดคนทำงาน")
        df_summary = df_proj.groupby(['Sub_Task', 'Main_Task', 'Dependency']).agg({'Progress': 'mean'}).reset_index()
        event = st.dataframe(df_summary, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if event.selection.rows:
            idx = event.selection.rows[0]
            sel_sub = df_summary.iloc[idx]['Sub_Task']
            team = df_proj[df_proj['Sub_Task'] == sel_sub]
            st.markdown(f"### 👥 ทีมงานรับผิดชอบ: {sel_sub}")
            for _, r in team.iterrows():
                c1, c2, c3 = st.columns([2, 5, 1])
                c1.markdown(f"**👤 {r['Employee']}**")
                c2.progress(int(r['Progress'])/100)
                c3.write(f"{int(r['Progress'])}%")

# --- TAB 2: แก้ไข/ลบข้อมูล (Full CRUD) ---
with tabs[2]:
    st.subheader("🛠️ การจัดการข้อมูลดิบ (แก้ไข / ลบ)")
    df_raw = st.session_state.get('data', pd.DataFrame()).copy()
    if not df_raw.empty:
        df_raw.insert(0, "Action", False)
        edited_df = st.data_editor(
            df_raw, 
            column_config={
                "Action": st.column_config.CheckboxColumn("เลือก", default=False),
                "Progress": st.column_config.NumberColumn("Progress (%)", min_value=0, max_value=100),
                "Status": st.column_config.SelectboxColumn("สถานะ", options=["⏳ กำลังทำ", "✅ เสร็จสมบูรณ์", "⚠️ ติดปัญหา"])
            }, 
            hide_index=True, use_container_width=True, key="admin_editor_v12_1"
        )
        
        c1, c2 = st.columns(2)
        if c1.button("💾 บันทึกการอัปเดต", use_container_width=True, type="primary"):
            # Auto Status Logic: 100% -> Complete
            edited_df.loc[edited_df['Progress'] == 100, 'Status'] = "✅ เสร็จสมบูรณ์"
            final_df = edited_df.drop(columns=["Action"])
            if save_data(final_df):
                st.success("✅ อัปเดตข้อมูลเรียบร้อย!"); st.rerun()
        
        if c2.button("🗑️ ลบรายการที่ติ๊กเลือก", use_container_width=True):
            to_del = edited_df[edited_df["Action"] == True]
            if not to_del.empty:
                if any(to_del['Progress'] == 100):
                    st.error("❌ ไม่อนุญาตให้ลบงานที่เสร็จสิ้น 100% แล้ว")
                else:
                    final_rem = edited_df[edited_df["Action"] == False].drop(columns=["Action"])
                    if save_data(final_rem):
                        st.warning(f"⚠️ ลบข้อมูล {len(to_del)} รายการแล้ว"); st.rerun()
            else:
                st.error("กรุณาเลือกแถวที่จะลบก่อนครับ")

# --- TABS 3 & 4: Rankings & Reports ---
with tabs[3]:
    st.subheader("🏆 Leaderboard")
    if not df_all.empty:
        ld = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        st.plotly_chart(px.bar(ld, x='Employee', y='Progress', color='Progress', text_auto='.1f'), use_container_width=True)

with tabs[4]:
    st.subheader("📑 Project Summary")
    if not df_all.empty:
        st.dataframe(df_all.groupby(['Project', 'Main_Task'])['Progress'].mean().reset_index(), use_container_width=True)
        csv = df_all.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Download Report (CSV)", data=csv, file_name=f"AII_Report_{date.today()}.csv")