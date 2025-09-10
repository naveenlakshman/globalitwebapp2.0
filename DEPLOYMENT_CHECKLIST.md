# Quick Deployment Checklist for PythonAnywhere
# ===============================================

## ✅ Pre-Deployment Checklist

### 1. Repository Status
- [ ] Code pushed to GitHub
- [ ] All tests passing (8/8 tests passed ✅)
- [ ] Database portability implemented ✅
- [ ] Alembic migrations configured ✅

### 2. PythonAnywhere Account Setup
- [ ] PythonAnywhere account created
- [ ] MySQL database created: `yourusername$globalit_lms`
- [ ] Database password set

## 🚀 Deployment Steps (30 minutes)

### Step 1: Clone Repository (5 min)
```bash
cd ~
git clone https://github.com/naveenlakshman/globalitwebapp2.0.git
cd globalitwebapp2.0
```

### Step 2: Virtual Environment (5 min)
```bash
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install python-dotenv mysqlclient gunicorn
```

### Step 3: Environment Configuration (5 min)
```bash
# Create .env file
cp env_template_pythonanywhere.txt .env
nano .env  # Edit with your actual database credentials
```

**Required .env variables:**
- `DATABASE_URL=mysql+pymysql://username:password@host/database`
- `SECRET_KEY=your-secret-key`
- `APP_ENV=production`

### Step 4: Database Setup (5 min)
```bash
source venv/bin/activate
python init_db.py
alembic upgrade head
```

### Step 5: Web App Configuration (5 min)
1. **Web Tab** → Add new web app → Manual configuration → Python 3.10
2. **WSGI File**: Copy content from `wsgi_pythonanywhere.py`
3. **Virtual Environment**: `/home/yourusername/globalitwebapp2.0/venv`
4. **Static Files**: URL: `/static/` → Directory: `/home/yourusername/globalitwebapp2.0/static/`

### Step 6: Final Steps (5 min)
```bash
mkdir -p logs
chmod 755 logs
```
- **Reload Web App** in Web tab
- **Test**: Visit `https://yourusername.pythonanywhere.com`

## 🔧 Quick Troubleshooting

### Database Connection Issues:
```bash
python -c "
import os
os.environ['APP_ENV'] = 'production'
from globalit_app import create_app
app = create_app()
print('Database URI:', app.config['SQLALCHEMY_DATABASE_URI'])
"
```

### Import Errors:
```bash
# Check Python path
python -c "import sys; print(sys.path)"
# Test app import
python -c "from globalit_app import create_app; print('✅ Import successful')"
```

### View Logs:
- **Web Tab** → Log files
- **Server log** and **Error log**
- **Application logs**: `~/globalitwebapp2.0/logs/`

## 📋 Post-Deployment

### Default Login:
- **URL**: `https://yourusername.pythonanywhere.com`
- **Username**: `admin`
- **Password**: `admin123`
- **⚠️ Change password immediately after first login!**

### Features to Test:
- [ ] Login functionality
- [ ] Dashboard access
- [ ] Student management
- [ ] Course management
- [ ] Data import system
- [ ] User role permissions

## 🔄 Future Updates

### Code Updates:
```bash
cd ~/globalitwebapp2.0
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
# Reload web app from Web tab
```

### Database Migrations:
```bash
cd ~/globalitwebapp2.0
source venv/bin/activate
alembic upgrade head
```

## 📞 Support
- Check error logs in PythonAnywhere Web tab
- Verify .env file configuration
- Test database connection
- Review WSGI file configuration

**Your GlobalIT LMS will be live at**: `https://yourusername.pythonanywhere.com`
