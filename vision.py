"""Latest-frame capture and vision worker, separate from the user interface."""
import threading
import queue
import time
import cv2
from detector import Detector,Association


class Vision:
    def __init__(self, index=0, target="Ball"):
        self.target=target
        self.loading="Loading YOLOE and your reference photos..."
        self.commands=queue.Queue()
        self.stop_event=threading.Event()
        self.condition=threading.Condition()
        self.lock=threading.Lock()
        self.latest=None
        self.result=None
        self.error=None
        self.sequence=0
        self.index=index
        self.reader=threading.Thread(target=self._capture,daemon=True)
        self.worker=threading.Thread(target=self._process,daemon=True)
        self.reader.start();self.worker.start()

    def _capture(self):
        import sys
        cap=None
        try:
            backend=cv2.CAP_DSHOW if sys.platform=='win32' else cv2.CAP_ANY
            cap=cv2.VideoCapture(self.index,backend)
            if not cap.isOpened():raise RuntimeError('Camera unavailable. Close other camera apps or change Camera number.')
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,640);cap.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
            cap.set(cv2.CAP_PROP_FPS,30)
            while not self.stop_event.is_set():
                ok,frame=cap.read()
                if not ok:raise RuntimeError('Camera stopped. Click Start camera to reconnect.')
                frame=cv2.flip(cv2.resize(frame,(640,480)),1)
                with self.condition:
                    self.sequence+=1
                    self.latest=(self.sequence,time.monotonic(),frame)
                    self.condition.notify_all()
        except Exception as exc:
            self.error=str(exc)
            with self.condition:self.condition.notify_all()
        finally:
            if cap is not None:cap.release()

    def _process(self):
        sequence=0;generation=0;association=Association(self.target)
        try:
            detector=Detector();self.loading=None
            while not self.stop_event.is_set():
                while True:
                    try:cmd=self.commands.get_nowait()
                    except queue.Empty:break
                    if cmd[0]=='target':
                        association=Association(cmd[1]);generation=cmd[2]
                    elif cmd[0]=='reset':association.reset();generation=cmd[1]
                with self.condition:
                    self.condition.wait_for(lambda:self.sequence!=sequence or self.error or self.stop_event.is_set(),timeout=.1)
                    if self.error or self.stop_event.is_set():break
                    if self.latest is None or self.sequence==sequence:continue
                    sequence,captured,frame=self.latest
                    frame=frame.copy()
                start=time.monotonic()
                rows=detector.detect(frame)
                now=time.monotonic();elapsed=now-start
                box=association.choose(rows,now) if now-captured<.3 else None
                state=association.state if now-captured<.3 else 'Processing too slow - movement paused'
                with self.lock:
                    self.result={'frame':frame,'box':box,'state':state,'captured':captured,
                                 'fps':1/max(elapsed,.001),'selected':True,'generation':generation,
                                 'device':detector.device_name}
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.error='YOLOE error: '+str(exc)
            self.loading=None

    def snapshot(self):
        with self.lock:return self.result

    def close(self):
        self.stop_event.set()
        with self.condition:self.condition.notify_all()
        self.reader.join(timeout=.4)
        self.worker.join(timeout=.4)
