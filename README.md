# Wedding Company Assignment
## Organization Management Service (Flask + MongoDB)

A modular Flask backend implementing a multi-tenant Organization Management Service.
Each organization has a dedicated MongoDB collection (`org_<sanitized_name>`), and a master database stores global metadata and admin users. Admin authentication uses JWTs and passwords are hashed with bcrypt (Passlib).

This repository includes a ready-to-run structure, cURL examples, a Postman collection, and production hardening notes.

## Table of Contents
- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Run the App](#run-the-app)
- [API Endpoints & Examples](#api-endpoints--examples)
- [Postman Collection](#postman-collection)
- [Testing](#testing)
- [Production Notes](#production-notes)
- [Troubleshooting](#troubleshooting)

## Features
- `POST /org/create` — create organization + admin + dynamic collection
- `GET /org/get` — fetch organization metadata
- `PUT /org/update` — update admin or rename org (copy-then-drop migration)
- `DELETE /org/delete` — delete org and its collection
- `POST /admin/login` — admin login issuing JWT
- Password hashing with bcrypt (Passlib)
- JWT tokens for authenticated endpoints
- Unique indexes on `organization_name` and `email`

## Project Structure
```
WeddingCompanyBackendAssignment/
├─ src/
│  ├─ app.py
│  ├─ Database.py
│  ├─ Helpers.py
├─ README.md
├─ .env
```

## Prerequisites
- Python 3.10+
- MongoDB running locally or accessible via network
- `curl` (optional: `jq` for parsing JSON)
- (Optional) Postman

## Installation
Clone the repo and enter the directory:

```bash
git clone https://github.com/AkiTheMemeGod/WeddingCompanyBackendAssignment
cd WeddingCompanyBackendAssignment
```

Create and activate a virtual environment:

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
./.venv/Scripts/Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables
create `.env` file and update values:

```env
MONGO_URI=mongodb://localhost:27017
MASTER_DB=master_db
JWT_SECRET=replace_with_a_strong_secret
JWT_ALGORITHM=HS256
JWT_EXP_SECONDS=3600
FLASK_ENV=development
```

- `MONGO_URI` — MongoDB connection string
- `MASTER_DB` — master database name (default: `master_db`)
- `JWT_SECRET` — strong secret to sign JWTs
- `JWT_ALGORITHM` — signing algorithm (e.g., `HS256`)
- `JWT_EXP_SECONDS` — token expiry in seconds

## Run the App
Ensure MongoDB is running, then start the app:

```bash
# activate venv if not already
source .venv/bin/activate

# run the Flask app
python3 src/app.py
```

Server starts at `http://0.0.0.0:8000` by default.

## API Endpoints & Examples

### 1) Create Organization
Endpoint: `POST /org/create`

Body (JSON):

```json
{
  "organization_name": "SRMRAMAPURAM",
  "email": "akash@srm.com",
  "password": "verysafepasswordhahaha"
}
```

cURL:

```bash
curl -X POST http://localhost:8000/org/create \
  -H "Content-Type: application/json" \
  -d '{"organization_name":"SRMRAMAPURAM","email":"akash@srm.com","password":"verysafepasswordhahah"}'
```

Response: `201 Created` with `org_id`, `collection_name`, etc.

### 2) Admin Login
Endpoint: `POST /admin/login`

Body:

```json
{
  "email": "akash@srm.com",
  "password": "verysafepasswordhahaha"
}
```

cURL:

```bash
curl -X POST http://localhost:8000/admin/login \
  -H "Content-Type: application/json" \
  -d '{"email":"akash@srm.com","password":"verysafepasswordhahaha"}'
```

Response contains `access_token` (JWT). Save it for authenticated requests.

Example: set shell variable (requires `jq`):

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/admin/login \
  -H "Content-Type: application/json" \
  -d '{"email":"akash@srm.com","password":"verysafepasswordhahaha"}' | jq -r .access_token)
```

### 3) Get Organization Metadata
Endpoint: `GET /org/get?organization_name=acme` (or JSON body equivalent)

cURL:

```bash
curl "http://localhost:8000/org/get?organization_name=acme"
```

### 4) Update Organization (admin password or rename)
Endpoint: `PUT /org/update` — requires `Authorization: Bearer <token>`

Update admin password:

```bash
curl -X PUT http://localhost:8000/org/update \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"organization_name":"srm","password":"veryverysafepasswordhahaha"}'
```

Rename org (copy-then-drop migration):

```bash
curl -X PUT http://localhost:8000/org/update \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"organization_name":"srm","new_organization_name":"srm_Corp"}'
```

Notes: rename performs a document copy from old collection to new collection, then drops the old collection. For large datasets, prefer `renameCollection` or an online migration approach.

### 5) Delete Organization
Endpoint: `DELETE /org/delete` — requires `Authorization: Bearer <token>`

cURL:

```bash
curl -X DELETE http://localhost:8000/org/delete \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"organization_name":"srm_corp"}'
```

This drops the organization collection and removes master DB docs for that org and its admins.

### Health Check
Endpoint: `GET /health`

```bash
curl http://localhost:8000/health
```

## Postman Collection
Import `postman_collection.json` (or the provided JSON snippet) into Postman.
After login, set an environment variable `token` and use it in Authorization headers for protected endpoints.

## Testing
Basic manual testing flow:

1. Create org
2. Login as admin (get token)
3. Get org metadata
4. Update admin password or rename org
5. Delete org

For automated tests: write `pytest` tests connecting to a test MongoDB database (e.g., set `MASTER_DB=test_master_db`). Tear down created collections between tests.

## Production Notes
- **Secrets**: store `JWT_SECRET` and DB credentials in a secret manager (Hashicorp Vault, AWS Secrets Manager); never store production secrets in `.env`.
- **HTTPS**: serve behind TLS (Nginx/Traefik) or use a cloud load balancer.
- **MongoDB**: run as a replica set to enable transactions and durability.
- **Transactions**: consider multi-document transactions for critical operations (requires replica set).
- **Large migrations**: for renames or big dataset migration, prefer `db.adminCommand({ renameCollection: ... })` or online migration with write-forwarding + migration lock.
- **Rate limiting**: protect `/admin/login` with rate limiting and possibly captcha.
- **Validation**: add request validation (Pydantic/Marshmallow).
- **Logging & monitoring**: integrate structured logs and error reporting (Sentry, Prometheus).
- **Backup & retention**: take regular backups and consider tombstone deletions for recovery windows.
- **Roles**: implement RBAC (admin/owner/editor) if delegated roles are needed.

## Troubleshooting
- **DuplicateKeyError on create**: ensure organization/email not already present; check unique indexes.
- **Token expired**: generate a new token via `/admin/login`. Consider refresh tokens in production.
- **Collection creation permission errors**: check MongoDB user privileges for the connection string used.
- **App doesn't start**: verify Python version, venv activation, and dependencies installed (`pip install -r requirements.txt`).