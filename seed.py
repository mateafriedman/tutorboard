"""
Sprint 2: load the sample sessions into Firestore. Run ONCE from Cloud Shell:
    pip install -r requirements.txt
    python seed.py

Optional: python seed.py --faker 10   adds 10 extra random fictitious sessions (pip install Faker).
"""
import random
import sys

from google.cloud import firestore

from sample_data import SAMPLE_SESSIONS

db = firestore.Client()
col = db.collection("appointments")

records = list(SAMPLE_SESSIONS)

if "--faker" in sys.argv:
    from faker import Faker
    fake = Faker()
    count = int(sys.argv[sys.argv.index("--faker") + 1])
    subjects = [("Statistics", "BTE 210"), ("Python Programming", "BTE 320"),
                ("Calculus I", "MTH 151"), ("Microeconomics", "ECO 211")]
    for _ in range(count):
        subj, code = random.choice(subjects)
        status = random.choice(["Open", "Requested", "Booked"])
        records.append({
            "subject": subj, "course_code": code, "tutor_name": fake.name(),
            "student_name": "" if status == "Open" else fake.name(),
            "date": fake.date_between("+1d", "+20d").isoformat(),
            "time": random.choice(["09:00", "11:00", "13:00", "15:00", "17:00"]),
            "location": random.choice(["Zoom", "Richter Library, Room 2", "Math Lab"]),
            "status": status, "notes": "",
        })

for r in records:
    col.add({**r, "created_at": firestore.SERVER_TIMESTAMP})

print(f"Added {len(records)} sessions to the 'appointments' collection.")
