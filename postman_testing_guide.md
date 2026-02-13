# Postman Testing Guide for Authentication System

This guide provides comprehensive instructions for testing the role-based authentication system using Postman, including all endpoints, authentication flows, and troubleshooting tips.

## Testing Overview

The authentication system requires JWT tokens for accessing protected endpoints. This guide covers login flows, token management, and testing both student and admin roles.

## Postman Collection Setup

### Base Configuration
- **Base URL**: `http://localhost:8000/api/v1`
- **Content-Type**: `application/json`
- **Authentication**: Bearer Token (for protected routes)

### Environment Variables
Create these environment variables in Postman:
```
base_url = http://localhost:8000/api/v1
access_token = {{response token from login}}
refresh_token = {{response token from login}}
student_id = std_XXXXX
admin_email = admin@teacherai.com
```

## Authentication Endpoints Testing

### 1. Login (Student)
```http
POST {{base_url}}/auth/login
Content-Type: application/json

{
  "email": "student@example.com",
  "password": "StudentPassword123!"
}
```

**Expected Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "user_id": "std_ABC123",
    "email": "student@example.com",
    "name": "John Doe",
    "role": "student",
    "is_active": true
  }
}
```

### 2. Login (Admin)
```http
POST {{base_url}}/auth/login
Content-Type: application/json

{
  "email": "admin@teacherai.com",
  "password": "Admin123!"
}
```

**Expected Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "user_id": "admin_ABC123",
    "email": "admin@teacherai.com",
    "name": "Default Admin",
    "role": "admin",
    "is_active": true,
    "permissions": ["all"]
  }
}
```

### 3. Get Current User
```http
GET {{base_url}}/auth/me
Authorization: Bearer {{access_token}}
```

### 4. Refresh Token
```http
POST {{base_url}}/auth/refresh
Content-Type: application/json

{
  "refresh_token": "{{refresh_token}}"
}
```

### 5. Change Password
```http
POST {{base_url}}/auth/change-password
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "current_password": "OldPassword123!",
  "new_password": "NewPassword123!"
}
```

### 6. Create Student (Admin Only)
```http
POST {{base_url}}/auth/create-student-with-auth
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "name": "Test Student",
  "email": "teststudent@example.com",
  "class_name": "10A",
  "password": "TestPassword123!"
}
```

### 7. Create Admin (Admin Only)
```http
POST {{base_url}}/auth/create-admin
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "name": "Test Admin",
  "email": "testadmin@example.com",
  "password": "AdminPassword123!",
  "permissions": ["all"]
}
```

## Protected Endpoints Testing

### Student Routes (Student Access)

#### Get Student Profile
```http
GET {{base_url}}/student/{{student_id}}
Authorization: Bearer {{access_token}}
```

#### Update Student Profile
```http
PUT {{base_url}}/student/{{student_id}}
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "name": "Updated Name",
  "email": "updated@example.com"
}
```

#### Agent Query
```http
POST {{base_url}}/student/agent-query
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "student_id": "{{student_id}}",
  "subject": "mathematics",
  "class_name": "10A",
  "query": "What is calculus?"
}
```

### Admin Routes (Admin Access)

#### List All Students
```http
GET {{base_url}}/student/student-list
Authorization: Bearer {{access_token}}
```

#### Create Student (Legacy)
```http
POST {{base_url}}/student/create-student
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "name": "New Student",
  "email": "newstudent@example.com",
  "class_name": "11B"
}
```

#### Get Base Prompt
```http
GET {{base_url}}/admin/current-base-prompt
Authorization: Bearer {{access_token}}
```

#### Update Base Prompt
```http
POST {{base_url}}/admin/update-base-prompt
Authorization: Bearer {{access_token}}
Content-Type: application/json

{
  "base_prompt": "Updated base prompt content"
}
```

## Postman Test Collection Structure

### Folder Structure
```
Student Learning API/
├── Authentication/
│   ├── Login (Student)
│   ├── Login (Admin)
│   ├── Get Current User
│   ├── Refresh Token
│   ├── Change Password
│   ├── Create Student (Admin)
│   └── Create Admin (Admin)
├── Student Routes/
│   ├── Get Student Profile
│   ├── Update Student Profile
│   ├── Agent Query
│   ├── Get Student List
│   └── Submit Feedback
└── Admin Routes/
    ├── List All Students
    ├── Get Base Prompt
    ├── Update Base Prompt
    └── List Admins
```

