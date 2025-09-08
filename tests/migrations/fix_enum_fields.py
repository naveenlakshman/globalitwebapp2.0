#!/usr/bin/env python3
"""
Check for empty string values in all enum fields and fix them
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from globalit_app import create_app
from init_db import db
from models.lead_model import Lead
from sqlalchemy import text

def check_and_fix_enum_fields():
    """Check and fix empty string values in all enum fields"""
    print("🔧 Checking all enum fields for empty string values...")
    
    # Define enum fields that should allow NULL (optional fields)
    nullable_enum_fields = [
        'employment_type',
        'lead_source', 
        'guardian_relation'
    ]
    
    # Define enum fields that should have defaults (required fields)
    required_enum_fields = {
        'lead_status': 'Open',
        'lead_stage': 'New', 
        'priority': 'Medium',
        'preferred_language': 'English',
        'decision_maker': 'Self',
        'mode_preference': 'Offline',
        'join_timeline': 'Not Sure'
    }
    
    total_fixed = 0
    
    try:
        # Check nullable enum fields
        for field in nullable_enum_fields:
            empty_count = db.session.execute(
                text(f"SELECT COUNT(*) FROM leads WHERE {field} = ''")
            ).scalar()
            
            if empty_count > 0:
                print(f"Found {empty_count} leads with empty {field} values")
                result = db.session.execute(
                    text(f"UPDATE leads SET {field} = NULL WHERE {field} = ''")
                )
                print(f"✅ Updated {result.rowcount} records for {field}")
                total_fixed += result.rowcount
        
        # Check required enum fields
        for field, default_value in required_enum_fields.items():
            empty_count = db.session.execute(
                text(f"SELECT COUNT(*) FROM leads WHERE {field} = ''")
            ).scalar()
            
            if empty_count > 0:
                print(f"Found {empty_count} leads with empty {field} values")
                result = db.session.execute(
                    text(f"UPDATE leads SET {field} = :default_val WHERE {field} = ''"),
                    {'default_val': default_value}
                )
                print(f"✅ Updated {result.rowcount} records for {field} (set to '{default_value}')")
                total_fixed += result.rowcount
        
        db.session.commit()
        print(f"\n🎉 Successfully fixed {total_fixed} total records!")
        
        # Verify all fields are clean
        print("\n🔍 Verifying all enum fields...")
        all_enum_fields = nullable_enum_fields + list(required_enum_fields.keys())
        
        for field in all_enum_fields:
            remaining_empty = db.session.execute(
                text(f"SELECT COUNT(*) FROM leads WHERE {field} = ''")
            ).scalar()
            
            if remaining_empty > 0:
                print(f"⚠️  {field}: {remaining_empty} empty values still remain")
            else:
                print(f"✅ {field}: clean")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing enum fields: {e}")
        db.session.rollback()
        return False

if __name__ == "__main__":
    print("Enum Fields Fix Script")
    print("=" * 50)
    
    # Create Flask application context
    app = create_app()
    with app.app_context():
        success = check_and_fix_enum_fields()
    
    if success:
        print("\n✅ Script completed successfully!")
    else:
        print("\n❌ Script failed!")
        sys.exit(1)
