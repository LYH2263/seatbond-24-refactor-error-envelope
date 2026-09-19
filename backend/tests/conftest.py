import os
import tempfile

# Hermetic DB for the API tests: point the app at a throwaway sqlite file and
# skip seeding. Must run before any app.* import (engine is built at import).
_TMPDIR = tempfile.mkdtemp(prefix="seatbond-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMPDIR}/seatbond_test.db"
os.environ["SEED_ON_EMPTY"] = "false"
