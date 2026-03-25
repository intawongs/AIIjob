import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import gspread

# ---------------------------------------------------------
# 1. CONFIGURATION & STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="AII Project Tracker V17.0", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
        .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #dee2e6; }
        [data-testid="stMetricValue"] { font-size: 1.8rem; color: #ff4b4b; }
        .stTabs [data-baseweb="tab"] { font-weight: bold; font-size: 1.1rem; }
        p, th, td { font-size: 16px; font-weight: 500; }
        .sidebar-content { padding: 10px; border-radius: 5px; background-color: #f1f3f4; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

st.title("🌌 AII Project Management System V17.0")

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
            
            for col in expected_logs:
                if col not in df_logs.columns: df_logs[col] = "" 
            
            if not df_logs.empty:
                df_logs['Start_Date'] = pd.to_datetime(df_logs['Start_Date'], errors='coerce')
                df_logs['End_Date'] = pd.to_datetime(df_logs['End_Date'], errors='coerce')
                df_logs['Progress'] = pd.to_numeric(df_logs['Progress'], errors='coerce').fillna(0)
            
            st.session_state['data'] = df_logs
            st.session_state['employees'] = df_emps['Name'].tolist() if not df_emps.empty else []
            st.session_state['projects_master'] = df_projs
            
            p_master = df_projs['Project'].dropna().unique().tolist() if not df_projs.empty else []
            p_logs = df_logs['Project'].dropna().unique().tolist() if not df_logs.empty else []
            st.session_state['projects_list'] = sorted(list(set(p_master + p_logs)))
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
            
            # 1. กำหนดรายชื่อคอลัมน์ที่ต้องมี (ป้องกันคอลัมน์หาย)
            expected_cols = [
                'Employee', 'Project', 'Main_Task', 'Sub_Task', 'Dependency', 
                'Start_Date', 'End_Date', 'Progress', 'Issue', 'Status'
            ]
            
            # 2. คัดลอกข้อมูลและตรวจสอบว่ามีคอลัมน์ครบไหม (ถ้าไม่มีให้สร้างคอลัมน์ว่าง)
            temp_df = df_to_save.copy()
            for col in expected_cols:
                if col not in temp_df.columns:
                    temp_df[col] = ""
            
            # 3. จัดระเบียบเรียงคอลัมน์ให้ตรงตามที่กำหนดไว้เสมอ
            temp_df = temp_df[expected_cols]

            # 4. จัดการเรื่องวันที่ (ป้องกัน NaT Error)
            for col in ['Start_Date', 'End_Date']:
                # แปลงเป็น datetime และเปลี่ยน format เป็น string, ถ้าว่างให้เป็น ""
                temp_df[col] = pd.to_datetime(temp_df[col], errors='coerce')
                temp_df[col] = temp_df[col].dt.strftime('%Y-%m-%d').fillna("")

            # 5. จัดการค่าว่างอื่นๆ (NaN, None) ให้เป็น "" และแปลงทุกอย่างเป็น String
            temp_df = temp_df.fillna("")
            
            # 6. เตรียมข้อมูลส่งออก (Header + Body)
            header = temp_df.columns.tolist()
            # แปลงทุก cell เป็น string เพื่อป้องกัน JSON Serializable Error
            body = temp_df.astype(str).values.tolist()
            
            # 7. อัปเดตลง Google Sheets
            ws_logs.clear()
            ws_logs.update(range_name="A1", values=[header] + body)
            
            return True
        except Exception as e:
            st.error(f"❌ Save Error: {e}")
            return False
    return False

if 'data' not in st.session_state:
    load_data()

# ==========================================
# 3. SIDEBAR (เมนูควบคุม)
# ==========================================
with st.sidebar:
    st.header("⚙️ เมนูควบคุม AII")
    if st.button("🔄 Sync ข้อมูลล่าสุด", use_container_width=True):
        st.cache_data.clear()
        load_data()
        st.rerun()
    
    st.divider()
    
    # --- จัดการพนักงาน ---
    with st.expander("👤 จัดการรายชื่อพนักงาน"):
        n_emp = st.text_input("ชื่อพนักงานใหม่", key="add_emp_side")
        if st.button("➕ บันทึกพนักงาน", use_container_width=True):
            if n_emp:
                sh = connect_gsheet()
                sh.worksheet('Employees').append_row([n_emp])
                st.success(f"เพิ่ม {n_emp} แล้ว")
                load_data()
                st.rerun()
        
        st.write("---")
        if st.session_state.get('employees'):
            del_emp = st.selectbox("เลือกชื่อที่ต้องการลบ", st.session_state['employees'], key="del_emp_side")
            if st.button("🗑️ ลบพนักงานคนนี้", type="secondary", use_container_width=True):
                sh = connect_gsheet()
                ws_e = sh.worksheet('Employees')
                all_names = ws_e.col_values(1)
                if del_emp in all_names:
                    row_idx = all_names.index(del_emp) + 1
                    ws_e.delete_rows(row_idx)
                    st.warning(f"ลบ {del_emp} แล้ว")
                    load_data()
                    st.rerun()

    # --- จัดการ Baseline โปรเจกต์ ---
    with st.expander("📂 จัดการ Baseline โปรเจกต์"):
        n_p = st.text_input("ชื่อโปรเจกต์ Baseline", key="add_proj_side")
        c1, c2 = st.columns(2)
        ps = c1.date_input("เริ่ม", key="add_proj_s")
        pe = c2.date_input("จบ", key="add_proj_e")
        if st.button("➕ บันทึก Baseline", use_container_width=True):
            if n_p:
                sh = connect_gsheet()
                sh.worksheet('Projects').append_row([n_p, ps.strftime('%Y-%m-%d'), pe.strftime('%Y-%m-%d')])
                st.success(f"เพิ่มโปรเจกต์ {n_p} แล้ว")
                load_data()
                st.rerun()
        
        st.write("---")
        master_projs = st.session_state.get('projects_master', pd.DataFrame())
        if not master_projs.empty:
            del_p = st.selectbox("เลือกโปรเจกต์ที่จะลบ", master_projs['Project'].tolist(), key="del_proj_side")
            if st.button("🗑️ ลบ Baseline นี้", type="secondary", use_container_width=True):
                sh = connect_gsheet()
                ws_p = sh.worksheet('Projects')
                all_projs = ws_p.col_values(1)
                if del_p in all_projs:
                    row_idx = all_projs.index(del_p) + 1
                    ws_p.delete_rows(row_idx)
                    st.warning(f"ลบ Baseline {del_p} แล้ว")
                    load_data()
                    st.rerun()

# ==========================================
# 4. MAIN INTERFACE
# ==========================================
tabs = st.tabs(["📝 ลงทะเบียน", "📊 Gantt Chart", "🛠️ แก้ไข/ลบข้อมูล", "🏆 Leaderboard", "📑 รายงาน"])

# --- TAB 0: ลงทะเบียน ---
with tabs[0]:
    st.subheader("📝 มอบหมายงานใหม่")
    df_curr = st.session_state.get('data', pd.DataFrame())
    p_list = st.session_state.get('projects_list', [])
    sel_p_reg = st.selectbox("📁 1. เลือกโปรเจกต์", p_list, key="reg_p_sel")
    
    filtered_mt = df_curr[df_curr['Project'] == sel_p_reg]['Main_Task'].unique().tolist() if not df_curr.empty and sel_p_reg else []
    
    with st.form("reg_form_v17", clear_on_submit=True):
        sel_mt = st.selectbox("📑 2. เลือกงานหลัก (เฟส)", ["-- สร้างงานรองใหม่ --"] + filtered_mt)
        new_mt = st.text_input("✨ หรือพิมพ์ชื่อเฟสใหม่")
        final_mt = new_mt if sel_mt == "-- สร้างงานรองใหม่ --" else sel_mt
        stk = st.text_input("📌 3. ชื่องานย่อย (Sub-task)")
        
        filtered_stk = df_curr[df_curr['Project'] == sel_p_reg]['Sub_Task'].unique().tolist() if not df_curr.empty and sel_p_reg else []
        sel_dep = st.selectbox("🔗 4. งานย่อยที่ต้องรอ (Dependency)", ["-- เริ่มได้ทันที --"] + filtered_stk)
        
        ems = st.multiselect("👥 5. ผู้รับผิดชอบ", st.session_state.get('employees', []))
        c1, c2 = st.columns(2)
        ds = c1.date_input("วันเริ่ม")
        de = c2.date_input("วันจบ")
        
        if st.form_submit_button("💾 บันทึกงาน", use_container_width=True):
            if final_mt and stk and ems:
                latest = st.session_state['data']
                new_rows = [{
                    'Employee': e, 'Project': sel_p_reg, 'Main_Task': final_mt, 
                    'Sub_Task': stk, 'Dependency': ("" if sel_dep == "-- เริ่มได้ทันที --" else sel_dep), 
                    'Start_Date': pd.to_datetime(ds), 'End_Date': pd.to_datetime(de), 
                    'Progress': 0, 'Status': '⏳ กำลังทำ'
                } for e in ems]
                updated = pd.concat([latest, pd.DataFrame(new_rows)], ignore_index=True)
                if save_data(updated):
                    st.success("บันทึกสำเร็จ!")
                    load_data()
                    st.rerun()

# --- TAB 1: Gantt Chart ---
# --- TAB 1: Gantt Chart (Isolation & Dynamic Project End-Date) ---
with tabs[1]:
    df_all = st.session_state.get('data', pd.DataFrame())
    
    if not df_all.empty:
        today = datetime.now().date()
        # กรองเฉพาะแถวที่มีวันจบ (ป้องกัน Error)
        df_valid = df_all.dropna(subset=['End_Date']).copy()
        
        # 1. ระบบ Alert งานล่าช้า (Grouped Alert)
        df_grouped = df_valid.groupby(['Project', 'Main_Task', 'Sub_Task', 'End_Date']).agg({
            'Employee': lambda x: ', '.join(x.unique()), 
            'Progress': 'mean'
        }).reset_index()
        
        late_tasks = df_grouped[(df_grouped['Progress'] < 100) & (df_grouped['End_Date'].dt.date < today)].copy()
        
        if not late_tasks.empty:
            st.error(f"🚩 ตรวจพบงานเลยกำหนดส่ง {len(late_tasks)} งาน")
            with st.expander("🔍 รายละเอียดงานที่เลยกำหนด", expanded=False):
                late_tasks['Days_Late'] = late_tasks['End_Date'].apply(lambda x: (today - x.date()).days)
                st.dataframe(
                    late_tasks[['Employee', 'Project', 'Sub_Task', 'End_Date', 'Days_Late', 'Progress']]
                    .style.highlight_max(subset=['Days_Late'], color='#ffcccc'), 
                    use_container_width=True, hide_index=True
                )

        # 2. ส่วนเลือกโปรเจกต์เพื่อแสดงผล Gantt
        sel_p = st.selectbox("📂 เลือกโปรเจกต์ที่จะแสดงผล:", st.session_state.get('projects_list', []), key="p_iso_v17")
        df_proj = df_all[df_all['Project'] == sel_p].copy().sort_values('Start_Date')
        
        if not df_proj.empty:
            p_pct = df_proj['Progress'].mean()
            st.metric(f"🚀 {sel_p} Overall Progress", f"{p_pct:.1f}%")
            
            # --- ส่วนคำนวณวันเริ่ม-จบโปรเจกต์แบบ Dynamic ---
            actual_start = df_proj['Start_Date'].min()
            actual_end = df_proj['End_Date'].max()

            master = st.session_state.get('projects_master', pd.DataFrame())
            if not master.empty and sel_p in master['Project'].values:
                p_info = master[master['Project'] == sel_p].iloc[0]
                base_s = pd.to_datetime(p_info['Start_Date'])
                base_e = pd.to_datetime(p_info['End_Date'])
                
                # Logic: เลือกวันที่ครอบคลุมที่สุด (เอาวันที่กว้างที่สุดระหว่างแผนกับงานจริง)
                p_s = min(base_s, actual_start) if not pd.isna(actual_start) else base_s
                p_e = max(base_e, actual_end) if not pd.isna(actual_end) else base_e
                # เพิ่ม 1 วันเพื่อให้แถบ Gantt แสดงผลถึงวันสุดท้ายพอดี
                p_e_display = p_e + pd.Timedelta(days=1)
                
                st.caption(f"📅 Baseline: {base_s.date()} ถึง {base_e.date()} | ปรับตามงานย่อยล่าสุดถึง: {actual_end.date() if not pd.isna(actual_end) else 'N/A'}")
            else:
                p_s = actual_start
                p_e_display = actual_end + pd.Timedelta(days=1)
            # --------------------------------------------
            
            SHADOW_COLOR = '#D5D8DC'
            plot_data = []
            
            # A. แถบภาพรวมโปรเจกต์ (Project Level)
            plot_data.append({'Task': f"🏢 {sel_p}", 'Start': p_s, 'End': p_e_display, 'Type': 'P_Plan', 'Label': '', 'Width': 0.8, 'Color': SHADOW_COLOR, 'Pos': 'inside'})
            plot_data.append({'Task': f"🏢 {sel_p}", 'Start': p_s, 'End': p_s+((p_e_display-p_s)*(p_pct/100)), 'Type': 'P_Act', 'Label': f"{int(p_pct)}%", 'Width': 0.8, 'Color': '#2C3E50', 'Pos': 'inside'})
            
            # B. แถบงานหลัก (Main Task Level)
            main_tasks_sorted = df_proj.groupby('Main_Task')['Start_Date'].min().sort_values().index
            colors = px.colors.qualitative.Prism
            for idx, mt in enumerate(main_tasks_sorted):
                df_mt = df_proj[df_proj['Main_Task'] == mt]
                g_col = colors[idx % len(colors)]
                ms, me, mp = df_mt['Start_Date'].min(), df_mt['End_Date'].max() + pd.Timedelta(days=1), df_mt['Progress'].mean()
                
                plot_data.append({'Task': f"📑 {mt}", 'Start': ms, 'End': me, 'Type': f'M_P_{idx}', 'Label': '', 'Width': 0.55, 'Color': SHADOW_COLOR, 'Pos': 'outside'})
                plot_data.append({'Task': f"📑 {mt}", 'Start': ms, 'End': ms+((me-ms)*(mp/100)), 'Type': f'M_A_{idx}', 'Label': f"{int(mp)}%", 'Width': 0.55, 'Color': g_col, 'Pos': 'outside'})
                
                # C. แถบงานย่อย (Sub Task Level)
                df_stk = df_mt.groupby(['Sub_Task', 'Dependency']).agg({'Start_Date':'min','End_Date':'max','Progress':'mean'}).reset_index().sort_values('Start_Date')
                for s_idx, srow in df_stk.iterrows():
                    ss, se, sp = srow['Start_Date'], srow['End_Date'] + pd.Timedelta(days=1), srow['Progress']
                    st_lab = f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;└ {srow['Sub_Task']}" + (f" (รอ: {srow['Dependency']})" if srow['Dependency'] else "")
                    
                    plot_data.append({'Task': st_lab, 'Start': ss, 'End': se, 'Type': f'S_P_{idx}_{s_idx}', 'Label': '', 'Width': 0.35, 'Color': SHADOW_COLOR, 'Pos': 'outside'})
                    plot_data.append({'Task': st_lab, 'Start': ss, 'End': ss+((se-ss)*(sp/100)), 'Type': f'S_A_{idx}_{s_idx}', 'Label': f"{int(sp)}%", 'Width': 0.35, 'Color': g_col, 'Pos': 'outside'})

            # 3. สร้าง Plotly Chart
            df_p = pd.DataFrame(plot_data)
            fig = px.timeline(df_p, x_start="Start", x_end="End", y="Task", color="Type", text="Label", height=len(plot_data)*28+150)
            
            fig.update_yaxes(categoryorder="array", categoryarray=df_p['Task'].unique()[::-1], tickfont=dict(size=16, family="Arial Black"), title="")
            
            for i, row in df_p.iterrows():
                f_col = "white" if row['Pos'] == 'inside' else "black"
                fig.update_traces(
                    marker_color=row['Color'], 
                    marker_line_color="black", 
                    marker_line_width=0.5, 
                    selector={'name': row['Type']}, 
                    patch={"width": row['Width'], "textposition": row['Pos'], "textfont": {"size": 14, "family": "Arial Black", "color": f_col}}
                )
            
            fig.update_layout(showlegend=False, barmode='overlay', margin=dict(r=150, l=250))
            fig.add_vline(x=datetime.now().timestamp()*1000, line_dash="solid", line_color="red", line_width=2)
            st.plotly_chart(fig, use_container_width=True)

            # 4. ระบบอัปเดตงาน (Sync ทั้งทีม)
            st.markdown("---")
            st.subheader("📱 ระบบอัปเดตงานด่วน")
            df_sum = df_proj.groupby(['Sub_Task', 'Main_Task']).agg({'Progress': 'mean'}).reset_index().sort_values('Sub_Task')
            ev = st.dataframe(df_sum, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
            
            if ev.selection.rows:
                sel = df_sum.iloc[ev.selection.rows[0]]
                with st.container(border=True):
                    st.markdown(f"### 📝 อัปเดตงาน: **{sel['Sub_Task']}**")
                    c1, c2 = st.columns(2)
                    up_p = c1.slider("% สำเร็จ", 0, 100, int(sel['Progress']))
                    up_i = c2.text_area("ปัญหาที่พบ/หมายเหตุ:")
                    
                    if st.button("🚀 บันทึกและ Sync ทั้งทีม", use_container_width=True, type="primary"):
                        # อัปเดตข้อมูลทุกแถวที่ชื่องานย่อยตรงกันในโปรเจกต์นี้
                        m = (df_all['Project']==sel_p) & (df_all['Sub_Task']==sel['Sub_Task'])
                        df_all.loc[m, 'Progress'] = up_p
                        if up_i: df_all.loc[m, 'Issue'] = up_i
                        df_all.loc[m, 'Status'] = "✅ เสร็จสมบูรณ์" if up_p == 100 else "⏳ กำลังทำ"
                        
                        if save_data(df_all):
                            st.cache_data.clear()
                            load_data()
                            st.rerun()

# --- TAB 2: แก้ไข/ลบข้อมูล (จุดที่มีบั๊กเดิม) ---
with tabs[2]:
    st.subheader("🛠️ แก้ไขข้อมูลดิบ (Admin)")
    # ดึงข้อมูลมาเป็น DF หลัก
    df_raw = st.session_state.get('data', pd.DataFrame()).copy()
    
    if not df_raw.empty:
        # แทรก Checkbox สำหรับเลือกลบ (จะไม่เซฟคอลัมน์นี้ลง Sheet)
        df_raw.insert(0, "เลือกเพื่อลบ", False)
        
        st.info("💡 วิธีลบ: ติ๊กถูกหน้าแถวที่ต้องการลบ แล้วกดปุ่มสีเทาด้านล่าง | วิธีแก้ไข: พิมพ์แก้ในตารางแล้วกดปุ่มสีแดง")
        
        # แสดง Data Editor
        edited_df = st.data_editor(
            df_raw, 
            column_config={
                "เลือกเพื่อลบ": st.column_config.CheckboxColumn("🗑️ ลบ?", default=False),
                "Progress": st.column_config.NumberColumn(min_value=0, max_value=100)
            },
            hide_index=True, 
            use_container_width=True,
            key="raw_data_editor"
        )
        
        c1, c2 = st.columns(2)
        
        # 1. บันทึกการแก้ไข (Update ข้อมูลที่แก้ในตาราง)
        if c1.button("💾 บันทึกการแก้ไขข้อมูล", type="primary", use_container_width=True):
            # เอาเฉพาะแถวที่ไม่ได้ติ๊ก 'เลือกลบ' และลบคอลัมน์ checkbox ออกก่อนเซฟ
            final_to_save = edited_df.drop(columns=["เลือกเพื่อลบ"])
            # เช็ค Status อัตโนมัติ
            final_to_save.loc[final_to_save['Progress'] >= 100, 'Status'] = "✅ เสร็จสมบูรณ์"
            final_to_save.loc[final_to_save['Progress'] < 100, 'Status'] = "⏳ กำลังทำ"
            
            if save_data(final_to_save):
                st.success("อัปเดตข้อมูลเรียบร้อยแล้ว!")
                load_data()
                st.rerun()

        # 2. ปุ่มลบ (จะลบเฉพาะแถวที่ติ๊กถูก)
        if c2.button("🗑️ ยืนยันลบรายการที่เลือก", use_container_width=True):
            # คัดเฉพาะแถวที่ไม่ได้ถูกติ๊กถูก (False) เพื่อเก็บไว้
            data_to_keep = edited_df[edited_df["เลือกเพื่อลบ"] == False].drop(columns=["เลือกเพื่อลบ"])
            
            # ถ้าจำนวนแถวน้อยลง แสดงว่ามีการเลือกเพื่อลบจริง
            if len(data_to_keep) < len(df_raw):
                if save_data(data_to_keep):
                    st.warning(f"ลบรายการออก {len(df_raw) - len(data_to_keep)} รายการแล้ว")
                    load_data()
                    st.rerun()
            else:
                st.info("กรุณาติ๊กถูกในช่อง 'ลบ?' หน้าแถวที่ต้องการลบก่อนกดปุ่มนี้")

# --- TAB 3: Leaderboard ---
with tabs[3]:
    st.subheader("🏆 Leaderboard")
    df_all = st.session_state.get('data', pd.DataFrame())
    if not df_all.empty:
        ld = df_all.groupby('Employee')['Progress'].mean().reset_index().sort_values('Progress', ascending=False)
        st.plotly_chart(px.bar(ld, x='Employee', y='Progress', color='Progress', color_continuous_scale="Viridis"), use_container_width=True)

# --- TAB 4: Report ---
with tabs[4]:
    st.subheader("📑 รายงานภาพรวม")
    df_all = st.session_state.get('data', pd.DataFrame())
    st.dataframe(df_all, use_container_width=True)
    st.download_button("📥 โหลด CSV", df_all.to_csv(index=False).encode('utf-8-sig'), f"Report_{date.today()}.csv")

# จบโค้ด