# Enhanced Role-Based Access Control System

## Business Requirements Analysis

### Current Problems:
1. Manager has access to ALL branches (security risk)
2. No role for branch employees (franchise staff)
3. Cannot assign managers to specific branches
4. Too broad permissions for non-owners

## Proposed Role Hierarchy

### 1. Admin (`admin`)
**Access Level**: System-wide
**Permissions**:
- All modules and features
- User management across all branches
- System configuration
- Financial oversight of all branches

### 2. Regional Manager (`regional_manager`)
**Access Level**: Assigned branches only
**Permissions**:
- Oversight of assigned branches
- Full financial access for assigned branches
- Can manage staff within assigned branches
- Cannot modify system settings

### 3. Franchise Owner (`franchise`)
**Access Level**: Owned branch only
**Permissions**:
- Full control of their branch
- All financial operations
- Staff management for their branch
- Branch-specific settings

### 4. Branch Manager (`branch_manager`)
**Access Level**: Assigned branch only
**Permissions**:
- Day-to-day operations
- Student management
- Basic financial operations (collect payments)
- Cannot access sensitive financial reports

### 5. Branch Staff (`staff`)
**Access Level**: Assigned branch only (limited)
**Permissions**:
- Student registration and management
- Payment collection
- Basic reporting
- Cannot access financial analytics

### 6. Trainer (`trainer`)
**Access Level**: Assigned branch only (course-focused)
**Permissions**:
- Student progress tracking
- Course management
- Basic student operations
- Limited financial access

## Database Schema Updates Required

### 1. User-Branch Assignment Table
```sql
CREATE TABLE user_branch_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    branch_id INTEGER NOT NULL,
    role TEXT NOT NULL, -- For role-specific permissions per branch
    assigned_by INTEGER, -- Who assigned this user
    assigned_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (branch_id) REFERENCES branches(id),
    FOREIGN KEY (assigned_by) REFERENCES users(id)
);
```

### 2. Role Permissions Matrix
```sql
CREATE TABLE role_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    module TEXT NOT NULL, -- finance, students, reports, etc.
    permission_level TEXT NOT NULL, -- full, read, write, none
    can_export INTEGER DEFAULT 0,
    can_modify INTEGER DEFAULT 0,
    can_delete INTEGER DEFAULT 0
);
```

## Implementation Strategy

### Phase 1: Update Finance Module
- Modify branch filtering logic
- Add role-based permission checks
- Implement user-branch assignment lookup

### Phase 2: Create User Management Interface
- Admin can assign users to branches
- Regional managers can manage their assigned branches
- Franchise owners can manage their branch staff

### Phase 3: Granular Permissions
- Module-level permission checking
- Feature-level access control
- Export and sensitive data restrictions

## Example Access Scenarios

### Scenario 1: Regional Manager
- Assigned to Mumbai and Delhi branches
- Can see financial data for both branches
- Cannot access Bangalore or Chennai data
- Can manage users in Mumbai and Delhi only

### Scenario 2: Branch Staff
- Works at Mumbai branch
- Can collect payments and register students
- Cannot access financial reports or analytics
- Cannot see other branch data

### Scenario 3: Franchise Owner
- Owns Bangalore branch
- Full access to all Bangalore operations
- Can hire and manage Bangalore staff
- Cannot see other franchise data

## Migration Plan

1. Add new role types to existing users table
2. Create user_branch_assignments table
3. Migrate existing users to new system
4. Update all route permission checks
5. Test with different user scenarios
