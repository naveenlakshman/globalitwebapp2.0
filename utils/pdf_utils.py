from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from datetime import datetime
import os
import tempfile
import pandas as pd

def generate_receipt_pdf(payment):
    """Generate PDF receipt for payment"""
    
    # Create temporary file
    temp_dir = tempfile.gettempdir()
    receipt_number = f"RCP-{payment.id}"
    filename = f"receipt_{receipt_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(temp_dir, filename)
    
    # Create PDF document
    doc = SimpleDocTemplate(filepath, pagesize=A4)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    normal_style = styles['Normal']
    
    # Header
    story.append(Paragraph("GLOBAL IT EDUCATION", title_style))
    story.append(Paragraph("Payment Receipt", styles['Heading2']))
    story.append(Spacer(1, 20))
    
    # Get student and branch info through invoice relationship
    student = payment.invoice.student if payment.invoice else None
    branch_name = student.batch.branch.branch_name if student and hasattr(student, 'batch') and student.batch and student.batch.branch else 'N/A'
    course_name = student.course_name if student else 'N/A'
    
    # Receipt details
    receipt_data = [
        ['Receipt No:', receipt_number],
        ['Date:', payment.paid_on.strftime('%d-%m-%Y %H:%M:%S') if payment.paid_on else ''],
        ['Student ID:', student.student_id if student else 'N/A'],
        ['Student Name:', student.full_name if student else 'N/A'],
        ['Branch:', branch_name],
        ['Course:', course_name],
        ['Amount Paid:', f'₹ {payment.amount:,.2f}'],
        ['Payment Method:', payment.mode.title()],
    ]
    
    # Add optional fields that exist in Payment model
    if payment.utr_number:
        receipt_data.append(['UTR Number:', payment.utr_number])
    
    if payment.discount_amount and payment.discount_amount > 0:
        receipt_data.append(['Discount:', f'₹ {payment.discount_amount:,.2f}'])
    
    if payment.notes:
        receipt_data.append(['Notes:', payment.notes])
    
    receipt_table = Table(receipt_data, colWidths=[2*inch, 3*inch])
    receipt_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(receipt_table)
    story.append(Spacer(1, 30))
    
    # Notes
    if payment.notes:
        story.append(Paragraph(f"<b>Notes:</b> {payment.notes}", normal_style))
        story.append(Spacer(1, 20))
    
    # Footer
    story.append(Paragraph("Thank you for your payment!", styles['Heading3']))
    story.append(Spacer(1, 20))
    story.append(Paragraph("This is a computer generated receipt.", normal_style))
    
    # Build PDF
    doc.build(story)
    
    return filepath

