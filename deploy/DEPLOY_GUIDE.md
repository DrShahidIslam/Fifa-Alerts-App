# Oracle Cloud Setup — Complete Beginner Guide

> This guide assumes zero cloud experience. Follow every step exactly.

---

## PART 1: Create Your Free Oracle Account (5 minutes)

### Step 1.1 — Open the signup page
- Open your browser and go to: **https://cloud.oracle.com/free**
- Click the big blue button that says **"Start for free"**

### Step 1.2 — Enter your details
You'll see a form. Fill it in:

| Field | What to enter |
|-------|--------------|
| **Country** | Pakistan |
| **First Name** | Your first name |
| **Last Name** | Your last name |
| **Email** | Your email address |

- Click **"Verify my email"**
- Go to your email inbox → find the Oracle email → click the verification link

### Step 1.3 — Set your password
- Create a password (must have uppercase + lowercase + number + special character)
- Example: `MyAgent2026!`

### Step 1.4 — Account details
| Field | What to enter |
|-------|--------------|
| **Cloud Account Name** | `fifaalerts` (or anything short, no spaces) |
| **Home Region** | Choose **India South (Hyderabad)** — closest to Pakistan with good availability |

> **IMPORTANT:** You CANNOT change your home region later. Pick India South (Hyderabad) or India West (Mumbai).

### Step 1.5 — Enter your address
- Fill in your real address. Oracle needs this for verification.

### Step 1.6 — Credit card verification
- Enter your credit/debit card details
- Oracle will do a **temporary $1 hold** to verify your card — this is **refunded immediately**
- **You will NEVER be charged.** Free tier resources have no cost. Ever.

### Step 1.7 — Wait for activation
- You'll see **"Your account is being set up"**
- Usually activates in **2-30 minutes**
- You'll get an email: **"Get Started Now with Oracle Cloud"**
- **Save this email** — it contains your login link

---

## PART 2: Create Your Free Server (5 minutes)

### Step 2.1 — Log in
- Go to: **https://cloud.oracle.com**
- Enter your **Cloud Account Name** (from Step 1.4, e.g., `fifaalerts`)
- Click **Next** → Enter your email and password → Click **Sign In**

### Step 2.2 — Navigate to Compute
- On the main dashboard, look at the left menu (hamburger icon ☰ in top-left)
- Click **☰** → **Compute** → **Instances**

### Step 2.3 — Create Instance
- Click the blue **"Create Instance"** button

Now fill in the form:

#### Name
- Type: `fifa-agent`

#### Image and Shape (IMPORTANT — don't skip!)
1. Under **Image**, make sure it says **Ubuntu** (Canonical Ubuntu 22.04 or 24.04)
   - If it shows Oracle Linux, click **"Change Image"** → Select **Ubuntu** → Click **"Select Image"**

2. Under **Shape**, click **"Change Shape"**
   - Click **"Ampere"** (ARM-based processors)
   - Select **VM.Standard.A1.Flex**
   - Set **Number of OCPUs:** `1`
   - Set **Amount of memory (GB):** `1`
   - Click **"Select Shape"**

> This shape is in the **Always Free** tier. You'll see a green banner confirming it.

#### Networking
- Leave everything as default
- Make sure **"Assign a public IPv4 address"** is checked (it usually is by default)

#### SSH Keys (VERY IMPORTANT)
1. Select **"Generate a key pair"**
2. Click **"Save Private Key"** — a `.key` file will download
3. Also click **"Save Public Key"**

> ⚠️ **SAVE THESE FILES SOMEWHERE SAFE!** You need the private key to connect to your server. If you lose it, you can never connect. I suggest saving it to `C:\Users\shahi\oracle-key.key`

#### Click "Create"
- Wait about 2 minutes
- The status will change from **PROVISIONING** → **RUNNING**
- You'll see **Public IP Address** displayed (something like `129.154.xx.xx`)
- **Copy this IP address** — you need it for the next steps

---

## PART 3: Connect to Your Server (2 minutes)

### Step 3.1 — Open PowerShell on your PC
- Press **Windows key** → Type `powershell` → Click **Windows PowerShell**

### Step 3.2 — Connect via SSH
Type this command (replace the two placeholders):

```powershell
ssh -i "C:\Users\shahi\oracle-key.key" ubuntu@PASTE_YOUR_IP_HERE
```

For example, if your IP is `129.154.50.100`:
```powershell
ssh -i "C:\Users\shahi\oracle-key.key" ubuntu@129.154.50.100
```

- If asked **"Are you sure you want to continue connecting?"** → Type `yes` → Press Enter
- You should see something like: `ubuntu@fifa-agent:~$`
- **Congratulations, you're inside your server!** 🎉

> **If it says "Permission denied"**: The key file permissions might need fixing. Run:
> ```powershell
> icacls "C:\Users\shahi\oracle-key.key" /inheritance:r /grant:r "%USERNAME%:R"
> ```
> Then try the SSH command again.

---

## PART 4: Set Up the Agent on Your Server (5 minutes)

### Step 4.1 — Run these commands one by one

Copy-paste each line into the terminal and press Enter after each:

```bash
sudo apt update && sudo apt upgrade -y
```
*(Wait for it to finish — takes about 2 min. If asked any questions, type `Y` and press Enter)*

```bash
sudo apt install -y python3 python3-pip python3-venv
```

```bash
sudo mkdir -p /opt/fifa-agent
```

```bash
sudo chown ubuntu:ubuntu /opt/fifa-agent
```

