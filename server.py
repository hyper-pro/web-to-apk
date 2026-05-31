import os
import re
import sys
import shutil
import subprocess
import tempfile
import threading
import queue
from flask import Flask, request, jsonify, send_file, send_from_directory
from PIL import Image, ImageOps, ImageDraw

app = Flask(__name__, static_folder='.')

# ── Path helpers ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def asset(name):
    return os.path.join(BASE_DIR, name)

APKTOOL  = asset('apktool.jar')
SIGNER   = asset('uber-apk-signer.jar')
TEMPLATE = asset('template.apk')

# ── Java detection ────────────────────────────────────────────
def find_java():
    # 1. System java
    try:
        r = subprocess.run(['java', '-version'], capture_output=True, text=True, shell=True)
        if 'version' in r.stderr.lower() or 'version' in r.stdout.lower():
            return 'java', 'keytool'
    except Exception:
        pass
    # 2. Local portable JRE (downloaded by desktop app)
    local = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'Web2APK', 'jre')
    for root, _, files in os.walk(local):
        if 'java.exe' in files:
            java = os.path.join(root, 'java.exe')
            kt   = os.path.join(root, 'keytool.exe')
            return f'"{java}"', f'"{kt}"' if os.path.exists(kt) else 'keytool'
    return None, None

# ── Icon processing ───────────────────────────────────────────
def process_icons(src, decomp_dir):
    img = Image.open(src).convert('RGBA')
    sizes = {
        'mipmap-mdpi': 48, 'mipmap-hdpi': 72,
        'mipmap-xhdpi': 96, 'mipmap-xxhdpi': 144,
        'mipmap-xxxhdpi': 192, 'mipmap': 144,
    }
    for folder, size in sizes.items():
        fpath = os.path.join(decomp_dir, 'res', folder)
        os.makedirs(fpath, exist_ok=True)
        sq = ImageOps.fit(img, (size, size), centering=(0.5, 0.5))
        sq.save(os.path.join(fpath, 'ic_launcher.png'), 'PNG')
        mask = Image.new('L', (size, size), 0)
        from PIL import ImageDraw as _D
        _D.Draw(mask).ellipse((0, 0, size, size), fill=255)
        rnd = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        rnd.paste(sq, (0, 0))
        rnd.putalpha(mask)
        rnd.save(os.path.join(fpath, 'ic_launcher_round.png'), 'PNG')

