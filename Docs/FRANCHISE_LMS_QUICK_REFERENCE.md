# 🚀 **Franchise LMS Quick Reference Guide**

## 🔗 **Quick Access URLs**
- **LMS Dashboard**: `http://localhost:5000/lms`
- **Course Management**: `http://localhost:5000/lms/management`
- **Franchise Dashboard**: `http://localhost:5000/dashboard/franchise`

## 🎯 **What Franchise Users Can Do**

### ✅ **ALLOWED Operations**
| Feature | URL | Description |
|---------|-----|-------------|
| 📊 **LMS Dashboard** | `/lms/dashboard` | View student progress & analytics |
| 🔧 **Course Management** | `/lms/management` | Sync students & courses |
| 👥 **Student Sync** | `/lms/sync/student/<id>` | Sync individual student |
| 📚 **Course Sync** | `/lms/sync/course/<id>` | Sync individual course |
| 🎓 **Student Enrollment** | `/lms/enroll/<student>/<course>` | Enroll student in course |
| 🔄 **Bulk Student Sync** | `/lms/api/sync-all-students` | Sync all branch students |

### ❌ **RESTRICTED Operations**
| Feature | Reason | Alternative |
|---------|--------|-------------|
| ⚙️ **LMS Settings** | Admin only | Contact administrator |
| 🌐 **Global Course Creation** | Admin only | Request via support |
| 🏢 **Other Branch Data** | Security restriction | Access only your branch |

## 📊 **Dashboard Features**

### **Student Analytics**
- 👥 **Total Students**: Count of branch students
- 🎓 **Enrolled Students**: Students in LMS courses  
- 📈 **Completion Rate**: Course completion percentage
- ⏱️ **Learning Time**: Average time spent learning

### **Course Management** 
- 📚 **Available Courses**: Courses your students can enroll in
- 🔄 **Sync Status**: Moodle synchronization status
- 👥 **Enrollment Stats**: Students per course
- 📊 **Progress Tracking**: Individual student progress

## 🔄 **Common Operations**

### **Sync New Student to LMS**
1. Go to `/lms/management`
2. Find student in the list
3. Click "Sync to Moodle"
4. Verify sync status

### **Enroll Student in Course**
1. Access student profile
2. Click "Enroll in Course"
3. Select appropriate course
4. Confirm enrollment

### **Monitor Student Progress**
1. Open `/lms/dashboard`
2. View progress charts
3. Click on individual students
4. Access detailed analytics

### **Bulk Sync Branch Students**
1. Go to course management page
2. Click "Sync All Students"
3. Operation filters to your branch only
4. Monitor sync progress

## 🔐 **Security Notes**

- ✅ You can only access students from your assigned branch
- ✅ All operations are logged for audit purposes
- ✅ Student data is protected and encrypted
- ❌ Cannot access other franchise data
- ❌ Cannot modify global system settings

## 🆘 **Troubleshooting**

### **Common Issues**
| Problem | Solution |
|---------|----------|
| 🔴 **"Permission Denied"** | Check if you're accessing correct branch data |
| 🔴 **"LMS Not Available"** | Moodle server may be down, contact admin |
| 🔴 **"Student Sync Failed"** | Check student email and course assignment |
| 🔴 **"Course Not Found"** | Verify course is available for your branch |

### **Getting Help**
- 📞 **Support Hotline**: Available 24/7
- 📧 **Email Support**: Include error screenshots
- 📚 **Documentation**: Full guide in `/Docs/` folder
- 👥 **User Community**: Franchise owner forums

## 📈 **Best Practices**

### **Student Management**
- ✅ Sync students immediately after enrollment
- ✅ Verify email addresses before sync
- ✅ Monitor sync status regularly
- ✅ Keep student course assignments updated

### **Progress Monitoring**
- ✅ Check dashboard weekly
- ✅ Follow up on low-progress students
- ✅ Share progress with parents/guardians
- ✅ Use analytics for improvement strategies

### **Data Security**
- ✅ Log out after each session
- ✅ Don't share login credentials
- ✅ Report suspicious activity immediately
- ✅ Keep student data confidential

---

*Quick Reference v1.0 | Updated: Aug 24, 2025*
