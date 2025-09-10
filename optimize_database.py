#!/usr/bin/env python
"""
Database Performance Optimizer
Adds missing indexes and optimizes SQLite settings for better performance
"""

import sqlite3
import os
import shutil
from datetime import datetime

def optimize_database():
    """Optimize database for better performance"""
    
    db_path = 'globalit_education_dev.db'
    
    if not os.path.exists(db_path):
        print('❌ Database file not found')
        return False
    
    try:
        # Create backup first
        backup_path = f"{db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"📁 Creating backup: {backup_path}")
        shutil.copy2(db_path, backup_path)
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔧 Optimizing Database...")
        
        # 1. Set optimal database settings (SQLite specific)
        print("⚙️  Setting optimal database configurations...")
        
        # Check if this is SQLite
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
        is_sqlite = True
        try:
            cursor.fetchone()
        except Exception:
            is_sqlite = False
        
        if is_sqlite:
            optimizations = [
                "PRAGMA journal_mode=WAL;",        # Write-Ahead Logging for better concurrency
                "PRAGMA synchronous=NORMAL;",      # Faster writes, still safe
                "PRAGMA cache_size=-32000;",       # 32MB cache (negative = KB)
                "PRAGMA temp_store=MEMORY;",       # Store temp tables in memory
                "PRAGMA mmap_size=268435456;",     # 256MB memory map
            ]
            
            for pragma in optimizations:
                cursor.execute(pragma)
                print(f"   ✅ {pragma}")
        else:
            print("   ℹ️  Database optimization skipped (not SQLite - MySQL optimizations handled by server configuration)")
        
        # 2. Create performance indexes
        print("\n📊 Creating performance indexes...")
        
        indexes = [
            # Student table indexes
            "CREATE INDEX IF NOT EXISTS idx_students_batch_id ON students(batch_id);",
            "CREATE INDEX IF NOT EXISTS idx_students_branch_id ON students(branch_id);", 
            "CREATE INDEX IF NOT EXISTS idx_students_status ON students(status);",
            "CREATE INDEX IF NOT EXISTS idx_students_admission_date ON students(admission_date);",
            "CREATE INDEX IF NOT EXISTS idx_students_course_id ON students(course_id);",
            
            # Lead table indexes  
            "CREATE INDEX IF NOT EXISTS idx_leads_assigned_to ON leads(assigned_to_user_id);",
            "CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at);",
            "CREATE INDEX IF NOT EXISTS idx_leads_lead_generation_date ON leads(lead_generation_date);",
            
            # Batch table indexes
            "CREATE INDEX IF NOT EXISTS idx_batches_branch_id ON batches(branch_id);",
            "CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);",
            "CREATE INDEX IF NOT EXISTS idx_batches_start_date ON batches(start_date);",
            
            # Payment table indexes
            "CREATE INDEX IF NOT EXISTS idx_payments_student_id ON payments(student_id);",
            "CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);",
            "CREATE INDEX IF NOT EXISTS idx_payments_mode ON payments(mode);",
            
            # Invoice table indexes
            "CREATE INDEX IF NOT EXISTS idx_invoices_student_id ON invoices(student_id);",
            "CREATE INDEX IF NOT EXISTS idx_invoices_invoice_date ON invoices(invoice_date);",
            "CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);",
            
            # Installment table indexes
            "CREATE INDEX IF NOT EXISTS idx_installments_invoice_id ON installments(invoice_id);",
            "CREATE INDEX IF NOT EXISTS idx_installments_due_date ON installments(due_date);",
            "CREATE INDEX IF NOT EXISTS idx_installments_status ON installments(status);",
            
            # Attendance table indexes
            "CREATE INDEX IF NOT EXISTS idx_attendance_student_id ON student_attendance(student_id);",
            "CREATE INDEX IF NOT EXISTS idx_attendance_date ON student_attendance(date);",
            "CREATE INDEX IF NOT EXISTS idx_attendance_batch_id ON student_attendance(batch_id);",
            
            # User table indexes
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(username);",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);",
            "CREATE INDEX IF NOT EXISTS idx_users_branch_id ON users(branch_id);",
            
            # Composite indexes for common queries
            "CREATE INDEX IF NOT EXISTS idx_students_branch_status ON students(branch_id, status);",
            "CREATE INDEX IF NOT EXISTS idx_leads_branch_status ON leads(branch_id, lead_status);",
            "CREATE INDEX IF NOT EXISTS idx_payments_student_date ON payments(student_id, payment_date);",
        ]
        
        created_count = 0
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                index_name = index_sql.split('idx_')[1].split(' ON')[0]
                print(f"   ✅ {index_name}")
                created_count += 1
            except sqlite3.Error as e:
                if "already exists" not in str(e):
                    print(f"   ⚠️  Index creation warning: {e}")
        
        print(f"\n📈 Created {created_count} performance indexes")
        
        # 3. Run VACUUM and ANALYZE
        print("\n🧹 Cleaning up database...")
        cursor.execute("VACUUM;")
        print("   ✅ VACUUM completed")
        
        # Check if this is SQLite before running SQLite-specific commands
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
        is_sqlite = True
        try:
            cursor.fetchone()
        except Exception:
            is_sqlite = False
        
        if is_sqlite:
            cursor.execute("ANALYZE;")
            print("   ✅ ANALYZE completed")
            
            # 4. Final optimization
            cursor.execute("PRAGMA optimize;")
            print("   ✅ Final optimization completed")
        else:
            print("   ℹ️  ANALYZE and PRAGMA optimize skipped (not SQLite)")
        
        # Commit all changes
        conn.commit()
        conn.close()
        
        # Show results
        print("\n📊 Optimization Results:")
        original_size = os.path.getsize(backup_path) / 1024 / 1024
        optimized_size = os.path.getsize(db_path) / 1024 / 1024
        
        print(f"   📁 Original size: {original_size:.2f} MB")
        print(f"   📁 Optimized size: {optimized_size:.2f} MB")
        
        if optimized_size < original_size:
            saved = ((original_size - optimized_size) / original_size) * 100
            print(f"   💾 Space saved: {saved:.1f}%")
        
        print(f"\n✅ Database optimization completed successfully!")
        print(f"📁 Backup saved as: {backup_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error optimizing database: {e}")
        return False

