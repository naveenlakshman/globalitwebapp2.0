# GlobalIT WebApp Tests

This directory contains test scripts and migration tools for the GlobalIT WebApp course management system.

## Directory Structure

```
tests/
├── migrations/
│   └── migrate_course_table.py    # Database migration script for course table
├── test_course_management.py      # Unit tests for course functionality
├── test_runner.py                 # Main test runner script
└── README.md                      # This file
```

## Quick Start

### 1. Run Migration Only
```bash
cd /workspaces/globalitwebapp2
python tests/test_runner.py --migration-only
```

### 2. Run Quick Validation
```bash
python tests/test_runner.py --quick
```

### 3. Run Full Test Suite
```bash
python tests/test_runner.py
```

## Migration Script

The `migrate_course_table.py` script updates your existing course table with new columns required for the enhanced course management system.

### What it does:
- ✅ Creates backup of your database
- ✅ Adds 32+ new columns to the courses table
- ✅ Sets appropriate default values
- ✅ Generates course codes for existing courses
- ✅ Validates the migration

### New Columns Added:
- Course metadata: `course_code`, `category`, `difficulty_level`
- Duration details: `duration_in_hours`, `duration_in_days`
- Pricing: `registration_fee`, `material_fee`, `certification_fee`, `early_bird_discount`, `group_discount`
- Content: `course_outline`, `prerequisites`, `learning_outcomes`, `software_requirements`
- Audience: `target_audience`, `career_opportunities`
- Delivery: `delivery_mode`, `batch_size_min`, `batch_size_max`, `typical_schedule`, `flexible_timing`
- Certification: `has_certification`, `certification_body`, `assessment_type`, `passing_criteria`
- Marketing: `is_featured`, `is_popular`, `display_order`, `course_image`, `brochure_path`
- Metadata: `updated_at`, `created_by`

## Test Categories

### 1. Database Migration Tests
- Tests database schema updates
- Validates column additions
- Verifies data integrity

### 2. Course Model Tests
- Tests course creation and validation
- Tests default values
- Tests serialization (to_dict)
- Tests computed properties

### 3. Search and Filter Tests
- Tests course search by name
- Tests filtering by category, status, difficulty
- Tests sorting functionality

### 4. Route Tests
- Tests route imports
- Validates blueprint configuration
- Tests route accessibility

### 5. Template Tests
- Validates template file existence
- Checks template structure

### 6. CSS Tests
- Validates CSS file existence
- Checks file integrity

### 7. Integration Tests
- Tests app integration
- Validates blueprint registration
- Tests complete system functionality

## Running Individual Components

### Migration Only
```bash
python tests/migrations/migrate_course_table.py
```

### Course Model Tests Only
```bash
python tests/test_course_management.py
```

### With Verbose Output
```bash
python tests/test_runner.py
```

## Troubleshooting

### Database Not Found
If you get a "Database file not found" error:
1. Make sure your app has been run at least once to create the database
2. Check the database path in `config.py`
3. Ensure the `instance/` directory exists

### Migration Fails
If migration fails:
1. Check the backup file created (`.backup_YYYYMMDD_HHMMSS`)
2. Restore from backup if needed
3. Check database permissions
4. Ensure no other processes are using the database

### Import Errors
If you get import errors:
1. Make sure you're running from the project root directory
2. Check that all required packages are installed
3. Ensure the virtual environment is activated

## Backup and Recovery

The migration script automatically creates backups with timestamps:
- Format: `globalit_education.db.backup_YYYYMMDD_HHMMSS`
- Location: Same directory as your database
- Automatic restoration: Copy backup over original file

## Test Output

Successful test run example:
```
🧪 GlobalIT WebApp Test Suite
==================================================
📅 Started at: 2025-08-20 14:30:25
📁 Project root: /workspaces/globalitwebapp2

🔄 Testing Database Migration...
----------------------------------------
✅ Database backed up to: /workspaces/globalitwebapp2/instance/globalit_education.db.backup_20250820_143025
✅ Added column: course_code
✅ Added column: category
... (more columns)
📊 Migration completed successfully!
✅ PASS Database Migration (2.45s)

🧪 Testing Course Model...
----------------------------------------
✅ PASS Course Model Tests (1.23s)

... (more tests)

📊 Test Summary
==================================================
⏱️  Total duration: 15.67s
✅ Passed: 6/6
❌ Failed: 0/6

🎉 All tests passed! Course management system is ready to use.
🚀 You can now start your application with: python run.py
```

## Next Steps

After successful migration and testing:

1. **Start your application**: `python run.py`
2. **Access course management**: Navigate to `/courses` in your browser
3. **Create your first course**: Use the "Add New Course" button
4. **Set up course categories**: Customize categories for your institute
5. **Configure pricing**: Set up registration, material, and certification fees

## Support

If you encounter issues:
1. Check the test output for specific error messages
2. Review the backup files created during migration
3. Ensure all dependencies are installed
4. Verify database permissions and accessibility
