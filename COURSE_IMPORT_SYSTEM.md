# Course Import System Documentation

## Overview
The GlobalIT Course Import System allows administrators to bulk import course data via CSV files. This system provides comprehensive validation, duplicate handling, and supports all course fields defined in the Course model.

## Features

### ✅ Comprehensive Field Support
- **Basic Information**: course_name, course_code, category, duration
- **Pricing**: fee, registration_fee, material_fee, certification_fee, discounts
- **Course Content**: description, course_outline, prerequisites, learning_outcomes
- **Delivery**: difficulty_level, delivery_mode, batch_size, scheduling
- **Certification**: has_certification, certification_body, assessment_type
- **Administrative**: status, display_order, featured/popular flags

### ✅ Advanced Validation
- **Required Field Validation**: course_name, duration, fee
- **Data Type Validation**: Numeric fields, boolean fields, text length limits
- **Enum Validation**: Categories, difficulty levels, delivery modes, etc.
- **Business Logic**: Batch size min/max validation, percentage ranges
- **Duplicate Detection**: By course name or course code

### ✅ Duplicate Handling Options
- **Skip**: Skip duplicate courses
- **Update**: Update existing courses with new data
- **Replace**: Replace existing courses completely

## Usage

### 1. Access Course Import
Navigate to: `http://127.0.0.1:5000/import/courses`

### 2. Prepare CSV File
Use the provided template or create your own with these required columns:
- `course_name` (Required)
- `duration` (Required) 
- `fee` (Required)

### 3. Upload and Import
1. Upload your CSV file
2. Map columns to course fields
3. Choose duplicate handling strategy
4. Review preview and proceed with import

## CSV Template

### Required Fields
```csv
course_name,duration,fee
Python Programming,3 Months,15000
Web Development,6 Months,25000
```

### Full Template
Download the complete template: `/static/templates/courses_sample.csv`

### Sample Full Format
```csv
course_name,course_code,category,duration,duration_in_hours,fee,description,difficulty_level,delivery_mode,status
Python Programming Fundamentals,PY-FUND,Programming,3 Months,120,15000,Complete Python course,Beginner,Classroom,Active
```

## Field Reference

### Basic Information
- **course_name**: Course title (5-120 characters) - Required
- **course_code**: Short identifier (max 20 characters)
- **category**: Programming, Office Suite, Web Development, Data Science, Digital Marketing, Graphic Design, Hardware, Networking, Cloud Computing, Mobile Development, Digital Foundations, Programming & AI, Finance & Accounting, Communication & Soft Skills, Other
- **duration**: Course duration description (max 50 characters) - Required

### Duration & Capacity
- **duration_in_hours**: Total course hours (numeric)
- **duration_in_days**: Total course days (numeric)
- **batch_size_min**: Minimum students per batch (default: 5)
- **batch_size_max**: Maximum students per batch (default: 30)

### Pricing
- **fee**: Course fee (numeric, > 0) - Required
- **registration_fee**: One-time registration fee (numeric, ≥ 0)
- **material_fee**: Books/materials fee (numeric, ≥ 0)
- **certification_fee**: Certificate fee (numeric, ≥ 0)
- **early_bird_discount**: Early bird discount % (0-100)
- **group_discount**: Group enrollment discount % (0-100)

### Course Content
- **description**: Course description (max 2000 characters)
- **course_outline**: Detailed syllabus (max 5000 characters)
- **prerequisites**: Required prior knowledge (max 1000 characters)
- **learning_outcomes**: What students will learn (max 2000 characters)
- **software_requirements**: Required software/tools (max 1000 characters)

### Target Audience & Career
- **target_audience**: Who should take this course (max 1000 characters)
- **career_opportunities**: Job opportunities (max 2000 characters)
- **difficulty_level**: Beginner, Intermediate, Advanced, Expert

### Delivery & Assessment
- **delivery_mode**: Classroom, Online, Hybrid, Offline, Offline/Hybrid
- **assessment_type**: Project, Exam, Both, Continuous
- **typical_schedule**: Example schedule (max 200 characters)
- **passing_criteria**: Requirements to pass (max 100 characters)

### Certification
- **has_certification**: true/false, 1/0, yes/no
- **certification_body**: Issuing authority (max 100 characters)

### Administrative
- **status**: Active, Inactive, Draft, Archived
- **flexible_timing**: Can timing be adjusted (true/false)
- **is_featured**: Show on homepage (true/false)
- **is_popular**: Mark as popular (true/false)
- **display_order**: Sort order (numeric)
- **course_image**: Image filename (max 200 characters)
- **brochure_path**: PDF brochure path (max 200 characters)

## Error Handling

### Common Errors
- **Missing required fields**: course_name, duration, fee
- **Invalid category**: Must be from predefined list
- **Invalid difficulty level**: Must be Beginner, Intermediate, Advanced, or Expert
- **Invalid delivery mode**: Must be from predefined list
- **Fee validation**: Must be greater than 0
- **Batch size logic**: Min cannot be greater than max
- **Text length**: Various fields have character limits

### Validation Messages
The system provides detailed error messages with:
- Row number where error occurred
- Specific field that caused the error
- Expected format or valid values

## API Endpoints

### Course Import Route
```
POST /import/process
Content-Type: multipart/form-data
```

### Course Import Page
```
GET /import/courses
```

## Integration

### Database Integration
- Creates new Course records in the database
- Handles foreign key relationships
- Maintains data integrity with validation
- Supports transaction rollback on errors

### User Permissions
Required roles: `super_admin`, `admin`, `branch_manager`

## Testing

### Test Files
- `test_courses_simple.csv`: Basic test with required fields
- `courses_sample.csv`: Complete template with all fields

### Validation Testing
Use the comprehensive template to test all validation rules and field types.

## Success Metrics
After import completion, the system reports:
- **Successful**: Number of courses successfully imported
- **Failed**: Number of courses that failed validation
- **Skipped**: Number of duplicate courses skipped
- **Errors**: Detailed error messages for failed imports

This system ensures reliable, validated course imports while maintaining data integrity and providing comprehensive feedback to administrators.