"""
Student Import Registration Number Compatibility Check

This script analyzes the student import functionality to check if it supports 
the new student_reg_no field and identifies any issues or improvements needed.
"""

import sys
sys.path.append('.')

def check_import_compatibility():
    """Check if student import supports registration numbers"""
    
    print("=== Student Import Registration Number Compatibility Check ===\n")
    
    issues = []
    improvements = []
    
    # 1. Check Student Model Fields
    print("1. Checking Student Model Fields...")
    try:
        from models.student_model import Student
        
        # Check if student_reg_no field exists
        if hasattr(Student, 'student_reg_no'):
            print("   ✅ student_reg_no field exists in Student model")
            
            # Check if it's required (nullable=False)
            student_reg_no_column = getattr(Student.__table__.c, 'student_reg_no', None)
            if student_reg_no_column and not student_reg_no_column.nullable:
                print("   ⚠️  student_reg_no is NOT NULL - import must handle this")
                issues.append("student_reg_no field is required but import may not generate it")
            else:
                print("   ✅ student_reg_no is nullable")
        else:
            print("   ❌ student_reg_no field NOT found in Student model")
            issues.append("Student model missing student_reg_no field")
            
    except Exception as e:
        print(f"   ❌ Error checking Student model: {e}")
        issues.append(f"Cannot access Student model: {e}")
    
    # 2. Check Import Routes
    print("\n2. Checking Import Routes...")
    try:
        from routes.import_routes import process_student_import
        print("   ✅ process_student_import function exists")
        
        # Check the source code to see if it handles student_reg_no
        import inspect
        source = inspect.getsource(process_student_import)
        
        if 'student_reg_no' in source:
            print("   ✅ student_reg_no mentioned in import process")
        else:
            print("   ❌ student_reg_no NOT handled in import process")
            issues.append("Import process does not handle student_reg_no field")
            
    except Exception as e:
        print(f"   ❌ Error checking import routes: {e}")
        issues.append(f"Cannot access import routes: {e}")
    
    # 3. Check Validator
    print("\n3. Checking Student Validator...")
    try:
        from utils.import_validator import StudentValidator
        
        # Check required fields
        required_fields = getattr(StudentValidator, 'REQUIRED_FIELDS', [])
        optional_fields = getattr(StudentValidator, 'OPTIONAL_FIELDS', [])
        
        if 'student_reg_no' in required_fields:
            print("   ✅ student_reg_no in required fields")
        elif 'student_reg_no' in optional_fields:
            print("   ⚠️  student_reg_no in optional fields")
            improvements.append("Consider making student_reg_no required in validator")
        else:
            print("   ❌ student_reg_no NOT in validator fields")
            issues.append("Validator does not include student_reg_no field")
            
        print(f"   📋 Required fields: {required_fields}")
        print(f"   📋 Optional fields: {optional_fields}")
        
    except Exception as e:
        print(f"   ❌ Error checking validator: {e}")
        issues.append(f"Cannot access validator: {e}")
    
    # 4. Check Data Mapper
    print("\n4. Checking Data Mapper...")
    try:
        from utils.csv_processor import DataMapper
        
        # Check if there's a function to generate student registration numbers
        if hasattr(DataMapper, 'generate_student_reg_no'):
            print("   ✅ generate_student_reg_no function exists")
        else:
            print("   ❌ generate_student_reg_no function NOT found")
            issues.append("No function to generate student registration numbers")
            
        # Check existing generate_student_id function
        if hasattr(DataMapper, 'generate_student_id'):
            print("   ✅ generate_student_id function exists")
            print("   ⚠️  But may need companion function for registration numbers")
            improvements.append("Need generate_student_reg_no function similar to generate_student_id")
        
    except Exception as e:
        print(f"   ❌ Error checking data mapper: {e}")
        issues.append(f"Cannot access data mapper: {e}")
    
    # 5. Check Sample Data Templates
    print("\n5. Checking Sample Data Templates...")
    try:
        import os
        template_file = 'data_templates/students_sample.csv'
        
        if os.path.exists(template_file):
            print(f"   ✅ Sample file exists: {template_file}")
            
            # Read and check headers
            import pandas as pd
            df = pd.read_csv(template_file)
            headers = df.columns.tolist()
            
            if 'student_reg_no' in headers:
                print("   ✅ student_reg_no in sample CSV headers")
            else:
                print("   ❌ student_reg_no NOT in sample CSV")
                issues.append("Sample CSV template missing student_reg_no column")
                
            print(f"   📋 CSV headers: {headers}")
        else:
            print(f"   ❌ Sample file not found: {template_file}")
            issues.append("Sample CSV template file missing")
            
    except Exception as e:
        print(f"   ❌ Error checking sample templates: {e}")
        issues.append(f"Cannot check sample templates: {e}")
    
    # 6. Test Registration Number Generation
    print("\n6. Testing Registration Number Generation...")
    try:
        # Try to generate a registration number
        from models.student_model import Student
        
        # Check existing students to see registration number pattern
        existing_students = Student.query.limit(5).all()
        
        if existing_students:
            print("   📊 Sample existing registration numbers:")
            for student in existing_students:
                if hasattr(student, 'student_reg_no') and student.student_reg_no:
                    print(f"      - {student.full_name}: {student.student_reg_no}")
                else:
                    print(f"      - {student.full_name}: ❌ No registration number")
                    issues.append(f"Existing student {student.full_name} missing registration number")
        else:
            print("   ℹ️  No existing students found")
            
    except Exception as e:
        print(f"   ❌ Error testing registration numbers: {e}")
    
    # Summary Report
    print(f"\n=== COMPATIBILITY ANALYSIS SUMMARY ===")
    print(f"🔍 Issues Found: {len(issues)}")
    print(f"💡 Improvements Suggested: {len(improvements)}")
    
    if issues:
        print(f"\n❌ CRITICAL ISSUES TO FIX:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    
    if improvements:
        print(f"\n💡 SUGGESTED IMPROVEMENTS:")
        for i, improvement in enumerate(improvements, 1):
            print(f"   {i}. {improvement}")
    
    if not issues and not improvements:
        print(f"\n✅ IMPORT SYSTEM IS FULLY COMPATIBLE!")
        print(f"   The student import functionality supports registration numbers.")
    elif issues:
        print(f"\n⚠️  IMPORT SYSTEM NEEDS UPDATES!")
        print(f"   Critical issues must be resolved before importing students.")
    else:
        print(f"\n✅ IMPORT SYSTEM IS MOSTLY COMPATIBLE!")
        print(f"   Consider implementing suggested improvements.")
    
    return len(issues) == 0, issues, improvements

if __name__ == "__main__":
    is_compatible, issues, improvements = check_import_compatibility()
    
    if not is_compatible:
        print(f"\n🛠️  RECOMMENDED ACTIONS:")
        print(f"   1. Update import process to handle student_reg_no")
        print(f"   2. Add registration number generation logic")
        print(f"   3. Update validator to include student_reg_no")
        print(f"   4. Update sample CSV template")
        print(f"   5. Test import with registration numbers")
    
    print(f"\n📚 For more details, check:")
    print(f"   - routes/import_routes.py (process_student_import function)")
    print(f"   - utils/import_validator.py (StudentValidator class)")
    print(f"   - utils/csv_processor.py (DataMapper class)")
    print(f"   - data_templates/students_sample.csv")