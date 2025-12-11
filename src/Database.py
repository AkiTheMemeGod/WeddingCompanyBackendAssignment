from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MASTER_DB = os.getenv("MASTER_DB", "MasterDB")

client = MongoClient(MONGO_URI)
master_db = client[MASTER_DB]
orgs_coll = master_db["organizations"]
admins_coll = master_db["admins"]