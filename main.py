"""
Tutoring Appointment Board - BTE 400
One Flask codebase that runs on Cloud Run (PaaS) and a Compute Engine VM (IaaS).

Environment variables (configuration differs by environment, code does not):
  APP_ENV        Label shown in the footer, e.g. "Cloud Run" or "Linux VM"
  USE_FIRESTORE  "true" to use Firestore, otherwise in-memory sample data (Sprint 1)
  SECRET_KEY     Random string used to sign flash messages
"""
import logging
import os

from flask import Flask, abort, flash, redirect, render_template, request, url_for

from sample_data import SAMPLE_SESSIONS

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tutorboard")

APP_ENV = os.environ.get("APP_ENV", "Local")
USE_FIRESTORE = os.environ.get("USE_FIRESTORE", "false").lower() == "true"
COLLECTION = "appointments"

STATUSES = ["Open", "Requested", "Booked", "Completed", "Cancelled"]
FIELDS = ["subject", "course_code", "tutor_name", "student_name",
          "date", "time", "location", "status", "notes"]
REQUIRED = ["subject", "tutor_name", "date", "time", "location"]


# ---------------------------------------------------------------- storage
class MemoryStore:
    """Sprint 1 only. Data resets when the app restarts."""

    def __init__(self):
        self.items = {str(i + 1): dict(s) for i, s in enumerate(SAMPLE_SESSIONS)}
        self.next_id = len(self.items) + 1

    def list(self):
        return [{**v, "id": k} for k, v in self.items.items()]

    def get(self, item_id):
        item = self.items.get(item_id)
        return {**item, "id": item_id} if item else None

    def add(self, data):
        item_id = str(self.next_id)
        self.next_id += 1
        self.items[item_id] = data
        return item_id

    def update(self, item_id, data):
        self.items[item_id].update(data)


class FirestoreStore:
    """Sprint 2+. Credentials come from the attached service account, never a key file."""

    def __init__(self):
        from google.cloud import firestore
        self.firestore = firestore
        self.col = firestore.Client().collection(COLLECTION)

    def list(self):
        return [{**d.to_dict(), "id": d.id} for d in self.col.stream()]

    def get(self, item_id):
        doc = self.col.document(item_id).get()
        return {**doc.to_dict(), "id": doc.id} if doc.exists else None

    def add(self, data):
        data["created_at"] = self.firestore.SERVER_TIMESTAMP
        _, ref = self.col.add(data)
        return ref.id

    def update(self, item_id, data):
        data["updated_at"] = self.firestore.SERVER_TIMESTAMP
        self.col.document(item_id).update(data)


store = FirestoreStore() if USE_FIRESTORE else MemoryStore()
log.info("Starting on %s using %s", APP_ENV, type(store).__name__)


# ---------------------------------------------------------------- helpers
def form_data():
    data = {f: request.form.get(f, "").strip() for f in FIELDS}
    if data["status"] not in STATUSES:
        data["status"] = "Open"
    return data


def missing_fields(data):
    """Validation added in Sprint 3 to fix the missing-field error."""
    return [f for f in REQUIRED if not data.get(f)]


@app.context_processor
def inject_globals():
    return {"app_env": APP_ENV, "statuses": STATUSES,
            "db_label": "Firestore" if USE_FIRESTORE else "In-memory sample data"}


# ---------------------------------------------------------------- routes
@app.route("/")
def index():
    q = request.args.get("q", "").strip().lower()
    status = request.args.get("status", "")
    sessions = store.list()
    if q:
        sessions = [s for s in sessions if q in " ".join(
            str(s.get(f, "")) for f in ("subject", "course_code", "tutor_name", "location")).lower()]
    if status in STATUSES:
        sessions = [s for s in sessions if s.get("status") == status]
    sessions.sort(key=lambda s: (s.get("date", ""), s.get("time", "")))
    return render_template("index.html", sessions=sessions, q=q, status=status)


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        data = form_data()
        missing = missing_fields(data)
        if missing:
            log.warning("Add rejected, missing fields: %s", missing)
            flash("Please fill in: " + ", ".join(m.replace("_", " ") for m in missing), "error")
            return render_template("form.html", session=data, mode="add"), 400
        new_id = store.add(data)
        log.info("Created appointment %s (%s with %s)", new_id, data["subject"], data["tutor_name"])
        flash("Session added.", "ok")
        return redirect(url_for("index"))
    return render_template("form.html", session={"status": "Open"}, mode="add")


@app.route("/edit/<item_id>", methods=["GET", "POST"])
def edit(item_id):
    session = store.get(item_id) or abort(404)
    if request.method == "POST":
        data = form_data()
        missing = missing_fields(data)
        if missing:
            log.warning("Edit %s rejected, missing fields: %s", item_id, missing)
            flash("Please fill in: " + ", ".join(m.replace("_", " ") for m in missing), "error")
            return render_template("form.html", session={**data, "id": item_id}, mode="edit"), 400
        store.update(item_id, data)
        log.info("Updated appointment %s", item_id)
        flash("Session updated.", "ok")
        return redirect(url_for("index"))
    return render_template("form.html", session=session, mode="edit")


@app.route("/status/<item_id>", methods=["POST"])
def change_status(item_id):
    store.get(item_id) or abort(404)
    new_status = request.form.get("status", "")
    if new_status not in STATUSES:
        abort(400)
    store.update(item_id, {"status": new_status})
    log.info("Appointment %s status -> %s", item_id, new_status)
    flash(f"Status changed to {new_status}.", "ok")
    return redirect(request.referrer or url_for("index"))


@app.route("/healthz")
def healthz():
    return {"ok": True, "env": APP_ENV}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
