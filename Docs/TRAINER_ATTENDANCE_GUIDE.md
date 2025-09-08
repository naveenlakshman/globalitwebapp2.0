# 📋 Trainer Attendance Management Guide

## Overview
This guide provides step-by-step instructions for trainers to mark student attendance in the Global IT Education system. The system ensures that trainers can only access and mark attendance for batches they are specifically assigned to.

---

## 🔐 System Access Requirements

### Prerequisites
- Valid trainer login credentials
- Must be assigned to specific batches by branch manager or admin
- Access to the web application via browser

### User Role
- **Role**: `trainer`
- **Access Level**: Limited to assigned batches only
- **Permissions**: Mark attendance, view reports, edit individual records

---

## 🚀 Getting Started

### 1. Login to the System
1. Navigate to the login page
2. Enter your username and password
3. Click "Login"
4. You will be redirected to the **Trainer Dashboard**

### 2. Trainer Dashboard Overview
Upon successful login, you'll see:
- **Welcome header** with your name and role
- **Key Performance Indicators** showing your assigned students and batches
- **Attendance Management** section with real-time status for your assigned batches
- **Quick Actions** for immediate access to attendance features
- **Today's Classes** showing your assigned batches

> **Note**: If you see "No Batches Assigned" but can access batches through "Operations → My Batches", please contact your system administrator. This has been resolved in the latest system update.

---

## 📚 Accessing Your Batches

### Method 1: From Dashboard
1. **Navigate to Dashboard** (automatic after login)
2. **View Attendance Management Section**
   - See cards for each assigned batch
   - Check attendance status (marked/not marked)
   - View student counts and present/absent summary
3. **Click "Mark Attendance"** or "Edit Attendance" button on any batch card

### Method 2: From Navigation Menu
1. **Click "Operations"** in the top navigation
2. **Select "My Batches"** from dropdown
3. **View your assigned batches** in grid format
4. **Click "Attendance"** button for the desired batch

### Method 3: Quick Actions
1. **Use Quick Actions** section on dashboard
2. **Click "Mark Attendance"** button
3. **Select batch** from your assigned batches list

---

## ✅ Marking Attendance - Step by Step

### Step 1: Access Batch Attendance Interface
1. **Select your target batch** using any method above
2. **You'll be redirected** to the batch attendance page
3. **URL format**: `/attendance/batch/<batch_id>`

### Step 2: Attendance Interface Overview
The attendance interface displays:
- **Batch Information**: Name, course, timing, branch
- **Date Selection**: Choose the date for attendance
- **Student List**: All enrolled students in the batch
- **Attendance Records**: Previously marked attendance (if any)
- **Statistics**: Total sessions, active students, today's summary

### Step 3: Set Attendance Date
1. **Locate the date picker** at the top of the form
2. **Select the date** you want to mark attendance for
3. **Default**: Today's date is pre-selected
4. **Note**: You can mark attendance for past dates if needed

### Step 4: Mark Individual Student Attendance
For each student in the list:

1. **Find the student** in the attendance table
2. **Select attendance status** from dropdown:
   - **Present** ✅ - Student attended the class
   - **Absent** ❌ - Student did not attend
   - **Late** ⏰ - Student arrived late
   - **Excused** 📋 - Authorized absence

3. **Add notes** (optional):
   - Click in the "Notes" field for the student
   - Enter relevant information (e.g., "Late due to traffic", "Medical leave")
   - Notes help track attendance patterns and reasons

### Step 5: Bulk Actions (Optional)
For faster marking:
1. **Use bulk selection** if available
2. **Mark all present** for regular attendance
3. **Individual adjustments** for absent/late students

### Step 6: Submit Attendance
1. **Review your entries** for accuracy
2. **Click "Mark Attendance"** or "Submit" button
3. **Confirmation message** will appear showing number of students marked
4. **System records** your user ID and timestamp automatically

---

## 📊 Attendance Status Options

### Available Status Types
| Status | Icon | Description | When to Use |
|--------|------|-------------|-------------|
| **Present** | ✅ | Student attended full session | Regular attendance |
| **Absent** | ❌ | Student did not attend | No-show, unexcused absence |
| **Late** | ⏰ | Student arrived after start time | Partial attendance |
| **Excused** | 📋 | Authorized absence | Medical, emergency, pre-approved |

### Best Practices
- **Mark attendance promptly** after each session
- **Use "Late" status** for students arriving >15 minutes after start
- **Add notes** for unusual circumstances
- **Use "Excused"** only for pre-approved absences

