"""
Lead Analytics Utility
Helper functions for lead source tracking and conversion analytics
"""

from models.lead_model import Lead
from models.student_model import Student
from init_db import db
from sqlalchemy import func, and_
from datetime import datetime, timedelta

class LeadAnalytics:
    
    @staticmethod
    def get_lead_source_stats(branch_id=None, start_date=None, end_date=None):
        """
        Get comprehensive lead source statistics including direct admissions
        """
        # Base query for regular leads
        lead_query = Lead.query.filter(Lead.is_deleted == False)
        
        # Base query for students with auto-created leads
        student_query = Student.query.filter(
            Student.is_deleted == 0,
            Student.auto_created_lead == True
        )
        
        # Apply filters
        if branch_id:
            lead_query = lead_query.filter(Lead.branch_id == branch_id)
            student_query = student_query.filter(Student.branch_id == branch_id)
            
        if start_date:
            lead_query = lead_query.filter(Lead.lead_generation_date >= start_date)
            student_query = student_query.filter(Student.admission_date >= start_date)
            
        if end_date:
            lead_query = lead_query.filter(Lead.lead_generation_date <= end_date)
            student_query = student_query.filter(Student.admission_date <= end_date)
        
        # Get regular lead source counts
        regular_leads = lead_query.with_entities(
            Lead.lead_source,
            func.count(Lead.id).label('count'),
            func.sum(func.case([(Lead.lead_stage == 'Closed Won', 1)], else_=0)).label('converted')
        ).group_by(Lead.lead_source).all()
        
        # Get direct admission (auto-created lead) source counts
        direct_admissions = student_query.with_entities(
            Student.lead_source,
            func.count(Student.student_id).label('count')
        ).group_by(Student.lead_source).all()
        
        # Combine the results
        source_stats = {}
        
        # Process regular leads
        for source, count, converted in regular_leads:
            if source not in source_stats:
                source_stats[source] = {
                    'total_leads': 0,
                    'regular_leads': 0,
                    'direct_admissions': 0,
                    'converted_leads': 0,
                    'conversion_rate': 0
                }
            source_stats[source]['regular_leads'] = count
            source_stats[source]['converted_leads'] = converted or 0
            source_stats[source]['total_leads'] += count
        
        # Process direct admissions
        for source, count in direct_admissions:
            if source not in source_stats:
                source_stats[source] = {
                    'total_leads': 0,
                    'regular_leads': 0,
                    'direct_admissions': 0,
                    'converted_leads': 0,
                    'conversion_rate': 0
                }
            source_stats[source]['direct_admissions'] = count
            source_stats[source]['converted_leads'] += count  # Direct admissions are always converted
            source_stats[source]['total_leads'] += count
        
        # Calculate conversion rates
        for source, stats in source_stats.items():
            if stats['total_leads'] > 0:
                stats['conversion_rate'] = round(
                    (stats['converted_leads'] / stats['total_leads']) * 100, 1
                )
        
        return source_stats
    
    @staticmethod
    def get_conversion_funnel(branch_id=None, start_date=None, end_date=None):
        """
        Get conversion funnel data including direct admissions
        """
        # Regular lead funnel
        lead_query = Lead.query.filter(Lead.is_deleted == False)
        
        if branch_id:
            lead_query = lead_query.filter(Lead.branch_id == branch_id)
        if start_date:
            lead_query = lead_query.filter(Lead.lead_generation_date >= start_date)
        if end_date:
            lead_query = lead_query.filter(Lead.lead_generation_date <= end_date)
        
        funnel_data = lead_query.with_entities(
            Lead.lead_stage,
            func.count(Lead.id).label('count')
        ).group_by(Lead.lead_stage).all()
        
        # Count direct admissions
        student_query = Student.query.filter(
            Student.is_deleted == 0,
            Student.auto_created_lead == True
        )
        
        if branch_id:
            student_query = student_query.filter(Student.branch_id == branch_id)
        if start_date:
            student_query = student_query.filter(Student.admission_date >= start_date)
        if end_date:
            student_query = student_query.filter(Student.admission_date <= end_date)
        
        direct_admission_count = student_query.count()
        
        # Process funnel data
        funnel = {}
        for stage, count in funnel_data:
            funnel[stage] = count
        
        # Add direct admissions to "Closed Won"
        if 'Closed Won' not in funnel:
            funnel['Closed Won'] = 0
        funnel['Closed Won'] += direct_admission_count
        
        return funnel
    
    @staticmethod
    def get_missed_lead_recovery_stats(branch_id=None, days_back=30):
        """
        Calculate how many leads would have been missed without auto-creation
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        query = Student.query.filter(
            Student.is_deleted == 0,
            Student.auto_created_lead == True,
            Student.admission_date >= start_date,
            Student.admission_date <= end_date
        )
        
        if branch_id:
            query = query.filter(Student.branch_id == branch_id)
        
        recovered_leads = query.count()
        
        # Get regular leads in the same period for comparison
        regular_query = Lead.query.filter(
            Lead.is_deleted == False,
            Lead.lead_generation_date >= start_date,
            Lead.lead_generation_date <= end_date
        )
        
        if branch_id:
            regular_query = regular_query.filter(Lead.branch_id == branch_id)
        
        regular_leads = regular_query.count()
        
        return {
            'recovered_leads': recovered_leads,
            'regular_leads': regular_leads,
            'total_leads': recovered_leads + regular_leads,
            'recovery_percentage': round((recovered_leads / (recovered_leads + regular_leads)) * 100, 1) if (recovered_leads + regular_leads) > 0 else 0
        }
    
    @staticmethod
    def get_lead_to_student_mapping():
        """
        Get mapping between leads and students to check conversion linkage
        """
        # Students with original lead linkage
        linked_students = db.session.query(
            Student.student_id,
            Student.full_name,
            Student.original_lead_id,
            Student.auto_created_lead,
            Lead.lead_sl_number
        ).outerjoin(
            Lead, Student.original_lead_id == Lead.id
        ).filter(
            Student.is_deleted == 0,
            Student.original_lead_id.isnot(None)
        ).all()
        
        return linked_students