## Authentication Flow Testing

### Complete Student Workflow
1. **Login** as student → Get access token
2. **Get Current User** → Verify student info
3. **Get Student Profile** → Access own data
4. **Update Profile** → Modify own data
5. **Agent Query** → Use learning features
6. **Change Password** → Update credentials

### Complete Admin Workflow
1. **Login** as admin → Get admin access token
2. **Get Current User** → Verify admin info
3. **List All Students** → View all users
4. **Create Student** → Add new user
5. **Update Base Prompt** → Modify system settings
6. **Create Admin** → Add another admin

## Error Testing Scenarios

### Authentication Errors
1. **Invalid Credentials**
   ```http
   POST {{base_url}}/auth/login
   {
     "email": "wrong@example.com",
     "password": "wrongpassword"
   }
   ```
   **Expected**: 401 Unauthorized

2. **Missing Token**
   ```http
   GET {{base_url}}/student/{{student_id}}
   ```
   **Expected**: 401 Unauthorized

3. **Invalid Token**
   ```http
   GET {{base_url}}/student/{{student_id}}
   Authorization: Bearer invalid_token
   ```
   **Expected**: 401 Unauthorized

4. **Expired Token**
   ```http
   GET {{base_url}}/student/{{student_id}}
   Authorization: Bearer expired_token
   ```
   **Expected**: 401 Unauthorized

### Authorization Errors
1. **Student Accessing Other Student Data**
   ```http
   GET {{base_url}}/student/other_student_id
   Authorization: Bearer {{student_access_token}}
   ```
   **Expected**: 403 Forbidden

2. **Student Accessing Admin Routes**
   ```http
   GET {{base_url}}/admin/current-base-prompt
   Authorization: Bearer {{student_access_token}}
   ```
   **Expected**: 403 Forbidden

3. **Invalid Password Change**
   ```http
   POST {{base_url}}/auth/change-password
   Authorization: Bearer {{access_token}}
   {
     "current_password": "wrongpassword",
     "new_password": "weak"
   }
   ```
   **Expected**: 400 Bad Request

## Postman Scripts

### Login Test Script
```javascript
// Tests tab for login endpoint
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response has access token", function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData.access_token).to.be.a('string');
    pm.expect(jsonData.refresh_token).to.be.a('string');
});

// Set environment variables
if (pm.response.code === 200) {
    const jsonData = pm.response.json();
    pm.environment.set("access_token", jsonData.access_token);
    pm.environment.set("refresh_token", jsonData.refresh_token);
    pm.environment.set("user_id", jsonData.user.user_id);
    pm.environment.set("user_role", jsonData.user.role);
}
```

### Protected Route Test Script
```javascript
// Tests tab for protected endpoints
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Authorization header is present", function () {
    pm.expect(pm.request.headers.get('Authorization')).to.include('Bearer');
});
```

## Troubleshooting

### Common Issues
1. **CORS Errors**: Ensure server is running with CORS enabled
2. **Token Not Found**: Check environment variables are set correctly
3. **401 Unauthorized**: Verify token is not expired and is correctly formatted
4. **403 Forbidden**: Check user role permissions
5. **400 Bad Request**: Validate request body format and required fields

### Debug Tips
1. Use Postman Console to view request/response details
2. Check token expiration time (30 minutes default)
3. Verify MongoDB connection and data
4. Test with fresh tokens if authentication fails
5. Check server logs for detailed error messages

### Performance Testing
1. Test token refresh flow before expiration
2. Verify concurrent request handling
3. Test rate limiting (if implemented)
4. Monitor response times for different endpoints

## Security Testing

### Token Security
1. Test token expiration behavior
2. Verify refresh token invalidation
3. Test token reuse after logout
4. Check token tampering detection

### Input Validation
1. Test SQL injection attempts
2. Verify XSS protection
3. Test malformed JSON inputs
4. Check file upload restrictions (if applicable)

This comprehensive guide covers all aspects of testing the authentication system in Postman, ensuring thorough validation of the role-based access control implementation.
