# 🧪 **LMS Testing Guide for Franchise Users**

## 🎯 **Testing Environment Setup**

### **Prerequisites**
- ✅ Flask app running on `http://localhost:5000`
- ✅ Moodle LMS running on `http://localhost:8080`
- ✅ Logged in as franchise user (username: `hoskote`)
- ✅ Database contains test students and courses

---

## 🔗 **URLs to Test**

### **1. LMS Dashboard Access**
**URL**: `http://localhost:5000/lms`
- **Expected**: Redirects to LMS dashboard
- **Should Show**: Student progress, course statistics, Moodle integration status

**Direct Dashboard URL**: `http://localhost:5000/lms/dashboard`
- **Expected**: Full LMS dashboard with analytics
- **Franchise View**: Only students from your branch

### **2. LMS Management Interface**
**URL**: `http://localhost:5000/lms/management`
- **Expected**: Course and student management interface
- **Features**: Sync buttons, student list, course list
- **Franchise Filter**: Only your branch students visible

### **3. Individual Student Sync**
**URL Pattern**: `http://localhost:5000/lms/sync/student/<student_id>`

**Test URLs** (Replace with actual student IDs from your database):
```
http://localhost:5000/lms/sync/student/1516170
http://localhost:5000/lms/sync/student/1516171
http://localhost:5000/lms/sync/student/1516172
```
- **Expected**: JSON response with sync status
- **Franchise Restriction**: Should work for your branch students only

### **4. Individual Course Sync**
**URL Pattern**: `http://localhost:5000/lms/sync/course/<course_id>`

**Test URLs** (Replace with actual course IDs):
```
http://localhost:5000/lms/sync/course/1
http://localhost:5000/lms/sync/course/2
http://localhost:5000/lms/sync/course/3
```
- **Expected**: JSON response with course sync status
- **Access**: Should work for franchise users

### **5. Student Enrollment**
**URL Pattern**: `http://localhost:5000/lms/enroll/<student_id>/<course_id>`

**Test URLs**:
```
http://localhost:5000/lms/enroll/1516170/1
http://localhost:5000/lms/enroll/1516171/2
```
- **Expected**: JSON response with enrollment status
- **Restriction**: Should work for your branch students only

### **6. Bulk Student Sync (API)**
**URL**: `http://localhost:5000/lms/api/sync-all-students`
- **Method**: POST
- **Expected**: Syncs only students from your branch
- **Test**: Use browser dev tools or Postman

### **7. LMS Settings (Should be Restricted)**
**URL**: `http://localhost:5000/lms/settings`
- **Expected**: Access denied message
- **Franchise Restriction**: "Settings require administrator privileges"

---

## 🧪 **Step-by-Step Testing Process**

### **Test 1: Basic LMS Access**
1. **Login as franchise user** (`hoskote`)
2. **Navigate to**: `http://localhost:5000/lms`
3. **Verify**: You see LMS dashboard
4. **Check**: Only your branch students are visible

### **Test 2: Management Interface**
1. **Go to**: `http://localhost:5000/lms/management`
2. **Verify**: You can access the management interface
3. **Check**: Student list shows only your branch
4. **Test**: Click "Sync to Moodle" button for a student

### **Test 3: Individual Operations**
1. **Student Sync**: Click sync button or use direct URL
2. **Course Sync**: Test course synchronization
3. **Enrollment**: Try enrolling a student in a course
4. **Verify**: All operations work without permission errors

### **Test 4: Security Boundaries**
1. **Try accessing**: Another branch's student (if you have IDs)
2. **Expected**: Should get permission denied
3. **Test Settings**: Try accessing `/lms/settings`
4. **Expected**: Should be denied with proper message

### **Test 5: Bulk Operations**
1. **Go to**: LMS management interface
2. **Click**: "Sync All Students" button
3. **Monitor**: Network tab in browser dev tools
4. **Verify**: Only your branch students are processed

---

## 🔍 **What to Check in Each Test**

