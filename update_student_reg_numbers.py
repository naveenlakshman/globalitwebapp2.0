#!/usr/bin/env python3
"""
Utility script to update existing students with GIT- registration numbers.
Run this script once to assign registration numbers to existing students.
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from init_db import db
from models.student_model import Student
from globalit_app import create_app

def update_existing_students():
    """Update existing students with GIT- registration numbers"""
    try:
        # Find students without registration numbers
        students_without_reg_no = Student.query.filter(
            (Student.student_reg_no == None) | 
            (Student.student_reg_no == '') | 
            (Student.student_reg_no == 'NULL')
        ).order_by(Student.admission_date.asc()).all()
        
        if not students_without_reg_no:
            print("✅ All students already have registration numbers.")
            return
        
        print(f"Found {len(students_without_reg_no)} students without registration numbers.")
        
        # Get the highest existing GIT- registration number
        try:
            result = db.session.execute(
                db.text("SELECT student_reg_no FROM students WHERE student_reg_no LIKE 'GIT-%' ORDER BY CAST(SUBSTRING(student_reg_no, 5) AS INTEGER) DESC LIMIT 1")
            ).fetchone()
            
            if result:
                last_number = int(result[0].replace("GIT-", ""))
                next_number = last_number + 1
            else:
                next_number = 1
                
        except Exception as e:
            print(f"Error getting last registration number: {e}")
            # Fallback: Query all GIT- numbers
            results = db.session.execute(
                db.text("SELECT student_reg_no FROM students WHERE student_reg_no LIKE 'GIT-%'")
            ).fetchall()
            
            if results:
                numbers = []
                for row in results:
                    try:
                        reg_no = row[0]
                        if reg_no.startswith("GIT-"):
                            numbers.append(int(reg_no[4:]))
                    except (ValueError, IndexError):
                        continue
                
                if numbers:
                    next_number = max(numbers) + 1
                else:
                    next_number = 1
            else:
                next_number = 1
        
        print(f"Starting registration number assignment from GIT-{next_number}")
        
        # Assign registration numbers to students (ordered by admission date)
        updated_count = 0
        for student in students_without_reg_no:
            # Make sure this registration number doesn't exist
            while Student.query.filter_by(student_reg_no=f"GIT-{next_number}").first():
                next_number += 1
            
            student.student_reg_no = f"GIT-{next_number}"
            print(f"  - {student.student_id} ({student.full_name}) -> {student.student_reg_no}")
            
            updated_count += 1
            next_number += 1
        
        # Commit all changes
        db.session.commit()
        print(f"✅ Successfully updated {updated_count} students with registration numbers.")
        
    except Exception as e:
        print(f"❌ Error updating students: {str(e)}")
        db.session.rollback()
        return False
    
    return True

def verify_registration_numbers():
    """Verify that all students have unique registration numbers"""
    try:
        # Check for students without registration numbers
        students_without_reg_no = Student.query.filter(
            (Student.student_reg_no == None) | 
            (Student.student_reg_no == '') | 
            (Student.student_reg_no == 'NULL')
        ).count()
        
        if students_without_reg_no > 0:
            print(f"⚠️  Warning: {students_without_reg_no} students still don't have registration numbers.")
            return False
        
        # Check for duplicate registration numbers
        duplicates = db.session.execute(
            db.text("SELECT student_reg_no, COUNT(*) as count FROM students WHERE student_reg_no IS NOT NULL GROUP BY student_reg_no HAVING COUNT(*) > 1")
        ).fetchall()
        
        if duplicates:
            print(f"⚠️  Warning: Found {len(duplicates)} duplicate registration numbers:")
            for dup in duplicates:
                print(f"    - {dup[0]}: {dup[1]} students")
            return False
        
        # Get total count and range
        total_students = Student.query.filter(Student.student_reg_no.isnot(None)).count()
        git_students = Student.query.filter(Student.student_reg_no.like('GIT-%')).count()
        
        print(f"✅ Verification complete:")
        print(f"   - Total students with reg numbers: {total_students}")
        print(f"   - Students with GIT- format: {git_students}")
        print(f"   - No duplicates found")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during verification: {str(e)}")
        return False

if __name__ == "__main__":
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        print("=== Student Registration Number Update Utility ===")
        
        if len(sys.argv) > 1 and sys.argv[1] == "--verify":
            print("Running verification only...")
            verify_registration_numbers()
        else:
            print("Updating existing students with registration numbers...")
            
            # Ask for confirmation
            response = input("This will assign GIT-N registration numbers to students who don't have them. Continue? (y/N): ")
            
            if response.lower() in ['y', 'yes']:
                if update_existing_students():
                    print("\n" + "="*50)
                    print("Running verification...")
                    verify_registration_numbers()
                else:
                    print("❌ Update failed. Please check the errors above.")
            else:
                print("Operation cancelled.")
        
        print("\nDone.")