import wx
import wx.grid
import wx.html2
import json
import os

# --- Constants ---
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'private_devbot_ui_config.json')

# --- Utility Functions ---
def load_json_config(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if 'page_size' not in config:
                config['page_size'] = 30
            if 'monitoring_interval' not in config:
                config['monitoring_interval'] = 10

            return config
        except (json.JSONDecodeError, IOError) as e:
            wx.LogError(f"Error loading config file {file_path}: {e}")
            raise e

def load_initial_json_config(file_path):
    if not os.path.exists(file_path):
        return {'page_size': 30, 'monitoring_interval': 10}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        if 'page_size' not in config:
            config['page_size'] = 30
        if 'monitoring_interval' not in config:
            config['monitoring_interval'] = 10

        return config
    except Exception as e:
        wx.LogError(f"Error loading config file {file_path}: {e}")
        return {'page_size': 30, 'monitoring_interval': 10}
        

def save_json_config(file_path, config_data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
    except IOError as e:
        wx.LogError(f"Error saving config file {file_path}: {e}")

def get_config_file():
    return CONFIG_FILE