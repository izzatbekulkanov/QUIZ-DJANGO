import os

search_dir = r"C:\\Users\\user\\AppData\\Roaming\\Code\\User\\History"
target_string = "def _docx_to_html_embedded_pure"

found = []
if os.path.exists(search_dir):
    for root, _, files in os.walk(search_dir):
        for f in files:
            path = os.path.join(root, f)
            try:
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    if target_string in content and "OMATH" not in content.upper():
                        found.append((path, len(content)))
            except Exception:
                pass
                
for p, l in found:
    print(f"Found: {p} (length {l})")
