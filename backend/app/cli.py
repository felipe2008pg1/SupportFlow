import argparse
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User

MIN_PASSWORD = 12
MAX_PASSWORD = 128


def create_admin(email: str) -> int:
    try:
        email = str(TypeAdapter(EmailStr).validate_python(email)).lower()
    except ValidationError:
        print("Invalid email address.", file=sys.stderr)
        return 2

    password = getpass.getpass("Password: ")
    if getpass.getpass("Confirm password: ") != password:
        print("Passwords do not match.", file=sys.stderr)
        return 2
    if not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
        print(f"Password must be {MIN_PASSWORD}-{MAX_PASSWORD} characters.", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print("A user with this email already exists.", file=sys.stderr)
            return 1
        db.add(User(email=email, hashed_password=hash_password(password), role=Role.ADMIN))
        db.commit()
    print(f"Admin created: {email}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-admin", help="Create an administrator (password via prompt)")
    p.add_argument("email")
    args = parser.parse_args()
    return create_admin(args.email)


if __name__ == "__main__":
    raise SystemExit(main())
