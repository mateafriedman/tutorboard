# Tutoring Appointment Board (BTE 400)

One Flask codebase deployed twice on Google Cloud: Cloud Run (PaaS) and a Compute Engine Linux VM (IaaS), both sharing one Firestore database. All records are fictitious.

Replace `PROJECT_ID` below with your Google Cloud project ID. Run commands in **Cloud Shell**.

## Run locally (optional)
```
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py        # open http://localhost:8080
```

## Sprint 1: Deploy to Cloud Run (in-memory data)
```
gcloud config set project PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com compute.googleapis.com
gcloud run deploy tutorboard --source . --region us-east1 --allow-unauthenticated \
  --set-env-vars "APP_ENV=Cloud Run,USE_FIRESTORE=false" --max-instances 3
```

## Sprint 2: Firestore + VM
1. Create database: `gcloud firestore databases create --location=nam5`
2. Seed data: `pip install -r requirements.txt && python seed.py` (add `--faker 10` for extra records)
3. Service accounts (least privilege, no key files):
```
gcloud iam service-accounts create tutorboard-run
gcloud iam service-accounts create tutorboard-vm
for SA in tutorboard-run tutorboard-vm; do
  gcloud projects add-iam-policy-binding PROJECT_ID \
    --member="serviceAccount:$SA@PROJECT_ID.iam.gserviceaccount.com" --role="roles/datastore.user"
done
```
4. Redeploy Cloud Run on Firestore:
```
gcloud run deploy tutorboard --source . --region us-east1 --allow-unauthenticated \
  --service-account tutorboard-run@PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars "APP_ENV=Cloud Run,USE_FIRESTORE=true" --max-instances 3
```
5. Create the VM and firewall rule:
```
gcloud compute instances create tutorboard-vm --zone us-east1-b --machine-type e2-micro \
  --image-family debian-12 --image-project debian-cloud \
  --service-account tutorboard-vm@PROJECT_ID.iam.gserviceaccount.com --scopes cloud-platform \
  --tags tutorboard-web
gcloud compute firewall-rules create allow-tutorboard-8080 --allow tcp:8080 --target-tags tutorboard-web
```
6. On the VM (click **SSH** in the console):
```
sudo apt update && sudo apt install -y python3-venv git
git clone YOUR_REPO_URL tutorboard && cd tutorboard
python3 -m venv venv && venv/bin/pip install -r requirements.txt
sed -i "s/YOUR_USER/$(whoami)/g" deploy/tutorboard.service
sudo cp deploy/tutorboard.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now tutorboard
```
Open `http://VM_EXTERNAL_IP:8080`. The footer shows which environment you're on.

## Sprint 3: Ops evidence
- **Cloud Run logs:** Cloud Run → tutorboard → Logs
- **VM logs:** `sudo journalctl -u tutorboard -n 50`
- **Error demo:** submit the Add form with Tutor name blank. Logs show `Add rejected, missing fields`. To show the "before" state, temporarily comment out the `missing_fields` check in `add()` and the blank submit will save an incomplete record; restore it to show the fix.
- **Scaling:** Cloud Run `--max-instances 3`; VM machine type `e2-micro`.
