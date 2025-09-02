import zipfile
import os

def extract_xlsx(xlsx_path):

    with zipfile.ZipFile(xlsx_path, "r") as zip_ref:
        zip_ref.extractall("resources/dirty_excel")
        file_names = zip_ref.namelist()

        for name in file_names:
            print(name)

extract_xlsx("resources/Retail_Sales_Dashboard_Example.xlsx")