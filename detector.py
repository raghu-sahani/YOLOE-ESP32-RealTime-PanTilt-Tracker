"""Photo-prompted YOLOE; reference selection persists across all target losses."""
import json
import os
import math
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent

def centre(box):
    x,y,w,h=box
    return x+w/2,y+h/2

class Association:
    """Choose the selected class, require two observations after loss/large jumps."""
    def __init__(self,target='Ball'):
        self.target=target;self.reset()

    def reset(self):
        self.box=None;self.last_seen=-100.;self.pending=None;self.hits=0
        self.state='Searching for '+self.target

    def choose(self,rows,now):
        allowed=(0,1) if self.target=='Ball' else (2,)
        candidates=[]
        for x1,y1,x2,y2,conf,cls in rows:
            w,h=x2-x1,y2-y1
            if int(cls) not in allowed or conf<.30 or min(w,h)<10:continue
            if not .40<w/max(h,1)<2.4:continue
            b=(float(x1),float(y1),float(w),float(h))
            distance=math.dist(centre(b),centre(self.box)) if self.box else 0
            score=float(conf)-(.15*min(distance/200,1) if now-self.last_seen<.5 else 0)
            candidates.append((score,b))
        if not candidates:
            self.pending=None;self.hits=0
            self.state='Target remembered - searching for '+self.target
            return None
        _,b=max(candidates,key=lambda v:v[0])
        continuous=(self.box is not None and now-self.last_seen<.5 and
                    math.dist(centre(b),centre(self.box))<max(90,1.8*max(self.box[2:])))
        if not continuous:
            close=(self.pending is not None and math.dist(centre(b),centre(self.pending))<max(80,max(b[2:])))
            self.hits=self.hits+1 if close else 1
            self.pending=b
            if self.hits<2:
                self.state='Confirming '+self.target
                return None
        self.box=b;self.last_seen=now;self.pending=None;self.hits=0
        self.state='Following '+self.target
        return b

class Detector:
    def __init__(self):
        from download_model import ensure_model
        ensure_model()
        os.environ["YOLO_OFFLINE"]="true"
        (ROOT/"runtime_config").mkdir(exist_ok=True)
        os.environ["YOLO_CONFIG_DIR"]=str(ROOT/"runtime_config")
        import torch
        from ultralytics import YOLOE,settings
        settings.update({"sync":False})
        from ultralytics.models.yolo.yoloe import YOLOEVPSegPredictor
        torch.set_num_threads(4)
        self.device=0 if torch.cuda.is_available() else 'cpu'
        self.device_name=torch.cuda.get_device_name(0) if self.device==0 else 'CPU'
        self.model=YOLOE(str(ROOT/'yoloe-26s-seg.pt'))
        prompts=json.loads((ROOT/'references/prompt.json').read_text())
        prompts={k:np.asarray(v) for k,v in prompts.items()}
        reference=str(ROOT/'references/prompt.jpg')
        self.model.predict(reference,refer_image=reference,visual_prompts=prompts,
            predictor=YOLOEVPSegPredictor,imgsz=640,device=self.device,verbose=False)
        self.model.predict(np.zeros((480,640,3),np.uint8),imgsz=640,conf=.30,verbose=False)

    def detect(self,frame):
        result=self.model.predict(frame,imgsz=640,conf=.30,max_det=20,verbose=False)[0]
        return result.boxes.data.cpu().numpy()
