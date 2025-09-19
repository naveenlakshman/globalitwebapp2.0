# lead_routes.py  — merged fixed core + import/export + reporting

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session, send_file, Response
from sqlalchemy import and_, or_, func, desc, asc, case
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta, date, time
from utils.timezone_helper import get_current_ist_datetime, get_current_ist_formatted, format_datetime_indian
import io
import csv
import uuid
import re

# ─── Adjust these imports to your project structure ─────────────────────────────
from models.lead_model import Lead, LeadFollowUp
from models.student_model import Student
from models.user_model import User
from models.branch_model import Branch
from models.course_model import Course
from utils.auth import login_required
from utils.role_permissions import get_user_accessible_branches
from init_db import db
# If you prefer flask_login current_user, refactor session uses accordingly.
# ────────────────────────────────────────────────────────────────────────────────

try:
    import pandas as pd  # for XLSX export (optional)
    HAS_PANDAS = True
except Exception:
    HAS_PANDAS = False

lead_bp = Blueprint("leads", __name__, url_prefix="/leads")

# ==============================================================================
# Access Control - Block Trainer Access to Lead Management
# ==============================================================================

@lead_bp.before_request
def check_trainer_access():
    """Block all trainer access to lead management routes"""
    current_user = User.query.get(session.get("user_id"))
    if current_user and current_user.role == "trainer":
        flash("Access denied. Trainers do not have permission to access lead management. Please focus on your teaching responsibilities.", "error")
        return redirect(url_for('dashboard_bp.trainer_dashboard'))

# ==============================================================================
# Helpers (responses, parsing, normalization, RBAC, etc.)
# ==============================================================================

MAX_PER_PAGE = 100
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def ok(data=None, status=200, **meta):
    return jsonify({"ok": True, "data": data, **meta}), status

def err(message, status=400):
    return jsonify({"ok": False, "error": message}), status

def wants_json_response():
    return request.args.get("format") == "json" or \
           request.accept_mimetypes.best == "application/json"

def _dt_fromiso(s):
    """Parse ISO datetime like '2025-08-10T10:30:00Z' or '2025-08-10 10:30:00' → naive UTC datetime."""
    if not s:
        return None
    s = s.strip().replace("Z", "")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def _date_fromiso(s):
    if not s: return None
    # Common formats
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

def _day_bounds(d: date):
    """Return [start, end) UTC day bounds for a date."""
    start = datetime.combine(d, time.min)
    end = start + timedelta(days=1)
    return start, end

def _norm_mobile(m): return "".join(filter(str.isdigit, (m or "").strip()))
def _norm_email(e):  return (e or "").strip().lower()
def _csv_safe(s):
    if s is None: return ''
    s = str(s)
    return "'" + s if s[:1] in ('=', '+', '-', '@') else s

def _norm_enum_field(value, allowed_values=None):
    """Normalize enum field values, converting empty strings to None"""
    if not value or value.strip() == '':
        return None
    value = value.strip()
    # If allowed_values is provided, validate against them
    if allowed_values and value not in allowed_values:
        return None
    return value

def _validate_mobile(m):
    m = _norm_mobile(m)
    # For Indian mobile numbers, we expect exactly 10 digits
    # Valid Indian mobile numbers start with 6, 7, 8, or 9
    if len(m) != 10:
        return False
    # Check if it starts with valid Indian mobile prefix
    return m[0] in ['6', '7', '8', '9']

def _validate_email(e):
    e = _norm_email(e)
    return not e or EMAIL_RE.match(e) is not None

def _user_branch_id():
    uid = session.get("user_id")
    u = User.query.get(uid) if uid else None
    return getattr(u, "branch_id", None) or session.get("user_branch_id")

def _user_has_corporate_access(user: User):
    return getattr(user, "has_corporate_access", lambda: False)()

def _get_users_for_assignment(current_user: User, branch_ids=None):
    """Get users available for lead assignment based on current user's role and branch access"""
    # Only show roles that actually handle lead follow-ups: branch_manager, franchise, staff
    LEAD_HANDLER_ROLES = ["branch_manager", "franchise", "staff"]
    
    if current_user.role == "admin":
        # Admin can assign to lead handlers in any branch
        if branch_ids:
            return User.query.filter(
                User.is_deleted == False,
                User.branch_id.in_(branch_ids),
                User.role.in_(LEAD_HANDLER_ROLES)
            ).all()
        else:
            return User.query.filter(
                User.is_deleted == False,
                User.role.in_(LEAD_HANDLER_ROLES)
            ).all()
    
    elif current_user.role == "regional_manager":
        # Regional manager can assign to lead handlers in their accessible branches
        accessible_branches = get_user_accessible_branches(current_user.id) or []
        if branch_ids:
            # Filter to only branches that are both accessible and requested
            allowed_branches = list(set(accessible_branches) & set(branch_ids))
        else:
            allowed_branches = accessible_branches
        
        if allowed_branches:
            return User.query.filter(
                User.is_deleted == False,
                User.branch_id.in_(allowed_branches),
                User.role.in_(LEAD_HANDLER_ROLES)
            ).all()
        else:
            return []
    
    elif current_user.role in ["branch_manager", "franchise"]:
        # Branch manager can only assign to lead handlers in their own branch
        user_branch_id = _user_branch_id()
        if user_branch_id:
            if branch_ids and user_branch_id not in branch_ids:
                # If specific branches requested and current user's branch not in list, return empty
                return []
            return User.query.filter(
                User.is_deleted == False,
                User.branch_id == user_branch_id,
                User.role.in_(LEAD_HANDLER_ROLES)
            ).all()
        else:
            return []
    
    elif current_user.role == "staff":
        # Staff can only assign to themselves or other staff in same branch
        user_branch_id = _user_branch_id()
        if user_branch_id:
            if branch_ids and user_branch_id not in branch_ids:
                return []
            return User.query.filter(
                User.is_deleted == False,
                User.branch_id == user_branch_id,
                User.role == "staff"
            ).all()
        else:
            return []
    
    else:
        # Other roles (like trainer, student, parent) should not have assignment privileges
        return []

def _scope_leads_for_user(query, user: User):
    """Apply branch/user scoping to a Lead query based on role."""
    if user.role == "admin":
        return query
    if user.role == "regional_manager":
        branches = get_user_accessible_branches(user.id) or []
        return query.filter(Lead.branch_id.in_(branches)) if branches else query.filter(False)
    if user.role == "franchise":
        # Handle multi-branch franchise users
        user_branch_ids = session.get("user_branch_ids", [])
        if user_branch_ids:
            # Multi-branch franchise user - use all assigned branches
            return query.filter(Lead.branch_id.in_(user_branch_ids))
        else:
            # Single branch fallback
            ubid = _user_branch_id()
            return query.filter(Lead.branch_id == ubid) if ubid else query.filter(False)
    if user.role in ["branch_manager", "staff"]:
        ubid = _user_branch_id()
        return query.filter(Lead.branch_id == ubid) if ubid else query.filter(False)
    # Trainers should not have access to lead management - business logic violation
    # if user.role == "trainer":
    #     return query.filter(Lead.assigned_to_user_id == user.id)
    return query.filter(False)

def _can_access_lead(user: User, lead: Lead):
    if user.role == "admin":
        return True
    if user.role == "regional_manager":
        branches = get_user_accessible_branches(user.id) or []
        return lead.branch_id in branches
    if user.role == "franchise":
        # Handle multi-branch franchise users
        user_branch_ids = session.get("user_branch_ids", [])
        if user_branch_ids:
            # Multi-branch franchise user - check if lead branch is in assigned branches
            return lead.branch_id in user_branch_ids
        else:
            # Single branch fallback
            return lead.branch_id == _user_branch_id()
    if user.role in ["branch_manager", "staff"]:
        return lead.branch_id == _user_branch_id()
    # Trainers should not have access to lead management
    # if user.role == "trainer":
    #     return lead.assigned_to_user_id == user.id
    return False

def _can_edit_lead(user: User, lead: Lead):
    if user.role == "admin":
        return True
    if user.role in ["regional_manager", "branch_manager", "franchise"]:
        return _can_access_lead(user, lead)
    if user.role == "staff":
        return lead.branch_id == _user_branch_id() and (lead.assigned_to_user_id in (None, user.id))
    # Trainers should not have access to lead management
    # if user.role == "trainer":
    #     return lead.assigned_to_user_id == user.id
    return False

def _generate_lead_serial_number(branch_id):
    """Robust unique generator with collision avoidance."""
    branch = Branch.query.get(branch_id)
    branch_code = branch.branch_code if branch else "UNK"
    today_str = get_current_ist_datetime().strftime("%Y%m%d")
    for _ in range(8):
        seq = uuid.uuid4().int % 1000  # 000–999
        candidate = f"{branch_code}{today_str}-{seq:03d}"
        if not Lead.query.filter_by(lead_sl_number=candidate).first():
            return candidate
    ts = get_current_ist_datetime().strftime("%H%M%S%f")[-6:]
    return f"{branch_code}{today_str}-{ts}"

# ==============================================================================
# List / Create / Read / Update / Delete
# ==============================================================================

@lead_bp.route("/", methods=["GET"])
@login_required
def lead_list():
    """List leads with filtering and pagination"""
    try:
        current_user = User.query.get(session.get("user_id"))
        query = _scope_leads_for_user(Lead.query.filter_by(is_deleted=False), current_user)

        filters = {}

        # Status / Source / Priority
        status = request.args.get("status")
        source = request.args.get("source")
        priority = request.args.get("priority")
        if status:   query = query.filter(Lead.lead_status == status);   filters["status"] = status
        if source:   query = query.filter(Lead.lead_source == source);   filters["source"] = source
        if priority: query = query.filter(Lead.priority == priority);    filters["priority"] = priority

        # Branch filter (admin / regional_manager only)
        branch_id = request.args.get("branch_id", type=int)
        if branch_id and current_user.role in ["admin", "regional_manager"]:
            query = query.filter(Lead.branch_id == branch_id); filters["branch_id"] = branch_id

        # Assigned to
        assigned_to = request.args.get("assigned_to", type=int)
        unassigned_only = request.args.get("unassigned_only")
        if assigned_to:
            query = query.filter(Lead.assigned_to_user_id == assigned_to); filters["assigned_to"] = assigned_to
        elif unassigned_only:
            query = query.filter(Lead.assigned_to_user_id.is_(None)); filters["unassigned_only"] = "1"

        # Search
        q = request.args.get("q")
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Lead.name.ilike(like),
                                     Lead.mobile.ilike(like),
                                     Lead.email.ilike(like),
                                     Lead.lead_sl_number.ilike(like)))
            filters["q"] = q

        # Date range on lead_generation_date
        df = _date_fromiso(request.args.get("date_from"))
        dt_ = _date_fromiso(request.args.get("date_to"))
        if df:
            start, _ = _day_bounds(df)
            query = query.filter(Lead.lead_generation_date >= start)
            filters["date_from"] = df.isoformat()
        if dt_:
            _, end = _day_bounds(dt_)
            query = query.filter(Lead.lead_generation_date < end)
            filters["date_to"] = dt_.isoformat()

        # Sorting
        sort_by = request.args.get("sort", "created_at")
        sort_order = request.args.get("order", "desc")
        if hasattr(Lead, sort_by):
            col = getattr(Lead, sort_by)
            query = query.order_by(desc(col) if sort_order == "desc" else asc(col))
        else:
            query = query.order_by(desc(Lead.created_at))

        # Pagination with caps
        page = max(request.args.get("page", 1, type=int), 1)
        per_page = request.args.get("per_page", 20, type=int)
        per_page = max(1, min(per_page, MAX_PER_PAGE))

        leads = query.paginate(page=page, per_page=per_page, error_out=False)

        # Calculate statistics for the dashboard cards
        base_query = _scope_leads_for_user(Lead.query.filter_by(is_deleted=False), current_user)
        
        # Active leads only (not converted or lost)
        active_leads_query = base_query.filter(
            ~Lead.lead_status.in_(['Converted', 'Not Interested'])
        )
        
        stats = {
            'open_count': base_query.filter(Lead.lead_status == 'Open').count(),
            'converted_count': base_query.filter(Lead.lead_status == 'Converted').count(),
            'hot_count': active_leads_query.filter(Lead.priority == 'Hot').count(),  # Only active hot leads
            'total_count': base_query.count()
        }

        # filter helpers for HTML form population
        branches = []
        users = []
        if current_user.role == "admin":
            branches = Branch.query.filter_by(is_deleted=False).all()
            users = _get_users_for_assignment(current_user)
        elif current_user.role == "regional_manager":
            accessible = get_user_accessible_branches(current_user.id) or []
            if accessible:
                branches = Branch.query.filter(Branch.id.in_(accessible)).all()
                users = _get_users_for_assignment(current_user, accessible)
        elif current_user.role == "branch_manager":
            ubid = _user_branch_id()
            if ubid:
                b = Branch.query.get(ubid); branches = [b] if b else []
                users = _get_users_for_assignment(current_user, [ubid])
        elif current_user.role == "franchise":
            ubid = _user_branch_id()
            if ubid:
                b = Branch.query.get(ubid); branches = [b] if b else []
                users = _get_users_for_assignment(current_user, [ubid])
        elif current_user.role == "staff":
            ubid = _user_branch_id()
            if ubid:
                b = Branch.query.get(ubid); branches = [b] if b else []
                users = _get_users_for_assignment(current_user, [ubid])

        if wants_json_response():
            return ok(
                data=[l.to_dict() for l in leads.items],
                pagination={"page": leads.page, "pages": leads.pages, "per_page": leads.per_page, "total": leads.total},
                filters=filters,
                stats=stats
            )

        return render_template("leads/lead_list.html", 
                               leads=leads, 
                               filters=filters, 
                               branches=branches, 
                               users=users,
                               **stats)

    except Exception as e:
        if wants_json_response():
            return err(f"Error loading leads: {str(e)}", 500)
        
        # Return error page for regular requests
        flash(f"Error loading leads: {str(e)}", "error")
        return render_template("leads/lead_list.html", 
                               leads=None, 
                               filters={}, 
                               branches=[], 
                               users=[],
                               open_count=0,
                               converted_count=0,
                               hot_count=0,
                               total_count=0)

