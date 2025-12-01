#!/usr/bin/env python3
"""User management for the photo rating application.

Usage:
    python manage_users.py add <username> [--display-name NAME]
    python manage_users.py update-password <username>
    python manage_users.py list
    python manage_users.py deactivate <username>
    python manage_users.py activate <username>
    python manage_users.py delete <username>
"""

import argparse
import getpass
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from home_media_ai.database import get_session
from home_media_ai.media import User


def add_user(username: str, display_name: str = None) -> bool:
    """Add a new user."""
    with get_session() as session:
        # Check if user exists
        existing = session.query(User).filter(User.username == username).first()
        if existing:
            print(f"Error: User '{username}' already exists")
            return False

        # Get password
        while True:
            password = getpass.getpass("Enter password: ")
            valid, msg = User.validate_password_strength(password)
            if not valid:
                print(f"Error: {msg}")
                continue

            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Error: Passwords do not match")
                continue
            break

        # Create user
        user = User(
            username=username,
            display_name=display_name or username
        )
        user.set_password(password)

        session.add(user)
        session.commit()
        print(f"User '{username}' created successfully")
        return True


def update_password(username: str) -> bool:
    """Update a user's password."""
    with get_session() as session:
        user = session.query(User).filter(User.username == username).first()
        if not user:
            print(f"Error: User '{username}' not found")
            return False

        # Get new password
        while True:
            password = getpass.getpass("Enter new password: ")
            valid, msg = User.validate_password_strength(password)
            if not valid:
                print(f"Error: {msg}")
                continue

            confirm = getpass.getpass("Confirm new password: ")
            if password != confirm:
                print("Error: Passwords do not match")
                continue
            break

        user.set_password(password)
        session.commit()
        print(f"Password updated for user '{username}'")
        return True


def list_users() -> None:
    """List all users."""
    with get_session() as session:
        users = session.query(User).order_by(User.username).all()

        if not users:
            print("No users found")
            return

        print(f"\n{'Username':<20} {'Display Name':<25} {'Active':<8} {'Last Login':<20}")
        print("-" * 75)

        for user in users:
            last_login = user.last_login.strftime("%Y-%m-%d %H:%M") if user.last_login else "Never"
            active = "Yes" if user.is_active else "No"
            print(f"{user.username:<20} {(user.display_name or '-'):<25} {active:<8} {last_login:<20}")

        print()


def set_user_active(username: str, active: bool) -> bool:
    """Activate or deactivate a user."""
    with get_session() as session:
        user = session.query(User).filter(User.username == username).first()
        if not user:
            print(f"Error: User '{username}' not found")
            return False

        user.is_active = active
        session.commit()

        status = "activated" if active else "deactivated"
        print(f"User '{username}' {status}")
        return True


def delete_user(username: str) -> bool:
    """Delete a user."""
    with get_session() as session:
        user = session.query(User).filter(User.username == username).first()
        if not user:
            print(f"Error: User '{username}' not found")
            return False

        confirm = input(f"Are you sure you want to delete user '{username}'? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Cancelled")
            return False

        session.delete(user)
        session.commit()
        print(f"User '{username}' deleted")
        return True


def main():
    parser = argparse.ArgumentParser(description='User management for photo rating')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Add user
    add_parser = subparsers.add_parser('add', help='Add a new user')
    add_parser.add_argument('username', help='Username for the new user')
    add_parser.add_argument('--display-name', help='Display name')

    # Update password
    passwd_parser = subparsers.add_parser('update-password', help='Update user password')
    passwd_parser.add_argument('username', help='Username')

    # List users
    subparsers.add_parser('list', help='List all users')

    # Deactivate user
    deact_parser = subparsers.add_parser('deactivate', help='Deactivate a user')
    deact_parser.add_argument('username', help='Username')

    # Activate user
    act_parser = subparsers.add_parser('activate', help='Activate a user')
    act_parser.add_argument('username', help='Username')

    # Delete user
    del_parser = subparsers.add_parser('delete', help='Delete a user')
    del_parser.add_argument('username', help='Username')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == 'add':
        success = add_user(args.username, args.display_name)
    elif args.command == 'update-password':
        success = update_password(args.username)
    elif args.command == 'list':
        list_users()
        success = True
    elif args.command == 'deactivate':
        success = set_user_active(args.username, False)
    elif args.command == 'activate':
        success = set_user_active(args.username, True)
    elif args.command == 'delete':
        success = delete_user(args.username)
    else:
        parser.print_help()
        success = False

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
