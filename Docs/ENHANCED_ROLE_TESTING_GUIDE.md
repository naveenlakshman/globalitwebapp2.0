# Enhanced Role System Testing Guide

## 🎯 Overview
This guide tests the new enhanced role-based access control system that provides granular permissions and multi-branch access management.

## 📋 Role Hierarchy Summary

| Role | Access Level | Finance Permissions | Branch Access |
|------|-------------|---------------------|---------------|
| **Admin** | System-wide | Full access, all exports | All branches |
| **Regional Manager** | Multi-branch | Full oversight, exports | Assigned branches only |
| **Franchise Owner** | Single branch | Full control | Owned branch only |
| **Branch Manager** | Single branch | Operations, limited exports | Assigned branch only |
| **Branch Staff** | Single branch | Payment collection only | Assigned branch only |
| **Trainer** | Single branch | View-only payments | Assigned branch only |

## 🔑 Test User Credentials

### System Administration
- **Username**: `admin`
- **Password**: `admin123`
- **Expected Access**: All branches, full system control

### Regional Management
- **Username**: `regional_manager_north`
- **Password**: `regional123`
- **Expected Access**: Mumbai + Delhi branches, full finance oversight

### Franchise Ownership
- **Username**: `mumbai_owner`
- **Password**: `mumbai123`
- **Expected Access**: Mumbai branch only, complete control

### Branch Management
- **Username**: `mumbai_branch_manager`
- **Password**: `branch123`
- **Expected Access**: Mumbai branch only, operations focus

### Branch Staff
- **Username**: `mumbai_staff_1`
- **Password**: `staff123`
- **Expected Access**: Mumbai branch only, limited functions

### Training Staff
- **Username**: `mumbai_trainer_python`
- **Password**: `trainer123`
- **Expected Access**: Mumbai branch only, student-focused

## 🧪 Test Scenarios

### Test 1: Admin Access (Full System Control)
**Login**: admin / admin123
**Expected Behavior**:
- ✅ Access to Finance Dashboard showing ALL branch data
- ✅ Can see payments from all branches
- ✅ All export functions available
- ✅ Can access all financial reports
- ✅ Branch filter dropdown shows all branches

**Verification Points**:
1. Dashboard shows combined revenue from all branches
2. Payment list includes data from Mumbai, Bangalore, Delhi, Chennai
3. Export PDF/Excel buttons are visible and functional
4. Reports section accessible with all data

### Test 2: Regional Manager (Multi-Branch Oversight)
**Login**: regional_manager_north / regional123
**Expected Behavior**:
- ✅ Access to Finance Dashboard showing Mumbai + Delhi data only
- ✅ Can see payments from assigned branches only
- ✅ Export functions available for assigned branches
- ✅ Cannot see Bangalore or Chennai data
- ✅ Branch filter shows only Mumbai and Delhi

**Verification Points**:
1. Dashboard metrics exclude Bangalore/Chennai data
2. Payment list filtered to Mumbai + Delhi only
3. Export functions work but only for accessible data
4. Branch dropdown limited to assigned branches

### Test 3: Franchise Owner (Complete Branch Control)
**Login**: mumbai_owner / mumbai123
**Expected Behavior**:
- ✅ Access to Finance Dashboard showing Mumbai data only
- ✅ Can see all Mumbai payments and financial data
- ✅ Full export capabilities for Mumbai branch
- ✅ Cannot access other branch data
- ✅ All finance features available for owned branch

**Verification Points**:
1. Dashboard shows only Mumbai branch metrics
2. Payment collection and management available
3. Can generate reports for Mumbai branch
4. No access to other branch information

### Test 4: Branch Manager (Operations Focus)
**Login**: mumbai_branch_manager / branch123
**Expected Behavior**:
- ✅ Access to Finance Dashboard showing Mumbai data
- ✅ Can collect payments and view transactions
- ✅ Limited export capabilities (basic reports only)
- ✅ Cannot access sensitive financial analytics
- ✅ Focus on operational finance tasks

**Verification Points**:
1. Can access payment collection forms
2. Can view payment history for Mumbai
3. Limited access to detailed financial reports
4. Cannot modify advanced financial settings

### Test 5: Branch Staff (Limited Operations)
**Login**: mumbai_staff_1 / staff123
**Expected Behavior**:
- ✅ Access to basic Finance functions for Mumbai
- ✅ Can collect payments from students
- ✅ Cannot access financial reports or analytics
- ✅ Cannot export financial data
- ✅ View-only access to payment history

