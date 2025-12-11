import os
from uuid import uuid4
from datetime import datetime, timedelta
import json
from flask import Flask, request, jsonify
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv

from Helpers import *


load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
JWT_EXP_SECONDS = int(os.getenv("JWT_EXP_SECONDS"))

app = Flask(__name__)
ensure_indexes()


@app.route("/org/create", methods=["POST"])
def create_organization():

    body = request.get_json() or {}
    org_name = body.get("organization_name")
    email = body.get("email")
    password = body.get("password")

    if not org_name or not email or not password:
        return jsonify(
            {"error": "organization_name, email and password are required"}
            ), 400

    collection_name = org_name

    try:
        admin_id = str(uuid4())
        org_id = str(uuid4())
        password_hash = hash_password(password)

        admin_doc = {
            "_id": admin_id,
            "email": email.lower(),
            "password_hash": password_hash,
            "org_id": org_id,
            "role": "owner",
            "created_at": datetime.utcnow()
        }

        org_doc = {
            "_id": org_id,
            "organization_name": org_name.lower(),
            "collection_name": collection_name,
            "admin_user_id": admin_id,
            "created_at": datetime.utcnow()
        }

        orgs_coll.insert_one(org_doc)
        admins_coll.insert_one(admin_doc)

        if collection_name not in master_db.list_collection_names():
            master_db.create_collection(collection_name)
            master_db[collection_name].insert_one({
                "_meta": True,
                "created_at": datetime.utcnow(),
                "org_id": org_id
            })

        return jsonify({
            "status": "ok",
            "org_id": org_id,
            "organization_name": org_name,
            "collection_name": collection_name
        }), 201

    except DuplicateKeyError as e:
        existing_org = orgs_coll.find_one({"organization_name": org_name.lower()})
        if existing_org:
            admins_coll.delete_many({"org_id": existing_org["_id"]})
            orgs_coll.delete_one({"_id": existing_org["_id"]})
        return jsonify({"error": "Organization or email already exists"}), 409
    except Exception as ex:
        return jsonify({"error": "internal_error", "detail": str(ex)}), 500

@app.route("/org/get", methods=["GET"])
def get_org():
    org_name = request.args.get("organization_name") or (request.get_json() or {}).get("organization_name")
    if not org_name:
        return jsonify({"error": "organization_name required"}), 400
    org_doc = orgs_coll.find_one({"organization_name": org_name.lower()}, {"_id": 1, "organization_name": 1, "collection_name": 1, "created_at": 1, "admin_user_id":1})
    if not org_doc:
        return jsonify({"error": "Organization not found"}), 404
    # do not return sensitive data
    org_doc["_id"] = str(org_doc["_id"])
    return jsonify({"organization": org_doc}), 200

@app.route("/admin/login", methods=["POST"])
def admin_login():

    body = request.get_json() or {}
    email = body.get("email")
    password = body.get("password")
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400

    admin = admins_coll.find_one({"email": email.lower()})
    if not admin:
        return jsonify({"error": "Invalid credentials"}), 401

    if not verify_password(password, admin["password_hash"]):
        return jsonify({"error": "Invalid credentials"}), 401

    org_id = admin["org_id"]
    org = orgs_coll.find_one({"_id": org_id})
    org_name = org["organization_name"] if org else None

    token = create_jwt(admin_id=admin["_id"], org_id=org_id, email=admin["email"], role=admin.get("role", "owner"))

    return jsonify({
        "access_token": token,
        "token_type": "bearer",
        "expires_in": JWT_EXP_SECONDS,
        "org_id": org_id,
        "org_name": org_name
    }), 200

@app.route("/org/update", methods=["PUT"])
def update_org():

    payload, err = decode_jwt_from_header()
    if err:
        return jsonify({"error": err[0]}), err[1]

    admin_id = payload.get("sub")
    org_id_in_token = payload.get("org_id")

    body = request.get_json() or {}
    current_name = body.get("organization_name")
    new_name = body.get("new_organization_name")
    new_email = body.get("email")
    new_password = body.get("password")

    if not current_name:
        return jsonify({"error": "organization_name required"}), 400

    admin = admins_coll.find_one({"_id": admin_id})
    if not admin or admin.get("org_id") != org_id_in_token:
        return jsonify({"error": "unauthorized"}), 401

    org_doc = orgs_coll.find_one({"organization_name": current_name.lower()})
    if not org_doc:
        return jsonify({"error": "Organization not found"}), 404

    if org_doc["_id"] != org_id_in_token:
        return jsonify({"error": "token org mismatch"}), 403

    updates = {}
    if new_email:
        updates["email"] = new_email.lower()
    if new_password:
        updates["password_hash"] = hash_password(new_password)

    try:
        if updates:
            admins_coll.update_one({"_id": admin_id}, {"$set": updates})

        if new_name and new_name.lower() != current_name.lower():
            if orgs_coll.find_one({"organization_name": new_name.lower()}):
                return jsonify({"error": "New organization name already exists"}), 409

            old_collection = org_doc["collection_name"]
            try:
                new_collection = new_name
            except ValueError as e:
                return jsonify({"error": "Invalid new organization name"}), 400

            old_coll_ref = master_db[old_collection]
            new_coll_ref = master_db[new_collection]
            if new_collection not in master_db.list_collection_names():
                master_db.create_collection(new_collection)

            batch = []
            BATCH_SIZE = 500
            cursor = old_coll_ref.find({})
            docs_copied = 0
            for doc in cursor:
                batch.append(doc)
                if len(batch) >= BATCH_SIZE:
                    new_coll_ref.insert_many(batch)
                    docs_copied += len(batch)
                    batch = []
            if batch:
                if len(batch):
                    new_coll_ref.insert_many(batch)
                    docs_copied += len(batch)

            orgs_coll.update_one({"_id": org_doc["_id"]}, {"$set": {"organization_name": new_name.lower(), "collection_name": new_collection}})

            master_db.drop_collection(old_collection)

            return jsonify({"status": "ok", "note": f"organization renamed and data copied ({docs_copied} documents)"}), 200

        return jsonify({"status": "ok", "note": "updated admin/profile"}), 200

    except DuplicateKeyError:
        return jsonify({"error": "email already exists"}), 409
    except Exception as ex:
        return jsonify({"error": "internal_error", "detail": str(ex)}), 500

@app.route("/org/delete", methods=["DELETE"])
def delete_org():
    payload, err = decode_jwt_from_header()
    if err:
        return jsonify({"error": err[0]}), err[1]

    admin_id = payload.get("sub")
    token_org_id = payload.get("org_id")

    body = request.get_json() or {}
    org_name = body.get("organization_name")
    if not org_name:
        return jsonify({"error": "organization_name required"}), 400

    org_doc = orgs_coll.find_one({"organization_name": org_name.lower()})
    if not org_doc:
        return jsonify({"error": "Organization not found"}), 404

    if org_doc["_id"] != token_org_id:
        return jsonify({"error": "Token org mismatch - unauthorized"}), 403

    admin = admins_coll.find_one({"_id": admin_id})
    if not admin or admin.get("org_id") != token_org_id:
        return jsonify({"error": "unauthorized"}), 401

    try:
        collection_name = org_doc["collection_name"]
        master_db.drop_collection(collection_name)
        admins_coll.delete_many({"org_id": org_doc["_id"]})
        orgs_coll.delete_one({"_id": org_doc["_id"]})

        return jsonify({"status": "ok", "note": "organization deleted"}), 200
    except Exception as ex:
        return jsonify({"error": "internal_error", "detail": str(ex)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()}), 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
