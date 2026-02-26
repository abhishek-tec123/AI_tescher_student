# Postman Test Plan for Shared Knowledge Documents

Create simple and minimal Postman tests to verify the Shared Knowledge Documents feature works correctly.

## Test Plan Overview

The plan is to create a comprehensive but minimal set of Postman collection tests that cover all major endpoints of the Shared Knowledge Documents feature, allowing you to verify the implementation works correctly.

## Test Categories

### 1. Authentication Setup
- Test admin authentication to get required tokens
- Verify admin role access

### 2. Shared Document Management
- Upload a simple test document
- List all shared documents
- Delete test document

### 3. Agent Integration
- Create a simple test agent
- Enable shared documents for the agent
- Get agent's enabled shared documents
- Disable shared documents for the agent

### 4. Search Verification
- Test agent query with shared knowledge enabled
- Verify search results include shared content

## Test Data Preparation

### Simple Test Document
- Create a small PDF or text file with educational content
- Content: "Sample educational guidelines for testing purposes"
- File size: < 100KB for quick upload

### Test Agent Data
- Simple agent metadata for testing
- Class: "Test"
- Subject: "Science"
- Agent name: "Test Agent"

## Postman Collection Structure

### Authentication Requests
1. **POST /auth/login** - Get admin token
2. **GET /admin/current-base-prompt** - Verify admin access

### Shared Document Requests
3. **POST /admin/shared-knowledge/upload** - Upload test document
4. **GET /admin/shared-knowledge** - List documents
5. **DELETE /admin/shared-knowledge/{document_id}** - Clean up

### Agent Integration Requests
6. **POST /vectors/create_vectors** - Create test agent
7. **POST /admin/shared-knowledge/{document_id}/enable** - Enable shared doc
8. **GET /admin/shared-knowledge/agent/{agent_id}** - Verify enabled docs
9. **POST /admin/shared-knowledge/{document_id}/disable** - Disable shared doc

## Expected Responses

### Success Indicators
- All endpoints return 200/201 status codes
- Document upload returns document_id and chunk count
- Agent operations return success messages
- Search includes source attribution

### Error Handling Tests
- Invalid file upload returns 400
- Missing authentication returns 401
- Invalid document_id returns 404
- Non-admin access returns 403

## Environment Variables for Postman

```json
{
  "baseUrl": "http://localhost:8000",
  "adminToken": "{{adminToken}}",
  "testDocumentId": "{{testDocumentId}}",
  "testAgentId": "{{testAgentId}}"
}
```

## Test Execution Order

1. **Setup Phase** - Authentication and basic verification
2. **Document Phase** - Upload and manage shared documents
3. **Agent Phase** - Create agent and integrate shared documents
4. **Cleanup Phase** - Remove test data

## Success Criteria

- All API endpoints respond correctly
- Shared documents are properly indexed
- Agent can use shared knowledge in search
- Source attribution works in responses
- No error logs in server
