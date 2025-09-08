"""
Database Schema Setup Script
Reads schema.sql and creates all tables in the Global IT database
Located in: Docs/setup_database_from_schema.py
"""

import sqlite3
import os
import sys

# Add parent directory to path to import from root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime

def read_schema_file():
    """Read the schema.sql file and return the SQL content"""
    schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
    
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found at: {schema_path}")
    
    with open(schema_path, 'r', encoding='utf-8') as file:
        return file.read()

def parse_sql_statements(sql_content):
    """Parse SQL content and extract CREATE TABLE statements"""
    # Split by semicolons but be careful with comments
    statements = []
    current_statement = ""
    
    for line in sql_content.split('\n'):
        # Skip empty lines and comments
        line = line.strip()
        if not line or line.startswith('--'):
            continue
            
        current_statement += line + '\n'
        
        # If line ends with semicolon, we have a complete statement
        if line.endswith(';'):
            if 'CREATE TABLE' in current_statement.upper():
                statements.append(current_statement.strip())
            current_statement = ""
    
    return statements

def get_database_path():
    """Get the path to the database file"""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, 'instance', 'global_it.db')
    
    # Ensure instance directory exists
    instance_dir = os.path.dirname(db_path)
    os.makedirs(instance_dir, exist_ok=True)
    
    return db_path

def create_tables_from_schema():
    """Create all tables from schema.sql in the database"""
    print("🚀 Global IT Database Schema Setup")
    print("=" * 50)
    
    try:
        # Read schema file
        print("📖 Reading schema.sql file...")
        sql_content = read_schema_file()
        
        # Parse SQL statements
        print("🔍 Parsing CREATE TABLE statements...")
        table_statements = parse_sql_statements(sql_content)
        print(f"✅ Found {len(table_statements)} CREATE TABLE statements")
        
        # Get database path
        db_path = get_database_path()
        print(f"📁 Database path: {db_path}")
        
        # Connect to database
        print("🔗 Connecting to database...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Execute each CREATE TABLE statement
        created_tables = 0
        failed_tables = []
        
        print("\n📋 Creating tables...")
        print("-" * 50)
        
        for i, statement in enumerate(table_statements, 1):
            try:
                # Extract table name from statement
                lines = statement.split('\n')
                table_line = next(line for line in lines if 'CREATE TABLE' in line.upper())
                table_name = table_line.split('(')[0].split()[-1]
                
                # Execute the statement
                cursor.execute(statement)
                print(f"✅ {i:2d}. Created table: {table_name}")
                created_tables += 1
                
            except sqlite3.Error as e:
                table_name = "Unknown"
                try:
                    lines = statement.split('\n')
                    table_line = next(line for line in lines if 'CREATE TABLE' in line.upper())
                    table_name = table_line.split('(')[0].split()[-1]
                except:
                    pass
                
                print(f"❌ {i:2d}. Failed to create table {table_name}: {e}")
                failed_tables.append((table_name, str(e)))
        
        # Commit changes
        conn.commit()
        print("\n💾 Changes committed to database")
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"\n📊 Database Setup Summary:")
        print("=" * 50)
        print(f"✅ Successfully created: {created_tables} tables")
        print(f"❌ Failed to create: {len(failed_tables)} tables")
        print(f"📋 Total tables in database: {len(existing_tables)}")
        
        if failed_tables:
            print(f"\n⚠️  Failed Tables:")
            for table_name, error in failed_tables:
                print(f"   - {table_name}: {error}")
        
        print(f"\n📁 Database file location: {db_path}")
        print(f"🕒 Setup completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Close connection
        conn.close()
        
        return True, created_tables, len(failed_tables)
        
    except Exception as e:
        print(f"❌ Error during database setup: {e}")
        return False, 0, 0

def verify_database_structure():
    """Verify the database structure and show table information"""
    print("\n🔍 Verifying Database Structure")
    print("=" * 50)
    
    try:
        db_path = get_database_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"📋 Found {len(tables)} tables in database:")
        
        # Group tables by category based on naming patterns
        categories = {
            "Authentication & Login": ["guardian_login", "student_login", "login_logs"],
            "Core Infrastructure": ["branches", "users", "user_branch_access"],
            "Course & Batch Management": ["courses", "batches", "course_modules"],
            "Student & Lead Management": ["leads", "students", "alumni"],
            "Finance & Billing": ["invoices", "invoice_courses", "payments", "installments"],
            "Attendance & Feedback": ["student_attendance", "staff_attendance", "feedback"],
            "HR & Payroll": ["payroll", "expenses"],
            "System & Security": ["api_keys", "system_audit_logs", "support_tickets"],
            "Other Tables": []
        }
        
        # Categorize tables
        categorized_tables = {cat: [] for cat in categories.keys()}
        
        for table in tables:
            categorized = False
            for category, table_list in categories.items():
                if category == "Other Tables":
                    continue
                if table in table_list:
                    categorized_tables[category].append(table)
                    categorized = True
                    break
            
            if not categorized:
                categorized_tables["Other Tables"].append(table)
        
        # Display categorized tables
        for category, table_list in categorized_tables.items():
            if table_list:
                print(f"\n📂 {category}:")
                for table in sorted(table_list):
                    # Get table info
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    print(f"   ✅ {table} ({len(columns)} columns)")
        
        # Show some statistics
        print(f"\n📊 Database Statistics:")
        print("-" * 30)
        
        # Count records in key tables
        key_tables = ["users", "students", "batches", "invoices", "payments", "installments"]
        for table in key_tables:
            if table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"   {table}: {count} records")
                except sqlite3.Error:
                    print(f"   {table}: Error reading count")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error verifying database: {e}")

def main():
    """Main function"""
    print("🏗️  Global IT Education - Database Schema Setup Tool")
    print("=" * 60)
    print("📝 This script creates all tables from schema.sql")
    print("📅 Run Date:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print()
    
    # Ask user for confirmation
    response = input("🤔 Do you want to proceed with database setup? (y/n): ")
    if response.lower() != 'y':
        print("❌ Database setup cancelled.")
        return
    
    # Create tables from schema
    success, created, failed = create_tables_from_schema()
    
    if success:
        # Verify database structure
        verify_database_structure()
        
        print(f"\n🎉 Database setup completed successfully!")
        print(f"✅ Created {created} tables")
        if failed > 0:
            print(f"⚠️  {failed} tables failed to create")
        
        print(f"\n🚀 Next Steps:")
        print("   1. Run: python run.py (to start the Flask app)")
        print("   2. Run: python create_sample_data.py (to add test data)")
        print("   3. Run: python test_api.py (to test the APIs)")
        
    else:
        print(f"\n❌ Database setup failed!")
        print("   Please check the error messages above and try again.")

if __name__ == "__main__":
    main()