# ── APK Build (runs in thread, streams logs via queue) ────────
def build_apk(url, app_name, pkg_name, icon_path, q):
    def log(msg, t='info'):
        q.put({'type': t, 'msg': msg})

    def fail(msg):
        log(msg, 'error')
        q.put({'type': 'done', 'success': False})

    try:
        java, keytool = find_java()
        if not java:
            return fail('Java not found. Please install Java or run the desktop app once to set up portable JRE.')

        for f, label in [(TEMPLATE,'template.apk'), (APKTOOL,'apktool.jar'), (SIGNER,'uber-apk-signer.jar')]:
            if not os.path.exists(f):
                return fail(f'Missing: {label}')

        log('Build environment verified.', 'ok')

        tmp = tempfile.mkdtemp(prefix='web2apk_')
        try:
            # Copy assets
            local_apk    = os.path.join(tmp, 'template.apk')
            local_jar    = os.path.join(tmp, 'apktool.jar')
            local_signer = os.path.join(tmp, 'uber-apk-signer.jar')
            shutil.copy2(TEMPLATE, local_apk)
            shutil.copy2(APKTOOL,  local_jar)
            shutil.copy2(SIGNER,   local_signer)

            decomp = os.path.join(tmp, 'decompiled')

            # 1. Decompile
            log('Extracting core WebView engine...', 'info')
            r = subprocess.run(
                [java, '-jar', 'apktool.jar', 'd', 'template.apk', '-o', 'decompiled', '-f'],
                cwd=tmp, capture_output=True, text=True, shell=True
            )
            if r.returncode != 0:
                return fail(f'Decompile failed:\n{r.stderr[-600:]}')

            # 2. App name
            log(f"Setting App Name: '{app_name}'", 'ok')
            strings = os.path.join(decomp, 'res', 'values', 'strings.xml')
            if os.path.exists(strings):
                with open(strings, 'r', encoding='utf-8') as f:
                    c = f.read()
                c = re.sub(r'<string name="app_name">[^<]+</string>',
                           f'<string name="app_name">{app_name}</string>', c)
                with open(strings, 'w', encoding='utf-8') as f:
                    f.write(c)

            # 3. Inject URL
            log(f'Injecting URL: {url}', 'ok')
            smali = os.path.join(decomp, 'smali', 'com', 'hyperpro', 'freecity', 'MainActivity.smali')
            if not os.path.exists(smali):
                return fail('Critical smali file missing from template APK.')
            with open(smali, 'r', encoding='utf-8') as f:
                c = f.read()
            c = c.replace('https://hyper-pro.github.io/Free-City/', url)
            with open(smali, 'w', encoding='utf-8') as f:
                f.write(c)

            # 4. Icons
            log('Processing launcher icons...', 'info')
            process_icons(icon_path, decomp)
            log('Icons applied (mdpi/hdpi/xhdpi/xxhdpi/xxxhdpi).', 'ok')

            # 5. Package rename
            old_pkg  = 'com.hyperpro.freecity'
            old_path = old_pkg.replace('.', '/')
            new_path = pkg_name.replace('.', '/')
            log(f"Renaming package: '{old_pkg}' → '{pkg_name}'", 'ok')
            count = 0
            for root, _, files in os.walk(decomp):
                for fname in files:
                    if not fname.endswith(('.xml','.smali','.txt','.yml','.json','.html')):
                        continue
                    fp = os.path.join(root, fname)
                    try:
                        with open(fp, 'r', encoding='utf-8') as f:
                            data = f.read()
                    except UnicodeDecodeError:
                        continue
                    nd = data.replace(old_pkg, pkg_name).replace(old_path, new_path)
                    if nd != data:
                        with open(fp, 'w', encoding='utf-8') as f:
                            f.write(nd)
                        count += 1
            log(f'Patched {count} files.', 'info')

            old_smali = os.path.join(decomp, 'smali', 'com', 'hyperpro', 'freecity')
            new_smali = os.path.join(decomp, 'smali', *new_path.split('/'))
            if os.path.exists(old_smali):
                os.makedirs(os.path.dirname(new_smali), exist_ok=True)
                shutil.move(old_smali, new_smali)
                try:
                    os.rmdir(os.path.join(decomp, 'smali', 'com', 'hyperpro'))
                except OSError:
                    pass

            # 6. Rebuild
            log('Compiling Android binaries...', 'info')
            r = subprocess.run(
                [java, '-jar', 'apktool.jar', 'b', 'decompiled', '-o', 'unsigned.apk'],
                cwd=tmp, capture_output=True, text=True, shell=True
            )
            if r.returncode != 0:
                return fail(f'Rebuild failed:\n{r.stderr[-600:]}')

            # 7. Keystore
            log('Generating signing keystore...', 'ok')
            r = subprocess.run(
                [keytool, '-genkeypair', '-v',
                 '-keystore', 'signing.jks',
                 '-keyalg', 'RSA', '-keysize', '2048',
                 '-validity', '10000', '-alias', 'web2apk',
                 '-storepass', 'web2apkpass', '-keypass', 'web2apkpass',
                 '-dname', 'CN=Web2APK,O=Web2APK,C=US'],
                cwd=tmp, capture_output=True, text=True, shell=True
            )
            has_ks = (r.returncode == 0)
            if not has_ks:
                log('Keytool unavailable – using auto-sign mode.', 'warn')

            # 8. Sign
            slug = re.sub(r'[^a-zA-Z0-9_]', '_', app_name)
            out_apk = os.path.join(tmp, f'{slug}.apk')
            shutil.copy2(os.path.join(tmp, 'unsigned.apk'), out_apk)

            log('Signing APK (v1/v2/v3/v4 schemas)...', 'ok')
            if has_ks:
                sign_cmd = [java, '-jar', 'uber-apk-signer.jar',
                            '--apks', out_apk,
                            '--ks', 'signing.jks',
                            '--ksAlias', 'web2apk',
                            '--ksPass', 'web2apkpass',
                            '--ksKeyPass', 'web2apkpass',
                            '--overwrite']
            else:
                sign_cmd = [java, '-jar', 'uber-apk-signer.jar',
                            '--apks', out_apk, '--overwrite']

            r = subprocess.run(sign_cmd, cwd=tmp, capture_output=True, text=True, shell=True)
            if r.returncode != 0:
                return fail(f'Signing failed:\n{r.stderr[-600:]}')

            # Check for -aligned-signed output
            signed = out_apk
            alt = out_apk.replace('.apk', '-aligned-signed.apk')
            if os.path.exists(alt):
                signed = alt

            log(f'SUCCESS! APK ready: {slug}.apk', 'ok')
            q.put({'type': 'done', 'success': True, 'apk_path': signed, 'filename': f'{slug}.apk'})

        except Exception as e:
            shutil.rmtree(tmp, ignore_errors=True)
            raise e

    except Exception as e:
        fail(f'Unexpected error: {str(e)}')


