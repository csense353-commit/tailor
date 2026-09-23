import json
import pandas as pd
import os
import streamlit as st
from datetime import date, datetime, timedelta
import winsound
from helper import load_data, add_data, update_order_status,delete_order,supabase

st.set_page_config(layout="wide", page_title="Tailor", page_icon="🪡")

@st.dialog("⚠️ Urgent & Delayed Deliveries Alert!", dismissible=False, width="large")
def show_delivery_alert(delayed_df, urgent_df):
    if not delayed_df.empty:
        st.error("🚨 **Delayed Orders (Past Due!)**")
        st.dataframe(delayed_df, use_container_width=True)
        
    if not urgent_df.empty:
        st.warning("⚠️ **Due Today or Tomorrow**")
        st.dataframe(urgent_df, use_container_width=True)
    
    # Optional Python beep (Windows only)
    try:
        winsound.Beep(2500, 600)
    except Exception:
        pass
    
    if st.button("Acknowledge & Stop Alarm", use_container_width=True):
        st.session_state.delivery_alert_acknowledged = True
        st.rerun()

def login():
    st.title("Track Order")
    o_id = st.text_input("Enter Order ID or Mobile No.")
    
    if o_id == "tailor":    
        clients = load_data("clients.json")
        orders = load_data("orders.json")
        
        tab1, tab2, tab3, tab4 = st.tabs(["Orders", "Add Order", "Update Order", "Update Client"])
        
        with tab1:
            st.header("Orders Dashboard")
            if orders:
                df_orders = pd.DataFrame.from_dict(orders, orient='index')

                if "Delivery" in df_orders.columns:
                    df_orders["Delivery_dt"] = pd.to_datetime(df_orders["Delivery"]).dt.date
                    
                    today = date.today()
                    tomorrow = today + timedelta(days=1)
                    
                    # 1. Delayed orders (Delivery date < today and not delivered)
                    delayed_orders = df_orders[
                        (df_orders["Delivery_dt"] < today) & 
                        (df_orders["Status"] != "DELIVERED")
                    ].drop(columns=["Delivery_dt"])
                    
                    # 2. Urgent orders (Delivery date is today or tomorrow and not delivered)
                    urgent_orders = df_orders[
                        (df_orders["Delivery_dt"].isin([today, tomorrow])) & 
                        (df_orders["Status"] != "DELIVERED")
                    ].drop(columns=["Delivery_dt"])
                    
                    # Trigger dialog if either list has orders and user hasn't acknowledged yet
                    if (not delayed_orders.empty or not urgent_orders.empty) and not st.session_state.get("delivery_alert_acknowledged", False):
                        show_delivery_alert(delayed_orders, urgent_orders)

                    # Sort regular dashboard table normally for display
                    df_orders["Delivery"] = pd.to_datetime(df_orders["Delivery"])
                    df_orders = df_orders.sort_values(by="Delivery", ascending=True)
                    df_orders["Delivery"] = df_orders["Delivery"].dt.date
                    
                    if "Delivery_dt" in df_orders.columns:
                        df_orders = df_orders.drop(columns=["Delivery_dt"])

                st.dataframe(df_orders, use_container_width=True)
            else:
                st.info("No orders have been added yet.")

        with tab2:
            st.header("Add Order")
            c_num = st.text_input("Client Mobile No.")
            if c_num:
                res = clients.get(c_num)
                if res:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.image("measure_t.png")
                    with col2:
                        st.markdown("* All Measurements In INCHES")
                        st.table(res)
                    with col3:
                        if not orders:
                            order_id = 1
                        else:
                            order_id = max([int(k) for k in orders.keys()]) + 1
                            
                        st.markdown(f"*Order ID: {order_id}*")
                        st.markdown(f"*Date: {date.today()}*")
                        del_date = st.date_input("Delivery Date", min_value=date.today())
                        items = st.number_input("Items", step=1, min_value=1)
                        note = st.text_area("Note", max_chars=500)
                        
                        uploaded_files = st.file_uploader("Choose images...", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)
                        
                        if st.button("Add Order", use_container_width=True):
                            saved_count = 0
                            if uploaded_files:
                                for index, uploaded_file in enumerate(uploaded_files):
                                    file_extension = os.path.splitext(uploaded_file.name)[1]
                                    new_filename = f"{order_id}_{index + 1}{file_extension}"
                                    file_bytes = uploaded_file.getvalue()

                                    # Upload bytes to Supabase Storage bucket 'client-images'
                                    supabase.storage.from_("client-images").upload(
                                        new_filename,
                                        file_bytes,
                                        file_options={"upsert": "true"}
                                    )
                                    saved_count += 1
                                    
                            order_data = {
                                "Date": str(datetime.today().date()),
                                "Delivery": str(del_date),
                                "Items": items,
                                "Note": note,
                                "Client": c_num,
                                "Status": "PENDING"
                            }
                            
                            if add_data("orders.json", order_data, str(order_id)):
                                st.toast(f"Order Added with {saved_count} images", duration="long")
                                try:
                                    winsound.Beep(2500, 600)
                                except Exception:
                                    pass
                                st.rerun()
                else:
                    st.warning("Client NOT FOUND!")
            else:
                st.info("Enter Client Mobile No. to Continue.")

        with tab3:
            st.header("Update Order")
            or_id = st.number_input("Order ID", step=1, key="up_order_input")
            
            if or_id:
                string_or_id = str(int(or_id))
                
                if string_or_id in orders:
                    order_info = orders[string_or_id]
                    
                    cc1, cc2, cc3 = st.columns(3)
                    with cc1:
                        st.table(order_info)
                    with cc3:
                        st.subheader("Attached Order Images")
                        try:
                            files_response = supabase.storage.from_("client-images").list()
                            matched_images = [
                                f["name"] for f in files_response 
                                if f["name"].startswith(f"{int(or_id)}_")
                            ]

                            if matched_images:
                                img_cols = st.columns(min(len(matched_images), 3))
                                for idx, img_file in enumerate(matched_images):
                                    public_url = supabase.storage.from_("client-images").get_public_url(img_file)
                                    with img_cols[idx % len(img_cols)]:
                                        st.image(public_url, caption=img_file, width=150)
                            else:
                                st.info("No images found for this order.")
                        except Exception:
                            st.info("Could not load images from cloud storage.")
                            
                    with cc2:
                        current_status = order_info.get("Status", "PENDING")
                        status_options = ["PENDING", "CUTTING", "STITCHING", "FINISHING", "IRONING", "READY", "DELIVERED"]
                        
                        default_value = current_status if current_status in status_options else status_options[0]
                        
                        new_status = st.select_slider("Order Status", options=status_options, value=default_value, key=f"slider_{or_id}")
                        
                        if st.button("Update Status", key=f"btn_update_status_{or_id}", use_container_width=True):
                            if update_order_status("orders.json", int(or_id), new_status):
                                st.success(f"Order Status updated to **{new_status}**!")
                                try:
                                    winsound.Beep(2500, 600)
                                except Exception:
                                    pass
                                    
                                st.rerun()
                            else:
                                st.error("Failed to update status.")
                        
                        st.divider()
                        
                        # --- DELETE ORDER SECTION ---
                        st.markdown("### Delete Order")
                        if st.button("🗑️ Delete Order & Images", key=f"btn_delete_{or_id}", use_container_width=True):
                            if delete_order("orders.json", int(or_id)):
                                st.success(f"Order #{or_id} and its images have been deleted successfully!")
                                try:
                                    winsound.Beep(2500, 600)
                                except Exception:
                                    pass
                                
                                st.rerun()
                            else:
                                st.error("Failed to delete order.")
                else:
                    st.info(f"Order ID {or_id} not found.")
            else:
                st.info("Enter Order ID to continue.")    
        with tab4:
            st.header("Update Client")
            s_c_num = st.text_input("Enter Client Mobile No.")
            
            if s_c_num and len(s_c_num) < 10:
                st.warning("Enter a valid 10-digit Client Mobile No.")
                st.stop()
                
            if s_c_num:
                res = clients.get(s_c_num)
                if res:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.image("measure_t.png")
                    with col2:
                        st.markdown("* All Measurements In INCHES")
                        # Added s_c_num to keys so they refresh when the mobile number changes
                        h = st.number_input("Shoulder Height", value=float(res.get("Height", 0)), key=f"up_h_{s_c_num}")
                        al = st.number_input("Arm Length", value=float(res.get("Arm Length", 0)), key=f"up_al_{s_c_num}")
                        ll = st.number_input("Leg Length", value=float(res.get("Leg Length", 0)), key=f"up_ll_{s_c_num}")
                        th = st.number_input("Thigh", value=float(res.get("Thigh", 0)), key=f"up_th_{s_c_num}")
                        hip = st.number_input("Hip", value=float(res.get("Hip", 0)), key=f"up_hip_{s_c_num}")
                        w = st.number_input("Waist", value=float(res.get("Waist", 0)), key=f"up_w_{s_c_num}")
                        c = st.number_input("Chest", value=float(res.get('Chest', 0)), key=f"up_c_{s_c_num}")
                        ap = st.number_input("Armpit", value=float(res.get('Armpit', 0)), key=f"up_ap_{s_c_num}")
                        sh = st.number_input("Shoulder", value=float(res.get("Shoulder", 0)), key=f"up_sh_{s_c_num}")
                        b = st.number_input('Bicep', value=float(res.get("Bicep", 0)), key=f"up_b_{s_c_num}")
                        
                        if st.button("Update Client Data", key=f"btn_update_{s_c_num}", use_container_width=True):
                            data = {"Height": h, "Arm Length": al, "Leg Length": ll, "Thigh": th, "Hip": hip, "Waist": w, 'Chest': c, 'Armpit': ap, "Shoulder": sh, "Bicep": b}
                            if add_data("clients.json", data, s_c_num):
                                st.success("Client Updated Successfully!")
                                try:
                                    winsound.Beep(2500, 600)
                                except Exception:
                                    pass
                                
                                st.rerun()
                            else:
                                st.error("Failed to update client data.")
                else:
                    st.info("Client not found. Fill details below to add a new client.")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.image("measure_t.png")
                    with col2:
                        st.markdown("* All Measurements In INCHES")
                        h = st.number_input("Shoulder Height", key=f"new_h_{s_c_num}")
                        al = st.number_input("Arm Length", key=f"new_al_{s_c_num}")
                        ll = st.number_input("Leg Length", key=f"new_ll_{s_c_num}")
                        th = st.number_input("Thigh", key=f"new_th_{s_c_num}")
                        hip = st.number_input("Hip", key=f"new_hip_{s_c_num}")
                        w = st.number_input("Waist", key=f"new_w_{s_c_num}")
                        c = st.number_input("Chest", key=f"new_c_{s_c_num}")
                        ap = st.number_input("Armpit", key=f"new_ap_{s_c_num}")
                        sh = st.number_input("Shoulder", key=f"new_sh_{s_c_num}")
                        b = st.number_input('Bicep', key=f"new_b_{s_c_num}")
                        
                        if st.button("Add New Client", key=f"btn_add_{s_c_num}", use_container_width=True):
                            data = {"Height": h, "Arm Length": al, "Leg Length": ll, "Thigh": th, "Hip": hip, "Waist": w, 'Chest': c, 'Armpit': ap, "Shoulder": sh, "Bicep": b}
                            if add_data("clients.json", data, s_c_num):
                                st.success("New Client Added!")
                                try:
                                    winsound.Beep(2500, 600)
                                except Exception:
                                    pass
                                
                                st.rerun()
                            else:
                                st.error("Failed to save new client.")
            else:
                st.info('Enter Client Mobile No. to continue.')

    elif o_id != "":
        orders = load_data("orders.json")
        
        if len(o_id) > 9:
            s_order_data = {k: v for k, v in orders.items() if v.get("Client") == o_id}
        elif len(o_id) < 9:
            order_info = orders.get(o_id)
            s_order_data = {o_id: order_info} if order_info else {}
        else:
            s_order_data = {}
        
        if s_order_data:
            cc1, cc2, cc3 = st.columns(3)
            
            with cc1:
                st.subheader("Order Details")
                if len(o_id) > 9:
                    df_client_orders = pd.DataFrame.from_dict(s_order_data, orient='index')
                    st.dataframe(df_client_orders, use_container_width=True)
                else:
                    st.table(list(s_order_data.values())[0])
                    
            with cc2:
                if len(o_id) < 9:
                    single_order_id = o_id
                    single_order_info = list(s_order_data.values())[0]
                    current_status = single_order_info.get("Status", "PENDING")
                    st.header(f"STATUS: {current_status}")
                    # Fixed syntax error (changed double quotes inside f-string to single quotes)
                    st.header(f"DELIVERY: {single_order_info.get('Delivery')}")
                        
            with cc3:
                st.subheader("Attached Order Images")
                if len(o_id) < 9:
                    try:
                        files_response = supabase.storage.from_("client-images").list()
                        matched_images = [
                            f["name"] for f in files_response 
                            if f["name"].startswith(f"{int(o_id)}_")
                        ]
                        if matched_images:
                            img_cols = st.columns(min(len(matched_images), 3))
                            for idx, img_file in enumerate(matched_images):
                                public_url = supabase.storage.from_("client-images").get_public_url(img_file)
                                with img_cols[idx % len(img_cols)]:
                                    st.image(public_url, caption=img_file, width=120)
                        else:
                            st.info("No images found for this order.")
                    except Exception:
                        st.info("Could not load images from cloud storage.")
                else:
                    st.info("Images are shown for single Order ID lookups.")
                    st.info("Enter order ID in Above Field")
        else:
            st.warning("No records found matching that ID or Mobile Number.")
    else:
        st.info("Enter Order ID or Mobile No. to continue")

login()