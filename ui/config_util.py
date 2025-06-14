import wx
import wx.grid
import wx.html2
import json
import os

# --- Constants ---
CONFIG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'private_devbot_ui_config.json')

# --- Utility Functions ---
def load_json_config():
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if 'page_size' not in config:
                config['page_size'] = 30
            if 'monitoring_interval' not in config:
                config['monitoring_interval'] = 10

            return config
        except (json.JSONDecodeError, IOError) as e:
            wx.LogError(f"Error loading config file {CONFIG_FILE_PATH}: {e}")
            raise e

def load_initial_json_config():
    if not os.path.exists(CONFIG_FILE_PATH):
        return {'page_size': 30, 'monitoring_interval': 10}
    
    try:
        with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)

        if 'page_size' not in config:
            config['page_size'] = 30
        if 'monitoring_interval' not in config:
            config['monitoring_interval'] = 10

        return config
    except Exception as e:
        wx.LogError(f"Error loading config file {CONFIG_FILE_PATH}: {e}")
        return {'page_size': 30, 'monitoring_interval': 10}
        

def save_json_config(config_data):
    try:
        with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
    except IOError as e:
        wx.LogError(f"Error saving config file {CONFIG_FILE_PATH}: {e}")

def save_port_config(port:int):
    if port is None:
        print("[Error] port is None")
        return

    config = load_json_config()
    config['port'] = port
    save_json_config(config)

def get_datastore_port():
    config = load_json_config()
    return config['port']