```bash
cd /opt/fifa-agent
```

```bash
python3 -m venv venv
```

```bash
source venv/bin/activate
```

```bash
pip install feedparser pytrends newsapi-python python-telegram-bot python-dotenv schedule google-genai trafilatura requests Pillow
```
*(This takes about 1-2 min)*

```bash
mkdir -p images logs database
```

### Step 4.2 — Keep this SSH window open, don't close it yet!

---

## PART 5: Upload Your Code to the Server (3 minutes)

### Step 5.1 — Open a NEW PowerShell window
- Press **Windows key** → Type `powershell` → Open a **second** PowerShell window
- (Keep the first SSH window open too)

### Step 5.2 — Edit the upload script
- Open `G:\Fifa Alerts App\deploy\upload_to_vm.ps1` in Notepad
- Change line 4: Replace `C:\path\to\your-oracle-key.key` with your actual key path
  - Example: `C:\Users\shahi\oracle-key.key`
- Change line 5: Replace `YOUR_PUBLIC_IP` with your server's IP
  - Example: `129.154.50.100`
- Save the file

### Step 5.3 — Run the upload
In the **new** PowerShell window, type:

```powershell
powershell -ExecutionPolicy Bypass -File "G:\Fifa Alerts App\deploy\upload_to_vm.ps1"
```

Wait for all files to upload. You'll see progress for each file.

> **If upload_to_vm.ps1 doesn't work**, you can upload manually with these commands (replace KEY and IP):
> ```powershell
> $K = "C:\Users\shahi\oracle-key.key"
> $IP = "129.154.50.100"
> scp -i $K "G:\Fifa Alerts App\main.py" "ubuntu@${IP}:/opt/fifa-agent/"
> scp -i $K "G:\Fifa Alerts App\config.py" "ubuntu@${IP}:/opt/fifa-agent/"
> scp -i $K "G:\Fifa Alerts App\.env" "ubuntu@${IP}:/opt/fifa-agent/"
> scp -i $K -r "G:\Fifa Alerts App\sources" "ubuntu@${IP}:/opt/fifa-agent/"
> scp -i $K -r "G:\Fifa Alerts App\detection" "ubuntu@${IP}:/opt/fifa-agent/"
> scp -i $K -r "G:\Fifa Alerts App\notifications" "ubuntu@${IP}:/opt/fifa-agent/"
> scp -i $K -r "G:\Fifa Alerts App\writer" "ubuntu@${IP}:/opt/fifa-agent/"
> scp -i $K -r "G:\Fifa Alerts App\publisher" "ubuntu@${IP}:/opt/fifa-agent/"
> scp -i $K -r "G:\Fifa Alerts App\database" "ubuntu@${IP}:/opt/fifa-agent/"
> scp -i $K "G:\Fifa Alerts App\deploy\fifa-agent.service" "ubuntu@${IP}:/opt/fifa-agent/"
> ```

---

## PART 6: Test and Start the Agent (2 minutes)

### Step 6.1 — Go back to your SSH window (the first PowerShell)

Run these commands:

```bash
cd /opt/fifa-agent
source venv/bin/activate
python main.py --test
```

You should see each service being tested. Check your **Telegram** — you should receive a test message!

### Step 6.2 — Install as a permanent service
This makes the agent start automatically and run forever:

```bash
sudo cp fifa-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fifa-agent
sudo systemctl start fifa-agent
```

### Step 6.3 — Verify it's running

```bash
sudo systemctl status fifa-agent
```

You should see: **Active: active (running)** in green.

Check your **Telegram** again — you should get a startup notification!

---

## PART 7: You're Done! 🎉

Your FIFA News Agent is now running **24/7** on Oracle Cloud, even when your PC is off.

Every 30 minutes, it will:
1. Scan 7 RSS feeds + NewsAPI + Google Trends
2. Detect trending World Cup topics
3. Send you Telegram alerts

### Commands You'll Use Later

| What you want | Command (run in SSH) |
|---|---|
| Check if agent is running | `sudo systemctl status fifa-agent` |
| See live logs | `sudo journalctl -u fifa-agent -f` |
| Restart the agent | `sudo systemctl restart fifa-agent` |
| Stop the agent | `sudo systemctl stop fifa-agent` |
| Start the agent | `sudo systemctl start fifa-agent` |

### How to Update Code Later

1. Edit files on your PC in `G:\Fifa Alerts App\`
2. Run the upload script again (Step 5.3)
3. SSH into server → run: `sudo systemctl restart fifa-agent`

### How to Connect to Server Anytime

```powershell
ssh -i "C:\Users\shahi\oracle-key.key" ubuntu@YOUR_IP
```

---

## Troubleshooting

**"Connection refused" when SSHing:**
- Wait 2 more minutes — the server might still be starting
- Check in Oracle Console that the instance status is "RUNNING"

**"Permission denied" when SSHing:**
- Run: `icacls "C:\Users\shahi\oracle-key.key" /inheritance:r /grant:r "%USERNAME%:R"`
- Try again

**Agent stops after a few hours:**
- Run: `sudo journalctl -u fifa-agent --since "1 hour ago"` to see what went wrong
- Usually it auto-restarts within 60 seconds (systemd handles this)

**"No module named X" error:**
```bash
cd /opt/fifa-agent
source venv/bin/activate
pip install feedparser pytrends newsapi-python python-telegram-bot python-dotenv schedule google-genai trafilatura requests Pillow
sudo systemctl restart fifa-agent
```
