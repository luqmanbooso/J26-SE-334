"""Component 3 workspace embedded in the HEART desktop application."""
import logging
import tkinter as tk
import json
import queue
import threading
import time
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk
from vision_oracle.frontend.presentation import present_result

C3_ROOT = Path(__file__).resolve().parents[1]

# The four HEART components in pipeline order. C3 is this window; the others are shown so the
# screen reads as one stage of the full pipeline.
FLOW_STAGES = (
    ('C1', 'Environment perturbation', 'Applies network, battery and interruption conditions'),
    ('C2', 'Human stress interaction', 'Drives the app like a stressed user'),
    ('C3', 'Vision oracle', 'Inspects each screen (this window)'),
    ('C4', 'Self-healing synthesis', 'Turns confirmed findings into regression tests'),
)
FLOW_COLORS = {'idle': '#64748b', 'active': '#1d4ed8', 'done': '#047857', 'alert': '#be123c', 'warn': '#a16207'}
FLOW_DEFAULTS = (('idle', 'Not run here'), ('idle', 'Not run here'), ('idle', 'Ready'), ('idle', 'Waiting for a result'))
FINDING_LABELS = {'component_overlap': 'Overlapping elements', 'text_truncation': 'Cut-off text',
                  'missing_component': 'Missing image or icon', 'data_binding_null': 'Placeholder text shown'}
DECISION_COLORS = {'defect_detected': '#be123c', 'no_defect_detected': '#047857', 'inconclusive': '#a16207'}


def default_service():
    from vision_oracle.services.oracle_service import get_oracle_service
    return get_oracle_service()