@lead_bp.route("/create-new", methods=["GET"])
@login_required
def lead_create_new():
    """Create lead form using new template (lead_create.html)"""
    try:
        current_user = User.query.get(session.get("user_id"))
        if not current_user:
            flash("User session expired", "error")
            return redirect(url_for("auth.login"))
            
        branches = []
        users = []
        courses = []
        
        # Simplified logic to test
        try:
            if current_user.role == "admin":
                branches = Branch.query.filter_by(is_deleted=False).all()
            elif current_user.role == "regional_manager":
                accessible = get_user_accessible_branches(current_user.id) or []
                branches = Branch.query.filter(Branch.id.in_(accessible)).all() if accessible else []
            else:
                ubid = _user_branch_id()
                b = Branch.query.get(ubid) if ubid else None
                branches = [b] if b else []
        except Exception as e:
            print(f"Error getting branches: {e}")
            branches = []

        try:
            # For branch-specific roles, only show users from their own branch
            # For admin/regional manager, initially show no users (they need to select branch first)
            if current_user.role in ["branch_manager", "franchise", "staff"]:
                # Branch-specific users: only show users from their own branch
                user_branch_id = _user_branch_id()
                if user_branch_id:
                    branch_ids = [user_branch_id]
                    users = _get_users_for_assignment(current_user, branch_ids)
                    print(f"DEBUG: Branch-specific user {current_user.username} ({current_user.role})")
                    print(f"DEBUG: Own branch ID: {user_branch_id}")
                    print(f"DEBUG: Found {len(users)} users for assignment from own branch")
                    for user in users:
                        print(f"DEBUG: User: {user.username} ({user.role}) - Branch: {user.branch_id}")
                else:
                    users = []
                    print(f"DEBUG: No branch found for user {current_user.username}")
            elif current_user.role in ["admin", "regional_manager"]:
                # Admin/Regional manager: start with empty users list
                # Users will be populated when they select a branch (future enhancement)
                users = []
                print(f"DEBUG: Admin/Regional manager {current_user.username}: showing empty user list initially")
                print(f"DEBUG: User should select branch first to see assignable users")
            else:
                users = []
                print(f"DEBUG: Role {current_user.role} not allowed to assign leads")
                    
        except Exception as e:
            print(f"Error getting users: {e}")
            users = []

        try:
            # Fetch active courses for the dropdown
            courses = Course.query.filter_by(status='Active', is_deleted=0).all()
        except Exception as e:
            print(f"Error getting courses: {e}")
            courses = []

        print(f"Debug: branches={len(branches)}, users={len(users)}, courses={len(courses)}")
        print(f"Current user: {current_user.username if current_user else 'None'}")
        print(f"Session data: user_id={session.get('user_id')}, role={session.get('role')}")
        return render_template("leads/lead_create.html", branches=branches, users=users, courses=courses)
        
    except Exception as e:
        print(f"Route error: {e}")
        import traceback
        traceback.print_exc()
        flash(f"Error loading create form: {str(e)}", "error")
        return redirect(url_for("leads.lead_list"))

@lead_bp.route("/create", methods=["POST"])
@login_required
def lead_store():
    """Create new lead (JSON or form)"""
    try:
        current_user = User.query.get(session.get("user_id"))
        data = request.get_json() if request.is_json else request.form.to_dict()

        # Required
        name = (data.get("name") or "").strip()
        mobile = _norm_mobile(data.get("mobile"))
        if not name:
            return err("Name is required", 422)
        if not _validate_mobile(mobile):
            return err("Valid 10-digit Indian mobile number is required", 422)
        email = _norm_email(data.get("email"))
        if not _validate_email(email):
            return err("Invalid email format", 422)

        # Validate decision_maker
        decision_maker = data.get("decision_maker")
        if not decision_maker or decision_maker.strip() == "":
            return err("Decision Maker is required", 422)
        
        # Validate enum values
        valid_decision_makers = ["Self", "Parent", "Employer", "Other"]
        if decision_maker not in valid_decision_makers:
            return err(f"Decision Maker must be one of: {', '.join(valid_decision_makers)}", 422)

        # Branch resolve & access
        branch_id = data.get("branch_id") or _user_branch_id()
        if not branch_id:
            return err("Branch is required", 422)
        
        # Validate branch exists
        branch = Branch.query.get(branch_id)
        if not branch:
            return err(f"Branch with ID {branch_id} does not exist", 422)
            
        if not _user_has_corporate_access(current_user):
            if str(branch_id) != str(_user_branch_id()):
                return err("You can only create leads for your branch", 403)

        # Serial
        lead_sl_number = _generate_lead_serial_number(branch_id)

        # Next follow-up
        next_follow_up_at = _dt_fromiso(data.get("next_follow_up_at"))

        # Handle multiple course selections
        course_interest = None
        
        # First check for course_ids from form checkboxes
        course_ids = data.get("course_ids")
        if course_ids:
            # Handle both single values and lists
            if isinstance(course_ids, str):
                course_ids = [course_ids]
            elif not isinstance(course_ids, list):
                course_ids = request.form.getlist("course_ids")
            
            # Get course names from IDs
            if course_ids:
                from models.course_model import Course
                selected_courses = Course.query.filter(Course.id.in_(course_ids)).all()
                if selected_courses:
                    course_names = [course.course_name for course in selected_courses]
                    course_interest = ", ".join(course_names)
        
        # Fallback to direct course_interest if provided
        if not course_interest:
            course_interest = data.get("course_interest")
            if isinstance(course_interest, list):
                course_interest = ", ".join(course_interest)

        # Validate assigned_to_user_id if provided
        assigned_to_user_id = data.get("assigned_to_user_id")
        if assigned_to_user_id:
            # Convert to int and validate
            try:
                assigned_to_user_id = int(assigned_to_user_id) if assigned_to_user_id else None
                if assigned_to_user_id:
                    # Check if user exists
                    assigned_user = User.query.get(assigned_to_user_id)
                    if not assigned_user:
                        return err(f"User with ID {assigned_to_user_id} does not exist", 422)
            except (ValueError, TypeError):
                return err("Invalid user ID format", 422)
        else:
            assigned_to_user_id = None

        # Build Lead
        lead = Lead(
            lead_sl_number=lead_sl_number,
            branch_id=branch_id,
            name=name,
            mobile=mobile,
            email=email or None,
            qualification=data.get("qualification"),
            employment_type=_norm_enum_field(data.get("employment_type"), ["Student","Employed","Self-Employed","Unemployed","Other"]),
            address=(data.get("address") or "").strip() or None,
            course_interest=course_interest,
            lead_status=data.get("lead_status", "Open"),
            priority=data.get("priority", "Medium"),
            lead_source=_norm_enum_field(data.get("lead_source"), ["Walk-in","Referral","Phone","Instagram","Facebook","Google","College Visit","Tally","Other"]),
            assigned_to_user_id=assigned_to_user_id,
            next_follow_up_at=next_follow_up_at,
            # Enhanced lead fields for scoring
            lead_stage=data.get("lead_stage", "New"),
            budget_comfort=data.get("budget_comfort"),
            decision_maker=data.get("decision_maker", "Self"),
            join_timeline=data.get("join_timeline", "Not Sure"),
            preferred_language=data.get("preferred_language", "English"),
            mode_preference=data.get("mode_preference", "Offline"),
            # Guardian information
            guardian_name=data.get("guardian_name"),
            guardian_mobile=_norm_mobile(data.get("guardian_mobile")) if data.get("guardian_mobile") else None,
            guardian_email=_norm_email(data.get("guardian_email")) if data.get("guardian_email") else None,
            guardian_relation=_norm_enum_field(data.get("guardian_relation"), ["Father","Mother","Guardian","Relative","Other"]),
            # Career goals
            career_goal=data.get("career_goal"),
            # Alternative contact
            alt_mobile=_norm_mobile(data.get("alt_mobile")) if data.get("alt_mobile") else None
        )

        db.session.add(lead)
        db.session.flush()  # get ID
        
        # Calculate initial lead score
        lead.update_lead_score()

        # Initial follow-up
        initial_note = data.get("initial_note")
        
        if initial_note and initial_note.strip():
            f = LeadFollowUp(
                lead_id=lead.id,
                note=initial_note.strip(),
                channel=data.get("initial_channel", "Other"),
                created_by_user_id=current_user.id,
                next_action_at=next_follow_up_at
            )
            db.session.add(f)
            # Recalculate score after adding follow-up
            db.session.flush()
            lead.update_lead_score()

        db.session.commit()

        if wants_json_response() or request.is_json:
            return ok({"message": f"Lead {lead.lead_sl_number} created", "lead": lead.to_dict()}, status=201)

        flash(f"Lead {lead.lead_sl_number} created successfully", "success")
        return redirect(url_for("leads.lead_detail", lead_id=lead.id))

    except Exception as e:
        db.session.rollback()
        return err(f"Error creating lead: {str(e)}", 500)

@lead_bp.route("/<int:lead_id>", methods=["GET"])
@login_required
def lead_detail(lead_id):
    """Lead detail (JSON/HTML)"""
    try:
        current_user = User.query.get(session.get("user_id"))
        if not current_user:
            return err("User not found", 401)

        lead = (
            Lead.query.options(
                joinedload(Lead.followups).joinedload(LeadFollowUp.created_by),
                joinedload(Lead.branch),
                joinedload(Lead.assigned_to)
            )
            .filter_by(id=lead_id, is_deleted=False)
            .first_or_404()
        )

        if not _can_access_lead(current_user, lead):
            return err("Access denied", 403)

        users = []
        if current_user.role in ["admin", "regional_manager", "branch_manager", "franchise"]:
            # Get users who can be assigned to this lead (same branch)
            users = _get_users_for_assignment(current_user, [lead.branch_id])

        # Load courses for conversion modal
        courses = []
        try:
            courses = Course.query.filter_by(status='Active', is_deleted=0).all()
        except Exception as e:
            print(f"Error loading courses: {e}")

        if wants_json_response():
            return ok({"lead": lead.to_dict(), "followups": [f.to_dict() for f in lead.followups]})

        # Add current date for template calculations
        current_date = get_current_ist_datetime().date()

        return render_template("leads/lead_view.html", lead=lead, followups=lead.followups, users=users, courses=courses, current_date=current_date)

    except Exception as e:
        return err(f"Error loading lead: {str(e)}", 500)

@lead_bp.route("/<int:lead_id>/edit", methods=["GET", "POST"])
@login_required
def lead_edit(lead_id):
    """Edit form (HTML) - GET displays form, POST processes form"""
    try:
        current_user = User.query.get(session.get("user_id"))
        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()
        if not _can_edit_lead(current_user, lead):
            flash("Access denied", "error")
            return redirect(url_for("leads.lead_detail", lead_id=lead_id))

        # Handle POST request (form submission)
        if request.method == "POST":
            try:
                # Update lead fields
                lead.name = request.form.get("name", "").strip()
                lead.mobile = request.form.get("mobile", "").strip()
                lead.email = request.form.get("email", "").strip() or None
                lead.qualification = request.form.get("qualification", "").strip() or None
                lead.employment_type = request.form.get("employment_type", "").strip() or None
                lead.address = request.form.get("address", "").strip() or None
                lead.lead_source = request.form.get("lead_source", "").strip() or None
                lead.lead_status = request.form.get("lead_status", "").strip() or None
                lead.priority = request.form.get("priority", "Medium").strip()
                lead.branch_id = int(request.form.get("branch_id")) if request.form.get("branch_id") else None
                lead.assigned_to_user_id = int(request.form.get("assigned_to_user_id")) if request.form.get("assigned_to_user_id") else None
                
                # Enhanced fields for better scoring
                lead.lead_stage = request.form.get("lead_stage", "").strip() or None
                lead.budget_comfort = request.form.get("budget_comfort", "").strip() or None
                lead.decision_maker = request.form.get("decision_maker", "").strip() or None
                lead.join_timeline = request.form.get("join_timeline", "").strip() or None
                lead.preferred_language = request.form.get("preferred_language", "").strip() or None
                lead.mode_preference = request.form.get("mode_preference", "").strip() or None
                
                # Handle course interest (multiple selections)
                course_interests = request.form.getlist("course_interest")
                lead.course_interest = ", ".join(course_interests) if course_interests else None
                
                # Apply AI stage-status consistency rules after updates
                lead.apply_ai_stage_status_rules()
                
                # Update last modified
                lead.updated_at = get_current_ist_datetime()
                
                # Recalculate lead score after updates
                lead.update_lead_score()
                
                db.session.commit()
                flash("Lead updated successfully!", "success")
                return redirect(url_for("leads.lead_detail", lead_id=lead_id))
                
            except Exception as e:
                db.session.rollback()
                flash(f"Error updating lead: {str(e)}", "error")

        # Handle GET request (display form) - also for POST with errors
        branches = []
        if current_user.role == "admin":
            branches = Branch.query.filter_by(is_deleted=False).all()
        elif current_user.role == "regional_manager":
            accessible = get_user_accessible_branches(current_user.id) or []
            branches = Branch.query.filter(Branch.id.in_(accessible)).all() if accessible else []
        else:
            b = Branch.query.get(lead.branch_id)
            branches = [b] if b else []

        users = []
        if current_user.role in ["admin", "regional_manager", "branch_manager", "franchise"]:
            # Get users who can be assigned to this lead (same branch)
            users = _get_users_for_assignment(current_user, [lead.branch_id])

        # Fetch active courses for consistency with create form
        courses = Course.query.filter_by(status='Active', is_deleted=0).all()

        # Add current date for template calculations
        current_date = get_current_ist_datetime().date()

        return render_template("leads/edit.html", lead=lead, branches=branches, users=users, courses=courses, current_date=current_date)
    except Exception as e:
        flash(f"Error loading edit form: {str(e)}", "error")
        return redirect(url_for("leads.lead_detail", lead_id=lead_id))

