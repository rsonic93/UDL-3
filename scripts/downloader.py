#!/usr/bin/env python3
import os
import sys
import subprocess
import urllib.parse
import re
from datetime import datetime

SPLIT_SIZE_MB = 90
DOWNLOADS_DIR = "downloads"

def get_env(key, default=""):
    return os.environ.get(key, default)

def urlencode(s):
    return urllib.parse.quote(s, safe='')

def sanitize_filename(name):
    name = urllib.parse.unquote(name)
    name = re.sub(r'[<>:"|?*]', '_', name)
    name = re.sub(r'[?#].*', '', name)
    return name

def get_unique_folder(base_path, name):
    if not os.path.exists(os.path.join(base_path, name)):
        return name
    import random
    suffix = f"_{random.randint(1000, 9999)}"
    return f"{name}{suffix}"

def download_file(url, filename, tmp_dir):
    filepath = os.path.join(tmp_dir, filename)
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # Try aria2c first
    try:
        result = subprocess.run([
            "aria2c",
            "--split=4", "--max-connection-per-server=4",
            "--min-split-size=10M", "--max-tries=5", "--retry-wait=3",
            "--timeout=120", "--connect-timeout=60",
            "--check-certificate=false",
            "--allow-overwrite=true", "--auto-file-renaming=false",
            f"--user-agent={ua}",
            "--header=Accept: */*",
            "--header=Accept-Language: en-US,en;q=0.9",
            f"--header=Referer: {url}",
            f"--dir={tmp_dir}", f"--out={filename}", url
        ], capture_output=True, text=True, timeout=7200)

        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"✅ Downloaded (aria2c): {filename}")
            return True
        print(f"aria2c stderr: {result.stderr[:200] if result.stderr else 'none'}")
    except Exception as e:
        print(f"aria2c error: {e}")

    # Fallback to wget (better for some servers)
    try:
        subprocess.run([
            "wget", "-q", "--show-progress",
            "--tries=5", "--timeout=120",
            f"--user-agent={ua}",
            "--header=Accept: */*",
            f"--header=Referer: {url}",
            "-O", filepath, url
        ], check=True, timeout=7200)

        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"✅ Downloaded (wget): {filename}")
            return True
    except Exception as e:
        print(f"wget error: {e}")

    # Fallback to curl
    try:
        subprocess.run([
            "curl", "-L", "-#",
            "--retry", "5", "--retry-delay", "3", "--retry-all-errors",
            "--connect-timeout", "60", "--max-time", "7200",
            "-H", f"User-Agent: {ua}",
            "-H", "Accept: */*",
            "-H", f"Referer: {url}",
            "-o", filepath, url
        ], check=True, timeout=7200)

        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"✅ Downloaded (curl): {filename}")
            return True
    except Exception as e:
        print(f"curl error: {e}")

    return False

def create_rar_archive(source_file, dest_folder, folder_name, password=""):
    """Split file into RAR parts at 90MB"""
    archive_path = os.path.join(dest_folder, f"{folder_name}.rar")

    cmd = ["rar", "a", "-v90m", "-ep"]
    if password:
        cmd.extend([f"-hp{password}"])
    cmd.extend([archive_path, source_file])

    try:
        subprocess.run(cmd, check=True)
        return True
    except Exception as e:
        print(f"RAR failed: {e}")
        # Fallback to zip if rar not available
        try:
            zip_path = os.path.join(dest_folder, f"{folder_name}.zip")
            cmd = ["zip", "-j", "-s", "90m"]
            if password:
                cmd.extend(["-P", password])
            cmd.extend([zip_path, source_file])
            subprocess.run(cmd, check=True)
            return True
        except:
            return False