def generate_invoice_pdf(invoice):
    """Generate PDF invoice"""
    
    # Create temporary file
    temp_dir = tempfile.gettempdir()
    filename = f"invoice_{invoice.invoice_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(temp_dir, filename)
    
    # Create PDF document
    doc = SimpleDocTemplate(filepath, pagesize=A4)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    # Header
    story.append(Paragraph("GLOBAL IT EDUCATION", title_style))
    story.append(Paragraph("INVOICE", styles['Heading2']))
    story.append(Spacer(1, 20))
    
    # Invoice details
    invoice_data = [
        ['Invoice No:', invoice.invoice_number],
        ['Date:', invoice.invoice_date.strftime('%d-%m-%Y') if invoice.invoice_date else ''],
        ['Due Date:', invoice.due_date.strftime('%d-%m-%Y') if invoice.due_date else ''],
        ['Student ID:', invoice.student.student_id if invoice.student else ''],
        ['Student Name:', invoice.student.full_name if invoice.student else ''],
        ['Course:', invoice.course_name or ''],
        ['Branch:', invoice.branch.branch_name if invoice.branch else ''],
    ]
    
    invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
    invoice_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (1, 0), (1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(invoice_table)
    story.append(Spacer(1, 30))
    
    # Items table
    items_data = [['Description', 'Amount']]
    items_data.append(['Course Fee', f'₹ {invoice.total_amount:,.2f}'])
    
    if invoice.discount_amount and invoice.discount_amount > 0:
        items_data.append(['Discount', f'- ₹ {invoice.discount_amount:,.2f}'])
    
    if invoice.tax_amount and invoice.tax_amount > 0:
        items_data.append(['Tax', f'₹ {invoice.tax_amount:,.2f}'])
    
    items_data.append(['Total Amount', f'₹ {invoice.final_amount:,.2f}'])
    
    items_table = Table(items_data, colWidths=[4*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    
    story.append(items_table)
    story.append(Spacer(1, 30))
    
    # Payment schedule if installments exist
    if invoice.installments:
        story.append(Paragraph("Payment Schedule:", styles['Heading3']))
        story.append(Spacer(1, 10))
        
        schedule_data = [['Installment', 'Due Date', 'Amount', 'Status']]
        for installment in invoice.installments:
            status = 'Paid' if installment.is_paid else 'Pending'
            if installment.is_overdue() and not installment.is_paid:
                status = 'Overdue'
            
            schedule_data.append([
                f'#{installment.installment_number}',
                installment.due_date.strftime('%d-%m-%Y') if installment.due_date else '',
                f'₹ {installment.amount:,.2f}',
                status
            ])
        
        schedule_table = Table(schedule_data, colWidths=[1*inch, 1.5*inch, 1.5*inch, 1*inch])
        schedule_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(schedule_table)
        story.append(Spacer(1, 20))
    
    # Terms and conditions
    story.append(Paragraph("Terms & Conditions:", styles['Heading4']))
    terms = [
        "1. Payment is due on or before the due date mentioned.",
        "2. Late payment charges may apply for overdue payments.",
        "3. Fees once paid are non-refundable.",
        "4. For any queries, contact the administration office."
    ]
    
    for term in terms:
        story.append(Paragraph(term, styles['Normal']))
    
    story.append(Spacer(1, 30))
    story.append(Paragraph("Thank you for choosing Global IT Education!", styles['Heading3']))
    
    # Build PDF
    doc.build(story)
    
    return filepath

def generate_fee_structure_pdf(course_name, fee_details):
    """Generate fee structure PDF"""
    
    # Create temporary file
    temp_dir = tempfile.gettempdir()
    filename = f"fee_structure_{course_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(temp_dir, filename)
    
    # Create PDF document
    doc = SimpleDocTemplate(filepath, pagesize=A4)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    # Header
    story.append(Paragraph("GLOBAL IT EDUCATION", title_style))
    story.append(Paragraph(f"Fee Structure - {course_name}", styles['Heading2']))
    story.append(Spacer(1, 20))
    
    # Fee structure table
    fee_data = [['Component', 'Amount']]
    total_fee = 0
    
    for component, amount in fee_details.items():
        fee_data.append([component, f'₹ {amount:,.2f}'])
        total_fee += amount
    
    fee_data.append(['Total Course Fee', f'₹ {total_fee:,.2f}'])
    
    fee_table = Table(fee_data, colWidths=[4*inch, 1.5*inch])
    fee_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
    ]))
    
    story.append(fee_table)
    story.append(Spacer(1, 30))
    
    # Additional information
    story.append(Paragraph("Payment Options:", styles['Heading3']))
    payment_info = [
        "• Full payment: 5% discount on total fee",
        "• Installment payment: Available in 2, 3, or 4 installments",
        "• Online payment: UPI, Credit/Debit Card, Net Banking",
        "• Offline payment: Cash, Cheque accepted"
    ]
    
    for info in payment_info:
        story.append(Paragraph(info, styles['Normal']))
    
    story.append(Spacer(1, 20))
    story.append(Paragraph("Contact us for more information!", styles['Heading3']))
    
    # Build PDF
    doc.build(story)
    
    return filepath

def generate_financial_report(report_data, report_type='summary', date_from=None, date_to=None):
    """Generate financial report PDF"""
    
    # Create temporary file
    temp_dir = tempfile.gettempdir()
    filename = f"financial_report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(temp_dir, filename)
    
    # Create PDF document
    doc = SimpleDocTemplate(filepath, pagesize=A4)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    # Header
    story.append(Paragraph("GLOBAL IT EDUCATION", title_style))
    story.append(Paragraph("FINANCIAL REPORT", styles['Heading2']))
    story.append(Spacer(1, 20))
    
    # Report period
    if date_from and date_to:
        period_text = f"Report Period: {date_from} to {date_to}"
        story.append(Paragraph(period_text, styles['Heading3']))
        story.append(Spacer(1, 20))
    
    # Summary data
    if 'total_collected' in report_data:
        summary_data = [
            ['Total Amount Collected:', f"₹ {report_data['total_collected']:,.2f}"],
            ['Total Transactions:', str(report_data.get('payment_count', 0))],
            ['Report Generated:', datetime.now().strftime('%d-%m-%Y %H:%M:%S')]
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 30))
    
    # Payment method breakdown
    if 'method_breakdown' in report_data and report_data['method_breakdown']:
        story.append(Paragraph("Payment Method Breakdown:", styles['Heading3']))
        story.append(Spacer(1, 10))
        
        method_data = [['Payment Method', 'Amount', 'Transactions']]
        for method, amount, count in report_data['method_breakdown']:
            method_data.append([
                method.title(),
                f"₹ {amount:,.2f}",
                str(count)
            ])
        
        method_table = Table(method_data, colWidths=[2*inch, 2*inch, 1.5*inch])
        method_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(method_table)
        story.append(Spacer(1, 30))
    
    # Branch breakdown (if available)
    if 'branch_breakdown' in report_data and report_data['branch_breakdown']:
        story.append(Paragraph("Branch-wise Breakdown:", styles['Heading3']))
        story.append(Spacer(1, 10))
        
        branch_data = [['Branch', 'Amount', 'Transactions']]
        for branch, amount, count in report_data['branch_breakdown']:
            branch_data.append([
                branch,
                f"₹ {amount:,.2f}",
                str(count)
            ])
        
        branch_table = Table(branch_data, colWidths=[2.5*inch, 2*inch, 1.5*inch])
        branch_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(branch_table)
        story.append(Spacer(1, 30))
    
    # Footer
    story.append(Paragraph("*** End of Report ***", styles['Heading3']))
    story.append(Spacer(1, 20))
    story.append(Paragraph("This is a computer generated report.", styles['Normal']))
    
    # Build PDF
    doc.build(story)
    
    return filepath

