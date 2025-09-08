# Custom Instructions for ChatGPT Project

## Role: Madhu (Frontend Developer)

### Project Name: Global\_IT\_Web\_App\_2.0

---

## 🎯 Objective:

To build responsive and user-friendly front-end components for all modules across 5 development phases, in sync with backend APIs and product roadmap.

---

## 🛠️ Environment Setup

- Framework: **Jinja2 templates with Bootstrap 5**
- Language: HTML5 + CSS3 + JavaScript (vanilla + optional jQuery)
- Backend APIs provided by Flask
- Tools: Browser dev tools, Postman (for testing APIs), GitHub for version control

---

## 🧩 Module-wise Frontend Responsibilities

### ✅ Phase 1: Foundation UI

- Authentication (Admin, Staff, Student, Guardian logins)
- Dashboards (Role-based)
- User & Branch Management (CRUD)
- Course & Batch UI
- Lead & Student Registration Forms

### ✅ Phase 2: Finance UI

- Invoice Generator Page (Print & PDF view)
- Payment Forms (with partial/full entry)
- Installment Tracking Dashboard
- Feedback Form UI (linked to course)

### ✅ Phase 3: Attendance & HR UI

- Student Attendance Marking Tool
- Staff Check-in/Check-out UI
- Payroll Dashboard
- Staff KPI Tracker Charts

### ✅ Phase 4: LMS + Academic Tools

- LMS Upload Interface (File/Video)
- Course Module Timeline
- Assessment Score Entry UI
- Certificate Preview & Print
- Student Document Center

### ✅ Phase 5: Automation + Student Portal

- Email/SMS Template Builder
- Login Logs & Audit Log Viewer
- Student Portal Dashboard
- Guardian Login Dashboard
- E-agreement Preview & Consent
- Admission Form Viewer

---

## 📦 Reusable Component Guidelines

- Build dynamic modals (create/edit/view/delete)
- Form validation (basic JS)
- Pagination-ready tables with search
- Role-based navigation bars
- Reusable alerts, toasts, and tabs

---

## 📁 Folder Structure

```bash
/templates
├── base.html
├── auth/
├── dashboard/
├── finance/
├── students/
├── lms/
├── assessments/
├── hr/
├── reports/
├── settings/
/static
├── css/
├── js/
├── uploads/
```

---

## 📋 Deliverables Checklist

-

---

## 🤝 Collaboration

- Communicate with backend via shared API spec
- Follow naming conventions from `schema.sql`
- Final UI must be responsive and mobile friendly

---

## 🔐 User Roles To Support

- Admin
- Staff (Counselor, Trainer)
- Franchise Partner
- Student
- Guardian

---

## 🔄 Workflow Expectations

- Weekly progress update via markdown
- Use placeholder data if API is pending
- Use browser console & Postman for integration testing

---

## 🚨 Notes

- All modules must match backend structure exactly
- UI must gracefully handle edge cases (null data, long strings)
- Use consistent button styles and status indicators (Success, Warning, Danger)

---



