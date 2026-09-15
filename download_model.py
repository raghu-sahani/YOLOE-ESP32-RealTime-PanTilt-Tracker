"""Download official model atomically and verify its exact SHA-256."""
from pathlib import Path
import hashlib
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent
MODEL=ROOT/'yoloe-26s-seg.pt'
URL='https://github.com/ultralytics/assets/releases/download/v8.4.0/yoloe-26s-seg.pt'
SHA256='48f24206bc8680d60cbbfa296b0140da849669b9515058b72f5a945142df0654'

def valid(path):
    if not path.is_file():return False
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()==SHA256

def ensure_model():
    if valid(MODEL):return MODEL
    temporary=MODEL.with_suffix('.download')
    error=None
    for attempt in range(1,4):
        try:
            print(f'Downloading YOLOE model, attempt {attempt}/3 (about 31 MB)...',flush=True)
            request=urllib.request.Request(URL,headers={'User-Agent':'PanTilt-Setup/1.0'})
            with urllib.request.urlopen(request,timeout=45) as response,temporary.open('wb') as out:
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk:break
                    out.write(chunk)
            if not valid(temporary):raise RuntimeError('Model checksum mismatch: download was incomplete or changed.')
            with zipfile.ZipFile(temporary) as archive:
                if archive.testzip() is not None:raise RuntimeError('Model archive is damaged.')
            temporary.replace(MODEL)
            print('YOLOE model verified. Ready.',flush=True)
            return MODEL
        except Exception as exc:
            error=exc
            temporary.unlink(missing_ok=True)
            print(str(exc),flush=True)
    raise RuntimeError('Could not download the model. Check internet access to GitHub and run START.bat again. '+str(error))

if __name__=='__main__':ensure_model()
