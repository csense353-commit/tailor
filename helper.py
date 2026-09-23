import json
from supabase import create_client
import streamlit as st

def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

supabase = init_supabase()

def load_data(filename):
    try:
        # Download file bytes from Supabase Storage
        response = supabase.storage.from_("app-data").download(filename)
        return json.loads(response.decode("utf-8"))
    except Exception:
        # If the file doesn't exist yet, return an empty dictionary
        return {}

def add_data(filename, new_data, key_id):
    try:
        current_data = load_data(filename)
        current_data[str(key_id)] = new_data
        
        # Convert dictionary to JSON string and upload (upsert=true overwrites/updates the file)
        json_data = json.dumps(current_data, indent=4)
        supabase.storage.from_("app-data").upload(
            filename,
            json_data.encode("utf-8"),
            file_options={"upsert": "true", "content-type": "application/json"}
        )
        return True
    except Exception as e:
        print(f"Error saving data: {e}")
        return False

def update_order_status(filename, order_id, new_status):
    try:
        current_data = load_data(filename)
        if str(order_id) in current_data:
            current_data[str(order_id)]["Status"] = new_status
            
            json_data = json.dumps(current_data, indent=4)
            supabase.storage.from_("app-data").upload(
                filename,
                json_data.encode("utf-8"),
                file_options={"upsert": "true", "content-type": "application/json"}
            )
            return True
        return False
    except Exception as e:
        print(f"Error updating status: {e}")
        return False

def delete_order(filename, order_id):
    try:
        # 1. Remove order from JSON data
        current_data = load_data(filename)
        string_order_id = str(order_id)
        
        if string_order_id in current_data:
            del current_data[string_order_id]
            
            # Re-upload updated JSON file
            json_data = json.dumps(current_data, indent=4)
            supabase.storage.from_("app-data").upload(
                filename,
                json_data.encode("utf-8"),
                file_options={"upsert": "true", "content-type": "application/json"}
            )
        
        # 2. Find and delete associated images from Supabase Storage 'client-images'
        files_response = supabase.storage.from_("client-images").list()
        matched_files = [
            f["name"] for f in files_response 
            if f["name"].startswith(f"{int(order_id)}_")
        ]
        
        if matched_files:
            supabase.storage.from_("client-images").remove(matched_files)
            
        return True
    except Exception as e:
        print(f"Error deleting order: {e}")
        return False