def generate_financial_report_excel(report_data, report_type='summary', date_from=None, date_to=None):
    """Generate financial report Excel file"""
    
    # Create temporary file
    temp_dir = tempfile.gettempdir()
    filename = f"financial_report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(temp_dir, filename)
    
    # Create Excel writer
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        
        # Summary sheet
        summary_data = {
            'Metric': ['Total Amount Collected', 'Total Transactions', 'Average Payment', 'Report Period', 'Report Generated'],
            'Value': [
                f"₹ {report_data.get('total_collected', 0):,.2f}",
                str(report_data.get('payment_count', 0)),
                f"₹ {report_data.get('average_payment', 0):,.2f}",
                f"{date_from} to {date_to}" if date_from and date_to else "All Time",
                datetime.now().strftime('%d-%m-%Y %H:%M:%S')
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Payment method breakdown sheet
        if 'method_breakdown' in report_data and report_data['method_breakdown']:
            method_data = []
            for method, amount, count, percentage in report_data['method_breakdown']:
                method_data.append({
                    'Payment Method': method.upper(),
                    'Amount': amount,
                    'Count': count,
                    'Percentage': f"{percentage:.1f}%"
                })
            
            method_df = pd.DataFrame(method_data)
            method_df.to_excel(writer, sheet_name='Payment Methods', index=False)
        
        # Branch breakdown sheet (if available)
        if 'branch_breakdown' in report_data and report_data['branch_breakdown']:
            branch_data = []
            for branch_name, amount, count, percentage in report_data['branch_breakdown']:
                branch_data.append({
                    'Branch': branch_name,
                    'Amount': amount,
                    'Count': count,
                    'Percentage': f"{percentage:.1f}%"
                })
            
            branch_df = pd.DataFrame(branch_data)
            branch_df.to_excel(writer, sheet_name='Branch Breakdown', index=False)
        
        # Daily breakdown sheet (for detailed reports)
        if 'daily_breakdown' in report_data and report_data['daily_breakdown']:
            daily_data = []
            for date, amount, count in report_data['daily_breakdown']:
                daily_data.append({
                    'Date': date,
                    'Amount Collected': amount,
                    'Number of Payments': count,
                    'Average per Payment': amount / count if count > 0 else 0
                })
            
            daily_df = pd.DataFrame(daily_data)
            daily_df.to_excel(writer, sheet_name='Daily Breakdown', index=False)
        
        # Comparison data sheet (for comparison reports)
        if 'comparison_data' in report_data and report_data['comparison_data']:
            comp_data = report_data['comparison_data']
            comparison_data = {
                'Period': ['Current Period', 'Previous Period', 'Growth (Amount)', 'Growth (Count)'],
                'Value': [
                    f"₹ {comp_data['current_period']['total']:,.2f} ({comp_data['current_period']['count']} payments)",
                    f"₹ {comp_data['previous_period']['total']:,.2f} ({comp_data['previous_period']['count']} payments)",
                    f"{comp_data['growth']['amount']:+.1f}%",
                    f"{comp_data['growth']['count']:+.1f}%"
                ]
            }
            comparison_df = pd.DataFrame(comparison_data)
            comparison_df.to_excel(writer, sheet_name='Period Comparison', index=False)
    
    return filepath
