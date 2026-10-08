"""Bounded local rescans for explicitly reviewed, unchanged archived messages."""
import hashlib,json,os,subprocess,tempfile,time
from pathlib import Path

REVIEW_FILE=Path('/etc/wwcx/mail-reviewed-scans/records.json')

def definitions_key(directory=Path('/var/lib/clamav')):
    files=sorted(p for p in directory.iterdir() if p.suffix in {'.cvd','.cld'})
    if not files:raise ValueError('Definitions missing')
    return hashlib.sha256(json.dumps([(p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in files]).encode()).hexdigest()

def reviewed_scan(raw, review_file=REVIEW_FILE, definitions=Path('/var/lib/clamav'), runner=subprocess.run):
    # No sender/domain exemptions: permission is bound to exact archived bytes.
    try:
        st=review_file.stat()
        if review_file.is_symlink() or st.st_uid!=0 or st.st_mode & 0o027:return False
        records=json.loads(review_file.read_text())
        digest=hashlib.sha256(raw).hexdigest()
        record=records.get(digest)
        if not record or record.get('approved') is not True or record.get('raw_sha256')!=digest:return False
        key=definitions_key(definitions)
        if record.get('definitions_key')==key and record.get('clean') is True and time.time()-86400<record.get('checked_at',0)<=time.time()+60:return True
        if os.geteuid()!=0:return False
        # Existing approval permits a larger bounded scan, never a clean verdict.
        with tempfile.TemporaryDirectory(prefix='mail-reviewed-scan-') as directory:
            path=Path(directory)/'message.eml';path.write_bytes(raw);path.chmod(0o600)
            result=runner(['clamscan','--max-scansize=150M','--max-filesize=50M','--max-recursion=10','--max-files=1000','--alert-exceeds-max=yes','--alert-encrypted=yes',str(path)],capture_output=True,timeout=120)
        clean=result.returncode==0 and key==definitions_key(definitions)
        record.update(clean=clean,definitions_key=key,checked_at=time.time(),report_sha256=hashlib.sha256(result.stdout+result.stderr).hexdigest())
        temporary=review_file.with_suffix('.tmp')
        temporary.write_text(json.dumps(records,indent=2));temporary.chmod(0o640);os.chown(temporary,0,st.st_gid);os.replace(temporary,review_file)
        return clean
    except (OSError,ValueError,TypeError,subprocess.TimeoutExpired):
        return False