**Verification Points**:
1. Payment collection interface available
2. Cannot access dashboard analytics
3. No export buttons visible
4. Limited to basic payment operations

### Test 6: Trainer (Course-Focused Access)
**Login**: mumbai_trainer_python / trainer123
**Expected Behavior**:
- ✅ Can view student payment status
- ✅ Cannot collect payments or access finance dashboard
- ✅ Limited to payment status information
- ✅ Cannot access financial reports
- ✅ Focus on student progress and payment verification

**Verification Points**:
1. Can see if student fees are paid
2. Cannot access full financial data
3. No payment collection capabilities
4. Limited to course-related financial info

## 🔍 Security Verification Tests

### Test 7: Cross-Branch Access Prevention
**Test Steps**:
1. Login as `mumbai_owner` (should only see Mumbai)
2. Try to access Bangalore student payments
3. Verify system blocks unauthorized access

**Expected Result**: Access denied messages, redirection to authorized content

### Test 8: Role Escalation Prevention
**Test Steps**:
1. Login as `mumbai_staff_1` (limited access)
2. Try to access financial reports directly via URL
3. Attempt to access admin functions

**Expected Result**: Permission denied, appropriate error messages

### Test 9: Data Isolation Verification
**Test Steps**:
1. Login as `mumbai_branch_manager`
2. Verify Mumbai-only data in all modules
3. Confirm no data leakage from other branches

**Expected Result**: Only Mumbai branch data visible throughout system

## 📊 Feature Access Matrix

| Feature | Admin | Regional Mgr | Franchise | Branch Mgr | Staff | Trainer |
|---------|-------|-------------|-----------|------------|-------|---------|
| Finance Dashboard | ✅ Full | ✅ Multi-branch | ✅ Branch | ✅ Limited | ❌ None | ❌ None |
| Payment Collection | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No |
| Financial Reports | ✅ All | ✅ Assigned | ✅ Branch | ⚠️ Basic | ❌ None | ❌ None |
| Export Data | ✅ All | ✅ Assigned | ✅ Branch | ⚠️ Limited | ❌ None | ❌ None |
| View Payments | ✅ All | ✅ Assigned | ✅ Branch | ✅ Branch | ✅ Branch | ⚠️ Status Only |
| Modify Settings | ✅ Yes | ⚠️ Limited | ⚠️ Branch | ❌ No | ❌ No | ❌ No |

## 🚀 Testing Execution Plan

### Phase 1: Basic Access Testing (30 minutes)
1. Test each user login
2. Verify dashboard access and data scope
3. Check branch filtering works correctly

### Phase 2: Feature Permission Testing (45 minutes)
1. Test payment collection for each role
2. Verify export function availability
3. Check report access permissions

### Phase 3: Security Testing (30 minutes)
1. Attempt unauthorized access
2. Test cross-branch data isolation
3. Verify role escalation prevention

### Phase 4: Integration Testing (15 minutes)
1. Test with real payment data
2. Verify data consistency across roles
3. Check performance with multiple users

## ✅ Success Criteria

**System passes if**:
- All roles can access their designated functions
- No unauthorized cross-branch data access
- Export functions respect role permissions
- Security controls prevent escalation
- User experience is intuitive for each role level

**System fails if**:
- Any role sees unauthorized branch data
- Security controls can be bypassed
- Performance degrades significantly
- User experience is confusing or broken

## 📝 Test Results Template

```
Test Date: ___________
Tester: ______________

✅ PASSED / ❌ FAILED

[ ] Test 1: Admin Access
[ ] Test 2: Regional Manager Access  
[ ] Test 3: Franchise Owner Access
[ ] Test 4: Branch Manager Access
[ ] Test 5: Branch Staff Access
[ ] Test 6: Trainer Access
[ ] Test 7: Cross-Branch Prevention
[ ] Test 8: Role Escalation Prevention
[ ] Test 9: Data Isolation

Issues Found:
____________________________________________
____________________________________________

Recommendations:
____________________________________________
____________________________________________
```

## 🔧 Troubleshooting Common Issues

### Issue: "No branch access configured"
**Solution**: Check user_branch_assignments table for user

### Issue: "Access denied: Insufficient permissions" 
**Solution**: Verify role_permissions table has correct entries

### Issue: User sees wrong branch data
**Solution**: Check branch_id assignments and filtering logic

### Issue: Export functions not working
**Solution**: Verify can_export permissions for user role
