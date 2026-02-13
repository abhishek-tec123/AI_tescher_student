# Role-Based Authentication System

This document describes the role-based authentication system implemented for the Student Learning API.

## Overview

The authentication system provides secure login functionality for both students and admins with role-based access control. It uses JWT tokens for stateless authentication and bcrypt for password hashing.

## Features

### 🔐 Authentication Features
- **Unified Login**: Single endpoint for both student and admin login
- **JWT Tokens**: Secure stateless authentication with access and refresh tokens
- **Role-Based Access**: Fine-grained permission control (student/admin)
- **Password Security**: Bcrypt hashing with complexity validation
- **Token Refresh**: Automatic token renewal without re-login
- **Password Management**: Change password functionality

### 🛡️ Security Features
- **Password Strength Validation**: Enforces strong password requirements
- **Rate Limiting Ready**: Infrastructure for login attempt limiting
- **Session Management**: Token-based session control
- **Role Protection**: Route-level access control

## API Endpoints

### Authentication Routes (`/api/v1/auth/`)

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "user_id": "std_ABC123",
    "email": "user@example.com",
    "name": "John Doe",
    "role": "student",
    "is_active": true
  }
}
```

#### Refresh Token
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

#### Get Current User
```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

#### Change Password
```http
POST /api/v1/auth/change-password
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "current_password": "oldpassword",
  "new_password": "NewPassword123!"
}
```

#### Create Student with Auth (Admin Only)
```http
POST /api/v1/auth/create-student-with-auth
Authorization: Bearer <admin_access_token>
Content-Type: application/json

{
  "name": "Jane Smith",
  "email": "jane@example.com",
  "class_name": "10A",
  "password": "OptionalPassword123!"
}
```

#### Create Admin (Admin Only)
```http
POST /api/v1/auth/create-admin
Authorization: Bearer <admin_access_token>
Content-Type: application/json

{
  "name": "Admin User",
  "email": "admin@example.com",
  "password": "AdminPassword123!",
  "permissions": ["all"]
}
```

## Protected Routes

All student and admin routes now require authentication. Include the access token in the Authorization header:

```http
Authorization: Bearer <access_token>
```

### Role-Based Access Control

- **Students**: Can only access their own data
- **Admins**: Can access all student data and admin functions

### Examples

#### Student accessing their own data:
```http
GET /api/v1/student/std_ABC123
Authorization: Bearer <student_access_token>
```

#### Admin accessing any student data:
```http
GET /api/v1/student/std_ABC123
Authorization: Bearer <admin_access_token>
```

## Database Schema Changes

### Students Collection
Added `auth` field to existing student documents:

```json
{
  "auth": {
    "password_hash": "$2b$12$...",
    "is_active": true,
    "last_login": "2024-01-01T12:00:00Z",
    "role": "student"
  }
}
```

### Admins Collection
New collection for admin users:

```json
{
  "_id": ObjectId("..."),
  "admin_id": "admin_ABC123",
  "name": "Admin User",
  "email": "admin@example.com",
  "auth": {
    "password_hash": "$2b$12$...",
    "is_active": true,
    "last_login": null,
    "role": "admin"
  },
  "permissions": ["all"],
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

## Migration

### Running the Migration

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run migration script:**
```bash
python migrate_auth.py
```

The migration will:
- Create a backup of existing student data
- Add authentication fields to existing students
- Generate temporary passwords for existing students
- Create a default admin user

### Default Admin Credentials
- **Email**: admin@teacherai.com
- **Password**: Admin123!
- **⚠️ Change this immediately after first login!**

## Password Requirements

Passwords must meet the following criteria:
- At least 8 characters long
- Contains at least one uppercase letter
- Contains at least one lowercase letter
- Contains at least one digit
- Contains at least one special character

## Environment Variables

Add these to your `.env` file:

```env
# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production

# MongoDB (existing)
MONGODB_URI=mongodb://localhost:27017
```

## Usage Examples

### Python Client Example

```python
import requests

# Login
login_response = requests.post('http://localhost:8000/api/v1/auth/login', json={
    'email': 'student@example.com',
    'password': 'StudentPassword123!'
})

tokens = login_response.json()
access_token = tokens['access_token']

# Use protected endpoint
headers = {'Authorization': f'Bearer {access_token}'}
student_data = requests.get(
    'http://localhost:8000/api/v1/student/std_ABC123',
    headers=headers
)
```

### JavaScript Client Example

```javascript
// Login
const loginResponse = await fetch('/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'student@example.com',
    password: 'StudentPassword123!'
  })
});

const { access_token } = await loginResponse.json();

// Use protected endpoint
const studentData = await fetch('/api/v1/student/std_ABC123', {
  headers: { 'Authorization': `Bearer ${access_token}` }
});
```

## Security Considerations

1. **Change Default Passwords**: Always change default passwords after first login
2. **Use HTTPS**: Ensure all API calls use HTTPS in production
3. **Secure JWT Secret**: Use a strong, random JWT secret key
4. **Token Expiration**: Tokens expire after 30 minutes by default
5. **Password Storage**: Passwords are hashed using bcrypt
6. **Input Validation**: All inputs are validated using Pydantic models

## Troubleshooting

### Common Issues

1. **Invalid Token Error**: Check if token is expired and use refresh token
2. **Access Denied**: Verify user has correct role for the endpoint
3. **Password Requirements**: Ensure password meets all complexity requirements
4. **Migration Issues**: Check MongoDB connection and permissions

### Debug Mode

For development, you can check token contents using JWT.io or the `/api/v1/auth/me` endpoint.

## Next Steps

1. Run the migration script
2. Test login with existing students (using generated passwords)
3. Change default admin password
4. Update client applications to use authentication
5. Implement rate limiting for production
6. Add password reset functionality (if needed)
