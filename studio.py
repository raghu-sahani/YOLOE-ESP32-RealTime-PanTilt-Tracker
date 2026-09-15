"""Run START.bat on Windows, or python studio.py after installing requirements."""
import json
import queue
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
import cv2
from PIL import Image,ImageTk
from serial.tools import list_ports
from transport import Link,track_relative
from detector import centre
from vision import Vision

ROOT=Path(__file__).resolve().parent


class Studio:
    def __init__(self, root):
        self.root=root;root.title('PanTilt Studio - YOLOE photo tracking')
        root.geometry('1100x820');root.minsize(1060,760);root.configure(bg='#101827')
        style=ttk.Style();style.theme_use('clam')
        style.configure('.',background='#101827',foreground='#e5edf8',font=('Segoe UI',10))
        style.configure('TButton',padding=8,background='#263954')
        style.map('TButton',background=[('active','#365577')])
        style.configure('TLabelframe',background='#101827',bordercolor='#35445d')
        style.configure('TLabelframe.Label',foreground='#71ccff')
        style.configure('TEntry',fieldbackground='#243249',foreground='white')
        style.configure('TCombobox',fieldbackground='#243249',foreground='white')
        style.configure('TSpinbox',fieldbackground='#243249',foreground='white')
        style.configure('TCheckbutton',background='#101827')
        self.link=Link();self.vision=None;self.connecting=False;self.events=queue.Queue()
        self.generation=0;self.frozen=False;self.drag_start=None;self.drag_rect=None
        self.frame=None;self.last_result=None;self.last_ack_text='No commands acknowledged yet'
        self.last_pulse=(1500,1500);self.last_hold=0;self.last_draw=0;self.photo=None
        self.port=tk.StringVar(value='COM7');self.camera=tk.IntVar(value=0)
        self.follow=tk.BooleanVar(value=False);self.target=tk.StringVar(value="Ball")
        self.reverse_pan=tk.BooleanVar();self.reverse_tilt=tk.BooleanVar();self.gain=tk.DoubleVar(value=1.0);self.track_speed=tk.DoubleVar(value=2.5)
        self.left=tk.IntVar(value=1100);self.right=tk.IntVar(value=1900)
        self.top=tk.IntVar(value=1200);self.bottom=tk.IntVar(value=1800)
        self.status=tk.StringVar(value='Starting camera...')
        self.connection=tk.StringVar(value='ESP32 disconnected - camera preview still works')
        self.motion=tk.StringVar(value='Commanded PWM: pan 1500 us | tilt 1500 us')
        self.ack_text=tk.StringVar(value=self.last_ack_text)
        self.telemetry=tk.StringVar(value='Camera: waiting')
        self._load()
        ttk.Label(root,text='PanTilt Studio',font=('Segoe UI',23,'bold')).pack(anchor='w',padx=20,pady=(14,0))
        ttk.Label(root,text='Your photos are loaded. Choose Ball or Wheel, then start following.',foreground='#a8bdd7').pack(anchor='w',padx=20,pady=(0,12))
        body=ttk.Frame(root);body.pack(fill='both',expand=True,padx=20)
        left=ttk.Frame(body);left.grid(row=0,column=0,sticky='nw')
        side=ttk.Frame(body);side.grid(row=0,column=1,sticky='nsew',padx=(18,0));body.columnconfigure(1,weight=1)
        self.canvas=tk.Canvas(left,width=640,height=480,bg='#020617',highlightthickness=0)
        self.canvas.pack();self.canvas.create_text(320,240,text='Opening laptop camera...',fill='white',font=('Segoe UI',16))
        ttk.Label(left,textvariable=self.status,wraplength=635,font=('Segoe UI',11,'bold'),foreground='#83dfb3').pack(anchor='w',pady=(10,4))
        ttk.Label(left,textvariable=self.telemetry,foreground='#a8bdd7').pack(anchor='w')
        controls=ttk.Frame(left);controls.pack(fill='x',pady=10)
        ttk.Label(controls,text='Target:').pack(side='left')
        target_box=ttk.Combobox(controls,textvariable=self.target,values=['Ball','Wheel'],state='readonly',width=8)
        target_box.pack(side='left',padx=5)
        target_box.bind('<<ComboboxSelected>>',lambda e:self.change_target())
        ttk.Button(controls,text='Start following',command=self.start_following).pack(side='left',padx=5)
        ttk.Button(controls,text='STOP movement',command=self.stop_motion).pack(side='left',padx=5)
        ttk.Checkbutton(left,text='Follow selected object with servos',variable=self.follow,command=self._follow_changed).pack(anchor='w',pady=3)
        ttk.Label(left,text='No mouse selection or repeated lock. Target loss holds the last servo command.',wraplength=630).pack(anchor='w',pady=3)
        ttk.Label(left,text='Camera stays fixed in your laptop. Servo positions below are commands, not measured angles.',wraplength=630,foreground='#9aaec7').pack(anchor='w',pady=8)
        self._connection_panel(side)
        self._motor_panel(side)
        ttk.Button(side,text='Save settings',command=self._save).pack(fill='x',pady=8)
        ttk.Label(side,text='New sketch required: ESP32_Studio.ino\nPan GPIO18 | Tilt GPIO19\nExternal servo supply + common GND',wraplength=350,foreground='#9aaec7').pack(anchor='w',pady=4)
        root.bind('<Escape>',lambda e:self.stop_motion())
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.refresh_ports();self.start_camera();root.after(40,self.tick)

    def _connection_panel(self,parent):
        panel=ttk.LabelFrame(parent,text='1. Connection',padding=10);panel.pack(fill='x')
        row=ttk.Frame(panel);row.pack(fill='x')
        self.port_box=ttk.Combobox(row,textvariable=self.port,width=12);self.port_box.pack(side='left')
        ttk.Button(row,text='Refresh',command=self.refresh_ports).pack(side='left',padx=5)
        ttk.Button(row,text='Connect',command=self.connect).pack(side='left')
        ttk.Label(panel,textvariable=self.connection,wraplength=340,foreground='#83dfb3').pack(anchor='w',pady=7)
        ttk.Label(panel,textvariable=self.ack_text,wraplength=340).pack(anchor='w')
        row=ttk.Frame(panel);row.pack(fill='x',pady=(8,0))
        ttk.Label(row,text='Camera').pack(side='left')
        ttk.Spinbox(row,from_=0,to=5,textvariable=self.camera,width=4).pack(side='left',padx=8)
        ttk.Button(row,text='Start camera',command=self.start_camera).pack(side='left')

    def _motor_panel(self,parent):
        panel=ttk.LabelFrame(parent,text='2. Motor test and calibration',padding=10);panel.pack(fill='x',pady=(12,0))
        ttk.Label(panel,text='Test buttons pause following. Each test moves only one axis.',wraplength=330).pack(anchor='w')
        row=ttk.Frame(panel);row.pack(fill='x',pady=5)
        for label,dp,dt in [('Pan -',-100,0),('Pan +',100,0),('Tilt -',0,-100),('Tilt +',0,100)]:
            ttk.Button(row,text=label,width=6,command=lambda dp=dp,dt=dt:self.jog_motor(dp,dt)).pack(side='left',padx=1)
        ttk.Button(panel,text='Centre both servos',command=self.centre_motors).pack(fill='x')
        ttk.Label(panel,textvariable=self.motion,wraplength=340).pack(anchor='w',pady=7)
        ttk.Checkbutton(panel,text='Reverse pan (left / right)',variable=self.reverse_pan).pack(anchor='w')
        ttk.Checkbutton(panel,text='Reverse tilt (up / down)',variable=self.reverse_tilt).pack(anchor='w')
        ttk.Label(panel,text='Movement gain (distance moved, not motor speed)').pack(anchor='w',pady=(8,0))
        ttk.Scale(panel,from_=.5,to=2.0,variable=self.gain).pack(fill='x')
        self.gain_label=ttk.Label(panel,text='1.00');self.gain_label.pack(anchor='e')
        ttk.Label(panel,text='Tracking speed (response rate)').pack(anchor='w',pady=(8,0))
        ttk.Scale(panel,from_=0.5,to=5.0,variable=self.track_speed).pack(fill='x')
        self.speed_label=ttk.Label(panel,text='2.50x');self.speed_label.pack(anchor='e')
        ttk.Label(panel,text='PWM endpoints in microseconds (900-2100)\nStart with defaults; check mechanical clearance.',wraplength=340).pack(anchor='w',pady=(5,4))
        grid=ttk.Frame(panel);grid.pack(fill='x')
        for i,(name,var) in enumerate([('Left',self.left),('Right',self.right),('Top',self.top),('Bottom',self.bottom)]):
            ttk.Label(grid,text=name).grid(row=i//2,column=(i%2)*2,sticky='w',padx=3,pady=3)
            ttk.Spinbox(grid,from_=900,to=2100,increment=25,textvariable=var,width=7).grid(row=i//2,column=(i%2)*2+1,padx=3)

    def refresh_ports(self):
        names=[p.device for p in list_ports.comports()];self.port_box['values']=names
        if self.port.get() not in names and len(names)==1:self.port.set(names[0])

    def connect(self):
        if self.connecting:return
        self.connecting=True;name=self.port.get().strip()
        self.connection.set('Connecting and checking the new ESP32 sketch...')
        def task():
            try:self.link.connect(name);self.events.put(('connected',name))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=task,daemon=True).start()

    def start_camera(self):
        try:index=self.camera.get()
        except tk.TclError:return
        if self.vision:self.vision.close()
        self.frame=None;self.frozen=False;self.generation=0;self.last_result=None
        self.vision=Vision(index,self.target.get())
        self.status.set('Starting camera...');self._hold()

    def _hold(self):
        if self.connecting:return
        try:
            if time.monotonic()-self.last_hold>.15:self.link.hold();self.last_hold=time.monotonic()
        except Exception as exc:self._serial_error(exc)

    def _serial_error(self,exc):
        self.follow.set(False);self.connection.set(str(exc))
        self.link.close()

    def _follow_changed(self):
        if not self.follow.get():self._hold()

    def change_target(self):
        self.generation+=1
        if self.vision:self.vision.commands.put(('target',self.target.get(),self.generation))
        self._hold()

    def start_following(self):
        self.follow.set(True)
        self.status.set('Looking for '+self.target.get()+f' from current servo position {self.last_pulse[0]}/{self.last_pulse[1]} us')

    def stop_motion(self):
        self.follow.set(False);self._hold();self.status.set('Movement paused. Selection is still remembered.')

    def jog_motor(self,dp,dt):
        if self.connecting or self.link.port is None:
            self.connection.set('Connect the ESP32 first, then use the motor test.');return
        self.follow.set(False)
        try:
            left,right,top,bottom=(self.left.get(),self.right.get(),self.top.get(),self.bottom.get())
            lo_pan,hi_pan=sorted((left,right));lo_tilt,hi_tilt=sorted((top,bottom))
            pan=max(lo_pan,min(hi_pan,self.last_pulse[0]+dp))
            tilt=max(lo_tilt,min(hi_tilt,self.last_pulse[1]+dt))
            self.link.send(pan,tilt,force=True);self.last_pulse=(pan,tilt)
        except Exception as exc:self._serial_error(exc)

    def centre_motors(self):
        if self.connecting or self.link.port is None:
            self.connection.set('Connect the ESP32 first, then use the motor test.');return
        self.follow.set(False)
        try:self.link.send(1500,1500,force=True);self.last_pulse=(1500,1500)
        except Exception as exc:self._serial_error(exc)

    def _draw(self,frame,box):
        shown=frame.copy()
        if box:
            x,y,w,h=map(round,box);cx,cy=map(round,centre(box))
            cv2.rectangle(shown,(x,y),(x+w,y+h),(70,240,110),2)
            cv2.drawMarker(shown,(cx,cy),(70,240,110),cv2.MARKER_CROSS,16,2)
        self.photo=ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(shown,cv2.COLOR_BGR2RGB)))
        self.canvas.delete('all');self.canvas.create_image(0,0,anchor='nw',image=self.photo)

    def tick(self):
        try:
            while True:
                kind,message=self.events.get_nowait();self.connecting=False
                if kind=='connected':
                    self.connection.set(message+' connected - correct firmware confirmed')
                else:self.connection.set(message)
        except queue.Empty:pass
        except Exception as exc:self._serial_error(exc)
        if not self.connecting:
            try:self.link.poll()
            except Exception as exc:self._serial_error(exc)
        if self.link.ack:
            self.ack_text.set(f'ESP32 acknowledged: {self.link.ack[0]} / {self.link.ack[1]} us')
            if not self.follow.get():
                self.last_pulse=self.link.ack
        self.motion.set(f'Commanded PWM: pan {self.last_pulse[0]} | tilt {self.last_pulse[1]} us')
        self.gain_label.configure(text=f'{self.gain.get():.2f}')
        self.speed_label.configure(text=f'{self.track_speed.get():.2f}x')
        if self.vision:
            result=self.vision.snapshot()
            if self.vision.loading:
                self.status.set(self.vision.loading)
            elif self.vision.error:
                self.status.set(self.vision.error);self._hold()
            elif result is not None and not self.frozen:
                self.frame=result['frame'];self.last_result=result
                age=time.monotonic()-result['captured']
                active=result['box'] is not None and age<.3 and result['generation']==self.generation
                label=result['state'] if age<.3 else 'Camera/processing delayed - movement paused'
                if not self.follow.get():label+=' | Motors paused'
                self.status.set(label)
                self.telemetry.set(f"Processing {result['fps']:.0f} FPS | Frame age {age*1000:.0f} ms | "+result['device'])
                if time.monotonic()-self.last_draw>.055:
                    self._draw(self.frame,result['box'] if active else None);self.last_draw=time.monotonic()
                if active and self.follow.get() and not self.connecting:
                    try:
                        ends=tuple(v.get() for v in (self.left,self.right,self.top,self.bottom))
                        if not all(900<=v<=2100 for v in ends):raise ValueError('Endpoints must be 900-2100 us')
                        p,t=track_relative(self.last_pulse,centre(result['box']),(640,480),ends,self.reverse_pan.get(),self.reverse_tilt.get(),self.gain.get(),self.track_speed.get())
                        if self.link.send(p,t):
                            self.last_pulse=(p,t)
                    except (tk.TclError,ValueError) as exc:self.status.set(str(exc));self._hold()
                    except Exception as exc:self._serial_error(exc)
                elif not active:self._hold()
        self.root.after(15,self.tick)

    def _load(self):
        try:
            data=json.loads((ROOT/'settings.json').read_text())
            for name in ('port','camera','target','reverse_pan','reverse_tilt','gain','track_speed','left','right','top','bottom'):
                if name in data:getattr(self,name).set(data[name])
        except (OSError,ValueError,tk.TclError):pass

    def _save(self):
        try:
            data={name:getattr(self,name).get() for name in ('port','camera','target','reverse_pan','reverse_tilt','gain','track_speed','left','right','top','bottom')}
            (ROOT/'settings.json').write_text(json.dumps(data,indent=2))
            self.status.set('Settings saved.')
        except (OSError,tk.TclError) as exc:messagebox.showerror('Could not save settings',str(exc))

    def close(self):
        if self.vision:self.vision.close()
        if not self.connecting:self.link.close()
        self.root.destroy()


if __name__=='__main__':
    cv2.setNumThreads(2)
    root=tk.Tk();Studio(root);root.mainloop()