def create_readme(folder_path, filename, parts, total_size_mb, password, repo_owner, repo_name, branch, status="Complete"):
    """Create summary README in Persian"""
    folder_name = os.path.basename(folder_path)
    folder_encoded = urlencode(folder_name)

    links_md = ""
    for i, part in enumerate(sorted(parts), 1):
        part_encoded = urlencode(part)
        raw_link = f"https://github.com/{repo_owner}/{repo_name}/raw/{branch}/downloads/{folder_encoded}/{part_encoded}"
        links_md += f"| {i} | `{part}` | [دانلود]({raw_link}) |\n"

    # Fork download link
    fork_zip_link = f"https://github.com/{repo_owner}/{repo_name}/archive/refs/heads/{branch}.zip"

    readme_content = f"""# {filename}

---

## اطلاعات دانلود

| ویژگی | مقدار |
|-------|-------|
| **نام فایل** | `{filename}` |
| **حجم کل** | {total_size_mb:.2f} MB ({len(parts)} پارت) |
| **وضعیت** | **{status}** |
| **رمز عبور** | {'**بله**' if password else '**خیر**'} |

---

## لینک های دانلود

| # | فایل | لینک |
|---|------|------|
{links_md}
---

## نحوه استخراج

1. **تمام پارت ها را دانلود کنید** (`.rar`, `.r00`, `.r01`... یا `.zip`, `.z01`...)
2. فایل اصلی را با WinRAR یا 7-Zip **باز کنید**
3. **استخراج کنید** — تمام پارت ها خودکار ترکیب می شوند
{'4. رمز عبور را وارد کنید' if password else ''}

---

## 📦 دانلود همه فایل ها به صورت یکجا

برای دانلود تمام فایل های این مخزن به صورت یک فایل ZIP:

**[⬇️ دانلود کل مخزن به صورت ZIP]({fork_zip_link})**

> نکته: پس از Fork کردن این پروژه، می توانید از لینک بالا استفاده کنید تا همه فایل ها را یکجا دانلود کنید.

---

طراحی شده توسط [آواسام](https://avasam.ir) 💚
"""

    with open(os.path.join(folder_path, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme_content)

def create_error_readme(folder_path, filename, url, error_msg, repo_owner, repo_name, branch):
    """Create error README"""
    fork_zip_link = f"https://github.com/{repo_owner}/{repo_name}/archive/refs/heads/{branch}.zip"

    content = f"""# {filename} - دانلود ناموفق

---

## اطلاعات

| ویژگی | مقدار |
|-------|-------|
| **فایل** | `{filename}` |
| **لینک** | {url} |
| **تاریخ** | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |
| **وضعیت** | **ناموفق** |

---

## خطا

```
{error_msg}
```

---

## راه حل ها

- بررسی کنید لینک صحیح باشد
- ممکن است فایل حذف شده باشد
- برخی سرورها دانلود خودکار را مسدود می کنند
- دوباره تلاش کنید

---

## 📦 دانلود کل مخزن

**[⬇️ دانلود ZIP]({fork_zip_link})**

طراحی شده توسط [آواسام](https://avasam.ir) 💚
"""
    with open(os.path.join(folder_path, "README.md"), "w", encoding="utf-8") as f:
        f.write(content)

def main():
    urls = get_env("INPUT_URLS", "").split()
    mode = get_env("INPUT_MODE", "normal")
    password = get_env("INPUT_PASSWORD", "")
    repo_owner = get_env("REPO_OWNER")
    repo_name = get_env("REPO_NAME")
    branch = get_env("BRANCH", "main")

    if not urls:
        print("❌ لینک دانلود وارد نشده!")
        sys.exit(1)

    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    tmp_dir = "/tmp/downloads"
    os.makedirs(tmp_dir, exist_ok=True)

    downloaded_files = []

    for url in urls:
        filename = sanitize_filename(os.path.basename(url))
        print(f"📥 دانلود: {url}")

        if download_file(url, filename, tmp_dir):
            downloaded_files.append((url, filename, os.path.join(tmp_dir, filename)))
        else:
            # Create error folder
            base_name = os.path.splitext(filename)[0]
            folder_name = get_unique_folder(DOWNLOADS_DIR, base_name)
            folder_path = os.path.join(DOWNLOADS_DIR, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            create_error_readme(folder_path, filename, url, "Download failed after retries", repo_owner, repo_name, branch)

    # Process downloaded files
    for url, filename, filepath in downloaded_files:
        file_size = os.path.getsize(filepath)
        size_mb = file_size / (1024 * 1024)
        base_name = os.path.splitext(filename)[0]
        folder_name = get_unique_folder(DOWNLOADS_DIR, base_name)
        folder_path = os.path.join(DOWNLOADS_DIR, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        print(f"📦 پردازش: {filename} ({size_mb:.2f} MB)")

        # Create RAR archive (will split if > 90MB)
        if create_rar_archive(filepath, folder_path, folder_name, password):
            # Get created parts
            parts = [f for f in os.listdir(folder_path) if f.endswith(('.rar', '.r00', '.r01', '.r02', '.zip', '.z01', '.z02')) or re.match(r'.*\.(r|z)\d+$', f)]
            if not parts:
                parts = [f for f in os.listdir(folder_path) if not f.endswith('.md')]

            total_size = sum(os.path.getsize(os.path.join(folder_path, p)) for p in parts)
            create_readme(folder_path, filename, parts, total_size/(1024*1024), password, repo_owner, repo_name, branch)
        else:
            create_error_readme(folder_path, filename, url, "Archive creation failed", repo_owner, repo_name, branch)

    # Create main downloads README
    folders = [d for d in os.listdir(DOWNLOADS_DIR) if os.path.isdir(os.path.join(DOWNLOADS_DIR, d))]
    fork_zip_link = f"https://github.com/{repo_owner}/{repo_name}/archive/refs/heads/{branch}.zip"

    with open(os.path.join(DOWNLOADS_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write("# لیست دانلودها\n\n")
        for folder in sorted(folders):
            f.write(f"- [{folder}](./{urlencode(folder)})\n")
        f.write(f"\n---\n\n## 📦 دانلود همه فایل ها\n\n")
        f.write(f"برای دانلود تمام فایل های این مخزن:\n\n")
        f.write(f"**[⬇️ دانلود کل مخزن به صورت ZIP]({fork_zip_link})**\n\n")
        f.write("\nطراحی شده توسط [آواسام](https://avasam.ir) 💚\n")

    print("✅ تمام شد!")

if __name__ == "__main__":
    main()
