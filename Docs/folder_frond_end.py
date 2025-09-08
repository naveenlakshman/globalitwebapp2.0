import os

# Set project base path
base_path = r"E:\Global_IT_Web_App_2.0"

# Define folder structure
folders = [
    "templates",
    "templates/auth",
    "templates/dashboard",
    "templates/students",
    "templates/finance",
    "templates/lms",
    "templates/assessments",
    "templates/hr",
    "templates/reports",
    "templates/settings",
    "static",
    "static/css",
    "static/js",
    "static/uploads"
]

# Optional placeholder files (path relative to base_path)
placeholder_files = {
    "templates/base.html": "<!-- Base Template for Global IT -->",
    "templates/auth/login.html": "<!-- Login Page -->",
    "templates/dashboard/admin_dashboard.html": "<!-- Admin Dashboard -->",
    "static/css/main.css": "/* Global styles */",
    "static/js/app.js": "// JS scripts here"
}

# Create folders
for folder in folders:
    full_path = os.path.join(base_path, folder)
    os.makedirs(full_path, exist_ok=True)
    print(f"✅ Created folder: {full_path}")

# Create placeholder files
for relative_path, content in placeholder_files.items():
    full_file_path = os.path.join(base_path, relative_path)
    with open(full_file_path, "w") as f:
        f.write(content)
    print(f"📄 Created file: {full_file_path}")

print("\n🎉 All frontend folders and files created successfully in Global_IT_Web_App_2.0!")
