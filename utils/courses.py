"""
Course Management Utilities
Handles loading course data from Excel files and course creation/initialization
"""

import pandas as pd
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional
from init_db import db


def load_courses_from_excel(excel_path: str) -> List[Dict]:
    """
    Load course data from Excel file and return list of course dictionaries
    
    Args:
        excel_path (str): Path to the Excel file containing course data
        
    Returns:
        List[Dict]: List of course dictionaries ready for database insertion
        
    Raises:
        FileNotFoundError: If Excel file doesn't exist
        Exception: If there's an error reading the Excel file
    """
    try:
        if not os.path.exists(excel_path):
            raise FileNotFoundError(f"Excel file not found: {excel_path}")
        
        # Read Excel file
        print(f"📖 Reading course data from: {excel_path}")
        df = pd.read_excel(excel_path)
        
        # Display column names for debugging
        print(f"📋 Excel columns found: {list(df.columns)}")
        print(f"📊 Total rows in Excel: {len(df)}")
        
        courses = []
        
        # Process each row
        for index, row in df.iterrows():
            try:
                # Extract data from Excel row with fallback values
                course_data = {
                    # Basic Information
                    'course_name': str(row.get('Course Name', row.get('course_name', f'Course {index + 1}'))).strip(),
                    'course_code': str(row.get('Course Code', row.get('course_code', ''))).strip() or None,
                    'category': str(row.get('Category', row.get('category', 'Other'))).strip(),
                    'description': str(row.get('Description', row.get('description', ''))).strip() or None,
                    
                    # Duration and Timing
                    'duration': str(row.get('Duration', row.get('duration', ''))).strip() or None,
                    'duration_in_hours': _safe_int(row.get('Duration Hours', row.get('duration_in_hours', 0))),
                    'duration_in_days': _safe_int(row.get('Duration Days', row.get('duration_in_days', 0))),
                    
                    # Pricing Information
                    'fee': _safe_float(row.get('Course Fee', row.get('fee', 0))),
                    'registration_fee': _safe_float(row.get('Registration Fee', row.get('registration_fee', 0))),
                    'material_fee': _safe_float(row.get('Material Fee', row.get('material_fee', 0))),
                    'certification_fee': _safe_float(row.get('Certification Fee', row.get('certification_fee', 0))),
                    'early_bird_discount': _safe_float(row.get('Early Bird Discount', row.get('early_bird_discount', 0))),
                    'group_discount': _safe_float(row.get('Group Discount', row.get('group_discount', 0))),
                    
                    # Course Content
                    'course_outline': str(row.get('Course Outline', row.get('course_outline', ''))).strip() or None,
                    'prerequisites': str(row.get('Prerequisites', row.get('prerequisites', ''))).strip() or None,
                    'learning_outcomes': str(row.get('Learning Outcomes', row.get('learning_outcomes', ''))).strip() or None,
                    'software_requirements': str(row.get('Software Requirements', row.get('software_requirements', ''))).strip() or None,
                    'target_audience': str(row.get('Target Audience', row.get('target_audience', ''))).strip() or None,
                    'career_opportunities': str(row.get('Career Opportunities', row.get('career_opportunities', ''))).strip() or None,
                    
                    # Course Settings
                    'difficulty_level': _clean_enum_value(str(row.get('Difficulty Level', row.get('difficulty_level', 'Beginner'))).strip(), 
                                                         ['Beginner', 'Intermediate', 'Advanced', 'Expert'], 'Beginner'),
                    'delivery_mode': _clean_enum_value(str(row.get('Delivery Mode', row.get('delivery_mode', 'Classroom'))).strip(),
                                                      ['Classroom', 'Online', 'Hybrid', 'Offline', 'Offline/Hybrid'], 'Classroom'),
                    'batch_size_min': _safe_int(row.get('Min Batch Size', row.get('batch_size_min', 5))),
                    'batch_size_max': _safe_int(row.get('Max Batch Size', row.get('batch_size_max', 30))),
                    
                    # Certification and Assessment
                    'has_certification': _safe_bool(row.get('Has Certification', row.get('has_certification', True))),
                    'certification_body': str(row.get('Certification Body', row.get('certification_body', 'Global IT Education'))).strip() or None,
                    'assessment_type': _clean_enum_value(str(row.get('Assessment Type', row.get('assessment_type', 'Both'))).strip(),
                                                       ['Project', 'Exam', 'Both', 'Continuous'], 'Both'),
                    'passing_criteria': str(row.get('Passing Criteria', row.get('passing_criteria', ''))).strip() or None,
                    
                    # Scheduling
                    'typical_schedule': str(row.get('Typical Schedule', row.get('typical_schedule', ''))).strip() or None,
                    'flexible_timing': _safe_bool(row.get('Flexible Timing', row.get('flexible_timing', True))),
                    
                    # Marketing and Display
                    'is_featured': _safe_bool(row.get('Is Featured', row.get('is_featured', False))),
                    'is_popular': _safe_bool(row.get('Is Popular', row.get('is_popular', False))),
                    'display_order': _safe_int(row.get('Display Order', row.get('display_order', 100))),
                    
                    # Status
                    'status': str(row.get('Status', row.get('status', 'Active'))).strip()
                }
                
                # Validate required fields
                if not course_data['course_name'] or course_data['course_name'] == 'nan':
                    print(f"⚠️ Skipping row {index + 1}: Missing course name")
                    continue
                
                if course_data['fee'] <= 0:
                    print(f"⚠️ Warning: Course '{course_data['course_name']}' has fee <= 0")
                
                # Auto-generate course code if not provided
                if not course_data['course_code']:
                    course_data['course_code'] = _generate_course_code(course_data['course_name'])
                
                courses.append(course_data)
                print(f"✅ Processed: {course_data['course_name']} ({course_data['course_code']})")
                
            except Exception as row_error:
                print(f"❌ Error processing row {index + 1}: {row_error}")
                continue
        
        print(f"📚 Successfully loaded {len(courses)} courses from Excel")
        return courses
        
    except FileNotFoundError:
        raise
    except Exception as e:
        raise Exception(f"Error reading Excel file: {e}")


