#!/usr/bin/env python3
"""
Simple database query without Flask app context using SQLite directly
"""
import sqlite3
import os

def check_database_content():
    """Check courses and branches in the database directly"""
    db_path = "globalit_education_prod.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔍 Checking Database Content")
        print("=" * 40)
        
        # Check courses
        print("\n📚 Courses in Database:")
        cursor.execute("SELECT id, course_name FROM courses ORDER BY id")
        courses = cursor.fetchall()
        for course_id, course_name in courses:
            print(f"  ID {course_id}: {course_name}")
        
        # Check branches
        print(f"\n🏢 Branches in Database:")
        cursor.execute("SELECT id, branch_name FROM branches ORDER BY id")
        branches = cursor.fetchall()
        for branch_id, branch_name in branches:
            print(f"  ID {branch_id}: {branch_name}")
        
        # Check CSV requirements
        print(f"\n✅ CSV Requirements Check:")
        csv_course_ids = [2, 4, 5, 10, 13]
        csv_branch_ids = [1, 2]
        
        existing_course_ids = [c[0] for c in courses]
        existing_branch_ids = [b[0] for b in branches]
        
        for cid in csv_course_ids:
            status = "✅ EXISTS" if cid in existing_course_ids else "❌ MISSING"
            print(f"  Course ID {cid}: {status}")
        
        for bid in csv_branch_ids:
            status = "✅ EXISTS" if bid in existing_branch_ids else "❌ MISSING"
            print(f"  Branch ID {bid}: {status}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database error: {e}")

if __name__ == "__main__":
    check_database_content()