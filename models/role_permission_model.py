"""
Role Permissions Model
Defines role-based access control for the application
"""

from init_db import db
from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint

class RolePermission(db.Model):
    """
    Model for role-based permissions
    Defines what each role can do in each module
    """
    __tablename__ = 'role_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50), nullable=False, index=True)
    module = db.Column(db.String(50), nullable=False, index=True)
    permission_level = db.Column(db.String(20), nullable=False, default='read')
    can_export = db.Column(db.Boolean, default=False)
    can_modify = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    can_create = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), 
                          onupdate=lambda: datetime.now(timezone.utc))
    
    # Ensure unique role-module combinations
    __table_args__ = (
        UniqueConstraint('role', 'module', name='unique_role_module'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}  # MySQL compatibility
    )
    
    def __repr__(self):
        return f'<RolePermission {self.role}:{self.module}:{self.permission_level}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'role': self.role,
            'module': self.module,
            'permission_level': self.permission_level,
            'can_export': self.can_export,
            'can_modify': self.can_modify,
            'can_delete': self.can_delete,
            'can_create': self.can_create,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def get_permission(cls, role, module):
        """Get permission for a specific role and module"""
        return cls.query.filter_by(role=role, module=module).first()
    
    @classmethod
    def has_permission(cls, role, module, action='read'):
        """Check if role has specific permission for module"""
        permission = cls.get_permission(role, module)
        if not permission:
            return False
        
        # Check permission based on action
        if action == 'read':
            return permission.permission_level in ['read', 'write', 'full']
        elif action == 'write':
            return permission.permission_level in ['write', 'full']
        elif action == 'full':
            return permission.permission_level == 'full'
        elif action == 'export':
            return permission.can_export
        elif action == 'modify':
            return permission.can_modify
        elif action == 'delete':
            return permission.can_delete
        elif action == 'create':
            return permission.can_create
        
        return False
    
    @classmethod
    def get_user_permissions(cls, role):
        """Get all permissions for a role"""
        return cls.query.filter_by(role=role).all()
    
    @classmethod
    def create_default_permissions(cls):
        """Create default permissions for all roles"""
        default_permissions = [
            # Admin - Full access to everything
            ('admin', 'finance', 'full', True, True, True, True),
            ('admin', 'leads', 'full', True, True, True, True),
            ('admin', 'students', 'full', True, True, True, True),
            ('admin', 'attendance', 'full', True, True, True, True),
            ('admin', 'courses', 'full', True, True, True, True),
            ('admin', 'batches', 'full', True, True, True, True),
            ('admin', 'staff', 'full', True, True, True, True),
            ('admin', 'reports', 'full', True, True, True, True),
            ('admin', 'settings', 'full', True, True, True, True),
            
            # Regional Manager - Almost full access
            ('regional_manager', 'finance', 'full', True, True, True, True),
            ('regional_manager', 'leads', 'full', True, True, True, True),
            ('regional_manager', 'students', 'full', True, True, False, True),
            ('regional_manager', 'attendance', 'write', True, True, False, True),
            ('regional_manager', 'courses', 'write', True, True, False, True),
            ('regional_manager', 'batches', 'write', True, True, False, True),
            ('regional_manager', 'staff', 'write', True, True, False, True),
            ('regional_manager', 'reports', 'full', True, False, False, False),
            ('regional_manager', 'settings', 'read', False, False, False, False),
            
            # Franchise - Finance and operational access
            ('franchise', 'finance', 'write', True, True, False, True),
            ('franchise', 'leads', 'write', True, True, False, True),
            ('franchise', 'students', 'write', True, True, False, True),
            ('franchise', 'attendance', 'write', True, True, False, True),
            ('franchise', 'courses', 'read', True, False, False, False),
            ('franchise', 'batches', 'write', True, True, False, True),
            ('franchise', 'staff', 'read', True, False, False, False),
            ('franchise', 'reports', 'read', True, False, False, False),
            ('franchise', 'settings', 'read', False, False, False, False),
            
            # Branch Manager - Branch-level access
            ('branch_manager', 'finance', 'write', True, True, False, True),
            ('branch_manager', 'leads', 'write', True, True, False, True),
            ('branch_manager', 'students', 'write', True, True, False, True),
            ('branch_manager', 'attendance', 'write', True, True, False, True),
            ('branch_manager', 'courses', 'read', True, False, False, False),
            ('branch_manager', 'batches', 'write', True, True, False, True),
            ('branch_manager', 'staff', 'read', True, False, False, False),
            ('branch_manager', 'reports', 'read', True, False, False, False),
            ('branch_manager', 'settings', 'read', False, False, False, False),
            
            # Staff - Limited access
            ('staff', 'finance', 'read', True, False, False, False),
            ('staff', 'leads', 'write', False, True, False, True),
            ('staff', 'students', 'write', False, True, False, True),
            ('staff', 'attendance', 'write', False, True, False, True),
            ('staff', 'courses', 'read', False, False, False, False),
            ('staff', 'batches', 'read', False, False, False, False),
            ('staff', 'reports', 'read', False, False, False, False),
            ('staff', 'settings', 'read', False, False, False, False),
            
            # Trainer - Very limited access (attendance focused)
            ('trainer', 'attendance', 'write', False, True, False, True),
            ('trainer', 'students', 'read', False, False, False, False),
            ('trainer', 'batches', 'read', False, False, False, False),
            ('trainer', 'courses', 'read', False, False, False, False),
            ('trainer', 'reports', 'read', False, False, False, False),
            ('trainer', 'settings', 'read', False, False, False, False),
        ]
        
        # Check if permissions already exist
        existing_count = cls.query.count()
        if existing_count > 0:
            return existing_count
        
        # Create permissions
        created_count = 0
        for role, module, level, can_export, can_modify, can_delete, can_create in default_permissions:
            permission = cls(
                role=role,
                module=module,
                permission_level=level,
                can_export=can_export,
                can_modify=can_modify,
                can_delete=can_delete,
                can_create=can_create
            )
            db.session.add(permission)
            created_count += 1
        
        try:
            db.session.commit()
            return created_count
        except Exception as e:
            db.session.rollback()
            raise e
