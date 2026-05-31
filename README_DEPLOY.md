# 🚀 Web2APK Web Edition Deployment Guide (සිංහල & English)

මෙම Web Edition එක Internet එකේ host කරලා ඕනෑම තැනක සිට Direct APK download කරගන්න පුළුවන් විදියට හදාගන්න ආකාරය මෙම ලිපියෙන් පැහැදිලි කර ඇත.

This guide explains how to host the Web2APK Web Edition on the internet for free so you can generate and download APKs directly from any device.

---

## 🛠️ Step 1: Create a GitHub Repository (GitHub Repo එකක් හදන්න)

1. [GitHub.com](https://github.com) එකට ගොස් නව **Private** හෝ **Public** repository එකක් සාදන්න.
2. `d:\Documents\experiments\web2apk\web_edition` බහලුම (folder) තුළ ඇති සියලුම files GitHub Repo එකට Upload / Commit කරන්න.

Your repo must contain:
- `index.html`
- `server.py`
- `Dockerfile`
- `requirements.txt`
- `template.apk`
- `apktool.jar`
- `uber-apk-signer.jar`

---

## 🚂 Option A: Deploy on Railway (Highly Recommended - Free & Always On)

Railway යනු Docker deploy කිරීමට ඉතා පහසු, Free credit ලැබෙන platform එකකි.

1. **Sign Up:** [railway.app](https://railway.app) වෙත ගොස් ඔබගේ GitHub account එකෙන් Log වෙන්න.
2. **New Project:** **"New Project"** -> **"Deploy from GitHub repo"** යන්න තෝරන්න.
3. **Select Repo:** ඔබ සාදාගත් `web2apk` repository එක select කරන්න.
4. **Deploy:** **"Deploy Now"** ක්ලික් කරන්න. Railway විසින් ස්වයංක්‍රීයව `Dockerfile` එක හඳුනාගෙන, Java runtime එක සමඟ app එක compile කර deploy කරනු ඇත.
5. **Add Domain:** Build එක සාර්ථක වූ පසු, Project settings වල **"Generate Domain"** ක්ලික් කරන්න. ඔබට `.up.railway.app` නොමිලේ ලැබෙන link එකක් ලැබෙනු ඇත.

🎉 **ඔබගේ Web App එක දැන් සජීවීව පවතී! (Live!)**

---

## ☁️ Option B: Deploy on Render (100% Free Alternative)

Render යනු නොමිලේ Web Services host කළ හැකි තවත් ජනප්‍රිය සේවාවකි.

1. [render.com](https://render.com) වෙත ගොස් GitHub හරහා Sign Up වෙන්න.
2. Dashboard එකෙන් **"New +"** ක්ලික් කර **"Web Service"** යන්න තෝරන්න.
3. ඔබගේ GitHub account එක connect කර `web2apk` repo එක තෝරන්න.
4. **Settings:**
   - **Name:** `web2apk-builder`
   - **Runtime:** `Docker` (ස්වයංක්‍රීයව select නොවන්නේ නම් Docker ලෙස තෝරන්න)
   - **Instance Type:** `Free`
5. **Deploy:** **"Create Web Service"** ක්ලික් කරන්න.
6. **Note:** Render Free tier එකෙහි විනාඩි 15ක් app එක භාවිතා නොකළහොත් එය "Sleep" වෙයි. නැවත open කරන විට load වීමට තත්පර 30-50ක් ගතවිය හැක.

---

## 🐳 Option C: Run locally with Docker (ඔබගේ පරිගණකයේ Docker මඟින් run කිරීමට)

ඔබගේ පරිගණකයේ Docker install කර ඇත්නම් පහත පරිදි run කළ හැක:

```bash
# Build the Docker image
docker build -t web2apk-web .

# Run the container
docker run -p 5050:5050 web2apk-web
```

ඉන්පසු browser එකෙන් `http://localhost:5050` වෙත පිවිසෙන්න.