class C3Workspace(ctk.CTkFrame):
    def __init__(self, master, service_factory=default_service, handover_callback=None, receiver_url_callback=None):
        super().__init__(master, fg_color='transparent')
        self.handover_callback=handover_callback
        # Called with the receiver URL when "Live from C2" starts, so the host app can fill C2's oracle field.
        self.receiver_url_callback=receiver_url_callback
        self.receiver=None;self.live_job=None;self.live_since=None
        self.service_factory=service_factory
        self.events=queue.Queue()
        self.busy=False
        self.latest=None
        self.image_path=None
        self.hierarchy_path=None
        self.session_id='mvp_'+uuid.uuid4().hex[:10]
        self.controls=[]
        self.build()
        self.poll_id=self.after(100,self.drain_events)
        self.refresh_devices()
        self.refresh_history()  # saved inspections are visible without pressing Refresh

    def label(self,parent,text,size=13,**kwargs):
        widget=ctk.CTkLabel(parent,text=text,font=ctk.CTkFont(size=size),**kwargs)
        widget.pack(anchor='w',padx=12,pady=4)
        return widget

    def buttons(self,parent,items):
        row=ctk.CTkFrame(parent,fg_color='transparent')
        row.pack(fill='x',padx=8,pady=5)
        for text,command in items:
            button=ctk.CTkButton(row,text=text,command=command,width=105,height=32)
            button.pack(side='left',expand=True,fill='x',padx=3)
            self.controls.append(button)

    def build(self):
        self.label(self,'Screen inspection',20)
        self.label(self,'Inspect a screenshot independently, or capture a connected phone.',13,wraplength=560,justify='left')
        self.label(self,'Review visual findings before taking action.',12,text_color='#a16207')
        self.build_flow()
        source=ctk.CTkFrame(self)
        source.pack(fill='x',padx=8,pady=6)
        self.buttons(source,[('Choose screenshot',self.choose_image),('Inspect screenshot',lambda:self.run('file')),('Capture my app (phone)',lambda:self.run('device'))])
        self.guide=self.label(source,'Check your own app: connect your phone with USB debugging on, open the screen you want to check, '
                              'pick the phone below, then press "Capture my app". The app\'s layout is read too, so findings name the element. '
                              'Every result is saved: reopen it later from the History tab.',11,wraplength=760,justify='left',text_color='#475569')
        self.file_label=self.label(source,'Choose an image to begin.',12,wraplength=560)
        self.build_model_selector(source)
        row=ctk.CTkFrame(source,fg_color='transparent');row.pack(fill='x',padx=8,pady=5)
        self.device=ctk.CTkOptionMenu(row,values=['No device'],width=150);self.device.pack(side='left',padx=3);self.controls.append(self.device)
        refresh=ctk.CTkButton(row,text='Refresh devices',command=self.refresh_devices,width=110);refresh.pack(side='left',padx=3);self.controls.append(refresh)
        self.slicing=ctk.CTkSwitch(row,text='Extra tile views (slower, not validated)');self.slicing.pack(side='left',padx=6);self.controls.append(self.slicing)
        self.device_label=self.label(source,'Checking connected phones…',11,wraplength=560)
        self.options_button=ctk.CTkButton(source,text='Advanced options',command=self.toggle_options,fg_color='#475569')
        self.options_button.pack(fill='x',padx=12,pady=3)
        self.controls.append(self.options_button)
        self.options=ctk.CTkFrame(source,fg_color='transparent')
        self.buttons(self.options,[('Add layout file',self.choose_hierarchy),('Remove layout',self.clear_hierarchy)])
        self.hierarchy_label=self.label(self.options,'No layout file attached',11,wraplength=560)
        self.action=ctk.CTkEntry(self.options,placeholder_text='Related action reference (optional)');self.action.pack(fill='x',padx=12,pady=5);self.controls.append(self.action)
        self.status=self.label(source,'Ready · Processing stays on this computer.',12,wraplength=560)
        self.progress=ctk.CTkProgressBar(source,mode='indeterminate');self.progress.pack(fill='x',padx=12,pady=(0,8));self.progress.set(0)
        self.feedback_pending = False
        self.tabs=ctk.CTkTabview(self,height=560);self.tabs.pack(fill='both',expand=True,padx=8,pady=8)
        inspect=self.tabs.add('Inspection');integration=self.tabs.add('Delivery')
        inspect.grid_columnconfigure(0,weight=1);inspect.grid_columnconfigure(1,weight=2);inspect.grid_rowconfigure(1,weight=1)
        self.build_result_header(inspect)
        dark=ctk.get_appearance_mode()=='Dark'
        self.preview=tk.Label(inspect,text='Screenshot preview\n(click to enlarge after inspecting)',bg='#1e293b' if dark else '#e2e8f0',fg='#94a3b8' if dark else '#334155',borderwidth=0,cursor='hand2')
        self.preview.grid(row=1,column=0,sticky='nsew',padx=4,pady=4);self.preview.bind('<Button-1>',lambda _e:self.enlarge_preview())
        right=ctk.CTkFrame(inspect,fg_color='transparent');right.grid(row=1,column=1,sticky='nsew',padx=4,pady=4)
        right.grid_columnconfigure(0,weight=1);right.grid_rowconfigure(1,weight=1)
        ctk.CTkLabel(right,text='Findings',font=ctk.CTkFont(size=13,weight='bold')).grid(row=0,column=0,sticky='w',padx=4)
        self.findings_frame=ctk.CTkScrollableFrame(right,height=200);self.findings_frame.grid(row=1,column=0,sticky='nsew')
        self.details=ctk.CTkTextbox(right,wrap='word',height=120,font=ctk.CTkFont(size=12));self.details.grid(row=2,column=0,sticky='nsew',pady=(6,0))
        self.set_text(self.details,'Choose a screenshot, then inspect it. You can also capture a connected phone.')
        self.current_preview=None;self.selected_finding=None;self.finding_cards=[]
        self.render_findings([])
        self.measurements=ctk.CTkLabel(inspect,text='Coverage — · Analysis time —',wraplength=560);self.measurements.grid(row=2,column=0,columnspan=2,sticky='w',padx=8,pady=4)
        self.export_button=ctk.CTkButton(inspect,text='Export inspection evidence',command=lambda:self.export(False),state='disabled');self.export_button.grid(row=3,column=0,columnspan=2,sticky='ew',padx=8,pady=5)
        self.review_choice = ctk.CTkOptionMenu(inspect, values=['Agree with result', 'Disagree with result'])
        self.review_choice.grid(row=4,column=0,sticky='ew',padx=8,pady=4)
        self.review_notes = ctk.CTkEntry(inspect,placeholder_text='What did you observe? (optional)')
        self.review_notes.grid(row=4,column=1,sticky='ew',padx=8,pady=4)
        self.review_button = ctk.CTkButton(inspect,text='Save my review',command=self.save_feedback,state='disabled')
        self.review_button.grid(row=5,column=0,columnspan=2,sticky='ew',padx=8,pady=4)
        self.label(integration,'Inspection → Review → Test workspace',18,wraplength=560)
        self.delivery_steps = self.label(integration,'1  Inspect screen     2  Review findings     3  Send evidence',13,wraplength=560)
        self.send_button = ctk.CTkButton(integration,text='Send to test workspace',command=self.send_handover,state='disabled')
        self.send_button.pack(fill='x',padx=8,pady=8)
        self.integration_status=self.label(integration,'Run an inspection to see its trace.',12,wraplength=560,justify='left')
        self.payload=ctk.CTkTextbox(integration,wrap='none',height=150,font=ctk.CTkFont(family='Consolas',size=11));self.payload.pack(fill='both',expand=True,padx=8,pady=4);self.set_text(self.payload,'No handover payload yet.')
        self.handover_button=ctk.CTkButton(integration,text='Export delivery payload',command=lambda:self.export(True),state='disabled');self.handover_button.pack(fill='x',padx=8,pady=5)
        self.build_live_tab(self.tabs.add('Live from C2'))
        self.build_history_tab(self.tabs.add('History'))
        self.build_model_tab(self.tabs.add('Model'))

    def build_live_tab(self,tab):
        """Receive C2's action triggers in this app: one model serves both this tab and the receiver."""
        ctk.CTkLabel(tab,text='Receive actions from the user-behaviour engine (C2)',font=ctk.CTkFont(size=14,weight='bold')).pack(anchor='w',padx=8,pady=(6,2))
        ctk.CTkLabel(tab,text='Start the receiver, then start a C2 run with this address in its "C3 Oracle URL" field. After each C2 action, '
                     'C3 captures the phone screen and its layout, inspects it, and lists the result here and in History.',
                     font=ctk.CTkFont(size=11),wraplength=760,justify='left',text_color='#475569').pack(anchor='w',padx=8)
        bar=ctk.CTkFrame(tab,fg_color='transparent');bar.pack(fill='x',padx=6,pady=6)
        self.live_button=ctk.CTkButton(bar,text='Start receiving',width=140,command=self.toggle_receiver);self.live_button.pack(side='left',padx=2)
        from vision_oracle.core.config import SERVICE_PORT
        self.live_url=f'http://127.0.0.1:{SERVICE_PORT}'
        ctk.CTkLabel(bar,text=self.live_url,font=ctk.CTkFont(family='Consolas',size=12)).pack(side='left',padx=10)
        ctk.CTkButton(bar,text='Copy address',width=110,command=self.copy_receiver_url).pack(side='left',padx=2)
        self.live_status=ctk.CTkLabel(tab,text='Receiver off.',font=ctk.CTkFont(size=12),wraplength=760,justify='left');self.live_status.pack(anchor='w',padx=8)
        self.live_list=ctk.CTkScrollableFrame(tab,height=360);self.live_list.pack(fill='both',expand=True,padx=6,pady=4)
        self.live_rows=[]

    def copy_receiver_url(self):
        self.clipboard_clear();self.clipboard_append(self.live_url)
        self.live_status.configure(text=f'Copied {self.live_url}. Paste it into C2\'s "C3 Oracle URL" field.')

    def toggle_receiver(self):
        if self.receiver:self.stop_receiver()
        else:self.start_receiver()

    def start_receiver(self):
        if self.receiver:return
        import socket
        from vision_oracle.core.config import SERVICE_PORT
        with socket.socket() as probe:
            probe.settimeout(0.3)
            if probe.connect_ex(('127.0.0.1',SERVICE_PORT))==0:
                self.live_status.configure(text=f'Port {SERVICE_PORT} is already in use. If a separate C3 server is running, C2 can use it directly; '
                                           'otherwise close the program using that port.');return
        try:
            import uvicorn
            from vision_oracle.server import create_app
            server=uvicorn.Server(uvicorn.Config(create_app(),host='127.0.0.1',port=SERVICE_PORT,log_level='warning'))
        except Exception as exc:
            self.live_status.configure(text=f'Receiver could not start: {exc}');return
        thread=threading.Thread(target=server.run,daemon=True,name='c3-receiver');thread.start()
        from datetime import datetime,timezone
        self.receiver=(server,thread);self.live_since=datetime.now(timezone.utc)
        self.live_button.configure(text='Stop receiving')
        self.live_status.configure(text='Starting. The model loads first (about 30 to 40 s the first time).')
        if self.receiver_url_callback:
            try:self.receiver_url_callback(self.live_url)
            except Exception:logging.getLogger(__name__).exception('Receiver URL callback failed')
        self.poll_live()

    def stop_receiver(self):
        if not self.receiver:return
        server,_thread=self.receiver;server.should_exit=True;self.receiver=None
        if self.live_job:self.after_cancel(self.live_job);self.live_job=None
        self.live_button.configure(text='Start receiving');self.live_status.configure(text='Receiver stopped. Results stay in History.')

    def poll_live(self):
        """While the receiver runs: report readiness and fetch C2-linked verdicts captured since it started."""
        if not self.receiver:return
        server,_thread=self.receiver
        since=self.live_since
        def worker():
            try:
                from vision_oracle.persistence.repository import get_repository
                repo=get_repository()
                pairs=[(v,getattr(repo.get_capture(v.capture_id),'timestamp_utc',None)) for v in repo.list_recent_verdicts(60)]
                self.events.put(('live',(bool(getattr(server,'started',False)),self.live_rows_since(pairs,since))))
            except Exception as exc:self.events.put(('live_error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()
        self.live_job=self.after(4000,self.poll_live)

    @staticmethod
    def live_rows_since(pairs,since):
        """Verdicts linked to a C2 action whose capture happened after the receiver started, newest first."""
        from datetime import datetime,timezone
        rows=[]
        for verdict,stamp in pairs:
            if not getattr(verdict,'action_id',None):continue
            if isinstance(stamp,str):
                try:stamp=datetime.fromisoformat(stamp.replace('Z','+00:00'))
                except ValueError:stamp=None
            if stamp is not None and stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
            if since is not None and (stamp is None or stamp<since):continue
            rows.append((verdict,stamp))
        return rows

    def show_live(self,ready,rows):
        if self.receiver:
            self.live_status.configure(text=(f'Listening at {self.live_url} · {len(rows)} C2 action(s) inspected since start.' if ready
                                             else 'Starting. The model loads first (about 30 to 40 s the first time).'))
        for row in self.live_rows:row.destroy()
        self.live_rows=[]
        labels={'defect_detected':'Defect','no_defect_detected':'No defect','inconclusive':'Inconclusive'}
        for verdict,stamp in rows:
            data=verdict.model_dump(mode='json');score=data['metadata'].get('defect_probability')
            row=ctk.CTkFrame(self.live_list,corner_radius=6);row.pack(fill='x',padx=2,pady=2)
            when=stamp.astimezone().strftime('%H:%M:%S') if hasattr(stamp,'astimezone') else '—'
            text=f"{when}   {data.get('action_id') or '—':<24}   {labels.get(data['decision'],data['decision']):<12}   {f'{score:.0%}' if isinstance(score,(int,float)) else '—':>5}   {len(data['findings'])} finding(s)"
            ctk.CTkLabel(row,text=text,font=ctk.CTkFont(family='Consolas',size=11),text_color=DECISION_COLORS.get(data['decision'])).pack(side='left',padx=6,pady=3)
            ctk.CTkButton(row,text='Open',width=60,height=24,command=lambda v=data:self.open_history(v)).pack(side='right',padx=4)
            self.live_rows.append(row)
        if rows:
            newest=rows[0][0].model_dump(mode='json')
            self.set_stage(1,'done',f'{len(rows)} action(s) sent')
            count=len(newest['findings'])
            state,text={'defect_detected':('alert',f"Latest: {count} finding{'s' if count!=1 else ''}"),'no_defect_detected':('done','Latest: no defect'),
                        'inconclusive':('warn','Latest: inconclusive')}[newest['decision']]
            if not self.latest:self.set_stage(2,state,text)

    def build_flow(self):
        """Pipeline strip: C1 -> C2 -> C3 -> C4, each with a coloured border and one status line."""
        self.flow=ctk.CTkFrame(self,fg_color='transparent');self.flow.pack(fill='x',padx=8,pady=(2,4))
        self.stage_cards=[];self.stage_status=[];self.preview_job=None
        for index,(code,name,_) in enumerate(FLOW_STAGES):
            self.flow.grid_columnconfigure(index*2,weight=1)
            card=ctk.CTkFrame(self.flow,corner_radius=8,border_width=2,border_color=FLOW_COLORS['idle'])
            card.grid(row=0,column=index*2,sticky='nsew',padx=2)
            ctk.CTkLabel(card,text=f'{code}  {name}',font=ctk.CTkFont(size=12,weight='bold'),wraplength=135).pack(anchor='w',padx=8,pady=(6,0))
            status=ctk.CTkLabel(card,text='',font=ctk.CTkFont(size=11),wraplength=135,justify='left');status.pack(anchor='w',padx=8,pady=(0,6))
            self.stage_cards.append(card);self.stage_status.append(status)
            if index<len(FLOW_STAGES)-1:
                ctk.CTkLabel(self.flow,text='→',font=ctk.CTkFont(size=18,weight='bold')).grid(row=0,column=index*2+1,padx=2)
        self.flow_note=ctk.CTkLabel(self,text='C3 runs on its own here: C1 and C2 would normally supply the perturbed run and the action reference.',font=ctk.CTkFont(size=11),wraplength=560,justify='left',text_color='#64748b')
        self.flow_note.pack(anchor='w',padx=12)
        self.preview_button=ctk.CTkButton(self,text='Preview full pipeline',command=self.preview_flow,width=150,height=24,fg_color='#475569')
        self.preview_button.pack(anchor='w',padx=12,pady=(2,4));self.controls.append(self.preview_button)
        self.reset_flow()

    def set_stage(self,index,state,text):
        color=FLOW_COLORS[state]
        self.stage_cards[index].configure(border_color=color);self.stage_status[index].configure(text=text,text_color=color)

    def reset_flow(self):
        for index,(state,text) in enumerate(FLOW_DEFAULTS):self.set_stage(index,state,text)

    def flow_from_view(self,view):
        """Show the finished inspection in the C3 card and the readiness of C4."""
        verdict=view['verdict'];count=len(verdict.get('findings') or [])
        state,text={'defect_detected':('alert',f"{count} finding{'s' if count!=1 else ''}"),
                    'no_defect_detected':('done','No defect found'),
                    'inconclusive':('warn','Inconclusive')}[verdict['decision']]
        self.set_stage(2,state,text);self.set_stage(3,'idle','Review, then send')

    def preview_flow(self):
        """Walk through the stages one by one, describing what each does in the full pipeline."""
        if self.busy or self.preview_job:return
        steps=list(enumerate(FLOW_STAGES))
        def step():
            if not self.winfo_exists():return
            if steps:
                index,(code,_,what)=steps.pop(0)
                for other in range(len(FLOW_STAGES)):self.set_stage(other,'idle' if other!=index else 'active',FLOW_DEFAULTS[other][1] if other!=index else what)
                self.preview_job=self.after(1400,step)
            else:
                self.preview_job=None
                if self.latest:self.flow_from_view(self.latest)
                else:self.reset_flow()
        step()

    def build_result_header(self,parent):
        """Verdict title, score bar with the alert level marked, and timing chips."""
        header=ctk.CTkFrame(parent,fg_color='transparent');header.grid(row=0,column=0,columnspan=2,sticky='ew',padx=4,pady=(4,2))
        header.grid_columnconfigure(0,weight=1)
        self.result_title=ctk.CTkLabel(header,text='Ready to inspect',font=ctk.CTkFont(size=18,weight='bold'));self.result_title.grid(row=0,column=0,sticky='w',padx=4)
        dark=ctk.get_appearance_mode()=='Dark'
        self.score_bg='#2b2b2b' if dark else '#ebebeb'
        self.score_canvas=tk.Canvas(header,width=300,height=34,highlightthickness=0,bg=self.score_bg);self.score_canvas.grid(row=0,column=1,sticky='e',padx=4)
        self.chips=ctk.CTkLabel(header,text='',font=ctk.CTkFont(size=11),text_color='#64748b');self.chips.grid(row=1,column=0,columnspan=2,sticky='w',padx=4)
        self.draw_score(None,None)

    def draw_score(self,score,threshold):
        c=self.score_canvas;c.delete('all');w,top,bottom=290,6,18
        c.create_rectangle(5,top,5+w,bottom,fill='#475569',width=0)
        if isinstance(score,(int,float)):
            flagged=isinstance(threshold,(int,float)) and score>=threshold
            c.create_rectangle(5,top,5+w*max(0.0,min(1.0,score)),bottom,fill='#ef4444' if flagged else '#10b981',width=0)
            c.create_text(5,bottom+8,text=f'model score {score:.0%}',anchor='w',fill='#94a3b8',font=('Segoe UI',8))
        else:
            c.create_text(5,bottom+8,text='model score —',anchor='w',fill='#94a3b8',font=('Segoe UI',8))
        if isinstance(threshold,(int,float)):
            x=5+w*threshold;c.create_line(x,top-4,x,bottom+3,fill='#f8fafc',width=2)
            c.create_text(5+w,bottom+8,text=f'alert at {threshold:.0%}',anchor='e',fill='#94a3b8',font=('Segoe UI',8))

    def render_findings(self,findings):
        """One card per finding; clicking a card highlights its box in the preview."""
        for card in self.finding_cards:card.destroy()
        self.finding_cards=[];self.selected_finding=None
        if not findings:
            card=ctk.CTkLabel(self.findings_frame,text='No findings to show.',text_color='#64748b');card.pack(anchor='w',padx=6,pady=6)
            self.finding_cards.append(card);return
        for index,finding in enumerate(findings,1):
            card=ctk.CTkFrame(self.findings_frame,border_width=1,border_color='#475569',corner_radius=8);card.pack(fill='x',padx=4,pady=3)
            kind=finding.get('type','')
            title=ctk.CTkLabel(card,text=f"{index}   {FINDING_LABELS.get(kind,kind.replace('_',' ').capitalize())}",font=ctk.CTkFont(size=13,weight='bold'))
            title.pack(anchor='w',padx=8,pady=(5,0))
            score=finding.get('confidence')
            detail=[f"Element: {finding['element_ref']}" if finding.get('element_ref') else 'Element: not matched (no layout file, or no single element under the box)',
                    f"Model score {score:.0%}" if isinstance(score,(int,float)) else 'Model score unavailable',
                    'Region shown in the preview (approximate)' if finding.get('bbox_xyxy') else 'No region given']
            body=ctk.CTkLabel(card,text='\n'.join(detail),font=ctk.CTkFont(size=11),justify='left',wraplength=420)
            body.pack(anchor='w',padx=8,pady=(0,6))
            for widget in (card,title,body):widget.bind('<Button-1>',lambda _e,i=index-1:self.select_finding(i))
            self.finding_cards.append(card)

    def select_finding(self,index):
        self.selected_finding=index
        for i,card in enumerate(self.finding_cards):
            if isinstance(card,ctk.CTkFrame):card.configure(border_color='#facc15' if i==index else '#475569',border_width=2 if i==index else 1)
        if self.current_preview:self.draw_preview(*self.current_preview,selected=index)

    def enlarge_preview(self):
        """Full-size view of the inspected screen with every finding drawn."""
        if not self.current_preview:return
        path,findings=self.current_preview
        try:
            with Image.open(path) as source:image=source.convert('RGB')
        except Exception as exc:
            messagebox.showerror('Preview unavailable',str(exc));return
        self.annotate(image,findings,self.selected_finding)
        limit=int(self.winfo_screenheight()*0.85);image.thumbnail((limit,limit))
        window=tk.Toplevel(self);window.title(Path(path).name)
        photo=ImageTk.PhotoImage(image,master=window);label=tk.Label(window,image=photo,borderwidth=0);label.pack()
        label.image=photo

    @staticmethod
    def annotate(image,findings,selected=None):
        draw=ImageDraw.Draw(image);width=max(3,image.width//200)
        for index,finding in enumerate(findings,1):
            box=finding.get('bbox_xyxy')
            if not box:continue
            chosen=selected==index-1
            color='#facc15' if chosen else '#ef4444'
            draw.rectangle(box,outline=color,width=width*2 if chosen else width)
            tag=(box[0],max(0,box[1]-width*7),box[0]+width*7,max(width*7,box[1]))
            draw.rectangle(tag,fill=color);draw.text((tag[0]+width,tag[1]+1),str(index),fill='#0f172a')

    def build_history_tab(self,tab):
        bar=ctk.CTkFrame(tab,fg_color='transparent');bar.pack(fill='x',padx=6,pady=4)
        ctk.CTkLabel(bar,text='Recent inspections saved on this computer',font=ctk.CTkFont(size=13,weight='bold')).pack(side='left')
        ctk.CTkButton(bar,text='Refresh',width=90,command=self.refresh_history).pack(side='right')
        self.history_list=ctk.CTkScrollableFrame(tab,height=420);self.history_list.pack(fill='both',expand=True,padx=6,pady=4)
        self.history_rows=[];self.history_note=ctk.CTkLabel(self.history_list,text='Press Refresh to load past inspections.',text_color='#64748b');self.history_note.pack(anchor='w',padx=6,pady=6)

    def refresh_history(self):
        def worker():
            try:
                from vision_oracle.persistence.repository import get_repository
                repo=get_repository();rows=[]
                for verdict in repo.list_recent_verdicts(30):
                    capture=repo.get_capture(verdict.capture_id)
                    rows.append((verdict,getattr(capture,'timestamp_utc',None)))
                self.events.put(('history',rows))
            except Exception as exc:self.events.put(('history_error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def show_history(self,rows):
        for row in self.history_rows:row.destroy()
        self.history_rows=[];self.history_note.configure(text='' if rows else 'No saved inspections yet.')
        labels={'defect_detected':'Defect','no_defect_detected':'No defect','inconclusive':'Inconclusive'}
        for verdict,stamp in rows:
            data=verdict.model_dump(mode='json');score=data['metadata'].get('defect_probability')
            row=ctk.CTkFrame(self.history_list,corner_radius=6);row.pack(fill='x',padx=2,pady=2)
            if isinstance(stamp,str):
                try:
                    from datetime import datetime
                    stamp=datetime.fromisoformat(stamp.replace('Z','+00:00'))
                except ValueError:pass
            when=stamp.strftime('%d %b %H:%M') if hasattr(stamp,'strftime') else str(stamp or '—')[:16]
            name=Path(data['screenshot']['storage_path']).name if data.get('screenshot') else '—'
            text=f"{when}   {labels.get(data['decision'],data['decision']):<12}   {f'{score:.0%}' if isinstance(score,(int,float)) else '—':>5}   {len(data['findings'])} finding(s)   {name}"
            ctk.CTkLabel(row,text=text,font=ctk.CTkFont(family='Consolas',size=11),text_color=DECISION_COLORS.get(data['decision'])).pack(side='left',padx=6,pady=3)
            ctk.CTkButton(row,text='Open',width=60,height=24,command=lambda v=data:self.open_history(v)).pack(side='right',padx=4)
            self.history_rows.append(row)

    def open_history(self,verdict):
        if self.busy:return
        try:
            self.clear_result();self.render(present_result({'verdict_v2':verdict}));self.tabs.set('Inspection')
            self.status.configure(text='Showing a saved inspection from history.')
        except Exception as exc:messagebox.showerror('Unable to open inspection',str(exc))

    def build_model_selector(self,parent):
        """Choose which trained adapter inspects the next screen. Only one is loaded at a time (4 GB GPU)."""
        row=ctk.CTkFrame(parent,fg_color='transparent');row.pack(fill='x',padx=8,pady=(0,4))
        ctk.CTkLabel(row,text='Model',font=ctk.CTkFont(size=12,weight='bold')).pack(side='left',padx=(4,6))
        self.adapter_choices={};self.model_menu=None
        try:
            from vision_oracle.services.oracle_service import available_adapters,active_adapter
            self.adapter_choices={label:folder for label,folder in available_adapters()}
            current=active_adapter()
            names=list(self.adapter_choices) or ['No model found']
            start=next((label for label,folder in self.adapter_choices.items() if current and folder.resolve()==Path(current).resolve()),names[0])
        except Exception as exc:
            names,start=['Model list unavailable'],'Model list unavailable';logging.getLogger(__name__).warning('Adapter discovery failed: %s',exc)
        self.model_menu=ctk.CTkOptionMenu(row,values=names,command=self.choose_model,width=330);self.model_menu.set(start)
        self.model_menu.pack(side='left',padx=3);self.controls.append(self.model_menu)
        self.model_note=ctk.CTkLabel(row,text='',font=ctk.CTkFont(size=11),text_color='#64748b',wraplength=300,justify='left');self.model_note.pack(side='left',padx=8)
        self.describe_model(start)

    def describe_model(self,label):
        note={'Fusion (experimental): screenshot + layout':'Reads the layout file as text; attach one under Advanced options. Measured weaker than the default.',
              'Earlier version (v1)':'Kept for comparison only.'}.get(label,'Loads on the next inspection.' if label in self.adapter_choices else '')
        self.model_note.configure(text=note)

    def choose_model(self,label):
        folder=self.adapter_choices.get(label)
        if folder is None:return
        if self.busy:
            self.status.configure(text='Wait for the current inspection to finish before changing the model.')
            current=self.current_adapter_label()
            if current:self.model_menu.set(current)
            return
        try:
            from vision_oracle.services.oracle_service import switch_adapter
            switch_adapter(folder)
        except Exception as exc:
            messagebox.showerror('Unable to change model',str(exc));return
        self.clear_result();self.describe_model(label)
        self.status.configure(text=f'Model changed to {folder.name}. It loads on the next inspection (about 30 to 40 s the first time).')
        self.refresh_model_tab()

    def current_adapter_label(self):
        try:
            from vision_oracle.services.oracle_service import active_adapter
            current=active_adapter()
            return next((label for label,folder in self.adapter_choices.items() if current and folder.resolve()==Path(current).resolve()),None)
        except Exception:return None

    def build_model_tab(self,tab):
        """What model is loaded and how well it measured, read from files next to the adapter."""
        self.model_box=ctk.CTkTextbox(tab,wrap='word',font=ctk.CTkFont(size=12));self.model_box.pack(fill='both',expand=True,padx=6,pady=6)
        self.refresh_model_tab()

    def refresh_model_tab(self):
        self.set_text(self.model_box,self.model_summary())

    @staticmethod
    def model_summary():
        try:
            from vision_oracle.services.oracle_service import active_adapter
            LORA_WEIGHTS_PATH=active_adapter()
        except Exception as exc:
            return f'Model configuration unavailable: {exc}'
        if not LORA_WEIGHTS_PATH:
            return 'No adapter folder found. Set C3_ADAPTER or place the adapter in vision_oracle/models.'
        folder=Path(LORA_WEIGHTS_PATH);lines=[f'Adapter: {folder.name}','Base model: Qwen2-VL-2B-Instruct, 4-bit, runs on this computer (no internet needed).']
        try:
            contract=json.loads((folder/'inference_contract.json').read_text(encoding='utf-8'))
            threshold=contract.get('decision_threshold')
            lines.append(f"Alert level: {threshold:.0%} (screens scoring at or above this are flagged)" if isinstance(threshold,(int,float)) else 'Alert level: not set')
            lines.append('Model input: screenshot and layout text' if contract.get('hierarchy_prompt') else 'Model input: screenshot only (a layout file, if added, names the affected element)')
            if contract.get('threshold_source'):lines.append(f"Alert level chosen on: {contract['threshold_source']}")
        except (OSError,ValueError) as exc:
            lines.append(f'Inference contract unavailable: {exc}')
        card=folder/'model_card.json'
        if card.exists():
            try:
                data=json.loads(card.read_text(encoding='utf-8'))
                lines+=['','Measured results'] + [f'  {item}' for item in data.get('results',[])]
                lines+=['','Limits'] + [f'  {item}' for item in data.get('limits',[])]
                if data.get('source'):lines+=['',f"Source: {data['source']}"]
            except (OSError,ValueError) as exc:lines.append(f'Model card unreadable: {exc}')
        else:
            lines+=['','No measured results file (model_card.json) for this adapter.']
        return '\n'.join(lines)

    def send_handover(self):
        if not self.latest or self.busy:
            return
        try:
            if self.handover_callback is None:
                raise RuntimeError('Test workspace is unavailable.')
            receipt = self.handover_callback(self.latest['handover'])
            if receipt.get('status') != 'received':
                raise RuntimeError('No delivery acknowledgement received.')
            self.delivery_steps.configure(text='✓ Inspected    ✓ Submitted    ✓ Received by test workspace')
            self.integration_status.configure(text='Delivered successfully. Evidence is saved in the test workspace inbox.')
            self.send_button.configure(state='disabled',text='Delivered')
            self.set_stage(3,'done','Receipt received')
        except Exception as exc:
            self.integration_status.configure(text='Delivery failed: ' + str(exc) + '\nYour result is still saved. Retry when the workspace is available.')

    def save_feedback(self):
        if not self.latest or self.busy or self.feedback_pending:
            return
        verdict_id = self.latest['verdict']['verdict_id']
        status = 'accepted' if self.review_choice.get() == 'Agree with result' else 'rejected'
        notes = self.review_notes.get().strip()
        self.feedback_pending = True
        self.review_button.configure(state='disabled')
        def worker():
            try:
                review_id = self.service_factory().repository.add_review(verdict_id=verdict_id, review_status=status, notes=notes)
                self.events.put(('feedback', 'Review saved: ' + review_id))
            except Exception as exc:
                self.events.put(('feedback', 'Could not save review: ' + str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def toggle_options(self):
        if self.options.winfo_manager():
            self.options.pack_forget()
        else:
            self.options.pack(fill='x',before=self.status)

    @staticmethod
    def set_text(widget,text):
        widget.configure(state='normal');widget.delete('1.0','end');widget.insert('1.0',text);widget.configure(state='disabled')

    def clear_result(self):
        self.latest=None
        self.reset_flow()
        self.send_button.configure(state='disabled',text='Send to test workspace')
        self.delivery_steps.configure(text='1  Inspect screen     2  Review findings     3  Send evidence')
        self.review_button.configure(state='disabled')
        self.export_button.configure(state='disabled');self.handover_button.configure(state='disabled')
        self.set_text(self.payload,'No handover payload for the current inspection.')
        self.integration_status.configure(text='Awaiting an inspection.')
        self.measurements.configure(text='Coverage — · Analysis time —')
        self.draw_score(None,None);self.chips.configure(text='');self.render_findings([])

    def choose_image(self):
        path=filedialog.askopenfilename(filetypes=[('Screenshots','*.png *.jpg *.jpeg')])
        if path:self.select_image(path)

    def select_image(self,path):
        try:
            with Image.open(path) as image:image.verify()
            self.image_path=str(Path(path).resolve());self.file_label.configure(text=Path(path).name)
            self.clear_hierarchy();self.clear_result()
            self.result_title.configure(text='Screenshot selected',text_color='#334155')
            self.set_text(self.details,'Ready for inspection. Results require human review.')
            self.draw_preview(path,[])
        except Exception as exc:messagebox.showerror('Unable to open screenshot',str(exc))

    def choose_hierarchy(self):
        path=filedialog.askopenfilename(filetypes=[('Hierarchy','*.xml')])
        if path:self.hierarchy_path=path;self.hierarchy_label.configure(text=Path(path).name)

    def clear_hierarchy(self):
        self.hierarchy_path=None;self.hierarchy_label.configure(text='No layout file attached')

    def refresh_devices(self):
        def worker():
            try:
                from common.adb import AdbDevice
                devices=AdbDevice.list_devices()
                self.events.put(('devices',(devices,'Select a phone.' if devices else 'No phone attached. Screenshot mode is available.')))
            except Exception as exc:self.events.put(('devices',([],str(exc))))
        threading.Thread(target=worker,daemon=True).start()

    def run(self,source):
        if self.busy:return
        if source=='file' and not self.image_path:
            messagebox.showinfo('Choose a screenshot','Select an image before inspection.');return
        serial=self.device.get()
        if source=='device' and serial=='No device':
            messagebox.showinfo('Connect a phone','Attach an Android device, enable USB debugging, then refresh devices.');return
        image_path,hierarchy_path=self.image_path,self.hierarchy_path
        action_id=self.action.get().strip() or None;slicing=bool(self.slicing.get())
        self.clear_result();self.busy=True;self.started=time.monotonic()
        if self.preview_job:self.after_cancel(self.preview_job);self.preview_job=None
        self.set_stage(2,'active','Inspecting…')
        for widget in self.controls:widget.configure(state='disabled')
        self.result_title.configure(text='Inspection in progress…',text_color='#1d4ed8')
        self.set_text(self.details,'Loading the local model and inspecting the screen. The first run can take longer.')
        self.progress.configure(mode='indeterminate');self.progress.start();self.tabs.set('Inspection')
        if source=='device':self.clear_preview('Capturing the selected phone…')
        def worker():
            try:
                service=self.service_factory()
                if source=='file':
                    hierarchy=Path(hierarchy_path).read_text(encoding='utf-8') if hierarchy_path else None
                    result=service.evaluate(image_input=image_path,raw_hierarchy=hierarchy,action_id=action_id,enable_sahi=slicing,session_id=self.session_id)
                else:result=service.evaluate_device(serial=serial,action_id=action_id,enable_sahi=slicing,session_id=self.session_id)
                self.events.put(('result',present_result(result)))
            except Exception as exc:self.events.put(('error',f'{type(exc).__name__}: {exc}'))
        threading.Thread(target=worker,daemon=True).start()

    def finish(self):
        self.busy=False;self.progress.stop();self.progress.configure(mode='determinate');self.progress.set(0)
        for widget in self.controls:widget.configure(state='normal')

    def drain_events(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='feedback':
                    self.feedback_pending = False
                    self.status.configure(text=value)
                    self.review_button.configure(state='normal' if self.latest and not self.busy else 'disabled')
                elif kind=='devices':
                    devices,note=value;self.device.configure(values=devices or ['No device']);self.device.set(devices[0] if devices else 'No device');self.device_label.configure(text=note)
                elif kind=='error':
                    self.finish();self.clear_result();self.result_title.configure(text='Inspection failed',text_color='#be123c')
                    self.set_stage(2,'alert','Failed. Retry')
                    self.set_text(self.details,value+'\n\nNo verdict was produced. Check model files, GPU memory or device connection, then retry.')
                    self.status.configure(text='Failed. You can retry.')
                elif kind=='result':self.finish();self.render(value)
                elif kind=='history':self.show_history(value)
                elif kind=='history_error':self.history_note.configure(text='Could not load history: '+value)
                elif kind=='live':self.show_live(*value)
                elif kind=='live_error':self.live_status.configure(text='Could not read results: '+value)
        except queue.Empty:
            pass
        except Exception:
            logging.getLogger(__name__).exception('Unable to render inspection event')
            self.finish()
            self.status.configure(text='Display update failed. You can retry the inspection.')
        finally:
            if self.winfo_exists():
                self.poll_id=self.after(100,self.drain_events)
        if self.busy:self.status.configure(text=f'Loading / inspecting · {time.monotonic()-self.started:.0f}s elapsed')

    def render(self,view):
        self.latest=view;verdict=view['verdict']
        self.flow_from_view(view)
        self.send_button.configure(state='normal')
        self.delivery_steps.configure(text='✓ Inspection complete    → Review findings    ○ Send evidence')
        self.review_button.configure(state='normal')
        self.review_notes.delete(0,'end')
        color={'defect_detected':'#be123c','no_defect_detected':'#047857','inconclusive':'#a16207'}[verdict['decision']]
        self.result_title.configure(text=view['title'],text_color=color);self.set_text(self.details,view['summary'])
        self.draw_score(verdict['metadata'].get('defect_probability'),verdict['metadata'].get('decision_threshold'))
        self.chips.configure(text='   ·   '.join(x for x in (view.get('verdict_time'),view.get('localization_time'),view['coverage']) if x))
        self.render_findings(verdict['findings'])
        elapsed=f"{view['total_ms']/1000:.2f}s" if view['total_ms'] is not None else 'unavailable'
        split=' · '.join(x for x in (view.get('verdict_time'),view.get('localization_time')) if x)
        self.measurements.configure(text=f"{view['coverage']} · Analysis: {elapsed}"+(f" ({split})" if split else '')+f" · {verdict['analysis_status']}")
        self.status.configure(text='Saved on this computer. Review the findings; reopen this inspection any time from the History tab.')
        self.refresh_history()
        self.draw_preview(verdict['screenshot']['storage_path'],verdict['findings'])
        self.integration_status.configure(text=f"Session: {verdict['session_id']}\nAction: {verdict.get('action_id') or 'None (unlinked)'}\nCapture: {verdict['capture_id']}\nVerdict: {verdict['verdict_id']}\nHandover: {view['outcome'].replace('_',' ')} · prepared, not sent")
        self.set_text(self.payload,json.dumps(view['handover'],indent=2))
        self.export_button.configure(state='normal');self.handover_button.configure(state='normal')

    def draw_preview(self,path,findings,selected=None):
        try:
            with Image.open(path) as source:image=source.convert('RGB')
            self.annotate(image,findings,selected)
            self.current_preview=(path,findings)
            image.thumbnail((320,560))
            # Bind to this widget's Tcl interpreter. Keep the old image alive
            # until Tk has switched the label to the new image.
            new_image = ImageTk.PhotoImage(image, master=self.preview)
            self.preview.configure(image=new_image, text='')
            self.preview_image = new_image
        except Exception as exc:
            self.clear_preview(f'Preview unavailable\n{exc}')

    def clear_preview(self, text='Screenshot preview'):
        # Clear the stale Tcl image name in the same native configure call.
        self.preview.configure(image='', text=text)
        self.preview_image = None
        self.current_preview = None

    def export(self,handover):
        if not self.latest or self.busy:return
        data=self.latest['handover' if handover else 'verdict'];suffix='c4_handover' if handover else 'evidence'
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile=f"{data['verdict_id']}_{suffix}.json",filetypes=[('JSON','*.json')])
        if path:
            try:Path(path).write_text(json.dumps(data,indent=2),encoding='utf-8');self.status.configure(text='JSON exported. No downstream service was called.')
            except OSError as exc:messagebox.showerror('Export failed',str(exc))

    def destroy(self):
        self.after_cancel(self.poll_id)
        if self.preview_job:self.after_cancel(self.preview_job)
        self.stop_receiver()
        super().destroy()