def verify_optimization():
    """Verify that optimization was successful"""
    
    db_path = 'globalit_education_dev.db'
    
    if not os.path.exists(db_path):
        print('❌ Database file not found')
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("\n🔍 Verification Results:")
        
        # Check if this is SQLite before running SQLite-specific checks
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
        is_sqlite = True
        try:
            cursor.fetchone()
        except Exception:
            is_sqlite = False
        
        if is_sqlite:
            # Check PRAGMA settings
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            print(f"   Journal mode: {journal_mode}")
            
            cursor.execute("PRAGMA synchronous;")
            synchronous = cursor.fetchone()[0]
            print(f"   Synchronous: {synchronous}")
            
            cursor.execute("PRAGMA cache_size;")
            cache_size = cursor.fetchone()[0]
            print(f"   Cache size: {cache_size}")
            
            # Check indexes
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND sql IS NOT NULL;")
            index_count = cursor.fetchone()[0]
            print(f"   Total indexes: {index_count}")
        else:
            print("   ℹ️  Database verification skipped (not SQLite - MySQL configuration handled by server)")
        
        conn.close()
        
        print("✅ Verification completed")
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")

if __name__ == '__main__':
    print("🚀 Database Performance Optimizer")
    print("=" * 50)
    
    # Run optimization
    if optimize_database():
        # Verify results
        verify_optimization()
        
        print("\n🎉 Database optimization completed!")
        print("\n💡 Next steps:")
        print("1. Restart your Flask application")
        print("2. Test page loading speeds")
        print("3. Monitor query performance")
    else:
        print("\n❌ Optimization failed. Check error messages above.")
