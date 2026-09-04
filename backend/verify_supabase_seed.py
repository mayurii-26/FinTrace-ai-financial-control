"""Run seed against the configured database (Supabase) and verify counts."""
import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.data.seeder import seed_database
from sqlalchemy import text

s = get_settings()
print(f"Database: {'SQLite' if s.is_sqlite else 'PostgreSQL'}")
print(f"SYNTHETIC_RECORD_COUNT from settings: {s.synthetic_record_count}")
print(f"SYNTHETIC_SEED from settings:         {s.synthetic_seed}")
print()

init_db()
db = SessionLocal()

try:
    # Seed with force=True, passing NO count/seed so they come from settings
    result = seed_database(db, count=None, seed=None, force=True)
    print(f"\nSeed result: {result} transactions inserted")

    # Verify all table counts
    tables = [
        "transactions", "orders", "payments", "refunds",
        "settlements", "bank_entries", "exceptions",
        "investigations", "audit_logs",
    ]
    print("\nTable counts after seed:")
    all_ok = True
    for t in tables:
        c = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        ok = ""
        if t == "transactions":
            ok = " PASS" if c == s.synthetic_record_count else f" FAIL (expected {s.synthetic_record_count})"
            if c != s.synthetic_record_count:
                all_ok = False
        if t == "investigations":
            ok = " PASS (should be 0)" if c == 0 else f" WARN ({c} unexpected)"
        print(f"  {t:<20} {c:>6}{ok}")

    print()
    if all_ok:
        print("ALL CHECKS PASSED - 600 transactions in Supabase.")
    else:
        print("SOME CHECKS FAILED - see above.")

finally:
    db.close()
