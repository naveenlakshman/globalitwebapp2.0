# PythonAnywhere Deployment Guide for GlobalIT LMS

## 🚀 Complete Deployment Steps for PythonAnywhere

### **Prerequisites**
- PythonAnywhere account (Free or Paid)
- Your GitHub repository: https://github.com/naveenlakshman/globalitwebapp2.0

---

## **Step 1: Clone Your Repository on PythonAnywhere**

1. **Log into PythonAnywhere Console**
   - Go to https://www.pythonanywhere.com
   - Log in to your account
   - Open a **Bash console**

2. **Clone Your Repository**
   ```bash
   cd ~
   git clone https://github.com/naveenlakshman/globalitwebapp2.0.git
   cd globalitwebapp2.0
   ```

---

## **Step 2: Set Up Virtual Environment**

```bash
# Create virtual environment
python3.10 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip install -r requirements.txt

# Install additional production dependencies
pip install gunicorn mysqlclient
```

---

## **Step 3: Configure MySQL Database**

### **3.1 Create MySQL Database**
1. Go to **Databases** tab in PythonAnywhere dashboard
2. Create a new database: `yourusername$globalit_lms`
3. Note down the connection details:
   - **Host**: `yourusername.mysql.pythonanywhere-services.com`
   - **Database**: `yourusername$globalit_lms`
   - **Username**: `yourusername`
   - **Password**: [set in database tab]

### **3.2 Set Environment Variables**
Create `.env` file in your project root:

```bash
# Create .env file
nano .env
```

Add the following content (replace with your actual values):

```env
# Production Environment
APP_ENV=production
FLASK_ENV=production
DEBUG=False

# Database Configuration
DATABASE_URL=mysql+pymysql://yourusername:your_password@yourusername.mysql.pythonanywhere-services.com/yourusername$globalit_lms

# Security
SECRET_KEY=your-super-secret-key-change-this-in-production

# Email Configuration (Optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# SMS Configuration (Optional)
SMS_API_KEY=your-sms-api-key
SMS_API_URL=your-sms-api-url

# Logging
LOG_LEVEL=INFO
LOG_FILE=/home/yourusername/globalitwebapp2.0/logs/app.log
```

---

## **Step 4: Initialize Database**

```bash
# Activate virtual environment
source venv/bin/activate

# Initialize database with Alembic
python -c "
from globalit_app import create_app
from init_db import db
import os

# Set production environment
os.environ['APP_ENV'] = 'production'

app = create_app()
with app.app_context():
    # Create all tables
    db.create_all()
    print('✅ Database tables created successfully!')
"

# Run Alembic migrations
pip install alembic
alembic upgrade head

# Initialize database with default data
python init_db.py
```

---

## **Step 5: Configure Web App**

### **5.1 Create Web App**
1. Go to **Web** tab in PythonAnywhere dashboard
2. Click **"Add a new web app"**
3. Choose **"Manual configuration"**
4. Select **Python 3.10**

### **5.2 Configure WSGI File**
Edit the WSGI file (usually at `/var/www/yourusername_pythonanywhere_com_wsgi.py`):

Replace the entire content with:

```python
import sys
import os

# Add your project directory to sys.path
project_home = '/home/yourusername/globalitwebapp2.0'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables
os.environ['APP_ENV'] = 'production'
os.environ['FLASK_ENV'] = 'production'

# Import your Flask application
from globalit_app import create_app
application = create_app()

if __name__ == "__main__":
    application.run()
```

### **5.3 Configure Virtual Environment**
In the **Web** tab:
- Set **Virtualenv** path to: `/home/yourusername/globalitwebapp2.0/venv`

### **5.4 Configure Static Files**
Add static file mappings:
- **URL**: `/static/`
- **Directory**: `/home/yourusername/globalitwebapp2.0/static/`

---

## **Step 6: Configure Logging**

```bash
# Create logs directory
mkdir -p /home/yourusername/globalitwebapp2.0/logs

# Set permissions
chmod 755 /home/yourusername/globalitwebapp2.0/logs
```

---

