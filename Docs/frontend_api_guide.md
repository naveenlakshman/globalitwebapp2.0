# 🧠 Global IT Backend - Frontend Integration Guide

This document provides a detailed explanation of the current project folder structure, API endpoints, data structures, and how your frontend should integrate with the backend.

---

## 📁 Folder Structure (root)

```
Global_IT_Web_App_2.0/
│
├── globalit_app/                  # Flask application package
│   ├── __init__.py                # Flask app factory
│   ├── init_db.py                 # DB setup & patch/migration logic
│   ├── config.py                  # App configuration
│   ├── utils/
│   │   └── timezone_helper.py     # Converts UTC to IST
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── user_model.py
│   │   ├── student_model.py
│   │   ├── batch_model.py
│   │   ├── invoice_model.py
│   │   ├── payment_model.py
│   │   ├── installment_model.py
│   │   ├── login_logs_model.py
│   │   └── system_audit_logs_model.py
│   └── routes/                    # API Route handlers (Flask Blueprints)
│       ├── auth_routes.py
│       ├── student_routes.py
│       ├── invoice_routes.py
│       ├── dashboard_routes.py
│       └── installment_routes.py (coming soon)
│
├── run.py                         # Entry point to start Flask app
├── schema.sql                     # Initial database schema
└── requirements.txt               # Python dependencies
```

---

## 🚀 API Blueprint Summary

| Module        | URL Prefix         | File                    |
|---------------|--------------------|--------------------------|
| Auth          | `/auth`            | auth_routes.py           |
| Students      | `/students`        | student_routes.py        |
| Invoices      | `/invoices`        | invoice_routes.py        |
| Dashboard     | `/dashboard`       | dashboard_routes.py      |

---

## 🔗 Key API Endpoints

### 🧑 Students

- **Create Student:** `POST /students/`
  ```json
  {
    "student_id": "S001",
    "full_name": "Ananya Sharma",
    "gender": "Female",
    "dob": "2001-04-12",
    "mobile": "9876543210",
    "email": "ananya@example.com",
    "address": "Hoskote",
    "admission_date": "2025-08-02",
    "batch_id": 1
  }
  ```
- Response includes `id`, `registered_on` in IST.

### 💳 Invoices & Payments

- **Create Invoice:** `POST /invoices/`
  ```json
  {
    "student_id": 1,
    "total_amount": 15000,
    "discount": 2000
  }
  ```

- **Record Payment:** `POST /invoices/pay`
  ```json
  {
    "invoice_id": 1,
    "amount": 2000,
    "mode": "Cash",
    "utr_number": "",
    "notes": "1st installment"
  }
  ```
  ✅ Overpayment blocked. IST timestamp returned.

- **Get Payment History:** `GET /invoices/<invoice_id>/payments`

- **Create Installments:** `POST /invoices/installments/create`
  ```json
  {
    "invoice_id": 1,
    "count": 3,
    "start_date": "2025-08-05"
  }
  ```

### 📊 Dashboard

- `GET /dashboard/` returns:
  ```json
  {
    "total_students": 25,
    "total_batches": 5,
    "total_revenue": 145000
  }
  ```

---

## 🔁 UTC to IST
- All datetime values stored in UTC.
- Use `paid_on`, `created_at`, `registered_on` fields (already converted using `utc_to_ist()` from utils).

---

## ⚠️ Notes for Frontend

- All responses are JSON.
- Use proper form validation before hitting endpoints.
- Handle 400 and 404 errors from backend.
- Avoid duplicate payments (backend enforces check).
- You don’t need to worry about authentication in current phase.

---

## ✅ Coming Soon (Phase 3)
- Installment status auto-updates ✅
- Admin user login and session
- Filter routes for `/installments/pending`, `/overdue`, `/due-today`
- Basic UI for Student, Invoice, and Payment modules

Let me know if you need example frontend forms or mock API test cases using Postman collections.

Happy coding 🚀

