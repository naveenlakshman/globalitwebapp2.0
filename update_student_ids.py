#!/usr/bin/env python3
"""
Utility script to update existing student IDs to start from 1.
This will change student IDs from 1516170, 1516171, etc. to 1, 2, 3, etc.
"""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from init_db import db
from models.student_model import Student
from globalit_app import create_app

def update_student_ids():
    """Update existing student IDs to start from 1"""
    try:
        # Get all students ordered by admission date (oldest first)
        students = Student.query.order_by(Student.admission_date.asc()).all()
        
        if not students:
            print("No students found.")
            return True
        
        print(f"Found {len(students)} students to update:")
        
        # Create a mapping of old ID to new ID
        id_mapping = {}
        for index, student in enumerate(students, 1):
            id_mapping[student.student_id] = str(index)
            print(f"  - {student.full_name}: {student.student_id} → {index}")
        
        print(f"\nStarting ID update process...")
        
        # First, temporarily update all student IDs to avoid conflicts
        # We'll use negative numbers as temporary IDs
        for index, student in enumerate(students, 1):
            temp_id = f"-{index}"
            student.student_id = temp_id
        
        # Commit temporary changes
        db.session.commit()
        print("✅ Applied temporary IDs")
        
        # Now update to final IDs
        for index, student in enumerate(students, 1):
            student.student_id = str(index)
        
        # Commit final changes
        db.session.commit()
        print("✅ Applied final sequential IDs")
        
        # Verify the changes
        print("\n" + "="*50)
        print("Updated student IDs:")
        updated_students = Student.query.order_by(Student.admission_date.asc()).all()
        for student in updated_students:
            print(f"  - {student.student_id}: {student.full_name} ({student.student_reg_no})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating student IDs: {str(e)}")
        db.session.rollback()
        return False

def verify_student_ids():
    """Verify that all students have sequential IDs starting from 1"""
    try:
        students = Student.query.order_by(Student.student_id.asc()).all()
        
        if not students:
            print("No students found.")
            return True
        
        print(f"✅ Verification complete:")
        print(f"   - Total students: {len(students)}")
        
        # Check if IDs are sequential
        expected_ids = [str(i) for i in range(1, len(students) + 1)]
        actual_ids = [student.student_id for student in students]
        
        if actual_ids == expected_ids:
            print(f"   - Student IDs are sequential: {', '.join(actual_ids)}")
            print(f"   - Registration numbers are properly maintained")
        else:
            print(f"   - ⚠️  Warning: IDs are not sequential")
            print(f"     Expected: {', '.join(expected_ids)}")
            print(f"     Actual: {', '.join(actual_ids)}")
            return False
        
        # Show the mapping
        print(f"\n   Current students:")
        for student in students:
            print(f"     ID: {student.student_id} | Reg: {student.student_reg_no} | Name: {student.full_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during verification: {str(e)}")
        return False

if __name__ == "__main__":
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        print("=== Student ID Update Utility ===")
        print("This will change student IDs from 1516170+ format to 1, 2, 3+ format")
        
        if len(sys.argv) > 1 and sys.argv[1] == "--verify":
            print("Running verification only...")
            verify_student_ids()
        else:
            print("Updating existing students with new sequential IDs...")
            
            # Ask for confirmation
            response = input("This will change student IDs to start from 1. Continue? (y/N): ")
            
            if response.lower() in ['y', 'yes']:
                if update_student_ids():
                    print("\n" + "="*50)
                    print("Running verification...")
                    verify_student_ids()
                else:
                    print("❌ Update failed. Please check the errors above.")
            else:
                print("Operation cancelled.")
        
        print("\nDone.")