## **Step 7: Test Deployment**

### **7.1 Test in Console**
```bash
cd ~/globalitwebapp2.0
source venv/bin/activate

python -c "
from globalit_app import create_app
app = create_app()
print('✅ App created successfully!')
print(f'✅ Database URI: {app.config[\"SQLALCHEMY_DATABASE_URI\"]}')
print(f'✅ Debug mode: {app.config[\"DEBUG\"]}')
"
```

### **7.2 Reload Web App**
1. Go to **Web** tab
2. Click **"Reload yourusername.pythonanywhere.com"**
3. Visit your URL: `https://yourusername.pythonanywhere.com`

---

## **Step 8: Verify Deployment**

✅ **Check these URLs work:**
- `https://yourusername.pythonanywhere.com/` - Login page
- `https://yourusername.pythonanywhere.com/dashboard` - Dashboard (after login)
- `https://yourusername.pythonanywhere.com/import/students` - Import functionality

✅ **Default Login Credentials:**
- **Username**: `admin`
- **Password**: `admin123`
- **⚠️ IMPORTANT**: Change this password immediately after first login!

---

## **Step 9: Production Optimizations**

### **9.1 Set Up SSL (Free with PythonAnywhere)**
- Your app automatically gets SSL at `https://yourusername.pythonanywhere.com`

### **9.2 Configure Email (Optional)**
If using Gmail for notifications:
1. Enable 2-factor authentication on Gmail
2. Create an "App Password" for the application
3. Use the app password in your `.env` file

### **9.3 Set Up Scheduled Tasks**
For maintenance tasks, go to **Tasks** tab and add:
```bash
# Daily database backup (example)
source /home/yourusername/globalitwebapp2.0/venv/bin/activate && python /home/yourusername/globalitwebapp2.0/backup_db.py
```

---

## **Step 10: Troubleshooting**

### **Common Issues:**

1. **Import Errors**
   ```bash
   # Check Python path
   cd ~/globalitwebapp2.0
   source venv/bin/activate
   python -c "import sys; print(sys.path)"
   ```

2. **Database Connection Issues**
   ```bash
   # Test database connection
   python -c "
   import os
   os.environ['APP_ENV'] = 'production'
   from globalit_app import create_app
   from init_db import db
   app = create_app()
   with app.app_context():
       print('✅ Database connected successfully!')
   "
   ```

3. **Static Files Not Loading**
   - Check static file mapping in Web tab
   - Ensure path is correct: `/home/yourusername/globalitwebapp2.0/static/`

4. **Environment Variables**
   ```bash
   # Check .env file is loaded
   python -c "
   import os
   from dotenv import load_dotenv
   load_dotenv()
   print(f'APP_ENV: {os.getenv(\"APP_ENV\")}')
   print(f'DATABASE_URL set: {bool(os.getenv(\"DATABASE_URL\"))}')
   "
   ```

### **Viewing Logs:**
- **Error logs**: Available in Web tab → Log files
- **Server logs**: Available in Web tab → Server log
- **Application logs**: `/home/yourusername/globalitwebapp2.0/logs/app.log`

---

## **Step 11: Maintenance**

### **Updating Code:**
```bash
cd ~/globalitwebapp2.0
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
# Reload web app from Web tab
```

### **Database Migrations:**
```bash
cd ~/globalitwebapp2.0
source venv/bin/activate
alembic upgrade head
```

---

## **🎉 Your GlobalIT LMS is now live!**

**Access your application at**: `https://yourusername.pythonanywhere.com`

**Features Available:**
- ✅ Student Management
- ✅ Course Management  
- ✅ Batch Management
- ✅ Finance & Payment Tracking
- ✅ Data Import System
- ✅ Role-based Access Control
- ✅ Attendance Management
- ✅ LMS Content Management

**Next Steps:**
1. Change default admin password
2. Create additional user accounts
3. Import your existing data using the CSV import feature
4. Configure email and SMS settings for notifications
5. Set up regular database backups

**Support**: If you encounter issues, check the error logs in PythonAnywhere's Web tab or contact support.
