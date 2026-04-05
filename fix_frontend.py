import os

target_str = "http://localhost:8000"
replacement_str = "http://35.169.145.225:8000"

frontend_dir = r"c:\Users\patel\Desktop\SimPPL\frontend\src"

for root, _, files in os.walk(frontend_dir):
    for f in files:
        if f.endswith(".jsx") or f.endswith(".js"):
            file_path = os.path.join(root, f)
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
            
            if target_str in content:
                new_content = content.replace(target_str, replacement_str)
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(new_content)
                print(f"Updated {file_path}")
