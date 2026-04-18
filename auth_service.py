"""
Authentication and registration helpers for local app usage.
"""
import secrets
from typing import Dict, Optional, Tuple
import bcrypt


class AuthService:
    def __init__(self, db):
        self.db = db

    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
        except Exception:
            return False

    def register_user(
        self,
        username: str,
        password: str,
        role: str,
        full_name: str,
        trusted_name: str,
        trusted_contact: str,
        trusted_relation: str,
    ) -> Tuple[bool, str]:
        existing = self.db.get_user_by_username(username)
        if existing:
            return False, "Username already exists"
        if len(password or "") < 6:
            return False, "Password must have at least 6 characters"

        user_id = self.db.create_user(
            username=username.strip(),
            password_hash=self.hash_password(password),
            role=role,
            full_name=full_name.strip() or username.strip(),
        )
        self.db.upsert_trusted_contact(
            user_id=user_id,
            name=trusted_name.strip(),
            relation=trusted_relation.strip() or "trusted_person",
            contact=trusted_contact.strip(),
        )
        return True, "Registration completed"

    def authenticate(self, username: str, password: str) -> Tuple[bool, Optional[Dict], str]:
        user = self.db.get_user_by_username(username)
        if not user:
            return False, None, "User not found"
        if not self.verify_password(password, user["password_hash"]):
            return False, None, "Invalid password"
        return True, user, "Login successful"

    def issue_clearance_code(self, user_id: str) -> str:
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        self.db.store_one_time_code(user_id=user_id, code=code, purpose="clear_memory")
        return code

    def verify_clearance_code(self, user_id: str, code: str) -> bool:
        return self.db.verify_one_time_code(user_id=user_id, code=code, purpose="clear_memory")

