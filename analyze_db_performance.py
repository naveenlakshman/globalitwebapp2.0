#!/usr/bin/env python
"""
Database Performance Analysis Script
Analyzes current database state and identifies performance bottlenecks
"""

import sqlite3
import os
import sys

def analyze_database():
    """Analyze database performance and structure"""
    
    # Check if database exists
    db_path = 'globalit_education_dev.db'
    if not os.path.exists(db_path):
        print('❌ Database file not found')
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print('🔍 Current Database Analysis')
        print('=' * 50)
        
        # Check database size
        size = os.path.getsize(db_path) / 1024 / 1024
        print(f'Database size: {size:.2f} MB')
        
        # Check existing indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL;")
        indexes = cursor.fetchall()
        print(f'\nExisting indexes: {len(indexes)}')
        for idx in indexes[:10]:  # Show first 10
            print(f'  - {idx[0]}')
        if len(indexes) > 10:
            print(f'  ... and {len(indexes) - 10} more')
        
        # Check table record counts
        tables = ['students', 'leads', 'batches', 'payments', 'users', 'branches', 'invoices', 'installments']
        print('\nTable record counts:')
        for table in tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                count = cursor.fetchone()[0]
                print(f'  {table}: {count:,} records')
            except sqlite3.Error as e:
                print(f'  {table}: table not found or error - {e}')
        
        # Check PRAGMA settings
        print('\n🔧 Current PRAGMA Settings:')
        pragmas = ['journal_mode', 'synchronous', 'cache_size', 'temp_store']
        for pragma in pragmas:
            try:
                cursor.execute(f'PRAGMA {pragma};')
                value = cursor.fetchone()[0]
                print(f'  {pragma}: {value}')
            except:
                print(f'  {pragma}: unable to read')
        
        # Performance analysis
        print('\n⚡ Performance Issues Detected:')
        issues_found = False
        
        # Check for large tables without proper indexing
        try:
            cursor.execute('SELECT COUNT(*) FROM leads')
            leads_count = cursor.fetchone()[0]
            if leads_count > 500:
                print(f'⚠️  Large leads table ({leads_count:,} records) - may need optimization')
                issues_found = True
        except:
            pass
        
        try:
            cursor.execute('SELECT COUNT(*) FROM students')
            students_count = cursor.fetchone()[0]
            if students_count > 1000:
                print(f'⚠️  Large students table ({students_count:,} records) - may need optimization')
                issues_found = True
        except:
            pass
        
        # Check for missing indexes on foreign keys
        recommended_indexes = [
            'idx_students_batch_id',
            'idx_students_branch_id', 
            'idx_leads_branch_id',
            'idx_leads_assigned_to',
            'idx_payments_student_id',
            'idx_invoices_student_id'
        ]
        
        missing_indexes = []
        for idx in recommended_indexes:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (idx,))
            if not cursor.fetchone():
                missing_indexes.append(idx)
        
        if missing_indexes:
            print(f'⚠️  Missing recommended indexes:')
            for idx in missing_indexes:
                print(f'    - {idx}')
            issues_found = True
        
        if not issues_found:
            print('✅ No major performance issues detected')
        
        # Recommendations
        print('\n💡 Performance Recommendations:')
        print('1. Add proper indexes on foreign key columns')
        print('2. Optimize pagination queries with LIMIT/OFFSET')
        print('3. Use SQLite WAL mode for better concurrency')
        print('4. Implement query result caching for dashboard stats')
        print('5. Consider pagination size reduction for large tables')
        
        conn.close()
        
    except Exception as e:
        print(f'❌ Error analyzing database: {e}')

if __name__ == '__main__':
    analyze_database()