def _safe_int(value, default=0) -> int:
    """Safely convert value to integer with default fallback"""
    try:
        if pd.isna(value) or value == '' or value == 'nan':
            return default
        return int(float(value))  # Handle string numbers
    except (ValueError, TypeError):
        return default


def _safe_float(value, default=0.0) -> float:
    """Safely convert value to float with default fallback"""
    try:
        if pd.isna(value) or value == '' or value == 'nan':
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_bool(value, default=False) -> bool:
    """Safely convert value to boolean with default fallback"""
    try:
        if pd.isna(value) or value == '' or value == 'nan':
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ['true', 'yes', '1', 'on', 'enabled']
        return bool(value)
    except (ValueError, TypeError):
        return default


def _clean_enum_value(value: str, valid_values: List[str], default: str) -> str:
    """Clean and validate enum values, return default if invalid"""
    if not value or value == 'nan' or pd.isna(value):
        return default
    
    # Direct match
    if value in valid_values:
        return value
    
    # Case-insensitive match
    for valid in valid_values:
        if value.lower() == valid.lower():
            return valid
    
    # Partial match for common variations
    value_lower = value.lower()
    for valid in valid_values:
        if value_lower in valid.lower() or valid.lower() in value_lower:
            return valid
    
    print(f"⚠️ Unknown enum value '{value}', using default '{default}'")
    return default


def _generate_course_code(course_name: str) -> str:
    """Generate course code from course name"""
    try:
        words = course_name.upper().replace('&', 'AND').split()
        if len(words) >= 2:
            # Take first 3 letters of first two words
            code = '-'.join([word[:3] for word in words[:2]])
        else:
            # Take first 6 letters of single word
            code = words[0][:6]
        return code
    except:
        return "COURSE"


def init_courses_from_excel(excel_path: str = None) -> bool:
    """
    Initialize courses in database from Excel file
    
    Args:
        excel_path (str, optional): Path to Excel file. Defaults to Course_Master___12_Programs.xlsx
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from models.course_model import Course
        
        # Use default Excel file path if not provided
        if excel_path is None:
            excel_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Course_Master___12_Programs.xlsx')
        
        # Check if courses already exist
        existing_count = Course.query.count()
        if existing_count > 0:
            print(f"ℹ️ Courses already exist ({existing_count} courses found)")
            return True
        
        # Load courses from Excel
        course_data_list = load_courses_from_excel(excel_path)
        
        if not course_data_list:
            print("⚠️ No valid course data found in Excel file")
            return False
        
        # Create course objects and add to database
        created_count = 0
        for course_data in course_data_list:
            try:
                # Check if course with same name already exists
                existing_course = Course.query.filter_by(course_name=course_data['course_name']).first()
                if existing_course:
                    print(f"⚠️ Course '{course_data['course_name']}' already exists, skipping")
                    continue
                
                course = Course(**course_data)
                db.session.add(course)
                created_count += 1
                
            except Exception as course_error:
                print(f"❌ Error creating course '{course_data.get('course_name', 'Unknown')}': {course_error}")
                continue
        
        # Commit all changes
        db.session.commit()
        print(f"✅ Successfully created {created_count} courses from Excel data")
        return True
        
    except Exception as e:
        print(f"❌ Error initializing courses from Excel: {e}")
        db.session.rollback()
        return False


def validate_excel_structure(excel_path: str) -> Dict:
    """
    Validate Excel file structure and return information about columns
    
    Args:
        excel_path (str): Path to Excel file
        
    Returns:
        Dict: Validation results with column information
    """
    try:
        if not os.path.exists(excel_path):
            return {'valid': False, 'error': 'File not found'}
        
        df = pd.read_excel(excel_path)
        
        # Expected columns (flexible matching)
        expected_columns = [
            'Course Name', 'Course Code', 'Category', 'Description',
            'Duration', 'Duration Hours', 'Duration Days', 'Course Fee',
            'Registration Fee', 'Material Fee', 'Certification Fee'
        ]
        
        found_columns = list(df.columns)
        missing_columns = []
        
        # Check for required columns (case-insensitive)
        for expected in expected_columns:
            found = False
            for actual in found_columns:
                if expected.lower() in str(actual).lower():
                    found = True
                    break
            if not found:
                missing_columns.append(expected)
        
        return {
            'valid': len(missing_columns) == 0,
            'total_rows': len(df),
            'found_columns': found_columns,
            'missing_columns': missing_columns,
            'recommendations': _get_column_recommendations(found_columns)
        }
        
    except Exception as e:
        return {'valid': False, 'error': str(e)}


def _get_column_recommendations(columns: List[str]) -> List[str]:
    """Get recommendations for improving Excel structure"""
    recommendations = []
    
    # Convert to lowercase for checking
    lower_columns = [col.lower() for col in columns]
    
    if 'course name' not in lower_columns and 'course_name' not in lower_columns:
        recommendations.append("Add 'Course Name' column for course names")
    
    if 'fee' not in ' '.join(lower_columns) and 'cost' not in ' '.join(lower_columns):
        recommendations.append("Add 'Course Fee' column for pricing")
    
    if 'category' not in lower_columns:
        recommendations.append("Add 'Category' column to classify courses")
    
    return recommendations


# Export functions for easy import
__all__ = [
    'load_courses_from_excel',
    'init_courses_from_excel', 
    'validate_excel_structure'
]