---

## 🔄 Editing Attendance Records

### Editing Individual Records
1. **Navigate to batch attendance** page
2. **Find the attendance record** to edit
3. **Click the edit icon** or record
4. **Update status and/or notes**
5. **Save changes**

### Editing via AJAX (Real-time)
- **Click directly** on attendance status
- **Select new status** from popup
- **Add/edit notes** as needed
- **Changes save automatically**

---

## 📈 Viewing Attendance Reports & Analytics

### Attendance History
1. **Click "View History"** or "Reports" for a batch
2. **Set date range** using filters
3. **View attendance patterns** and statistics
4. **Export data** (if available)

### Student-Specific History
1. **Click on individual student** name
2. **View complete attendance history**
3. **See attendance rate** and patterns
4. **Track improvement/concerns**

### Batch Analytics
1. **Access analytics** from batch menu
2. **View comprehensive statistics**:
   - Overall attendance rate
   - Student-wise performance
   - Daily/weekly trends
   - At-risk student identification

---

## 🛡️ System Security & Validation

### Access Control
- **Batch Assignment**: You can only see batches assigned to you
- **No Cross-Access**: Cannot view other trainers' batches
- **Role Verification**: System verifies trainer role on each action
- **Session Security**: Automatic logout after inactivity

### Data Validation
- **Date Validation**: Cannot mark future dates beyond reasonable limits
- **Status Validation**: Only valid status options accepted
- **Duplicate Prevention**: System prevents duplicate attendance entries
- **Audit Trail**: All actions logged with user ID and timestamp

---

## 🔍 Navigation Guide

### Main Navigation Paths

#### From Trainer Dashboard:
```
Dashboard → Attendance Management Section → Select Batch → Mark Attendance
```

#### From Navigation Menu:
```
Operations → My Batches → Select Batch → Attendance Button
```

#### From Quick Actions:
```
Dashboard → Quick Actions → Mark Attendance → Select Batch
```

### URL Patterns
- **Dashboard**: `/dashboard/trainer`
- **My Batches**: `/attendance/trainer/my-batches`
- **Batch Attendance**: `/attendance/batch/<batch_id>`
- **Student History**: `/attendance/student/<student_id>`

---

## ❗ Troubleshooting Common Issues

### Issue: "Access Denied" Error
**Cause**: You're not assigned to this batch
**Solution**: 
- Contact your branch manager
- Verify batch assignments
- Check if batch is still active

### Issue: "Attendance Date Required" Error
**Cause**: No date selected for attendance
**Solution**: 
- Select a valid date from date picker
- Ensure date is not in far future

### Issue: Can't See Expected Batches
**Cause**: Batch assignments not updated
**Solution**: 
- Contact branch manager or admin
- Verify your trainer assignments
- Check if batches are active

### Issue: Attendance Not Saving
**Cause**: Form validation or network issues
**Solution**: 
- Check all required fields are filled
- Verify network connection
- Try refreshing page and re-entering data

---

## 📱 Mobile Access

### Mobile-Friendly Features
- **Responsive Design**: Works on tablets and smartphones
- **Touch-Friendly**: Easy selection on mobile devices
- **Quick Actions**: Streamlined interface for mobile use

### Mobile Best Practices
- **Use landscape mode** for better visibility
- **Zoom in** on forms if needed
- **Save frequently** to prevent data loss

---

## 📞 Support & Help

### Getting Help
- **Technical Issues**: Contact IT support
- **Batch Assignments**: Contact branch manager
- **Training**: Refer to this guide or request additional training

### Contact Information
- **Branch Manager**: For batch-related queries
- **IT Support**: For technical difficulties
- **Admin**: For system access issues

---

## 📝 Quick Reference

### Essential Steps Summary
1. **Login** to trainer dashboard
2. **Navigate** to attendance section
3. **Select** your assigned batch
4. **Choose** attendance date
5. **Mark** individual student status
6. **Add** notes if needed
7. **Submit** attendance form
8. **Verify** confirmation message

### Important Notes
- ✅ Only assigned batches are accessible
- ✅ Attendance can be marked for past dates
- ✅ Notes are optional but recommended
- ✅ All actions are logged for audit
- ✅ Real-time updates available
- ✅ Mobile-friendly interface

---

## 🔄 System Updates

This guide reflects the current system as of August 2025. For the latest features and updates, please refer to system announcements or contact your administrator.

---

**Version**: 1.0  
**Last Updated**: August 9, 2025  
**Applicable To**: Trainer Role in Global IT Education Management System
