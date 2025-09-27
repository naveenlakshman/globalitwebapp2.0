"""
MySQL SSL Configuration Guide for GlobalIT Education Web Application

This guide explains how to configure SSL/TLS encryption for MySQL connections in production.
"""

# =============================================================================
# MYSQL SSL CONFIGURATION GUIDE
# =============================================================================

## 1. ENVIRONMENT VARIABLES FOR SSL CONFIGURATION

# Basic SSL Settings (Production Defaults)
DATABASE_URL=mysql+pymysql://username:password@mysql-server:3306/globalit_education_prod
MYSQL_SSL_DISABLED=false          # Enable SSL (default: false)
MYSQL_SSL_VERIFY_CERT=true        # Verify server certificate (default: true)
MYSQL_SSL_VERIFY_IDENTITY=true    # Verify server identity (default: true)

# SSL Certificate Files (Optional - for mutual TLS authentication)
MYSQL_SSL_CA=/path/to/ca-cert.pem          # Certificate Authority file
MYSQL_SSL_CERT=/path/to/client-cert.pem    # Client certificate file  
MYSQL_SSL_KEY=/path/to/client-key.pem      # Client private key file

## 2. PRODUCTION DEPLOYMENT EXAMPLES

### AWS RDS MySQL with SSL:
```bash
# Set these environment variables:
export DATABASE_URL="mysql+pymysql://admin:password@globalit-db.abc123.us-east-1.rds.amazonaws.com:3306/globalit_education_prod"
export MYSQL_SSL_VERIFY_CERT=true
export MYSQL_SSL_VERIFY_IDENTITY=true
# AWS RDS uses server-side certificates by default
```

### Google Cloud SQL with SSL:
```bash
export DATABASE_URL="mysql+pymysql://root:password@35.123.456.789:3306/globalit_education_prod"
export MYSQL_SSL_CA=/path/to/server-ca.pem
export MYSQL_SSL_CERT=/path/to/client-cert.pem
export MYSQL_SSL_KEY=/path/to/client-key.pem
```

### Azure Database for MySQL with SSL:
```bash
export DATABASE_URL="mysql+pymysql://admin@servername:password@servername.mysql.database.azure.com:3306/globalit_education_prod"
export MYSQL_SSL_VERIFY_CERT=true
# Azure enforces SSL by default
```

### Self-Managed MySQL Server with SSL:
```bash
export DATABASE_URL="mysql+pymysql://globalit_user:secure_password@your-mysql-server.com:3306/globalit_education_prod"
export MYSQL_SSL_CA=/etc/ssl/certs/mysql-ca.pem
export MYSQL_SSL_CERT=/etc/ssl/certs/mysql-client-cert.pem
export MYSQL_SSL_KEY=/etc/ssl/private/mysql-client-key.pem
```

## 3. DEVELOPMENT vs PRODUCTION

### Development Environment (config):
- SSL verification can be disabled for local MySQL servers
- Set FLASK_ENV=development to allow relaxed SSL settings
- Use: MYSQL_SSL_DISABLED=true for local development if needed

### Production Environment (config):
- SSL is ALWAYS enabled and verified by default
- Certificate verification is enforced
- Server identity verification is enforced
- Use proper SSL certificates from trusted CA

## 4. SSL CERTIFICATE SETUP

### For Self-Managed MySQL Server:

1. **Generate SSL Certificates on MySQL Server:**
```sql
-- On MySQL server, check if SSL is enabled:
SHOW VARIABLES LIKE 'have_ssl';

-- Create SSL certificates (MySQL 8.0+):
-- This is usually done during MySQL installation
```

2. **Download Client Certificates:**
```bash
# Copy from MySQL server to application server:
scp mysql-server:/var/lib/mysql/ca.pem /etc/ssl/certs/mysql-ca.pem
scp mysql-server:/var/lib/mysql/client-cert.pem /etc/ssl/certs/mysql-client-cert.pem  
scp mysql-server:/var/lib/mysql/client-key.pem /etc/ssl/private/mysql-client-key.pem

# Set proper permissions:
chmod 644 /etc/ssl/certs/mysql-ca.pem
chmod 644 /etc/ssl/certs/mysql-client-cert.pem
chmod 600 /etc/ssl/private/mysql-client-key.pem
```

### For Cloud Providers:

**AWS RDS:** SSL certificates are managed automatically
**Google Cloud SQL:** Download certificates from Cloud Console
**Azure MySQL:** SSL is enforced by default, certificates available in portal

## 5. TESTING SSL CONNECTION

```python
# Test script to verify SSL connection:
import os
from sqlalchemy import create_engine, text

# Set your database URL
database_url = "mysql+pymysql://user:pass@host:3306/dbname"

# Create engine with SSL
engine = create_engine(
    database_url,
    connect_args={
        'ssl_verify_cert': True,
        'ssl_verify_identity': True,
        'ssl_ca': '/path/to/ca.pem'  # if using custom CA
    }
)

# Test connection
try:
    with engine.connect() as conn:
        result = conn.execute(text("SHOW STATUS LIKE 'Ssl_cipher'"))
        for row in result:
            print(f"SSL Cipher: {row[1]}")
        print("✅ SSL connection successful!")
except Exception as e:
    print(f"❌ SSL connection failed: {e}")
```

## 6. TROUBLESHOOTING

### Common SSL Issues:

1. **SSL Certificate Verification Failed:**
   - Check if certificate files exist and have correct permissions
   - Verify certificate paths in environment variables
   - Ensure certificates are not expired

2. **SSL Connection Refused:**
   - Verify MySQL server has SSL enabled
   - Check firewall rules allow SSL port (usually 3306)
   - Confirm server certificate is valid

3. **Development vs Production Issues:**
   - Use MYSQL_SSL_DISABLED=true for local development only
   - Never disable SSL verification in production
   - Set FLASK_ENV=development for relaxed SSL in dev environment

### Debug Commands:
```bash
# Check SSL status on MySQL server:
mysql -u root -p -e "SHOW VARIABLES LIKE '%ssl%';"

# Test SSL connection from command line:
mysql -u username -p -h hostname --ssl-mode=REQUIRED

# Verify certificate details:
openssl x509 -in /path/to/certificate.pem -text -noout
```

## 7. SECURITY BEST PRACTICES

1. **Always use SSL in production**
2. **Verify server certificates** (ssl_verify_cert=True)  
3. **Verify server identity** (ssl_verify_identity=True)
4. **Use strong passwords** for database users
5. **Limit database user privileges** to only required operations
6. **Rotate certificates** regularly (annual or bi-annual)
7. **Monitor SSL certificate expiration** dates
8. **Use mutual TLS** (client certificates) for enhanced security
9. **Network security:** Use VPC, security groups, or firewall rules
10. **Audit database access** and enable MySQL audit logging

## 8. DEPLOYMENT CHECKLIST

Before deploying to production with SSL:

- [ ] MySQL server has SSL enabled
- [ ] SSL certificates are properly configured  
- [ ] Environment variables are set correctly
- [ ] SSL connection tested successfully
- [ ] Certificate expiration monitoring is in place
- [ ] Database user has appropriate privileges only
- [ ] Network security (VPC/firewall) is configured
- [ ] Backup strategy includes certificate backup
- [ ] SSL configuration is documented for team
- [ ] Monitoring/alerting for SSL connection failures

## 9. EXAMPLE DOCKER DEPLOYMENT

```dockerfile
# Dockerfile with SSL certificates
FROM python:3.9-slim

# Copy SSL certificates
COPY certs/mysql-ca.pem /etc/ssl/certs/
COPY certs/mysql-client-cert.pem /etc/ssl/certs/  
COPY certs/mysql-client-key.pem /etc/ssl/private/

# Set proper permissions
RUN chmod 644 /etc/ssl/certs/mysql-*.pem && \
    chmod 600 /etc/ssl/private/mysql-client-key.pem

# Copy application
COPY . /app
WORKDIR /app

# Install dependencies
RUN pip install -r requirements.txt

# Set environment variables
ENV DATABASE_URL=mysql+pymysql://user:pass@mysql:3306/globalit_education_prod
ENV MYSQL_SSL_CA=/etc/ssl/certs/mysql-ca.pem
ENV MYSQL_SSL_CERT=/etc/ssl/certs/mysql-client-cert.pem
ENV MYSQL_SSL_KEY=/etc/ssl/private/mysql-client-key.pem

CMD ["python", "run.py"]
```

Remember: SSL configuration ensures data in transit is encrypted and helps prevent man-in-the-middle attacks on your database connections.