### **Dashboard Tests**
- ✅ Page loads without errors
- ✅ Student count matches your branch
- ✅ Course statistics are shown
- ✅ Moodle connection status displayed
- ✅ No "Permission Denied" errors

### **Management Interface Tests**
- ✅ Student list loads
- ✅ Course list displays
- ✅ Sync buttons are functional
- ✅ No errors in browser console
- ✅ Only branch-specific data shown

### **API Endpoint Tests**
- ✅ Returns proper JSON responses
- ✅ Success/error status appropriate
- ✅ Branch filtering working
- ✅ No cross-branch data access

### **Security Tests**
- ❌ Cannot access other branch students
- ❌ Cannot access global settings
- ❌ Cannot perform admin-only operations
- ✅ Proper error messages displayed

---

## 🛠️ **Testing Tools**

### **Browser Testing**
- **Chrome/Firefox**: Use developer tools
- **Network Tab**: Monitor API calls
- **Console**: Check for JavaScript errors
- **Application Tab**: Verify session data

### **API Testing with Browser Console**
```javascript
// Test bulk sync API
fetch('/lms/api/sync-all-students', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    }
})
.then(response => response.json())
.then(data => console.log(data));

// Test individual student sync
fetch('/lms/sync/student/1516170')
.then(response => response.json())
.then(data => console.log(data));
```

### **Testing with Postman (Optional)**
```
POST http://localhost:5000/lms/api/sync-all-students
Headers: Cookie: session=<your_session_cookie>

GET http://localhost:5000/lms/sync/student/1516170
Headers: Cookie: session=<your_session_cookie>
```

---

## 📊 **Expected Results Summary**

### **✅ Should Work (Franchise Access)**
| URL | Method | Expected Result |
|-----|--------|----------------|
| `/lms` | GET | Dashboard with branch data |
| `/lms/dashboard` | GET | Full analytics view |
| `/lms/management` | GET | Management interface |
| `/lms/sync/student/<id>` | GET | Student sync (branch only) |
| `/lms/sync/course/<id>` | GET | Course sync |
| `/lms/enroll/<s>/<c>` | GET | Student enrollment |
| `/lms/api/sync-all-students` | POST | Bulk sync (branch filtered) |

### **❌ Should Fail (Restricted Access)**
| URL | Expected Result |
|-----|----------------|
| `/lms/settings` | "Settings require administrator privileges" |
| Other branch student IDs | Permission denied |
| Admin-only operations | Access denied |

---

## 🚨 **Common Issues & Solutions**

### **Issue: "Permission Denied"**
- **Check**: You're logged in as franchise user
- **Verify**: Accessing your branch data only
- **Solution**: Use correct student/course IDs

### **Issue: "LMS Not Available"**
- **Check**: Moodle server is running
- **Verify**: Moodle configuration in app
- **Solution**: Start Moodle or check config

### **Issue: "Student Not Found"**
- **Check**: Student ID exists in database
- **Verify**: Student belongs to your branch
- **Solution**: Use correct student IDs

### **Issue: Empty Dashboard**
- **Check**: Students exist in your branch
- **Verify**: Database has test data
- **Solution**: Add test students or check branch assignment

---

## 📝 **Test Checklist**

```
□ Login as franchise user (hoskote)
□ Access /lms (should redirect to dashboard)
□ Access /lms/dashboard (should show branch data)
□ Access /lms/management (should show management interface)
□ Test individual student sync
□ Test individual course sync  
□ Test student enrollment
□ Test bulk student sync (POST API)
□ Try accessing /lms/settings (should be denied)
□ Verify no cross-branch data access
□ Check browser console for errors
□ Verify all operations work smoothly
```

---

## 📞 **Need Help?**

If you encounter issues during testing:

1. **Check browser console** for error messages
2. **Verify Flask app logs** in terminal
3. **Confirm Moodle connectivity** at `http://localhost:8080`
4. **Check student/course IDs** in database
5. **Ensure proper franchise user login**

---

*Testing Guide v1.0 | Updated: Aug 24, 2025 | Author: LMS Team*
