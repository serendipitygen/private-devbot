Set WshShell = CreateObject("WScript.Shell") 
WshShell.Run "cmd /c .\private_devbot_conda\Scripts\activate.bat && python private_devbot_ui.py", 0, False 
Set WshShell = Nothing