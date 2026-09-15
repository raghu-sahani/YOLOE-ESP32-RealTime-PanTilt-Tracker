"""Install inside START.bat's isolated environment; prefer NVIDIA when available."""
import subprocess,sys,shutil
from pathlib import Path

def pip(*args):
    subprocess.check_call([sys.executable,'-m','pip',*args])

if __name__=='__main__':
    pip('install','--upgrade','pip')
    gpu=shutil.which('nvidia-smi') is not None
    index='https://download.pytorch.org/whl/'+('cu126' if gpu else 'cpu')
    print('Installing '+('NVIDIA GPU' if gpu else 'CPU')+' PyTorch. First setup can take several minutes.',flush=True)
    pip('install','torch==2.13.0','torchvision==0.28.0','--index-url',index)
    pip('install','-r',str(Path(__file__).with_name('requirements.txt')))
    subprocess.check_call([sys.executable,'-c','import torch, cv2; print("CUDA available:", torch.cuda.is_available()); print("OpenCV:",cv2.__version__)'])
