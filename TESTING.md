# 🧪 Testing Guide

Step-by-step test cases to verify the AI code review integration is working correctly.  
Run these in order — SIMPLE first, then COMPLEX.

---

## Before You Start

Make sure:
- [ ] `PR-review-agentic-system` is public on GitHub
- [ ] `GROQ_API_KEY` secret is added to the repo you are testing
- [ ] `ai_code_review.yml` workflow is in `.github/workflows/` of the test repo
- [ ] No hardcoded API keys in `crew.py`

---

## Test 1 — SIMPLE path (Quick LLM Review → Approve)

**What it tests:** Small, low-risk changes route to the quick LLM path and get approved.

**Steps:**

1. Go to your test repo on GitHub
2. Click `README.md` → ✏️ edit icon
3. Add this line anywhere:
```
## About
This project handles user authentication for the web app.
```
4. Scroll down → select **"Create a new branch"** → name it `test/simple-review`
5. Click **Propose changes → Create pull request**

**Expected result:**
```
Review type: Quick LLM Review
Decision:    APPROVE
Time:        ~15 seconds
```

---

## Test 2 — COMPLEX path (Multi-Agent Crew → Request Changes)

**What it tests:** Security-sensitive code routes to the full 3-agent crew and gets rejected due to real vulnerabilities.

**Steps:**

1. Go to your test repo → **Add file → Create new file**
2. Name the file `auth/login.py`
3. Paste this code:

```python
import sqlite3

def login(username, password):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # SQL injection vulnerability — user input directly in query
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    cursor.execute(query)
    result = cursor.fetchone()

    if result:
        return {"status": "success", "user": result}
    return {"status": "failed"}

def reset_password(email):
    # No rate limiting, hardcoded token
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET reset_token='abc123' WHERE email='{email}'")
    conn.commit()
    send_email(email, "Your reset link: http://app.com/reset?token=abc123")
```

4. Select **"Create a new branch"** → name it `test/complex-request-changes`
5. Click **Propose changes → Create pull request**

**Expected result:**
```
Review type: Multi-Agent Crew Review
Decision:    REQUEST CHANGES
Time:        ~60-90 seconds
```

**Issues the crew should flag:**
- SQL injection via f-string query
- Hardcoded reset token `abc123`
- No rate limiting on password reset
- No error handling

---

## Test 3 — COMPLEX path (Multi-Agent Crew → Approve)

**What it tests:** Production-quality code that is complex enough to trigger the crew but clean enough to be approved.

**Steps:**

1. Go to your test repo → **Add file → Create new file**
2. Name the file `api/users.py`
3. Paste this code:

```python
import bcrypt
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def get_user(user_id: int, db) -> dict:
    """Fetch user by ID using parameterised query."""
    try:
        result = db.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        )
        user = result.fetchone()
        if not user:
            raise ValueError(f"User {user_id} not found")
        return dict(user)
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        raise

def email_exists(email: str, db) -> bool:
    """Check if an email is already registered."""
    result = db.execute("SELECT 1 FROM users WHERE email = ?", (email,))
    return result.fetchone() is not None

def validate_email(email: str) -> None:
    """Validate email format."""
    if not EMAIL_REGEX.match(email):
        raise ValueError(f"Invalid email format: {email}")

def create_user(name: str, email: str, password: str, db) -> dict:
    """Create a new user with securely hashed password."""
    validate_email(email)
    if email_exists(email, db):
        raise ValueError("Email already in use")
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")
    try:
        db.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, datetime.utcnow())
        )
        db.commit()
        logger.info(f"User created: {email}")
        return {"status": "created", "name": name, "email": email}
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        raise

def update_email(user_id: int, new_email: str, db) -> dict:
    """Update user email with validation and duplicate check."""
    validate_email(new_email)
    if email_exists(new_email, db):
        raise ValueError("Email already in use")
    try:
        get_user(user_id, db)
        db.execute(
            "UPDATE users SET email = ? WHERE id = ?", (new_email, user_id)
        )
        db.commit()
        logger.info(f"Email updated for user {user_id}")
        return {"status": "updated", "user_id": user_id, "email": new_email}
    except ValueError:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating email for user {user_id}: {e}")
        raise
```

4. Select **"Create a new branch"** → name it `test/complex-approve`
5. Click **Propose changes → Create pull request**

**Expected result:**
```
Review type: Multi-Agent Crew Review
Decision:    APPROVE
Time:        ~60-90 seconds
```

**Why the crew approves:**
- Parameterised queries — no SQL injection risk ✅
- bcrypt with 12 rounds — strong password hashing ✅
- Duplicate email check before insert/update ✅
- try/except + rollback on all DB operations ✅
- Proper logging throughout ✅
- Input validation with regex ✅

---

## Summary

| Test | Branch | Review Type | Expected Decision |
|---|---|---|---|
| 1 — README edit | `test/simple-review` | Quick LLM Review | ✅ APPROVE |
| 2 — Vulnerable login | `test/complex-request-changes` | Multi-Agent Crew | 🔴 REQUEST CHANGES |
| 3 — Clean user API | `test/complex-approve` | Multi-Agent Crew | ✅ APPROVE |

---

## Troubleshooting

If a test doesn't behave as expected, go to the **Actions tab** of your test repo → click the workflow run → expand each step to see the logs.

| Symptom | Likely Cause |
|---|---|
| Workflow doesn't trigger | Check workflow file is in `.github/workflows/` |
| `GROQ_API_KEY not set` | Add secret to the test repo settings |
| Wrong decision posted | Check `parse_decision()` fix in `scripts/github_review_runner.py` |
| `repository not found` | Verify `YOUR_USERNAME` is updated in the reusable workflow |
| SIMPLE code routed to COMPLEX | LLM classifier is being cautious — expected occasionally |