@lead_bp.route("/<int:lead_id>", methods=["PUT", "PATCH"])
@login_required
def lead_update(lead_id):
    """Update lead core fields (JSON or form)"""
    try:
        current_user = User.query.get(session.get("user_id"))
        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()
        if not _can_edit_lead(current_user, lead):
            return err("Access denied", 403)

        data = request.get_json() if request.is_json else request.form.to_dict()

        fields = ["name", "mobile", "email", "qualification", "employment_type",
                  "address", "course_interest", "priority", "lead_source"]
        for f in fields:
            if f in data:
                if f == "mobile":
                    val = _norm_mobile(data[f])
                    if not _validate_mobile(val): return err("Invalid mobile", 422)
                    setattr(lead, f, val)
                elif f == "email":
                    val = _norm_email(data[f])
                    if not _validate_email(val): return err("Invalid email", 422)
                    setattr(lead, f, val or None)
                else:
                    setattr(lead, f, (data[f] or "").strip() or None)

        if "next_follow_up_at" in data:
            lead.next_follow_up_at = _dt_fromiso(data.get("next_follow_up_at"))

        lead.updated_at = get_current_ist_datetime()
        db.session.commit()
        return ok({"message": "Lead updated", "lead": lead.to_dict()})

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

@lead_bp.route("/<int:lead_id>/delete", methods=["POST", "DELETE"])
@login_required
def lead_delete(lead_id):
    """Enhanced soft delete lead with reason tracking and audit trail"""
    try:
        current_user = User.query.get(session.get("user_id"))
        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()
        
        if current_user.role not in ["admin", "regional_manager", "branch_manager", "franchise"]:
            return err("Access denied", 403)
        if not _can_access_lead(current_user, lead):
            return err("Access denied", 403)

        # Get deletion details from request
        data = request.get_json() or {}
        deletion_reason = data.get('reason', 'not_specified')
        deletion_notes = data.get('notes', '')
        
        # Validate required fields for enhanced deletion
        if not deletion_reason or deletion_reason == '':
            return err("Deletion reason is required", 400)
        
        # Log the deletion in audit trail
        from models.system_audit_logs_model import SystemAuditLog
        
        # Create comprehensive audit log
        audit_details = {
            'lead_id': lead.id,
            'lead_sl_number': lead.lead_sl_number,
            'lead_name': lead.name,
            'lead_mobile': lead.mobile,
            'lead_email': lead.email or '',
            'deletion_reason': deletion_reason,
            'deletion_notes': deletion_notes,
            'deleted_by_user_id': current_user.id,
            'deleted_by_username': current_user.username,
            'deletion_timestamp': get_current_ist_datetime().isoformat(),
            'lead_status_at_deletion': lead.lead_status,
            'lead_stage_at_deletion': lead.lead_stage,
            'lead_source': lead.lead_source or '',
            'course_interest': lead.course_interest or '',
            'followup_count': len(lead.followups) if lead.followups else 0
        }
        
        audit_log = SystemAuditLog(
            user_id=current_user.id,
            username=current_user.username,
            action='DELETE_LEAD',
            target=f'leads:{lead.id}',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:255] if request.headers.get('User-Agent') else '',
            details=str(audit_details),
            success=True,
            risk_level='MEDIUM'
        )
        
        # Store deletion metadata in lead record before soft delete
        lead.deletion_reason = deletion_reason
        lead.deletion_notes = deletion_notes
        lead.deleted_by_user_id = current_user.id
        lead.deleted_at = get_current_ist_datetime()
        
        # Perform soft delete
        lead.is_deleted = True
        lead.updated_at = get_current_ist_datetime()
        
        # Save both audit log and lead update
        db.session.add(audit_log)
        db.session.commit()
        
        return ok({
            "message": f"Lead {lead.lead_sl_number} deleted successfully",
            "reason": deletion_reason,
            "deleted_by": current_user.username,
            "audit_logged": True
        })
        
    except Exception as e:
        db.session.rollback()
        return err(f"Error deleting lead: {str(e)}", 500)

# ==============================================================================
# Status / Assign / Convert
# ==============================================================================

@lead_bp.route("/<int:lead_id>/status", methods=["POST"])
@login_required
def lead_update_status(lead_id):
    """Update lead status (JSON)"""
    try:
        current_user = User.query.get(session.get("user_id"))
        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()
        if not _can_edit_lead(current_user, lead):
            return err("Access denied", 403)

        p = request.get_json(force=True)
        new_status = p.get("status")
        if not new_status:
            return err("Status is required", 422)

        valid = ["Open", "In Progress", "Follow-up Scheduled", "Demo Scheduled", "Converted", "Not Interested"]
        if new_status not in valid:
            return err("Invalid status", 422)

        if new_status == "Not Interested" and not (p.get("reason") or "").strip():
            return err("Reason is required when marking a lead Not Interested", 422)

        old_status = lead.lead_status
        lead.lead_status = new_status

        if new_status in ["Converted", "Not Interested"]:
            lead.lead_closed_at = get_current_ist_datetime()
        elif old_status in ["Converted", "Not Interested"]:
            lead.lead_closed_at = None

        if new_status == "Not Interested":
            lead.reason_for_lost = (p.get("reason") or "").strip()

        # Apply AI stage-status consistency rules
        lead.apply_ai_stage_status_rules()

        lead.updated_at = get_current_ist_datetime()

        note_suffix = (p.get("note") or "").strip()
        note = f"Status changed from {old_status} to {new_status}."
        if note_suffix:
            note += f" {note_suffix}"

        db.session.add(LeadFollowUp(
            lead_id=lead.id, note=note, channel="Other", created_by_user_id=current_user.id
        ))

        db.session.commit()
        return ok({"message": f"Lead status updated to {new_status}", "lead": lead.to_dict()})

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

@lead_bp.route("/<int:lead_id>/assign", methods=["POST"])
@login_required
def lead_assign(lead_id):
    """Assign lead to a user"""
    try:
        current_user = User.query.get(session.get("user_id"))
        if current_user.role not in ["admin", "regional_manager", "branch_manager", "franchise"]:
            return err("Access denied", 403)

        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()
        if not _can_access_lead(current_user, lead):
            return err("Access denied", 403)

        p = request.get_json(force=True)
        assigned_to_user_id = p.get("assigned_to_user_id")

        assigned_user = None
        if assigned_to_user_id:
            assigned_user = User.query.get(assigned_to_user_id)
            if not assigned_user:
                return err("User not found", 404)

        lead.assigned_to_user_id = assigned_to_user_id
        lead.updated_at = get_current_ist_datetime()

        assignee_name = assigned_user.full_name if assigned_user else "Unassigned"
        note_suffix = (p.get("note") or "").strip()
        note = f"Lead assigned to {assignee_name}."
        if note_suffix:
            note += f" {note_suffix}"

        db.session.add(LeadFollowUp(
            lead_id=lead.id, note=note, channel="Other", created_by_user_id=current_user.id
        ))

        db.session.commit()
        return ok({"message": "Lead assignment updated", "lead": lead.to_dict()})

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

@lead_bp.route("/<int:lead_id>/convert", methods=["POST"])
@login_required
def lead_convert(lead_id):
    """Convert lead to student (managers only)"""
    try:
        current_user = User.query.get(session.get("user_id"))
        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()

        if current_user.role not in ["admin", "regional_manager", "branch_manager", "franchise"]:
            return err("Only managers can convert leads", 403)
        if not _can_edit_lead(current_user, lead):
            return err("Access denied", 403)
        if lead.lead_status == "Converted":
            return err("Lead already converted", 400)

        p = request.get_json(force=True)

        # Validate required fields from form
        required_fields = ['full_name', 'mobile', 'course_name']
        for field in required_fields:
            if not p.get(field) or not p.get(field).strip():
                return err(f"Field '{field}' is required", 400)

        # Validate Date of Birth and age limits (8-50 years)
        dob_str = p.get('dob')
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                today = get_current_ist_datetime().date()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                
                if age < 8:
                    return err("Student age must be at least 8 years old", 400)
                elif age > 50:
                    return err("Student age must be 50 years or younger", 400)
                    
            except ValueError:
                return err("Invalid date of birth format. Please use YYYY-MM-DD", 400)
        else:
            # DOB is optional, but if provided must be valid
            pass

        student_sid = "S" + uuid.uuid4().hex[:6].upper()
        
        # Handle course name with package information
        course_name = p.get("course_name", lead.course_interest).strip()
        course_package = p.get('course_package', '').strip()
        
        # If a course package is selected, append it to the course name
        if course_package and course_package != '':
            course_name = f"{course_name} ({course_package})"
        
        # Use form data with fallbacks to lead data
        student = Student(
            student_id=student_sid,
            full_name=p.get('full_name', lead.name).strip(),
            gender=p.get('gender'),
            dob=datetime.strptime(p.get('dob'), '%Y-%m-%d').date() if p.get('dob') else None,
            mobile=p.get('mobile', lead.mobile).strip(),
            email=p.get('email', lead.email or '').strip() or None,
            address=p.get('address', lead.address or '').strip() or None,
            qualification=p.get('qualification', lead.qualification or '').strip() or None,
            guardian_name=p.get('guardian_name', '').strip() or None,
            guardian_mobile=p.get('guardian_mobile', '').strip() or None,
            branch_id=lead.branch_id,
            batch_id=p.get("batch_id") or None,
            course_name=course_name,
            admission_mode=p.get('admission_mode', 'Regular'),
            referred_by=p.get('referred_by', '').strip() or None,
            admission_date=datetime.strptime(p.get('admission_date'), '%Y-%m-%d').date() if p.get('admission_date') else get_current_ist_datetime().date(),
            registered_by=current_user.username,
            original_lead_id=lead.id
        )
        db.session.add(student)
        db.session.flush()

        lead.lead_status = "Converted"
        lead.converted_student_id = student.student_id
        lead.lead_closed_at = get_current_ist_datetime()
        lead.updated_at = get_current_ist_datetime()

        # Apply AI stage-status consistency rules
        lead.apply_ai_stage_status_rules()

        db.session.add(LeadFollowUp(
            lead_id=lead.id,
            note=f"Lead converted to student {student.student_id}",
            channel="Other",
            created_by_user_id=current_user.id
        ))

        db.session.commit()
        return ok({
            "message": f"Lead converted to student {student.student_id}",
            "student_id": student.student_id, 
            "student_sid": student.student_id, 
            "lead": lead.to_dict(),
            "ok": True,
            "success": True,
            "data": {
                "student_sid": student.student_id,
                "student_id": student.student_id
            }
        })

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

