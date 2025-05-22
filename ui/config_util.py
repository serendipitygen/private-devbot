import wx
import wx.grid
import wx.html2
import json
import os

# --- Constants ---
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'private_devbot_ui_config.json')

# --- Utility Functions ---
def load_json_config(file_path, default_config=None):
    if default_config is None:
        default_config = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            wx.LogError(f"Error loading config file {file_path}: {e}")
            return default_config
    return default_config

def save_json_config(file_path, config_data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
    except IOError as e:
        wx.LogError(f"Error saving config file {file_path}: {e}")

def get_config_file():
    return CONFIG_FILE