# ── Build job registry ────────────────────────────────────────
jobs = {}  # job_id -> {'q': queue, 'apk_path': str, 'done': bool}

# ── Routes ───────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/build', methods=['POST'])
def api_build():
    url      = request.form.get('url', '').strip()
    app_name = request.form.get('app_name', '').strip()
    pkg_name = request.form.get('pkg_name', '').strip()
    icon     = request.files.get('icon')

    # Validate
    if not url or not url.startswith(('http://', 'https://')):
        return jsonify(error='Invalid URL'), 400
    if not app_name:
        return jsonify(error='App name required'), 400
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$', pkg_name):
        return jsonify(error='Invalid package ID'), 400
    if not icon:
        return jsonify(error='Icon required'), 400

    # Save icon to temp
    icon_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    icon.save(icon_tmp.name)
    icon_tmp.close()

    import uuid
    job_id = str(uuid.uuid4())
    q = queue.Queue()
    jobs[job_id] = {'q': q, 'apk_path': None, 'done': False, 'tmp_icon': icon_tmp.name}

    def run():
        build_apk(url, app_name, pkg_name, icon_tmp.name, q)

    t = threading.Thread(target=run, daemon=True)
    t.start()

    return jsonify(job_id=job_id)


@app.route('/api/logs/<job_id>')
def api_logs(job_id):
    """Server-Sent Events stream for build logs."""
    job = jobs.get(job_id)
    if not job:
        return jsonify(error='Job not found'), 404

    def generate():
        q = job['q']
        while True:
            try:
                item = q.get(timeout=60)
            except queue.Empty:
                yield 'data: {"type":"timeout"}\n\n'
                break

            import json
            yield f'data: {json.dumps(item)}\n\n'

            if item.get('type') == 'done':
                if item.get('success'):
                    job['apk_path'] = item['apk_path']
                    job['filename'] = item['filename']
                job['done'] = True
                break

    from flask import Response
    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/api/download/<job_id>')
def api_download(job_id):
    job = jobs.get(job_id)
    if not job or not job.get('apk_path') or not os.path.exists(job['apk_path']):
        return jsonify(error='APK not ready or not found'), 404

    path = job['apk_path']
    fname = job.get('filename', 'app.apk')

    response = send_file(path, as_attachment=True, download_name=fname,
                         mimetype='application/vnd.android.package-archive')

    # Cleanup after send
    @response.call_on_close
    def cleanup():
        try:
            # Remove tmp dir (parent of apk)
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)
            # Remove tmp icon
            os.remove(job.get('tmp_icon', ''))
        except Exception:
            pass
        jobs.pop(job_id, None)

    return response


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    print('\n  Web2APK Web Edition Server')
    print('  --------------------------')
    print(f'  Open: http://localhost:{port}\n')
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