@lead_bp.route("/<int:lead_id>/recalculate-score", methods=["POST"])
@login_required
def recalculate_lead_score(lead_id):
    """Recalculate lead score and update priority"""
    try:
        current_user = User.query.get(session.get("user_id"))
        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()

        # Check access permissions
        if not _can_edit_lead(current_user, lead):
            return err("Access denied", 403)

        # Recalculate score
        old_score = lead.lead_score
        new_score = lead.update_lead_score()
        
        # Get priority info based on new score
        priority_info = lead.get_priority_display()
        
        # Save to database
        db.session.commit()
        
        # Log the score update as a follow-up
        score_change = new_score - (old_score or 0)
        change_text = f"+{score_change}" if score_change > 0 else str(score_change)
        
        db.session.add(LeadFollowUp(
            lead_id=lead.id,
            note=f"Lead score recalculated: {old_score or 0} → {new_score} ({change_text} points). Priority: {priority_info['text']}",
            channel="System",
            created_by_user_id=current_user.id
        ))
        
        db.session.commit()
        
        return ok({
            "message": f"Lead score updated from {old_score or 0} to {new_score}",
            "score": new_score,
            "old_score": old_score or 0,
            "score_change": score_change,
            "priority_info": priority_info,
            "lead": lead.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

@lead_bp.route("/dashboard", methods=["GET"])
@login_required
def lead_dashboard():
    """Lead Management Dashboard"""
    try:
        current_user = User.query.get(session.get("user_id"))
        if not current_user:
            return err("User not found", 401)

        from datetime import datetime, timedelta
        current_time = get_current_ist_datetime()
        today = current_time.date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        yesterday = today - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday, datetime.min.time())

        # Base query with user access control - exclude converted, not interested, and lost leads
        base_query = _scope_leads_for_user(
            Lead.query.options(
                joinedload(Lead.followups).joinedload(LeadFollowUp.created_by),
                joinedload(Lead.branch),
                joinedload(Lead.assigned_to)
            ).filter(
                and_(
                    Lead.is_deleted == False,
                    Lead.lead_status.notin_(['Converted', 'Not Interested', 'Lost'])
                )
            ),
            current_user
        )

        # Key Metrics for the top cards
        metrics = {}
        
        # Overdue follow-ups (urgent) - only active leads
        overdue_followups = base_query.filter(
            and_(
                Lead.next_follow_up_at < current_time,
                Lead.lead_status.in_(['New', 'Contacted', 'Open', 'In Progress', 'Follow-up Scheduled'])
            )
        ).all()
        metrics['overdue_followups'] = len(overdue_followups)

        # Today's follow-ups - only active leads (not converted/closed)
        todays_followups = base_query.filter(
            and_(
                Lead.next_follow_up_at >= today_start,
                Lead.next_follow_up_at <= today_end,
                Lead.lead_status.in_(['New', 'Contacted', 'Open', 'In Progress', 'Follow-up Scheduled'])
            )
        ).all()
        metrics['due_today'] = len(todays_followups)

        # Hot leads (score 150+) - only active leads
        hot_leads = base_query.filter(Lead.lead_score >= 150).all()
        metrics['hot_leads'] = len(hot_leads)

        # New leads in last 24 hours
        new_leads = base_query.filter(
            Lead.created_at >= yesterday_start
        ).all()
        metrics['new_leads'] = len(new_leads)

        # Performance Statistics
        stats = {}
        
        # Total active leads (excluding converted, not interested, lost)
        stats['total_leads'] = base_query.count()
        
        # Conversion rate calculation (for all leads, including closed ones)
        all_leads_query = _scope_leads_for_user(
            Lead.query.filter(Lead.is_deleted == False),
            current_user
        )
        total_closed = all_leads_query.filter(
            Lead.lead_status.in_(['Converted', 'Not Interested', 'Lost'])
        ).count()
        converted = all_leads_query.filter(Lead.lead_status == 'Converted').count()
        stats['conversion_rate'] = round((converted / total_closed * 100) if total_closed > 0 else 0, 1)
        
        # Average response time (mock data for now - can be calculated from first follow-up)
        stats['avg_response_time'] = 4  # hours
        
        # Follow-up completion rate (for active leads only)
        total_followups = db.session.query(LeadFollowUp).join(Lead).filter(
            and_(
                Lead.is_deleted == False,
                Lead.lead_status.notin_(['Converted', 'Not Interested', 'Lost'])
            )
        ).count()
        completed_followups = db.session.query(LeadFollowUp).join(Lead).filter(
            and_(
                Lead.is_deleted == False,
                Lead.lead_status.notin_(['Converted', 'Not Interested', 'Lost']),
                LeadFollowUp.is_completed == True
            )
        ).count()
        stats['follow_up_completion'] = round((completed_followups / total_followups * 100) if total_followups > 0 else 0, 1)

        # Lead sources with average scores - apply user scoping (active leads only)
        lead_sources_query = _scope_leads_for_user(
            db.session.query(
                Lead.lead_source,
                func.count(Lead.id).label('count'),
                func.avg(Lead.lead_score).label('avg_score')
            ).filter(
                and_(
                    Lead.is_deleted == False,
                    Lead.lead_status.notin_(['Converted', 'Not Interested', 'Lost']),
                    Lead.lead_source.isnot(None),
                    Lead.lead_source != '',
                    Lead.lead_source != 'Unknown',
                    Lead.lead_source != 'Not specified'
                )
            ),
            current_user
        )
        lead_sources = lead_sources_query.group_by(Lead.lead_source).order_by(desc('count')).limit(6).all()

        # Stage distribution - apply user scoping (active leads only)  
        stage_distribution_query = _scope_leads_for_user(
            db.session.query(
                Lead.lead_stage,
                func.count(Lead.id).label('count')
            ).filter(
                and_(
                    Lead.is_deleted == False,
                    Lead.lead_status.notin_(['Converted', 'Not Interested', 'Lost'])
                )
            ),
            current_user
        )
        stage_distribution = stage_distribution_query.group_by(Lead.lead_stage).order_by(desc('count')).all()

        # Pipeline Data for Funnel View
        pipeline = {}
        
        # Get counts for each pipeline stage
        pipeline['new_leads'] = base_query.filter(
            or_(Lead.lead_stage == 'New', Lead.lead_stage.is_(None))
        ).count()
        
        pipeline['contacted_leads'] = base_query.filter(
            Lead.lead_stage == 'Contacted'
        ).count()
        
        pipeline['qualified_leads'] = base_query.filter(
            Lead.lead_stage == 'Qualified'
        ).count()
        
        pipeline['demo_leads'] = base_query.filter(
            Lead.lead_stage.in_(['Demo Scheduled', 'Demo Completed', 'Proposal Sent'])
        ).count()
        
        pipeline['negotiation_leads'] = base_query.filter(
            Lead.lead_stage.in_(['Negotiation', 'Decision Pending'])
        ).count()
        
        # For converted leads, we need to include them
        converted_query = _scope_leads_for_user(
            Lead.query.filter(
                and_(
                    Lead.is_deleted == False,
                    Lead.lead_status == 'Converted'
                )
            ),
            current_user
        )
        pipeline['converted_leads'] = converted_query.count()
        
        # Calculate average cycle time (from creation to conversion)
        converted_leads_with_time = converted_query.filter(
            Lead.updated_at.isnot(None)
        ).all()
        
        if converted_leads_with_time:
            total_days = sum([
                (lead.updated_at - lead.created_at).days 
                for lead in converted_leads_with_time 
                if lead.updated_at and lead.created_at
            ])
            pipeline['avg_cycle_time'] = round(total_days / len(converted_leads_with_time))
        else:
            pipeline['avg_cycle_time'] = 0
        
        # Hot leads currently in pipeline
        pipeline['hot_in_pipeline'] = base_query.filter(
            Lead.lead_score >= 150
        ).count()
        
        # Stalled leads (no activity for 14+ days)
        stall_date = current_time - timedelta(days=14)
        pipeline['stuck_leads'] = base_query.filter(
            or_(
                Lead.next_follow_up_at < stall_date,
                and_(
                    Lead.next_follow_up_at.is_(None),
                    Lead.updated_at < stall_date
                )
            )
        ).count()
        
        # Smart Recommendations based on pipeline analysis
        recommendations = []
        
        # Check for bottlenecks and provide actionable insights
        if pipeline['new_leads'] > 0 and pipeline['contacted_leads'] / max(pipeline['new_leads'], 1) < 0.5:
            recommendations.append({
                'title': 'Low Contact Rate',
                'description': f"Only {pipeline['contacted_leads']} of {pipeline['new_leads']} new leads contacted",
                'icon': 'fa-phone',
                'type': 'warning',
                'action_url': url_for('leads.lead_list', status='New')
            })
        
        if pipeline['stuck_leads'] > 5:
            recommendations.append({
                'title': 'Stalled Leads Alert',
                'description': f"{pipeline['stuck_leads']} leads have no activity for 14+ days",
                'icon': 'fa-clock',
                'type': 'danger',
                'action_url': url_for('leads.lead_list', filter='stalled')
            })
        
        if pipeline['demo_leads'] > 0 and pipeline['negotiation_leads'] / max(pipeline['demo_leads'], 1) < 0.3:
            recommendations.append({
                'title': 'Demo to Negotiation Gap',
                'description': f"Low conversion from demo ({pipeline['demo_leads']}) to negotiation ({pipeline['negotiation_leads']})",
                'icon': 'fa-chart-line',
                'type': 'info',
                'action_url': url_for('leads.lead_list', stage='Demo')
            })
        
        if pipeline['hot_in_pipeline'] > 10:
            recommendations.append({
                'title': 'Hot Leads Opportunity',
                'description': f"{pipeline['hot_in_pipeline']} hot leads in pipeline - prioritize follow-ups",
                'icon': 'fa-fire',
                'type': 'success',
                'action_url': url_for('leads.lead_list', priority='Hot')
            })
        
        pipeline['recommendations'] = recommendations

        # Debug: Print lead sources for troubleshooting
        print(f"DEBUG: Found {len(lead_sources)} lead sources:")
        for source in lead_sources:
            print(f"  {source.lead_source}: {source.count} leads, avg score: {source.avg_score:.1f}")

        return render_template("leads/dashboard.html", 
                             metrics=metrics,
                             stats=stats,
                             pipeline=pipeline,
                             overdue_followups=overdue_followups[:10],
                             todays_followups=todays_followups[:10],
                             hot_leads=hot_leads[:10],
                             new_leads=new_leads[:10],
                             lead_sources=lead_sources,
                             stage_distribution=stage_distribution,
                             current_time=current_time)

    except Exception as e:
        return err(f"Error loading dashboard: {str(e)}", 500)

@lead_bp.route("/dashboard/refresh", methods=["GET"])
@login_required
def dashboard_refresh():
    """Refresh dashboard data"""
    try:
        from datetime import datetime
        return jsonify({
            'success': True,
            'timestamp': get_current_ist_formatted()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==============================================================================
# Bulk Operations
# ==============================================================================

@lead_bp.route("/bulk/status", methods=["POST"])
@login_required
def leads_bulk_status():
    try:
        current_user = User.query.get(session.get("user_id"))
        p = request.get_json(force=True)
        lead_ids = p.get("lead_ids") or []
        new_status = p.get("status")

        if not lead_ids:
            return err("No leads selected", 422)
        if not new_status:
            return err("Status is required", 422)
        if new_status == "Not Interested" and not (p.get("reason") or "").strip():
            return err("Reason is required when marking Not Interested", 422)

        leads = Lead.query.filter(Lead.id.in_(lead_ids), Lead.is_deleted == False).all()
        editable = [l for l in leads if _can_edit_lead(current_user, l)]
        if not editable:
            return err("No accessible leads found", 404)

        updated = 0
        for lead in editable:
            old = lead.lead_status
            lead.lead_status = new_status
            if new_status in ["Converted", "Not Interested"]:
                lead.lead_closed_at = get_current_ist_datetime()
                if new_status == "Not Interested":
                    lead.reason_for_lost = (p.get("reason") or "").strip()
            elif old in ["Converted", "Not Interested"]:
                lead.lead_closed_at = None
            
            # Apply AI stage-status consistency rules
            lead.apply_ai_stage_status_rules()
            
            lead.updated_at = get_current_ist_datetime()

            db.session.add(LeadFollowUp(
                lead_id=lead.id,
                note=f"Bulk status update from {old} to {new_status}",
                channel="Other",
                created_by_user_id=current_user.id
            ))
            updated += 1

        db.session.commit()
        return ok({"message": f"Updated status for {updated} leads", "updated_count": updated})

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

@lead_bp.route("/bulk/assign", methods=["POST"])
@login_required
def leads_bulk_assign():
    try:
        current_user = User.query.get(session.get("user_id"))
        if current_user.role not in ["admin", "regional_manager", "branch_manager", "franchise"]:
            return err("Access denied", 403)

        p = request.get_json(force=True)
        lead_ids = p.get("lead_ids") or []
        assigned_to_user_id = p.get("assigned_to_user_id")

        if not lead_ids:
            return err("No leads selected", 422)

        assigned_user = None
        if assigned_to_user_id:
            assigned_user = User.query.get(assigned_to_user_id)
            if not assigned_user:
                return err("User not found", 404)

        leads = Lead.query.filter(Lead.id.in_(lead_ids), Lead.is_deleted == False).all()
        accessible = [l for l in leads if _can_access_lead(current_user, l)]
        if not accessible:
            return err("No accessible leads found", 404)

        updated = 0
        for lead in accessible:
            lead.assigned_to_user_id = assigned_to_user_id
            lead.updated_at = get_current_ist_datetime()

            assignee_name = assigned_user.full_name if assigned_user else "Unassigned"
            db.session.add(LeadFollowUp(
                lead_id=lead.id,
                note=f"Bulk assignment to {assignee_name}",
                channel="Other",
                created_by_user_id=current_user.id
            ))
            updated += 1

        db.session.commit()
        return ok({"message": f"Assigned {updated} leads", "updated_count": updated})

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

@lead_bp.route("/bulk/delete", methods=["POST"])
@login_required
def leads_bulk_delete():
    try:
        current_user = User.query.get(session.get("user_id"))
        if current_user.role not in ["admin", "regional_manager", "branch_manager", "franchise"]:
            return err("Access denied", 403)

        p = request.get_json(force=True)
        lead_ids = p.get("lead_ids") or []
        if not lead_ids:
            return err("No leads selected", 422)

        leads = Lead.query.filter(Lead.id.in_(lead_ids), Lead.is_deleted == False).all()
        accessible = [l for l in leads if _can_access_lead(current_user, l)]
        if not accessible:
            return err("No accessible leads found", 404)

        deleted = 0
        for lead in accessible:
            lead.is_deleted = True
            lead.updated_at = get_current_ist_datetime()
            deleted += 1

        db.session.commit()
        return ok({"message": f"Deleted {deleted} leads", "deleted_count": deleted})

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

# ==============================================================================
# Duplicate Check
# ==============================================================================

@lead_bp.route("/dedupe-check", methods=["GET"])
@login_required
def lead_dedupe_check():
    try:
        current_user = User.query.get(session.get("user_id"))
        mobile = _norm_mobile(request.args.get("mobile"))
        email = _norm_email(request.args.get("email"))

        if not mobile and not email:
            return err("Provide mobile or email", 422)

        q = Lead.query.filter(Lead.is_deleted == False)
        if not _user_has_corporate_access(current_user):
            ubid = _user_branch_id()
            q = q.filter(Lead.branch_id == ubid)

        clauses = []
        if mobile: clauses.append(Lead.mobile == mobile)
        if email:  clauses.append(func.lower(Lead.email) == email)
        q = q.filter(or_(*clauses))

        duplicates = q.limit(25).all()
        return ok({"has_duplicates": len(duplicates) > 0, "duplicates": [d.to_dict() for d in duplicates]})

    except Exception as e:
        return err(str(e), 500)

# ==============================================================================
# Follow-ups (CRUD + scheduling)
# ==============================================================================

@lead_bp.route("/<int:lead_id>/followups", methods=["GET"])
@login_required
def followup_list(lead_id):
    try:
        current_user = User.query.get(session.get("user_id"))
        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()
        if not _can_access_lead(current_user, lead):
            return err("Access denied", 403)

        followups = LeadFollowUp.query.filter_by(lead_id=lead_id)\
                        .order_by(LeadFollowUp.created_at.desc()).all()
        return ok([f.to_dict() for f in followups])

    except Exception as e:
        return err(str(e), 500)

@lead_bp.route("/<int:lead_id>/followups", methods=["POST"])
@login_required
def followup_create(lead_id):
    try:
        current_user = User.query.get(session.get("user_id"))
        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()
        if not _can_edit_lead(current_user, lead):
            return err("Access denied", 403)

        p = request.get_json(force=True)
        
        # Handle both frontend field names and API field names
        note = (p.get("notes") or p.get("note") or "").strip()
        if not note:
            return err("Note is required", 422)

        # Handle follow_up_date from frontend or next_action_at from API
        follow_up_date = p.get("follow_up_date") or p.get("next_action_at")
        next_action_at = _dt_fromiso(follow_up_date)

        # Handle follow_up_type from frontend or channel from API
        channel = p.get("follow_up_type") or p.get("channel") or "Other"

        # Phase 2: Check for duplicate follow-ups
        if next_action_at:
            duplicate = lead.check_duplicate_followup(channel, next_action_at)
            if duplicate:
                return err(f"Duplicate follow-up detected. Similar {channel} already scheduled for {duplicate.next_action_at.strftime('%Y-%m-%d %H:%M')}", 422)
            
            # Check for conflicts and suggest alternatives
            conflicts = lead.get_conflicting_followups(next_action_at)
            if conflicts:
                alternative_time = lead.suggest_alternative_followup_time(next_action_at)
                return {
                    "ok": False,
                    "error": "Time conflict detected",
                    "conflicts": [f.to_dict() for f in conflicts],
                    "suggested_alternative": alternative_time.isoformat(),
                    "message": f"Conflict detected. Alternative time suggested: {alternative_time.strftime('%Y-%m-%d %H:%M')}"
                }, 409

        f = LeadFollowUp(
            lead_id=lead_id,
            note=note,
            channel=channel,
            created_by_user_id=current_user.id,
            next_action_at=next_action_at
        )
        db.session.add(f)

        if next_action_at:
            lead.next_follow_up_at = next_action_at
            lead.updated_at = get_current_ist_datetime()
        
        # Phase 2: Apply Smart Automation
        # Auto-advance stage from follow-up scheduling
        stage_changed = lead.auto_advance_stage_from_followup(channel)
        
        # Auto-update stage based on any status changes
        status_changed = lead.auto_update_stage_from_status()
        
        # Apply AI consistency rules
        lead.apply_ai_stage_status_rules()
        
        # Recalculate lead score after adding follow-up
        db.session.flush()  # Ensure follow-up is in the database
        lead.update_lead_score()

        db.session.commit()
        
        # Phase 2: Get smart suggestions for next actions
        smart_suggestions = lead.suggest_smart_next_actions(channel)
        
        response_data = {
            "message": "Follow-up added", 
            "followup": f.to_dict(),
            "stage_changed": stage_changed,
            "status_changed": status_changed,
            "smart_suggestions": smart_suggestions
        }
        
        return ok(response_data, status=201)

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

@lead_bp.route("/followups/<int:fup_id>", methods=["PUT", "PATCH"])
@login_required
def followup_update(fup_id):
    try:
        current_user = User.query.get(session.get("user_id"))
        f = LeadFollowUp.query.get_or_404(fup_id)
        lead = Lead.query.get(f.lead_id)
        if not _can_edit_lead(current_user, lead):
            return err("Access denied", 403)
        if f.created_by_user_id != current_user.id and current_user.role not in ["admin", "regional_manager", "branch_manager", "franchise"]:
            return err("Access denied", 403)

        p = request.get_json(force=True)
        if "note" in p:    f.note = (p["note"] or "").strip()
        if "channel" in p: f.channel = p["channel"]
        if "next_action_at" in p: f.next_action_at = _dt_fromiso(p.get("next_action_at"))

        db.session.commit()
        return ok({"message": "Follow-up updated", "followup": f.to_dict()})

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

@lead_bp.route("/followups/<int:fup_id>/next-action", methods=["POST"])
@login_required
def followup_next_action(fup_id):
    try:
        current_user = User.query.get(session.get("user_id"))
        f = LeadFollowUp.query.get_or_404(fup_id)
        lead = Lead.query.get(f.lead_id)
        if not _can_edit_lead(current_user, lead):
            return err("Access denied", 403)

        p = request.get_json(force=True)
        f.next_action_at = _dt_fromiso(p.get("next_action_at"))
        if f.next_action_at:
            lead.next_follow_up_at = f.next_action_at
            lead.updated_at = get_current_ist_datetime()

        db.session.commit()
        return ok({"message": "Next action updated", "followup": f.to_dict()})

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

@lead_bp.route("/followups/<int:fup_id>/complete", methods=["POST"])
@login_required
def followup_complete(fup_id):
    """Mark a follow-up as complete with detailed outcome and next action"""
    print(f"🔥 COMPLETE ROUTE CALLED: fup_id={fup_id}")
    print(f"🔥 Request method: {request.method}")
    print(f"🔥 Request headers: {dict(request.headers)}")
    print(f"🔥 Request data: {request.data}")
    
    try:
        current_user = User.query.get(session.get("user_id"))
        f = LeadFollowUp.query.get_or_404(fup_id)
        lead = Lead.query.get(f.lead_id)
        if not _can_edit_lead(current_user, lead):
            return err("Access denied", 403)

        p = request.get_json(force=True)
        
        # Enhanced outcome handling
        outcome_category = (p.get("outcome_category") or "").strip()
        outcome_notes = (p.get("outcome_notes") or "").strip()
        full_outcome = (p.get("outcome") or "").strip()
        
        # Use structured outcome if available, otherwise fall back to simple outcome in outcome_category
        if outcome_category:
            final_outcome_category = outcome_category
        elif full_outcome:
            final_outcome_category = full_outcome
        else:
            final_outcome_category = "Follow-up Completed"
        
        # Next action data
        next_action_at_str = p.get("next_action_at")
        next_action_notes = (p.get("next_action") or "").strip()
        next_action_type = (p.get("next_action_type") or "Other").strip()
        next_action_priority = (p.get("next_action_priority") or "Medium").strip()
        reminder_before = p.get("reminder_before")
        
        # Parse next_action_at if provided
        next_action_at = None
        if next_action_at_str:
            try:
                # Parse ISO format datetime from frontend
                next_action_at = datetime.fromisoformat(next_action_at_str.replace('Z', '+00:00'))
            except:
                # Fallback to default if parsing fails
                next_action_at = get_current_ist_datetime() + timedelta(days=1)

        # Mark the follow-up as completed
        f.is_completed = True
        f.completed_at = get_current_ist_datetime()
        
        # Store structured outcome data in new fields
        f.outcome_category = final_outcome_category
        if outcome_notes:
            f.outcome_notes = outcome_notes
        
        if next_action_notes:
            f.next_action = next_action_notes
        
        # Create new follow-up if next action is scheduled
        if next_action_at and next_action_notes:
            # Create a new follow-up for the next action
            next_followup = LeadFollowUp(
                lead_id=lead.id,
                note=next_action_notes,
                channel=next_action_type,
                created_by_user_id=current_user.id,
                next_action_at=next_action_at
            )
            db.session.add(next_followup)
            
            # Update lead's next follow-up time
            lead.next_follow_up_at = next_action_at
            
            # Update lead priority if specified
            if next_action_priority and next_action_priority != lead.priority:
                lead.priority = next_action_priority
        else:
            # Clear the next follow-up if no new one is scheduled
            lead.next_follow_up_at = None

        # Update lead based on outcome category using AI logic
        if outcome_category:
            # Phase 2: Use smart automation for status updates
            status_changed = lead.auto_update_status_from_followup_completion(
                f.channel, outcome_category, next_action_at is not None
            )
            
            # Auto-advance stage based on follow-up completion
            stage_changed = lead.auto_advance_stage_from_followup(f.channel, outcome_category)
            
            # Auto-update stage from status changes
            additional_stage_change = lead.auto_update_stage_from_status()
            stage_changed = stage_changed or additional_stage_change
            
            # Apply AI consistency rules
            lead.apply_ai_stage_status_rules()
            
            # Handle specific outcomes for lead closure
            if lead.lead_status == "Converted":
                lead.lead_closed_at = get_current_ist_datetime()
            elif lead.lead_status == "Not Interested":
                lead.lead_closed_at = get_current_ist_datetime()
                if outcome_notes:
                    lead.reason_for_lost = outcome_notes

        lead.updated_at = get_current_ist_datetime()
        
        # Recalculate lead score after completing follow-up
        lead.update_lead_score()
        
        db.session.commit()
        
        # Phase 2: Get smart suggestions for next actions based on outcome
        smart_suggestions = lead.suggest_smart_next_actions(f.channel, outcome_category)
        
        response_data = {
            "message": "Follow-up completed successfully",
            "followup": f.to_dict(),
            "outcome_category": outcome_category,
            "next_action_scheduled": next_action_at is not None,
            "stage_changed": stage_changed,
            "status_changed": status_changed,
            "smart_suggestions": smart_suggestions
        }
        
        return ok(response_data)

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

# ==============================================================================
# Phase 2: Smart Automation Endpoints
# ==============================================================================

@lead_bp.route("/<int:lead_id>/smart-suggestions", methods=["GET"])
@login_required
def get_smart_suggestions(lead_id):
    """Get AI-powered smart suggestions for next actions"""
    try:
        print(f"🔍 Smart suggestions API called for lead {lead_id}")
        
        current_user = User.query.get(session.get("user_id"))
        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()
        
        if not _can_edit_lead(current_user, lead):
            print("❌ Access denied for smart suggestions")
            return err("Access denied", 403)

        # Get query parameters
        last_follow_up_type = request.args.get("last_follow_up_type")
        last_outcome = request.args.get("last_outcome")
        
        print(f"📋 Getting suggestions for lead: {lead.name}, stage: {lead.lead_stage}")
        
        # Get smart suggestions
        suggestions = lead.suggest_smart_next_actions(last_follow_up_type, last_outcome)
        print(f"💡 Found {len(suggestions)} suggestions")
        
        # Process templates safely
        for suggestion in suggestions:
            try:
                template_data = lead.get_smart_followup_templates(suggestion["action"])
                if isinstance(template_data, dict):
                    suggestion["template"] = template_data.get("script", "")
                    suggestion["duration"] = template_data.get("duration", "")
                    suggestion["objectives"] = template_data.get("objectives", [])
                else:
                    suggestion["template"] = str(template_data) if template_data else ""
            except Exception as template_error:
                print(f"⚠️ Template error for {suggestion['action']}: {template_error}")
                suggestion["template"] = "Template not available"
        
        response_data = {
            "lead_id": lead_id,
            "current_stage": lead.lead_stage,
            "current_status": lead.lead_status,
            "suggestions": suggestions,
            "lead_age_days": getattr(lead, 'lead_age_days', 0)
        }
        
        print(f"✅ Returning smart suggestions response: {len(response_data['suggestions'])} items")
        return ok(response_data)

    except Exception as e:
        print(f"💥 Smart suggestions error: {str(e)}")
        import traceback
        traceback.print_exc()
        return err(f"Smart suggestions error: {str(e)}", 500)

# Debug endpoint for testing
@lead_bp.route("/<int:lead_id>/smart-suggestions-test", methods=["GET"])
@login_required  
def get_smart_suggestions_test(lead_id):
    """Simple test endpoint for smart suggestions"""
    try:
        return ok({
            "lead_id": lead_id,
            "test": True,
            "suggestions": [
                {"action": "Outbound Call", "priority": "High", "reason": "Test suggestion 1"},
                {"action": "WhatsApp", "priority": "Medium", "reason": "Test suggestion 2"}
            ]
        })
    except Exception as e:
        return err(str(e), 500)

@lead_bp.route("/<int:lead_id>/check-conflicts", methods=["POST"])
@login_required
def check_followup_conflicts(lead_id):
    """Check for follow-up scheduling conflicts"""
    try:
        current_user = User.query.get(session.get("user_id"))
        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()
        
        if not _can_edit_lead(current_user, lead):
            return err("Access denied", 403)

        p = request.get_json(force=True)
        
        follow_up_type = p.get("follow_up_type", "Other")
        proposed_time_str = p.get("proposed_time")
        
        if not proposed_time_str:
            return err("Proposed time is required", 422)
        
        try:
            proposed_time = datetime.fromisoformat(proposed_time_str.replace('Z', '+00:00'))
        except:
            return err("Invalid time format", 422)
        
        # Check for duplicates
        duplicate = lead.check_duplicate_followup(follow_up_type, proposed_time)
        
        # Check for conflicts
        conflicts = lead.get_conflicting_followups(proposed_time)
        
        # Suggest alternative if conflicts exist
        alternative_time = None
        if conflicts or duplicate:
            alternative_time = lead.suggest_alternative_followup_time(proposed_time)
        
        return ok({
            "has_duplicate": duplicate is not None,
            "duplicate_info": duplicate.to_dict() if duplicate else None,
            "has_conflicts": len(conflicts) > 0,
            "conflicts": [c.to_dict() for c in conflicts],
            "suggested_alternative": alternative_time.isoformat() if alternative_time else None,
            "can_schedule": duplicate is None and len(conflicts) == 0
        })

    except Exception as e:
        return err(str(e), 500)

@lead_bp.route("/<int:lead_id>/auto-update-stage", methods=["POST"])
@login_required
def auto_update_lead_stage(lead_id):
    """Manually trigger auto-update of lead stage based on current status"""
    try:
        current_user = User.query.get(session.get("user_id"))
        lead = Lead.query.filter_by(id=lead_id, is_deleted=False).first_or_404()
        
        if not _can_edit_lead(current_user, lead):
            return err("Access denied", 403)

        old_stage = lead.lead_stage
        old_status = lead.lead_status
        
        # Apply smart automation
        stage_changed = lead.auto_update_stage_from_status()
        lead.apply_ai_stage_status_rules()
        
        lead.updated_at = get_current_ist_datetime()
        lead.update_lead_score()
        
        db.session.commit()
        
        return ok({
            "message": "Lead auto-updated successfully",
            "old_stage": old_stage,
            "new_stage": lead.lead_stage,
            "old_status": old_status,
            "new_status": lead.lead_status,
            "stage_changed": stage_changed,
            "lead": lead.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return err(str(e), 500)

# ==============================================================================
# Scheduling / Due Views
# ==============================================================================

def _scope_followups_base(user: User, start_dt: datetime, end_dt: datetime):
    q = db.session.query(LeadFollowUp).join(Lead).filter(
        LeadFollowUp.next_action_at >= start_dt,
        LeadFollowUp.next_action_at < end_dt,
        Lead.is_deleted == False
    )
    if user.role == "franchise":
        ubid = _user_branch_id()
        if ubid: q = q.filter(Lead.branch_id == ubid)
    elif user.role == "regional_manager":
        branches = get_user_accessible_branches(user.id) or []
        if branches: q = q.filter(Lead.branch_id.in_(branches))
    elif user.role in ["branch_manager", "staff"]:
        ubid = _user_branch_id()
        if ubid: q = q.filter(Lead.branch_id == ubid)
    elif user.role == "trainer":
        q = q.filter(Lead.assigned_to_user_id == user.id)
    return q

@lead_bp.route("/followups/due-today", methods=["GET"])
@login_required
def followups_due_today():
    try:
        current_user = User.query.get(session.get("user_id"))
        start, end = _day_bounds(date.today())
        q = _scope_followups_base(current_user, start, end)

        assigned_to = request.args.get("assigned_to", type=int)
        if assigned_to:
            q = q.filter(Lead.assigned_to_user_id == assigned_to)

        followups = q.order_by(LeadFollowUp.next_action_at).all()
        return ok({"followups": [f.to_dict() for f in followups], "count": len(followups)})

    except Exception as e:
        return err(str(e), 500)

@lead_bp.route("/followups/upcoming", methods=["GET"])
@login_required
def followups_upcoming():
    try:
        current_user = User.query.get(session.get("user_id"))
        start, _ = _day_bounds(date.today())
        end = start + timedelta(days=7)
        q = _scope_followups_base(current_user, start, end)
        followups = q.order_by(LeadFollowUp.next_action_at).all()
        return ok({"followups": [f.to_dict() for f in followups], "count": len(followups)})

    except Exception as e:
        return err(str(e), 500)

@lead_bp.route("/followups/calendar", methods=["GET"])
@login_required
def followups_calendar():
    """JSON feed for calendar widgets"""
    try:
        current_user = User.query.get(session.get("user_id"))
        start_param = request.args.get("start")
        end_param = request.args.get("end")

        start_d = _date_fromiso(start_param) or date.today()
        end_d = _date_fromiso(end_param) or (date.today() + timedelta(days=30))
        start, _ = _day_bounds(start_d)
        _, end = _day_bounds(end_d)

        q = db.session.query(LeadFollowUp)\
             .options(joinedload(LeadFollowUp.lead))\
             .join(Lead)\
             .filter(LeadFollowUp.next_action_at >= start,
                     LeadFollowUp.next_action_at < end,
                     Lead.is_deleted == False)

        if current_user.role == "franchise":
            ubid = _user_branch_id()
            if ubid: q = q.filter(Lead.branch_id == ubid)
        elif current_user.role == "regional_manager":
            branches = get_user_accessible_branches(current_user.id) or []
            if branches: q = q.filter(Lead.branch_id.in_(branches))
        elif current_user.role in ["branch_manager", "staff"]:
            ubid = _user_branch_id()
            if ubid: q = q.filter(Lead.branch_id == ubid)
        elif current_user.role == "trainer":
            q = q.filter(Lead.assigned_to_user_id == current_user.id)

        followups = q.order_by(LeadFollowUp.next_action_at).all()

        events = []
        for f in followups:
            lead = f.lead
            events.append({
                "id": f"followup_{f.id}",
                "title": f"{lead.name} - {f.channel or 'Follow-up'}",
                "start": f.next_action_at.isoformat() if f.next_action_at else None,
                "description": f.note,
                "extendedProps": {
                    "leadId": lead.id,
                    "followupId": f.id,
                    "leadStatus": lead.lead_status,
                    "priority": lead.priority,
                    "mobile": lead.mobile
                }
            })
        return ok({"events": events})

    except Exception as e:
        return err(str(e), 500)

# ==============================================================================
# Import / Export
# ==============================================================================

@lead_bp.route("/export", methods=["GET"])
@login_required
def leads_export():
    """Export leads to CSV (streamed) or XLSX (memory)"""
    try:
        current_user = User.query.get(session.get("user_id"))
        export_format = (request.args.get('format') or 'csv').lower()

        query = _scope_leads_for_user(
            Lead.query.options(joinedload(Lead.assigned_to), joinedload(Lead.branch)).filter(Lead.is_deleted == False),
            current_user
        )

        # Apply filters (reuse list filters)
        status = request.args.get('status');  source = request.args.get('source');  priority = request.args.get('priority')
        if status:   query = query.filter(Lead.lead_status == status)
        if source:   query = query.filter(Lead.lead_source == source)
        if priority: query = query.filter(Lead.priority == priority)

        # Date range
        df = _date_fromiso(request.args.get('date_from'))
        dt_ = _date_fromiso(request.args.get('date_to'))
        if df:
            start, _ = _day_bounds(df);  query = query.filter(Lead.lead_generation_date >= start)
        if dt_:
            _, end = _day_bounds(dt_);   query = query.filter(Lead.lead_generation_date < end)

        timestamp = get_current_ist_datetime().strftime('%Y%m%d_%H%M%S')
        filename = f'leads_export_{timestamp}'

        if export_format == 'xlsx':
            if not HAS_PANDAS:
                return err("Pandas/openpyxl not installed on server for XLSX export", 500)
            rows = []
            for lead in query.yield_per(1000):
                rows.append({
                    'Lead Number': lead.lead_sl_number,
                    'Generation Date': lead.lead_generation_date.strftime('%Y-%m-%d %H:%M:%S') if lead.lead_generation_date else '',
                    'Name': _csv_safe(lead.name),
                    'Mobile': _csv_safe(lead.mobile),
                    'Email': _csv_safe(lead.email or ''),
                    'Qualification': _csv_safe(lead.qualification or ''),
                    'Employment Type': _csv_safe(lead.employment_type or ''),
                    'Address': _csv_safe(lead.address or ''),
                    'Course Interest': _csv_safe(lead.course_interest or ''),
                    'Status': lead.lead_status,
                    'Priority': lead.priority,
                    'Source': _csv_safe(lead.lead_source or ''),
                    'Assigned To': _csv_safe(lead.assigned_to.full_name if lead.assigned_to else ''),
                    'Branch': _csv_safe(lead.branch.branch_name if lead.branch else ''),
                    'Next Follow-up': lead.next_follow_up_at.strftime('%Y-%m-%d %H:%M:%S') if lead.next_follow_up_at else '',
                    'Closed Date': lead.lead_closed_at.strftime('%Y-%m-%d %H:%M:%S') if lead.lead_closed_at else '',
                    'Created Date': lead.created_at.strftime('%Y-%m-%d %H:%M:%S') if lead.created_at else ''
                })
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                pd.DataFrame(rows).to_excel(writer, index=False, sheet_name='Leads')
            out.seek(0)
            return send_file(out,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True, download_name=f'{filename}.xlsx')

        # CSV streaming
        def generate():
            fieldnames = ['Lead Number','Generation Date','Name','Mobile','Email','Qualification','Employment Type',
                          'Address','Course Interest','Status','Priority','Source','Assigned To','Branch',
                          'Next Follow-up','Closed Date','Created Date']
            sio = io.StringIO()
            writer = csv.DictWriter(sio, fieldnames=fieldnames)
            writer.writeheader(); yield sio.getvalue(); sio.seek(0); sio.truncate(0)
            for lead in query.yield_per(2000):
                row = {
                    'Lead Number': lead.lead_sl_number,
                    'Generation Date': lead.lead_generation_date.strftime('%Y-%m-%d %H:%M:%S') if lead.lead_generation_date else '',
                    'Name': _csv_safe(lead.name),
                    'Mobile': _csv_safe(lead.mobile),
                    'Email': _csv_safe(lead.email or ''),
                    'Qualification': _csv_safe(lead.qualification or ''),
                    'Employment Type': _csv_safe(lead.employment_type or ''),
                    'Address': _csv_safe(lead.address or ''),
                    'Course Interest': _csv_safe(lead.course_interest or ''),
                    'Status': lead.lead_status,
                    'Priority': lead.priority,
                    'Source': _csv_safe(lead.lead_source or ''),
                    'Assigned To': _csv_safe(lead.assigned_to.full_name if lead.assigned_to else ''),
                    'Branch': _csv_safe(lead.branch.branch_name if lead.branch else ''),
                    'Next Follow-up': lead.next_follow_up_at.strftime('%Y-%m-%d %H:%M:%S') if lead.next_follow_up_at else '',
                    'Closed Date': lead.lead_closed_at.strftime('%Y-%m-%d %H:%M:%S') if lead.lead_closed_at else '',
                    'Created Date': lead.created_at.strftime('%Y-%m-%d %H:%M:%S') if lead.created_at else ''
                }
                writer.writerow(row)
                yield sio.getvalue(); sio.seek(0); sio.truncate(0)
        return Response(generate(), mimetype='text/csv',
                        headers={'Content-Disposition': f'attachment; filename={filename}.csv'})

    except Exception as e:
        if wants_json_response():
            return err(f'Export failed: {str(e)}', 500)
        flash(f'Export failed: {str(e)}', 'error')
        return redirect(url_for('leads.lead_list'))

@lead_bp.route("/import", methods=["GET"])
@login_required
def leads_import_get():
    """Show import page and provide template download"""
    try:
        current_user = User.query.get(session.get('user_id'))

        if current_user.role not in ['admin', 'regional_manager', 'branch_manager', 'franchise']:
            flash('Access denied. Only managers can import leads.', 'error')
            return redirect(url_for('leads.lead_list'))

        # Branch choices
        branches = []
        if current_user.role == 'admin':
            branches = Branch.query.filter_by(is_deleted=False).all()
        elif current_user.role == 'regional_manager':
            accessible = get_user_accessible_branches(current_user.id) or []
            if accessible:
                branches = Branch.query.filter(Branch.id.in_(accessible)).all()
        else:
            ubid = _user_branch_id()
            if ubid:
                b = Branch.query.get(ubid)
                if b: branches = [b]

        # Template download
        if request.args.get('download_template'):
            template_data = [{
                'name': 'John Doe',
                'mobile': '9876543210',
                'email': 'john.doe@example.com',
                'qualification': 'B.Tech',
                'employment_type': 'Student',
                'address': '123 Main St, City',
                'course_interest': 'Python Programming',
                'priority': 'Medium',
                'lead_source': 'Walk-in',
                'assigned_to_email': 'counselor@example.com',
                'next_follow_up_date': '2025-08-15'
            }]
            output = io.StringIO()
            fieldnames = list(template_data[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader(); writer.writerows(template_data)
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name='leads_import_template.csv'
            )

        return render_template("leads/import.html", branches=branches)

    except Exception as e:
        flash(f'Error loading import page: {str(e)}', 'error')
        return redirect(url_for('leads.lead_list'))

@lead_bp.route("/import", methods=["POST"])
@login_required
def leads_import_post():
    """Process CSV import (supports dry-run)"""
    dry_run = False
    try:
        current_user = User.query.get(session.get('user_id'))
        if current_user.role not in ['admin', 'regional_manager', 'branch_manager', 'franchise']:
            return err('Access denied', 403)

        file = request.files.get('file')
        branch_id = request.form.get('branch_id')
        dry_run = (request.form.get('dry_run') == 'true')

        if not file or not file.filename:
            return err('No file uploaded', 400)
        if not branch_id:
            return err('Branch is required', 400)

        if not _user_has_corporate_access(current_user):
            ubid = _user_branch_id()
            if str(branch_id) != str(ubid):
                return err('Access denied for this branch', 403)

        try:
            stream = io.StringIO(file.stream.read().decode("utf-8"), newline=None)
            reader = csv.DictReader(stream)
            rows = list(reader)
        except Exception as ex:
            return err(f'Error reading CSV: {str(ex)}', 400)

        if not rows:
            return err('CSV file is empty', 400)

        errors, created = [], []
        for idx, row in enumerate(rows, start=2):
            name = (row.get('name') or '').strip()
            mobile = _norm_mobile(row.get('mobile'))
            email  = _norm_email(row.get('email'))

            if not name or not mobile:
                errors.append(f"Row {idx}: name and mobile are required"); continue
            if not _validate_mobile(mobile):
                errors.append(f"Row {idx}: invalid mobile"); continue
            if not _validate_email(email):
                errors.append(f"Row {idx}: invalid email"); continue

            # Duplicate check (scoped)
            dup_q = Lead.query.filter(Lead.is_deleted == False, Lead.mobile == mobile)
            if not _user_has_corporate_access(current_user):
                dup_q = dup_q.filter(Lead.branch_id == branch_id)
            if dup_q.first():
                errors.append(f"Row {idx}: mobile {mobile} already exists"); continue

            assigned_to_user_id = None
            email_assignee = _norm_email(row.get('assigned_to_email'))
            if email_assignee:
                u = User.query.filter(func.lower(User.email) == email_assignee).first()
                if u: assigned_to_user_id = u.id
                else: errors.append(f"Row {idx}: user {email_assignee} not found")

            next_follow_up_at = None
            if row.get('next_follow_up_date'):
                try:
                    next_follow_up_at = datetime.strptime(row['next_follow_up_date'], '%Y-%m-%d')
                except ValueError:
                    errors.append(f"Row {idx}: invalid next_follow_up_date (YYYY-MM-DD)")

            lead_sl = _generate_lead_serial_number(branch_id)

            if not dry_run:
                lead = Lead(
                    lead_sl_number=lead_sl,
                    branch_id=branch_id,
                    name=name,
                    mobile=mobile,
                    email=email or None,
                    qualification=(row.get('qualification') or '').strip() or None,
                    employment_type=(row.get('employment_type') or '').strip() or None,
                    address=(row.get('address') or '').strip() or None,
                    course_interest=(row.get('course_interest') or '').strip() or None,
                    priority=(row.get('priority') or 'Medium'),
                    lead_source=(row.get('lead_source') or None),
                    assigned_to_user_id=assigned_to_user_id,
                    next_follow_up_at=next_follow_up_at
                )
                db.session.add(lead)
                created.append(lead_sl)
            else:
                created.append(f"Would create: {lead_sl}")

        if not dry_run and created:
            db.session.commit()

        return ok({
            'message': f'Import completed. {"Dry run: " if dry_run else ""}{len(created)} leads processed',
            'created_count': len(created),
            'error_count': len(errors),
            'errors': errors[:25],
            'dry_run': dry_run
        })

    except Exception as e:
        if not dry_run:
            db.session.rollback()
        return err(str(e), 500)

# ================================
# REPORTING / METRICS
# ================================

@lead_bp.route("/metrics/overview", methods=["GET"])
@login_required
def leads_metrics_overview():
    """Lead overview metrics"""
    try:
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Base query with role-based filtering
        query = Lead.query.filter_by(is_deleted=False)
        
        # Apply role-based filtering
        if current_user.role == 'franchise':
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'regional_manager':
            accessible_branches = get_user_accessible_branches(current_user_id)
            if accessible_branches:
                query = query.filter(Lead.branch_id.in_(accessible_branches))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'trainer':
            query = query.filter_by(assigned_to_user_id=current_user_id)
        
        # Get counts by status
        status_counts = {}
        for status in ['Open', 'Contacted', 'Qualified', 'Converted', 'On Hold', 'Lost']:
            count = query.filter_by(lead_status=status).count()
            status_counts[status.lower()] = count
        
        # Get counts by priority
        priority_counts = {}
        for priority in ['Low', 'Medium', 'High', 'Hot']:
            count = query.filter_by(priority=priority).count()
            priority_counts[priority.lower()] = count
        
        # Get today's stats
        today = get_current_ist_datetime().date()
        today_leads = query.filter(func.date(Lead.created_at) == today).count()
        
        # Get this week's stats
        week_start = today - timedelta(days=today.weekday())
        week_leads = query.filter(Lead.created_at >= week_start).count()
        
        # Get conversion rate
        total_closed = query.filter(Lead.lead_status.in_(['Converted', 'Lost'])).count()
        converted = query.filter_by(lead_status='Converted').count()
        conversion_rate = (converted / total_closed * 100) if total_closed > 0 else 0
        
        return jsonify({
            'success': True,
            'metrics': {
                'total': query.count(),
                'today': today_leads,
                'this_week': week_leads,
                'conversion_rate': round(conversion_rate, 2),
                'by_status': status_counts,
                'by_priority': priority_counts
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@lead_bp.route("/metrics/by-source", methods=["GET"])
@login_required
def leads_metrics_by_source():
    """Lead metrics grouped by source"""
    try:
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Base query with role-based filtering
        query = Lead.query.filter_by(is_deleted=False)
        
        # Apply role-based filtering (same as overview)
        if current_user.role == 'franchise':
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'regional_manager':
            accessible_branches = get_user_accessible_branches(current_user_id)
            if accessible_branches:
                query = query.filter(Lead.branch_id.in_(accessible_branches))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'trainer':
            query = query.filter_by(assigned_to_user_id=current_user_id)
        
        # Get source metrics
        source_metrics = db.session.query(
            Lead.lead_source,
            func.count(Lead.id).label('total'),
            func.sum(func.case([(Lead.lead_status == 'Converted', 1)], else_=0)).label('converted'),
            func.sum(func.case([(Lead.lead_status == 'Lost', 1)], else_=0)).label('lost')
        ).filter_by(is_deleted=False)
        
        # Apply same role filtering to aggregation query
        if current_user.role == 'franchise':
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                source_metrics = source_metrics.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'regional_manager':
            accessible_branches = get_user_accessible_branches(current_user_id)
            if accessible_branches:
                source_metrics = source_metrics.filter(Lead.branch_id.in_(accessible_branches))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                source_metrics = source_metrics.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'trainer':
            source_metrics = source_metrics.filter_by(assigned_to_user_id=current_user_id)
        
        source_metrics = source_metrics.group_by(Lead.lead_source).all()
        
        # Format results
        results = []
        for metric in source_metrics:
            source = metric.lead_source or 'Unknown'
            total = metric.total or 0
            converted = metric.converted or 0
            lost = metric.lost or 0
            conversion_rate = (converted / total * 100) if total > 0 else 0
            
            results.append({
                'source': source,
                'total': total,
                'converted': converted,
                'lost': lost,
                'conversion_rate': round(conversion_rate, 2)
            })
        
        # Sort by total descending
        results.sort(key=lambda x: x['total'], reverse=True)
        
        return jsonify({
            'success': True,
            'metrics': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@lead_bp.route("/metrics/by-owner", methods=["GET"])
@login_required
def leads_metrics_by_owner():
    """Lead metrics grouped by assigned owner"""
    try:
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Base query with role-based filtering
        base_query = Lead.query.filter_by(is_deleted=False)
        
        # Apply role-based filtering
        if current_user.role == 'franchise':
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                base_query = base_query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'regional_manager':
            accessible_branches = get_user_accessible_branches(current_user_id)
            if accessible_branches:
                base_query = base_query.filter(Lead.branch_id.in_(accessible_branches))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                base_query = base_query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'trainer':
            base_query = base_query.filter_by(assigned_to_user_id=current_user_id)
        
        # Get owner metrics
        owner_metrics = db.session.query(
            User.id,
            User.full_name,
            func.count(Lead.id).label('total'),
            func.sum(func.case([(Lead.lead_status == 'Open', 1)], else_=0)).label('open'),
            func.sum(func.case([(Lead.lead_status == 'In Progress', 1)], else_=0)).label('in_progress'),
            func.sum(func.case([(Lead.lead_status == 'Follow-up Scheduled', 1)], else_=0)).label('followup_scheduled'),
            func.sum(func.case([(Lead.lead_status == 'Demo Scheduled', 1)], else_=0)).label('demo_scheduled'),
            func.sum(func.case([(Lead.lead_status == 'Converted', 1)], else_=0)).label('converted'),
            func.sum(func.case([(Lead.lead_status == 'Not Interested', 1)], else_=0)).label('not_interested')
        ).select_from(User).join(Lead, User.id == Lead.assigned_to_user_id, isouter=True)
        
        # Apply same filtering to join query
        owner_metrics = owner_metrics.filter(Lead.is_deleted == False)
        
        if current_user.role == 'franchise':
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                owner_metrics = owner_metrics.filter(Lead.branch_id == user_branch_id)
        elif current_user.role == 'regional_manager':
            accessible_branches = get_user_accessible_branches(current_user_id)
            if accessible_branches:
                owner_metrics = owner_metrics.filter(Lead.branch_id.in_(accessible_branches))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                owner_metrics = owner_metrics.filter(Lead.branch_id == user_branch_id)
        elif current_user.role == 'trainer':
            owner_metrics = owner_metrics.filter(Lead.assigned_to_user_id == current_user_id)
        
        owner_metrics = owner_metrics.group_by(User.id, User.full_name).all()
        
        # Format results
        results = []
        for metric in owner_metrics:
            if metric.total > 0:  # Only include users with leads
                conversion_rate = (metric.converted / metric.total * 100) if metric.total > 0 else 0
                
                results.append({
                    'user_id': metric.id,
                    'user_name': metric.full_name,
                    'total': metric.total or 0,
                    'open': metric.open or 0,
                    'contacted': metric.contacted or 0,
                    'qualified': metric.qualified or 0,
                    'converted': metric.converted or 0,
                    'lost': metric.lost or 0,
                    'conversion_rate': round(conversion_rate, 2)
                })
        
        # Sort by total descending
        results.sort(key=lambda x: x['total'], reverse=True)
        
        return jsonify({
            'success': True,
            'metrics': results
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@lead_bp.route("/metrics/funnel", methods=["GET"])
@login_required
def leads_metrics_funnel():
    """Lead funnel conversion stats"""
    try:
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Base query with role-based filtering
        query = Lead.query.filter_by(is_deleted=False)
        
        # Apply role-based filtering
        if current_user.role == 'franchise':
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'regional_manager':
            accessible_branches = get_user_accessible_branches(current_user_id)
            if accessible_branches:
                query = query.filter(Lead.branch_id.in_(accessible_branches))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'trainer':
            query = query.filter_by(assigned_to_user_id=current_user_id)
        
        # Define funnel stages
        stages = ['Open', 'In Progress', 'Follow-up Scheduled', 'Demo Scheduled', 'Converted']
        funnel_data = []
        
        total_leads = query.count()
        
        for i, stage in enumerate(stages):
            count = query.filter_by(lead_status=stage).count()
            percentage = (count / total_leads * 100) if total_leads > 0 else 0
            
            # Calculate conversion rate from previous stage
            if i > 0:
                prev_stage_count = query.filter_by(lead_status=stages[i-1]).count()
                stage_conversion = (count / prev_stage_count * 100) if prev_stage_count > 0 else 0
            else:
                stage_conversion = 100  # First stage is 100%
            
            funnel_data.append({
                'stage': stage,
                'count': count,
                'percentage_of_total': round(percentage, 2),
                'conversion_from_previous': round(stage_conversion, 2)
            })
        
        # Add lost leads
        lost_count = query.filter_by(lead_status='Lost').count()
        lost_percentage = (lost_count / total_leads * 100) if total_leads > 0 else 0
        
        return jsonify({
            'success': True,
            'funnel': funnel_data,
            'total_leads': total_leads,
            'lost_leads': {
                'count': lost_count,
                'percentage': round(lost_percentage, 2)
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@lead_bp.route("/metrics/aging", methods=["GET"])
@login_required
def leads_metrics_aging():
    """Lead aging analysis"""
    try:
        current_user_id = session.get('user_id')
        current_user = User.query.get(current_user_id)
        
        # Base query with role-based filtering
        query = Lead.query.filter_by(is_deleted=False)
        
        # Apply role-based filtering
        if current_user.role == 'franchise':
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'regional_manager':
            accessible_branches = get_user_accessible_branches(current_user_id)
            if accessible_branches:
                query = query.filter(Lead.branch_id.in_(accessible_branches))
        elif current_user.role in ['branch_manager', 'staff']:
            user_branch_id = session.get("user_branch_id")
            if user_branch_id:
                query = query.filter_by(branch_id=user_branch_id)
        elif current_user.role == 'trainer':
            query = query.filter_by(assigned_to_user_id=current_user_id)
        
        today = get_current_ist_datetime()
        
        # Get aging by days in current stage
        aging_buckets = {
            '0-1 days': 0,
            '2-3 days': 0,
            '4-7 days': 0,
            '8-14 days': 0,
            '15-30 days': 0,
            '30+ days': 0
        }
        
        leads = query.filter(Lead.lead_status.in_(['Open', 'Contacted', 'Qualified', 'On Hold'])).all()
        
        for lead in leads:
            days_old = (today - lead.created_at).days if lead.created_at else 0
            
            if days_old <= 1:
                aging_buckets['0-1 days'] += 1
            elif days_old <= 3:
                aging_buckets['2-3 days'] += 1
            elif days_old <= 7:
                aging_buckets['4-7 days'] += 1
            elif days_old <= 14:
                aging_buckets['8-14 days'] += 1
            elif days_old <= 30:
                aging_buckets['15-30 days'] += 1
            else:
                aging_buckets['30+ days'] += 1
        
        # Get overdue follow-ups
        overdue_followups = query.filter(
            and_(
                Lead.next_follow_up_at < today,
                Lead.lead_status.in_(['Open', 'Contacted', 'Qualified', 'On Hold'])
            )
        ).count()
        
        return jsonify({
            'success': True,
            'aging': aging_buckets,
            'overdue_followups': overdue_followups,
            'total_active': len(leads)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# SMART NEXT ACTION AUTOMATION - Advanced AI Suggestions Route
# =============================================================================

@lead_bp.route('/api/leads/<int:lead_id>/advanced-ai-suggestions', methods=['POST'])
@login_required
def get_advanced_ai_suggestions(lead_id):
    """
    Get advanced AI suggestions based on lead context and history
    Enhanced Smart Next Action Automation endpoint
    """
    try:
        # Validate request data
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        outcome_id = data.get('outcome_id')
        outcome_details = data.get('outcome_details', '')
        lead_context = data.get('lead_context', {})
        
        if not outcome_id:
            return jsonify({'success': False, 'error': 'Outcome ID is required'}), 400
        
        lead = Lead.query.get_or_404(lead_id)
        
        # Get lead history and context for AI analysis
        from sqlalchemy import text
        
        # Get recent follow-ups for pattern analysis
        recent_followups = db.session.execute(text("""
            SELECT follow_up_type, outcome_id, outcome_details, created_at, next_follow_up_at
            FROM lead_follow_ups 
            WHERE lead_id = :lead_id 
            ORDER BY created_at DESC 
            LIMIT 10
        """), {'lead_id': lead_id}).fetchall()
        
        # Get lead details for context
        lead_data = {
            'source': lead.lead_source,
            'status': lead.lead_status,
            'stage': lead.stage,
            'interest_level': getattr(lead, 'interest_level', 'Unknown'),
            'courses_interested': lead.courses_interested or '',
            'budget_range': getattr(lead, 'budget_range', 'Unknown'),
            'timeline': getattr(lead, 'preferred_timeline', 'Unknown'),
            'contact_attempts': len(recent_followups),
            'last_contact': recent_followups[0].created_at.isoformat() if recent_followups else None,
            'progression_pattern': [f.outcome_id for f in recent_followups[:5]]
        }
        
        # Generate advanced AI suggestions based on comprehensive analysis
        suggestions = generate_advanced_ai_suggestions(
            outcome_id=outcome_id,
            outcome_details=outcome_details,
            lead_data=lead_data,
            follow_up_history=recent_followups,
            lead_context=lead_context
        )
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'lead_context': lead_data,
            'analysis_timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting advanced AI suggestions: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

def generate_advanced_ai_suggestions(outcome_id, outcome_details, lead_data, follow_up_history, lead_context):
    """
    Generate advanced AI suggestions using comprehensive lead analysis
    Part of Smart Next Action Automation system
    """
    try:
        # Outcome-to-Action intelligence mapping
        ADVANCED_ACTION_MAPPING = {
            # Positive Engagement Outcomes
            'INTERESTED_NEED_INFO': {
                'priority_actions': [
                    {'action': 'send_course_brochure', 'timing': 'immediate', 'priority': 'high'},
                    {'action': 'schedule_demo', 'timing': '2_hours', 'priority': 'high'},
                    {'action': 'send_pricing_info', 'timing': '4_hours', 'priority': 'medium'}
                ],
                'follow_up_sequence': [
                    {'timing': '1_day', 'type': 'email', 'purpose': 'provide_detailed_info'},
                    {'timing': '3_days', 'type': 'call', 'purpose': 'discuss_requirements'},
                    {'timing': '1_week', 'type': 'demo', 'purpose': 'show_platform'}
                ]
            },
            'WANTS_DEMO': {
                'priority_actions': [
                    {'action': 'schedule_demo', 'timing': 'immediate', 'priority': 'urgent'},
                    {'action': 'send_pre_demo_materials', 'timing': '1_hour', 'priority': 'high'},
                    {'action': 'prepare_personalized_demo', 'timing': '2_hours', 'priority': 'high'}
                ],
                'follow_up_sequence': [
                    {'timing': '30_minutes', 'type': 'confirmation', 'purpose': 'confirm_demo_time'},
                    {'timing': '1_day', 'type': 'demo', 'purpose': 'conduct_demo'},
                    {'timing': '2_hours_post_demo', 'type': 'call', 'purpose': 'gather_feedback'}
                ]
            },
            'BUDGET_DISCUSSION': {
                'priority_actions': [
                    {'action': 'prepare_custom_quote', 'timing': '2_hours', 'priority': 'high'},
                    {'action': 'send_roi_calculator', 'timing': '1_hour', 'priority': 'medium'},
                    {'action': 'schedule_budget_call', 'timing': '4_hours', 'priority': 'high'}
                ],
                'follow_up_sequence': [
                    {'timing': '4_hours', 'type': 'email', 'purpose': 'send_pricing_options'},
                    {'timing': '1_day', 'type': 'call', 'purpose': 'discuss_budget'},
                    {'timing': '3_days', 'type': 'follow_up', 'purpose': 'address_concerns'}
                ]
            },
            # Objection Handling
            'PRICE_OBJECTION': {
                'priority_actions': [
                    {'action': 'send_roi_analysis', 'timing': '2_hours', 'priority': 'high'},
                    {'action': 'offer_payment_plans', 'timing': '1_hour', 'priority': 'high'},
                    {'action': 'schedule_value_discussion', 'timing': '4_hours', 'priority': 'high'}
                ],
                'follow_up_sequence': [
                    {'timing': '4_hours', 'type': 'email', 'purpose': 'address_price_concerns'},
                    {'timing': '1_day', 'type': 'call', 'purpose': 'discuss_value_proposition'},
                    {'timing': '3_days', 'type': 'follow_up', 'purpose': 'offer_alternatives'}
                ]
            },
            'NOT_INTERESTED': {
                'priority_actions': [
                    {'action': 'understand_objection', 'timing': 'immediate', 'priority': 'medium'},
                    {'action': 'add_to_nurture_campaign', 'timing': '1_hour', 'priority': 'low'},
                    {'action': 'schedule_long_term_follow_up', 'timing': '2_hours', 'priority': 'low'}
                ],
                'follow_up_sequence': [
                    {'timing': '3_months', 'type': 'reengagement', 'purpose': 'check_status_change'},
                    {'timing': '6_months', 'type': 'newsletter', 'purpose': 'stay_top_of_mind'},
                    {'timing': '1_year', 'type': 'requalification', 'purpose': 'reassess_fit'}
                ]
            },
            'NO_RESPONSE': {
                'priority_actions': [
                    {'action': 'try_different_channel', 'timing': 'immediate', 'priority': 'medium'},
                    {'action': 'send_re_engagement_email', 'timing': '1_hour', 'priority': 'medium'},
                    {'action': 'check_contact_details', 'timing': '2_hours', 'priority': 'high'}
                ],
                'follow_up_sequence': [
                    {'timing': '2_days', 'type': 'different_channel', 'purpose': 'attempt_reconnection'},
                    {'timing': '1_week', 'type': 'final_attempt', 'purpose': 'last_chance_contact'},
                    {'timing': '1_month', 'type': 'dormant_followup', 'purpose': 'reactivation_attempt'}
                ]
            }
        }
        
        # Get base suggestions from mapping
        base_suggestions = ADVANCED_ACTION_MAPPING.get(outcome_id, {
            'priority_actions': [
                {'action': 'generic_follow_up', 'timing': '1_day', 'priority': 'medium'}
            ],
            'follow_up_sequence': [
                {'timing': '3_days', 'type': 'call', 'purpose': 'general_follow_up'}
            ]
        })
        
        # Enhance suggestions based on lead context and history
        enhanced_suggestions = enhance_suggestions_with_context(
            base_suggestions, lead_data, follow_up_history, outcome_details
        )
        
        # Add personalized messaging templates
        enhanced_suggestions['templates'] = generate_personalized_templates(
            outcome_id, lead_data, outcome_details
        )
        
        # Add urgency scoring and prioritization
        enhanced_suggestions['urgency_score'] = calculate_urgency_score(
            lead_data, follow_up_history, outcome_id
        )
        
        return enhanced_suggestions
        
    except Exception as e:
        current_app.logger.error(f"Error generating advanced AI suggestions: {str(e)}")
        return {
            'priority_actions': [
                {'action': 'manual_review_required', 'timing': 'immediate', 'priority': 'high'}
            ],
            'error': str(e)
        }

def enhance_suggestions_with_context(base_suggestions, lead_data, follow_up_history, outcome_details):
    """Enhance base suggestions with lead-specific context"""
    enhanced = base_suggestions.copy()
    
    # Adjust timing based on contact frequency
    contact_frequency = len(follow_up_history)
    if contact_frequency > 5:
        # Reduce aggressive follow-up for heavily contacted leads
        for action in enhanced['priority_actions']:
            if action['timing'] == 'immediate':
                action['timing'] = '4_hours'
    
    # Adjust based on lead stage
    if lead_data.get('stage') == 'Hot':
        # Accelerate actions for hot leads
        for action in enhanced['priority_actions']:
            action['priority'] = 'urgent' if action['priority'] == 'high' else 'high'
    
    # Add context-specific actions
    if 'budget' in outcome_details.lower():
        enhanced['priority_actions'].insert(0, {
            'action': 'prepare_budget_justification',
            'timing': '1_hour',
            'priority': 'high'
        })
    
    return enhanced

def generate_personalized_templates(outcome_id, lead_data, outcome_details):
    """Generate personalized message templates based on context"""
    templates = {
        'email_subject': f"Next steps for {lead_data.get('courses_interested', 'your training needs')}",
        'email_body': f"""
        Hi {{contact_name}},
        
        Thank you for our recent conversation about {lead_data.get('courses_interested', 'your training requirements')}.
        
        Based on your {outcome_details.lower()}, I've prepared some next steps that will help move your training initiative forward.
        
        {{personalized_content}}
        
        Best regards,
        {{agent_name}}
        """,
        'sms_template': f"Hi! Following up on our discussion about {lead_data.get('courses_interested', 'training')}. {{action_specific_message}}"
    }
    
    return templates

def calculate_urgency_score(lead_data, follow_up_history, outcome_id):
    """Calculate urgency score for prioritizing actions"""
    score = 50  # Base score
    
    # Stage-based scoring
    stage_scores = {'Hot': 30, 'Warm': 20, 'Cold': 10}
    score += stage_scores.get(lead_data.get('stage'), 10)
    
    # Outcome-based scoring
    urgent_outcomes = ['WANTS_DEMO', 'BUDGET_DISCUSSION', 'READY_TO_ENROLL']
    if outcome_id in urgent_outcomes:
        score += 25
    
    # Contact frequency penalty (avoid over-contacting)
    contact_count = len(follow_up_history)
    if contact_count > 10:
        score -= 20
    elif contact_count > 5:
        score -= 10
    
    # Time since last contact boost
    if follow_up_history and follow_up_history[0]:
        last_contact = follow_up_history[0].created_at
        days_since = (datetime.now() - last_contact).days
        if days_since > 7:
            score += 15
        elif days_since > 3:
            score += 10
    
    return max(0, min(100, score))  # Clamp between 0-100