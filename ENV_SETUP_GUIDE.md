# Quick Setup Guide for .env File

## For PythonAnywhere Production Deployment:

### Step 1: Create .env file
```bash
cp .env.example .env
```

### Step 2: Update Critical Variables
Edit your `.env` file and set these REQUIRED values:

```bash
# MUST CHANGE THESE:
FLASK_ENV=production
SECRET_KEY=your-unique-secret-key-here-make-it-long-and-random
DATABASE_URL=sqlite:///globalit_education_prod.db

# RECOMMENDED FOR EMAIL FEATURES:
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password
```

### Step 3: Generate Secret Key
Run this in Python to generate a secure secret key:
```python
import secrets
print(secrets.token_hex(32))
```

### Step 4: Gmail App Password Setup (if using email)
1. Go to Google Account settings
2. Enable 2-factor authentication
3. Generate App Password for "Mail"
4. Use App Password (not your regular password) in MAIL_PASSWORD

### Step 5: PythonAnywhere Specific Settings
```bash
# Use absolute path for logs
LOG_FILE=/home/yourusername/logs/globalit_app.log
LOG_LEVEL=WARNING
```

## Minimum .env for Basic Operation:
```bash
FLASK_ENV=production
SECRET_KEY=your-generated-secret-key-here
DATABASE_URL=sqlite:///globalit_education_prod.db
```

## Security Notes:
- ✅ .env file is already in .gitignore (won't be committed)
- ✅ Your config.py is optimized for production
- ✅ Use the optimized config.py (not config_pythonanywhere.py)
- ⚠️  Change SECRET_KEY from default before going live
- ⚠️  Use App Passwords for Gmail, not regular passwords
