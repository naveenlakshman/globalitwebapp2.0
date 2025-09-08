"""
Migration Script: Update Course Table Schema
Date: August 20, 2025
Purpose: Add new columns to courses table for comprehensive course management

This script will:
1. Add new columns to the existing courses table
2. Set default values for existing records
3. Update any necessary constraints
"""

import sqlite3
import os
from datetime import datetime

def get_database_path():
    """Get the database path from the application"""
    # First try the instance folder
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'globalit_education.db')
    if os.path.exists(db_path):
        return db_path
    
    # Fallback to other possible locations
    fallback_paths = [
        'globalit_education.db',
        'instance/globalit_education.db',
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'globalit_education.db')
    ]
    
    for path in fallback_paths:
        if os.path.exists(path):
            return path
    
    raise FileNotFoundError("Database file not found. Please ensure the database exists.")

def backup_database(db_path):
    """Create a backup of the database before migration"""
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"✅ Database backed up to: {backup_path}")
    return backup_path

def check_existing_schema(cursor):
    """Check the current schema of the courses table"""
    cursor.execute("PRAGMA table_info(courses)")
    columns = cursor.fetchall()
    
    existing_columns = [col[1] for col in columns]
    print(f"📋 Existing columns: {existing_columns}")
    return existing_columns

def migrate_courses_table():
    """Main migration function"""
    try:
        # Get database path
        db_path = get_database_path()
        print(f"🔍 Using database: {db_path}")
        
        # Create backup
        backup_path = backup_database(db_path)
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🚀 Starting course table migration...")
        
        # Check existing schema
        existing_columns = check_existing_schema(cursor)
        
        # Define new columns to add
        new_columns = [
            ("course_code", "VARCHAR(20)", "NULL"),
            ("category", "VARCHAR(50)", "'Programming'"),
            ("duration_in_hours", "INTEGER", "NULL"),
            ("duration_in_days", "INTEGER", "NULL"),
            ("registration_fee", "REAL", "0.0"),
            ("material_fee", "REAL", "0.0"),
            ("certification_fee", "REAL", "0.0"),
            ("early_bird_discount", "REAL", "0.0"),
            ("group_discount", "REAL", "0.0"),
            ("course_outline", "TEXT", "NULL"),
            ("prerequisites", "TEXT", "NULL"),
            ("learning_outcomes", "TEXT", "NULL"),
            ("software_requirements", "TEXT", "NULL"),
            ("target_audience", "TEXT", "NULL"),
            ("career_opportunities", "TEXT", "NULL"),
            ("difficulty_level", "VARCHAR(20)", "'Beginner'"),
            ("delivery_mode", "VARCHAR(20)", "'Classroom'"),
            ("batch_size_min", "INTEGER", "5"),
            ("batch_size_max", "INTEGER", "30"),
            ("has_certification", "BOOLEAN", "1"),
            ("certification_body", "VARCHAR(100)", "NULL"),
            ("assessment_type", "VARCHAR(20)", "'Both'"),
            ("passing_criteria", "VARCHAR(100)", "NULL"),
            ("typical_schedule", "VARCHAR(200)", "NULL"),
            ("flexible_timing", "BOOLEAN", "1"),
            ("is_featured", "BOOLEAN", "0"),
            ("is_popular", "BOOLEAN", "0"),
            ("display_order", "INTEGER", "100"),
            ("course_image", "VARCHAR(200)", "NULL"),
            ("brochure_path", "VARCHAR(200)", "NULL"),
            ("updated_at", "DATETIME", "CURRENT_TIMESTAMP"),
            ("created_by", "INTEGER", "NULL")
        ]
        
        # Add columns that don't exist
        added_columns = []
        for column_name, column_type, default_value in new_columns:
            if column_name not in existing_columns:
                try:
                    sql = f"ALTER TABLE courses ADD COLUMN {column_name} {column_type}"
                    if default_value != "NULL":
                        sql += f" DEFAULT {default_value}"
                    
                    cursor.execute(sql)
                    added_columns.append(column_name)
                    print(f"✅ Added column: {column_name}")
                except sqlite3.Error as e:
                    print(f"⚠️  Failed to add column {column_name}: {e}")
        
        # Update status column to have proper values if it exists
        if 'status' in existing_columns:
            try:
                cursor.execute("""
                    UPDATE courses 
                    SET status = CASE 
                        WHEN status = 'Active' OR status = '1' OR status IS NULL THEN 'Active'
                        WHEN status = 'Inactive' OR status = '0' THEN 'Inactive'
                        ELSE 'Active'
                    END
                """)
                print("✅ Updated status column values")
            except sqlite3.Error as e:
                print(f"⚠️  Failed to update status column: {e}")
        
        # Generate course codes for existing courses that don't have them
        if 'course_code' in added_columns:
            try:
                cursor.execute("SELECT id, course_name FROM courses WHERE course_code IS NULL")
                courses_without_codes = cursor.fetchall()
                
                for course_id, course_name in courses_without_codes:
                    # Generate course code from course name
                    words = course_name.upper().split()
                    if len(words) >= 2:
                        code = ''.join([word[:3] for word in words[:2]])
                    else:
                        code = words[0][:6] if words else 'COURSE'
                    
                    # Ensure uniqueness
                    counter = 1
                    original_code = code
                    cursor.execute("SELECT COUNT(*) FROM courses WHERE course_code = ?", (code,))
                    while cursor.fetchone()[0] > 0:
                        code = f"{original_code}{counter:02d}"
                        counter += 1
                        cursor.execute("SELECT COUNT(*) FROM courses WHERE course_code = ?", (code,))
                    
                    cursor.execute("UPDATE courses SET course_code = ? WHERE id = ?", (code, course_id))
                
                print(f"✅ Generated course codes for {len(courses_without_codes)} courses")
            except sqlite3.Error as e:
                print(f"⚠️  Failed to generate course codes: {e}")
        
        # Commit changes
        conn.commit()
        
        # Verify the migration
        cursor.execute("PRAGMA table_info(courses)")
        new_columns_list = cursor.fetchall()
        
        print(f"\n📊 Migration completed successfully!")
        print(f"📋 Total columns after migration: {len(new_columns_list)}")
        print(f"🆕 Added {len(added_columns)} new columns: {', '.join(added_columns)}")
        
        # Count courses
        cursor.execute("SELECT COUNT(*) FROM courses WHERE is_deleted = 0")
        course_count = cursor.fetchone()[0]
        print(f"📚 Total active courses in database: {course_count}")
        
        conn.close()
        
        print(f"\n✅ Migration completed successfully!")
        print(f"💾 Backup saved at: {backup_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def verify_migration():
    """Verify that the migration was successful"""
    try:
        db_path = get_database_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if all expected columns exist
        cursor.execute("PRAGMA table_info(courses)")
        columns = [col[1] for col in cursor.fetchall()]
        
        expected_columns = [
            'id', 'course_name', 'duration', 'fee', 'description', 'status', 'is_deleted', 'created_at',
            'course_code', 'category', 'duration_in_hours', 'duration_in_days', 'registration_fee',
            'material_fee', 'certification_fee', 'early_bird_discount', 'group_discount',
            'course_outline', 'prerequisites', 'learning_outcomes', 'software_requirements',
            'target_audience', 'career_opportunities', 'difficulty_level', 'delivery_mode',
            'batch_size_min', 'batch_size_max', 'has_certification', 'certification_body',
            'assessment_type', 'passing_criteria', 'typical_schedule', 'flexible_timing',
            'is_featured', 'is_popular', 'display_order', 'course_image', 'brochure_path',
            'updated_at', 'created_by'
        ]
        
        missing_columns = [col for col in expected_columns if col not in columns]
        
        if missing_columns:
            print(f"⚠️  Missing columns: {missing_columns}")
            return False
        else:
            print("✅ All expected columns are present")
            
        # Test a simple query
        cursor.execute("SELECT id, course_name, category, difficulty_level FROM courses LIMIT 5")
        sample_courses = cursor.fetchall()
        
        print(f"📋 Sample courses after migration:")
        for course in sample_courses:
            print(f"   - ID: {course[0]}, Name: {course[1]}, Category: {course[2]}, Level: {course[3]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Course Table Migration Script")
    print("=" * 50)
    
    # Run migration
    success = migrate_courses_table()
    
    if success:
        print("\n🔍 Verifying migration...")
        verify_migration()
        print("\n🎉 Migration completed successfully!")
        print("You can now start your application.")
    else:
        print("\n❌ Migration failed. Please check the errors above.")
        print("Your database backup is available for restore if needed.")
