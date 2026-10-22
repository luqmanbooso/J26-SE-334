"""Component 3 workspace embedded in the HEART desktop application."""
import asyncio  # noqa: F401  imported here on the main thread: torch pulls it in from a worker thread and, racing another
# thread's first import of it, saw a half-initialised module ("NameError: name 'base_events' is not defined")
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

FINDING_LABELS = {'component_overlap': 'Overlapping elements', 'text_truncation': 'Cut-off text',
                  'missing_component': 'Missing image or icon', 'data_binding_null': 'Placeholder text shown'}
# HEART design tokens: the same values as THEME in heart_desktop_app.py, so this tab reads as part of the app.
T = {'card': '#ffffff', 'box': '#f1f5f9', 'border': '#e2e8f0', 'heading': '#0f172a', 'body': '#334155', 'muted': '#64748b',
     'primary': '#2563eb', 'primary_hover': '#1d4ed8', 'primary_light': '#eff6ff', 'primary_border': '#bfdbfe',
     'success': '#059669', 'success_bg': '#ecfdf5', 'danger': '#dc2626', 'danger_bg': '#fef2f2',
     'warning': '#d97706', 'warning_bg': '#fffbeb'}
FONT = 'Segoe UI'
DECISION_COLORS = {'defect_detected': T['danger'], 'no_defect_detected': T['success'], 'inconclusive': T['warning']}
DECISION_FILL = {'defect_detected': T['danger_bg'], 'no_defect_detected': T['success_bg'], 'inconclusive': T['warning_bg']}


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

    def font(self,size=10,bold=False,family=FONT):
        # One font object per style, kept for the workspace's lifetime. Fonts made per call get garbage-collected
        # on whichever thread runs GC, and a Tk font freed off the main thread blocks that thread (it hung the receiver).
        fonts=self.__dict__.setdefault('_fonts',{})
        key=(family,size,bold)
        if key not in fonts:fonts[key]=ctk.CTkFont(family=family,size=size,weight='bold' if bold else 'normal')
        return fonts[key]

    def label(self,parent,text,size=10,bold=False,**kwargs):
        kwargs.setdefault('text_color',T['body'])
        widget=ctk.CTkLabel(parent,text=text,font=self.font(size,bold),**kwargs)
        widget.pack(anchor='w',padx=14,pady=3)
        return widget

    def card(self,parent,title,subtitle=None):
        """A HEART card: white panel, slate header strip with the title left and a muted subtitle right."""
        card=ctk.CTkFrame(parent,fg_color=T['card'],corner_radius=10,border_width=1,border_color=T['border'])
        card.pack(fill='x',padx=2,pady=(0,10))
        head=ctk.CTkFrame(card,fg_color=T['box'],height=32,corner_radius=8);head.pack(fill='x',padx=6,pady=(6,8));head.pack_propagate(False)
        ctk.CTkLabel(head,text=title,font=self.font(11,True),text_color=T['heading']).pack(side='left',padx=10)
        if subtitle:ctk.CTkLabel(head,text=subtitle,font=self.font(9),text_color=T['muted']).pack(side='right',padx=10)
        return card

    def button(self,parent,text,command,kind='primary',width=130,height=30):
        """HEART buttons: one filled primary action per group, outlined secondaries, text-only links."""
        style={'primary':dict(fg_color=T['primary'],hover_color=T['primary_hover'],text_color='#ffffff',border_width=0),
               'secondary':dict(fg_color=T['card'],hover_color=T['primary_light'],text_color=T['primary'],border_width=1,border_color=T['primary_border']),
               'link':dict(fg_color='transparent',hover_color=T['box'],text_color=T['primary'],border_width=0)}[kind]
        return ctk.CTkButton(parent,text=text,command=command,width=width,height=height,corner_radius=6,font=self.font(10,True),**style)

    def menu(self,parent,values,command=None,width=200):
        return ctk.CTkOptionMenu(parent,values=values,command=command,width=width,height=28,font=self.font(10,True),
                                 fg_color=T['box'],text_color=T['heading'],button_color=T['border'],button_hover_color=T['primary_border'],
                                 dropdown_font=self.font(10))

    def buttons(self,parent,items):
        row=ctk.CTkFrame(parent,fg_color='transparent')
        row.pack(fill='x',padx=10,pady=4)
        for text,command in items:
            button=self.button(row,text,command,'secondary',width=130);button.pack(side='left',padx=4)
            self.controls.append(button)

    def build(self):
        source=self.card(self,'Inspect a screen','Local model · nothing leaves this computer')
        actions=ctk.CTkFrame(source,fg_color='transparent');actions.pack(fill='x',padx=10,pady=(0,6))
        for text,command,kind in (('Capture my app (phone)',lambda:self.run('device'),'primary'),
                                  ('Choose screenshot',self.choose_image,'secondary'),
                                  ('Inspect screenshot',lambda:self.run('file'),'secondary')):
            button=self.button(actions,text,command,kind,width=180 if kind=='primary' else 150,height=32);button.pack(side='left',padx=4)
            self.controls.append(button)
        tip=ctk.CTkFrame(source,fg_color=T['primary_light'],border_width=1,border_color=T['primary_border'],corner_radius=8)
        tip.pack(fill='x',padx=14,pady=(2,8))
        ctk.CTkLabel(tip,text='Check a screen from your own app',font=self.font(10,True),text_color=T['heading']).pack(anchor='w',padx=12,pady=(8,0))
        self.guide=ctk.CTkLabel(tip,text='1   Connect your phone with USB debugging on, then press Refresh devices.\n'
                                '2   Open the screen you want to check on the phone.\n'
                                '3   Press "Capture my app" to inspect your own app. Its layout is read too, so findings name the element.\n'
                                'Every result is saved: reopen it any time from the History tab.',
                                font=self.font(10),text_color=T['body'],justify='left',wraplength=760)
        self.guide.pack(anchor='w',padx=12,pady=(0,8))
        self.file_label=self.label(source,'No screenshot chosen.',9,text_color=T['muted'],wraplength=560)
        form=ctk.CTkFrame(source,fg_color='transparent');form.pack(fill='x',padx=10,pady=2)
        form.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(form,text='Model',font=self.font(10,True),text_color=T['body'],width=60,anchor='w').grid(row=0,column=0,sticky='w',padx=4,pady=4)
        model_row=ctk.CTkFrame(form,fg_color='transparent');model_row.grid(row=0,column=1,sticky='w')
        self.build_model_selector(model_row)
        ctk.CTkLabel(form,text='Device',font=self.font(10,True),text_color=T['body'],width=60,anchor='w').grid(row=1,column=0,sticky='w',padx=4,pady=4)
        row=ctk.CTkFrame(form,fg_color='transparent');row.grid(row=1,column=1,sticky='w')
        self.device=self.menu(row,['No device'],width=200);self.device.pack(side='left',padx=(0,6));self.controls.append(self.device)
        refresh=self.button(row,'Refresh devices',self.refresh_devices,'secondary',width=130,height=28);refresh.pack(side='left',padx=3);self.controls.append(refresh)
        self.slicing=ctk.CTkSwitch(row,text='Extra tile views (slower, not validated)',font=self.font(9),text_color=T['muted'],progress_color=T['primary'])
        self.slicing.pack(side='left',padx=10);self.controls.append(self.slicing)
        self.device_label=self.label(source,'Checking connected phones…',9,text_color=T['muted'],wraplength=560)
        self.options_button=self.button(source,'Advanced options ▾',self.toggle_options,'link',width=150,height=24)
        self.options_button.pack(anchor='w',padx=10,pady=(0,2))
        self.controls.append(self.options_button)
        self.options=ctk.CTkFrame(source,fg_color='transparent')
        self.buttons(self.options,[('Add layout file',self.choose_hierarchy),('Remove layout',self.clear_hierarchy)])
        self.hierarchy_label=self.label(self.options,'No layout file attached',9,text_color=T['muted'],wraplength=560)
        self.action=ctk.CTkEntry(self.options,placeholder_text='Related action reference (optional)',height=28,font=self.font(10),
                                 fg_color=T['card'],border_color=T['border'],text_color=T['heading'])
        self.action.pack(fill='x',padx=14,pady=4);self.controls.append(self.action)
        self.status=self.label(source,'Ready.',10,text_color=T['body'],wraplength=760)
        self.progress=ctk.CTkProgressBar(source,mode='indeterminate',height=6,progress_color=T['primary'],fg_color=T['box'])
        self.progress.set(0)  # packed only while an inspection runs
        ctk.CTkFrame(source,fg_color='transparent',height=6).pack()
        self.feedback_pending = False

        self.tabs=ctk.CTkTabview(self,height=560,fg_color=T['card'],border_width=1,border_color=T['border'],corner_radius=10,
                                 segmented_button_fg_color=T['box'],segmented_button_selected_color=T['primary'],
                                 segmented_button_selected_hover_color=T['primary_hover'],segmented_button_unselected_color='#f8fafc',
                                 segmented_button_unselected_hover_color=T['border'],text_color=T['heading'])
        self.tabs.pack(fill='both',expand=True,padx=2,pady=(0,8))
        self.tabs._segmented_button.configure(font=self.font(10,True))
        inspect=self.tabs.add('Inspection');integration=self.tabs.add('Delivery')
        inspect.grid_columnconfigure(0,weight=1);inspect.grid_columnconfigure(1,weight=2);inspect.grid_rowconfigure(1,weight=1)
        self.build_result_header(inspect)
        self.preview=tk.Label(inspect,text='No screen yet\n\nCapture your app or choose a screenshot.\nClick the preview to enlarge it.',
                              bg=T['box'],fg=T['muted'],font=(FONT,9),borderwidth=0,cursor='hand2',justify='center')
        self.preview.grid(row=1,column=0,sticky='nsew',padx=(10,6),pady=6);self.preview.bind('<Button-1>',lambda _e:self.enlarge_preview())
        right=ctk.CTkFrame(inspect,fg_color='transparent');right.grid(row=1,column=1,sticky='nsew',padx=(6,10),pady=6)
        right.grid_columnconfigure(0,weight=1);right.grid_rowconfigure(1,weight=1)
        ctk.CTkLabel(right,text='Findings',font=self.font(11,True),text_color=T['heading']).grid(row=0,column=0,sticky='w',padx=2,pady=(0,4))
        self.findings_frame=ctk.CTkScrollableFrame(right,height=200,fg_color=T['box'],corner_radius=8);self.findings_frame.grid(row=1,column=0,sticky='nsew')
        ctk.CTkLabel(right,text='Details',font=self.font(10,True),text_color=T['body']).grid(row=2,column=0,sticky='w',padx=2,pady=(8,2))
        self.details=ctk.CTkTextbox(right,wrap='word',height=110,font=self.font(9),fg_color=T['box'],text_color=T['body'],border_width=0,corner_radius=8)
        self.details.grid(row=3,column=0,sticky='nsew')
        self.set_text(self.details,'Details of the inspection appear here.')
        self.current_preview=None;self.selected_finding=None;self.finding_cards=[]
        self.render_findings([])
        self.measurements=ctk.CTkLabel(inspect,text='',font=self.font(9),text_color=T['muted'],wraplength=760)
        self.measurements.grid(row=2,column=0,columnspan=2,sticky='w',padx=12,pady=(2,4))
        review=ctk.CTkFrame(inspect,fg_color=T['box'],corner_radius=8);review.grid(row=3,column=0,columnspan=2,sticky='ew',padx=10,pady=(4,10))
        review.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(review,text='Your review',font=self.font(10,True),text_color=T['heading']).grid(row=0,column=0,columnspan=4,sticky='w',padx=10,pady=(8,2))
        self.review_choice=self.menu(review,['Agree with result','Disagree with result'],width=180)
        self.review_choice.grid(row=1,column=0,sticky='w',padx=(10,6),pady=(2,10))
        self.review_notes=ctk.CTkEntry(review,placeholder_text='What did you observe? (optional)',height=28,font=self.font(10),
                                       fg_color=T['card'],border_color=T['border'],text_color=T['heading'])
        self.review_notes.grid(row=1,column=1,sticky='ew',padx=6,pady=(2,10))
        self.review_button=self.button(review,'Save my review',self.save_feedback,'primary',width=130,height=28);self.review_button.configure(state='disabled')
        self.review_button.grid(row=1,column=2,padx=6,pady=(2,10))
        self.export_button=self.button(review,'Export evidence',lambda:self.export(False),'secondary',width=130,height=28);self.export_button.configure(state='disabled')
        self.export_button.grid(row=1,column=3,padx=(0,10),pady=(2,10))

        self.label(integration,'Inspection → Review → Test workspace (C4)',13,True,text_color=T['heading'])
        self.delivery_steps=self.label(integration,'1  Inspect screen     2  Review findings     3  Send evidence',10,text_color=T['muted'])
        self.send_button=self.button(integration,'Send to test workspace',self.send_handover,'primary',width=220,height=32);self.send_button.configure(state='disabled')
        self.send_button.pack(anchor='w',padx=14,pady=8)
        self.integration_status=self.label(integration,'Run an inspection to see its trace.',10,wraplength=760,justify='left')
        self.payload=ctk.CTkTextbox(integration,wrap='none',height=150,font=self.font(10,family='Consolas'),fg_color=T['box'],text_color=T['body'],corner_radius=8)
        self.payload.pack(fill='both',expand=True,padx=14,pady=4);self.set_text(self.payload,'No handover payload yet.')
        self.handover_button=self.button(integration,'Export delivery payload',lambda:self.export(True),'secondary',width=200,height=28);self.handover_button.configure(state='disabled')
        self.handover_button.pack(anchor='w',padx=14,pady=(4,10))
        self.build_live_tab(self.tabs.add('Live from C2'))
        self.build_history_tab(self.tabs.add('History'))
        self.build_model_tab(self.tabs.add('Model'))

    def build_live_tab(self,tab):
        """Receive C2's action triggers in this app: one model serves both this tab and the receiver."""
        self.label(tab,'Receive actions from the user-behaviour engine (C2)',12,True,text_color=T['heading']).pack_configure(pady=(10,2))
        self.label(tab,'Start the receiver, then start a C2 run with this address in its "C3 Oracle URL" field. After each C2 action, '
                   'C3 captures the phone screen and its layout, inspects it, and lists the result here and in History.',
                   10,text_color=T['muted'],wraplength=760,justify='left')
        bar=ctk.CTkFrame(tab,fg_color=T['box'],corner_radius=8);bar.pack(fill='x',padx=14,pady=8)
        self.live_button=self.button(bar,'Start receiving',self.toggle_receiver,'primary',width=150,height=30);self.live_button.pack(side='left',padx=8,pady=8)
        from vision_oracle.core.config import SERVICE_PORT
        self.live_url=f'http://127.0.0.1:{SERVICE_PORT}'
        ctk.CTkLabel(bar,text=self.live_url,font=self.font(11,family='Consolas'),text_color=T['heading']).pack(side='left',padx=10)
        self.button(bar,'Copy address',self.copy_receiver_url,'secondary',width=120,height=28).pack(side='left',padx=4)
        self.live_status=self.label(tab,'Receiver off.',10,wraplength=760,justify='left')
        self.live_progress=ctk.CTkProgressBar(tab,mode='indeterminate',height=6,progress_color=T['primary'],fg_color=T['box']);self.live_progress.set(0)
        self.live_list=ctk.CTkScrollableFrame(tab,height=360,fg_color=T['box'],corner_radius=8);self.live_list.pack(fill='both',expand=True,padx=14,pady=(4,12))
        self.live_rows=[]
        self.live_empty=ctk.CTkLabel(self.live_list,text='Results from C2 actions appear here.',font=self.font(10),text_color=T['muted'],wraplength=700,justify='left')
        self.live_empty.pack(anchor='w',padx=10,pady=10)

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
        self.live_progress.pack(fill='x',padx=14,pady=(0,4),after=self.live_status);self.live_progress.start()
        if self.receiver_url_callback:
            try:self.receiver_url_callback(self.live_url)
            except Exception:logging.getLogger(__name__).exception('Receiver URL callback failed')
        self.poll_live()

    def stop_receiver(self):
        if not self.receiver:return
        server,_thread=self.receiver;server.should_exit=True;self.receiver=None
        if self.live_job:self.after_cancel(self.live_job);self.live_job=None
        self.live_button.configure(text='Start receiving');self.live_status.configure(text='Receiver stopped. Results stay in History.')
        self.live_progress.stop();self.live_progress.set(0);self.live_progress.pack_forget()

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
            if ready:self.live_progress.stop();self.live_progress.pack_forget()
        self.live_empty.configure(text='' if rows else ('No C2 actions yet. Start a run in the User Touch & Biometrics tab. If C2 is running and nothing '
                                                        'appears, connect a phone: C3 captures each screen from the phone, and without one it refuses the action.'))
        for row in self.live_rows:row.destroy()
        self.live_rows=[]
        for verdict,stamp in rows:
            data=verdict.model_dump(mode='json')
            when=stamp.astimezone().strftime('%H:%M:%S') if hasattr(stamp,'astimezone') else '—'
            self.live_rows.append(self.result_row(self.live_list,data,when,data.get('action_id') or '—'))

    def result_row(self,parent,data,when,source):
        """One saved verdict as a white row: decision badge, time, score, findings, where it came from, Open."""
        labels={'defect_detected':'Defect','no_defect_detected':'No defect','inconclusive':'Inconclusive'}
        decision=data['decision'];score=data['metadata'].get('defect_probability');count=len(data['findings'])
        row=ctk.CTkFrame(parent,fg_color=T['card'],corner_radius=8,border_width=1,border_color=T['border']);row.pack(fill='x',padx=4,pady=3)
        ctk.CTkLabel(row,text=labels.get(decision,decision),width=96,height=24,corner_radius=6,font=self.font(9,True),
                     fg_color=DECISION_FILL.get(decision,T['box']),text_color=DECISION_COLORS.get(decision,T['body'])).pack(side='left',padx=(8,10),pady=8)
        ctk.CTkLabel(row,text=when,width=90,anchor='w',font=self.font(10,True),text_color=T['heading']).pack(side='left')
        ctk.CTkLabel(row,text=f'score {score:.0%}' if isinstance(score,(int,float)) else 'score —',width=80,anchor='w',font=self.font(10),text_color=T['body']).pack(side='left')
        ctk.CTkLabel(row,text=f"{count} finding{'s' if count!=1 else ''}",width=80,anchor='w',font=self.font(10),text_color=T['body']).pack(side='left')
        ctk.CTkLabel(row,text=source,anchor='w',font=self.font(9),text_color=T['muted']).pack(side='left',padx=6)
        self.button(row,'Open',lambda v=data:self.open_history(v),'secondary',width=70,height=26).pack(side='right',padx=8)
        return row

    def build_result_header(self,parent):
        """Verdict title, score bar with the alert level marked, and timing chips."""
        header=ctk.CTkFrame(parent,fg_color='transparent');header.grid(row=0,column=0,columnspan=2,sticky='ew',padx=10,pady=(6,2))
        header.grid_columnconfigure(0,weight=1)
        self.result_title=ctk.CTkLabel(header,text='No inspection yet',font=self.font(15,True),text_color=T['heading']);self.result_title.grid(row=0,column=0,sticky='w',padx=2)
        self.score_bg=T['card']
        self.score_canvas=tk.Canvas(header,width=300,height=34,highlightthickness=0,bg=self.score_bg);self.score_canvas.grid(row=0,column=1,rowspan=2,sticky='e',padx=2)
        self.chips=ctk.CTkLabel(header,text='',font=self.font(9),text_color=T['muted']);self.chips.grid(row=1,column=0,sticky='w',padx=2)
        self.draw_score(None,None)

    def draw_score(self,score,threshold):
        c=self.score_canvas;c.delete('all');w,top,bottom=290,6,16
        if not isinstance(score,(int,float)):
            c.grid_remove();return  # no empty bar before there is a score
        c.grid()
        c.create_rectangle(5,top,5+w,bottom,fill=T['box'],outline=T['border'])
        flagged=isinstance(threshold,(int,float)) and score>=threshold
        c.create_rectangle(5,top,5+w*max(0.0,min(1.0,score)),bottom,fill=T['danger'] if flagged else T['success'],width=0)
        c.create_text(5,bottom+9,text=f'model score {score:.0%}',anchor='w',fill=T['body'],font=(FONT,8,'bold'))
        if isinstance(threshold,(int,float)):
            x=5+w*threshold;c.create_line(x,top-4,x,bottom+3,fill=T['heading'],width=2)
            c.create_text(5+w,bottom+9,text=f'alert at {threshold:.0%}',anchor='e',fill=T['muted'],font=(FONT,8))

    def render_findings(self,findings):
        """One card per finding; clicking a card highlights its box in the preview."""
        for card in self.finding_cards:card.destroy()
        self.finding_cards=[];self.selected_finding=None
        if not findings:
            card=ctk.CTkLabel(self.findings_frame,text='No findings yet. Findings from an inspection are listed here;\nclick one to highlight it on the screenshot.',
                              font=self.font(10),text_color=T['muted'],justify='left');card.pack(anchor='w',padx=10,pady=10)
            self.finding_cards.append(card);return
        for index,finding in enumerate(findings,1):
            card=ctk.CTkFrame(self.findings_frame,fg_color=T['card'],border_width=1,border_color=T['border'],corner_radius=8);card.pack(fill='x',padx=4,pady=3)
            kind=finding.get('type','')
            top=ctk.CTkFrame(card,fg_color='transparent');top.pack(fill='x',padx=8,pady=(8,2))
            badge=ctk.CTkLabel(top,text=str(index),width=22,height=22,corner_radius=11,fg_color=T['danger'],text_color='#ffffff',font=self.font(9,True))
            badge.pack(side='left',padx=(0,8))
            title=ctk.CTkLabel(top,text=FINDING_LABELS.get(kind,kind.replace('_',' ').capitalize()),font=self.font(11,True),text_color=T['heading'])
            title.pack(side='left')
            score=finding.get('confidence')
            chip=ctk.CTkLabel(top,text=f'score {score:.0%}' if isinstance(score,(int,float)) else 'score —',height=22,corner_radius=6,
                              fg_color=T['danger_bg'],text_color=T['danger'],font=self.font(9,True))
            chip.pack(side='right',ipadx=6)
            detail=[f"Element: {finding['element_ref']}" if finding.get('element_ref') else 'Element: not named (no layout, or the box covers several elements)',
                    'Region shown in the preview (approximate)' if finding.get('bbox_xyxy') else 'No region given']
            body=ctk.CTkLabel(card,text='\n'.join(detail),font=self.font(9),text_color=T['body'],justify='left',wraplength=420)
            body.pack(anchor='w',padx=38,pady=(0,8))
            for widget in (card,top,badge,title,chip,body):
                widget.bind('<Button-1>',lambda _e,i=index-1:self.select_finding(i));widget.configure(cursor='hand2')
            self.finding_cards.append(card)

    def select_finding(self,index):
        self.selected_finding=index
        for i,card in enumerate(self.finding_cards):
            if isinstance(card,ctk.CTkFrame):
                chosen=i==index
                card.configure(border_color=T['primary'] if chosen else T['border'],border_width=2 if chosen else 1,
                               fg_color=T['primary_light'] if chosen else T['card'])
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
        bar=ctk.CTkFrame(tab,fg_color='transparent');bar.pack(fill='x',padx=14,pady=(10,4))
        ctk.CTkLabel(bar,text='Recent inspections saved on this computer',font=self.font(12,True),text_color=T['heading']).pack(side='left')
        self.button(bar,'Refresh',self.refresh_history,'secondary',width=90,height=28).pack(side='right')
        self.history_list=ctk.CTkScrollableFrame(tab,height=420,fg_color=T['box'],corner_radius=8);self.history_list.pack(fill='both',expand=True,padx=14,pady=(4,12))
        self.history_rows=[];self.history_note=ctk.CTkLabel(self.history_list,text='Loading saved inspections…',font=self.font(10),text_color=T['muted'])
        self.history_note.pack(anchor='w',padx=10,pady=10)

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
        if rows:self.history_note.pack_forget()
        elif not self.history_note.winfo_manager():self.history_note.pack(anchor='w',padx=10,pady=10)
        for verdict,stamp in rows:
            data=verdict.model_dump(mode='json')
            if isinstance(stamp,str):
                try:
                    from datetime import datetime
                    stamp=datetime.fromisoformat(stamp.replace('Z','+00:00'))
                except ValueError:pass
            when=stamp.strftime('%d %b %H:%M') if hasattr(stamp,'strftime') else str(stamp or '—')[:16]
            self.history_rows.append(self.result_row(self.history_list,data,when,self.source_of(data)))

    @staticmethod
    def source_of(data):
        """Where a saved inspection came from, in words: a C2 action, the user's phone, or a screenshot file."""
        meta=data.get('metadata') or {}
        if data.get('action_id'):
            c2=str(data.get('session_id','')).startswith(('live','c2'))
            return f"{'C2 action' if c2 else 'action'} {data['action_id']}"
        if meta.get('device_serial'):return 'phone' + (f" · {meta['app_package']}" if meta.get('app_package') else '')
        return 'screenshot file'

    def open_history(self,verdict):
        if self.busy:return
        try:
            self.clear_result();self.render(present_result({'verdict_v2':verdict}));self.tabs.set('Inspection')
            self.status.configure(text='Showing a saved inspection from history.')
        except Exception as exc:messagebox.showerror('Unable to open inspection',str(exc))

    def build_model_selector(self,parent):
        """Choose which trained adapter inspects the next screen. Only one is loaded at a time (4 GB GPU)."""
        row=ctk.CTkFrame(parent,fg_color='transparent');row.pack(fill='x')
        self.adapter_choices={};self.model_menu=None
        try:
            from vision_oracle.services.oracle_service import available_adapters,active_adapter
            self.adapter_choices={label:folder for label,folder in available_adapters()}
            current=active_adapter()
            names=list(self.adapter_choices) or ['No model found']
            start=next((label for label,folder in self.adapter_choices.items() if current and folder.resolve()==Path(current).resolve()),names[0])
        except Exception as exc:
            names,start=['Model list unavailable'],'Model list unavailable';logging.getLogger(__name__).warning('Adapter discovery failed: %s',exc)
        self.model_menu=self.menu(row,names,self.choose_model,width=330);self.model_menu.set(start)
        self.model_menu.pack(side='left',padx=(0,6));self.controls.append(self.model_menu)
        self.model_note=ctk.CTkLabel(row,text='',font=self.font(9),text_color=T['muted'],wraplength=380,justify='left');self.model_note.pack(side='left',padx=8)
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
        self.label(tab,'Loaded model and how it measured',12,True,text_color=T['heading']).pack_configure(pady=(10,2))
        self.label(tab,'Read from the files next to the adapter (inference_contract.json, model_card.json).',9,text_color=T['muted'])
        self.model_box=ctk.CTkTextbox(tab,wrap='word',font=self.font(10),fg_color=T['box'],text_color=T['body'],border_width=0,corner_radius=8)
        self.model_box.pack(fill='both',expand=True,padx=14,pady=(4,12))
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
        self.send_button.configure(state='disabled',text='Send to test workspace')
        self.delivery_steps.configure(text='1  Inspect screen     2  Review findings     3  Send evidence')
        self.review_button.configure(state='disabled')
        self.export_button.configure(state='disabled');self.handover_button.configure(state='disabled')
        self.set_text(self.payload,'No handover payload for the current inspection.')
        self.integration_status.configure(text='Awaiting an inspection.')
        self.measurements.configure(text='')
        self.result_title.configure(text='No inspection yet',text_color=T['heading'])
        self.draw_score(None,None);self.chips.configure(text='');self.render_findings([])

    def choose_image(self):
        path=filedialog.askopenfilename(filetypes=[('Screenshots','*.png *.jpg *.jpeg')])
        if path:self.select_image(path)

    def select_image(self,path):
        try:
            with Image.open(path) as image:image.verify()
            self.image_path=str(Path(path).resolve());self.file_label.configure(text=Path(path).name)
            self.clear_hierarchy();self.clear_result()
            self.result_title.configure(text='Screenshot selected · press Inspect screenshot',text_color=T['heading'])
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
            messagebox.showinfo('Connect your phone','Connect your phone with USB debugging on, press Refresh devices, pick it in the list, then press Capture my app.');return
        image_path,hierarchy_path=self.image_path,self.hierarchy_path
        action_id=self.action.get().strip() or None;slicing=bool(self.slicing.get())
        self.clear_result();self.busy=True;self.started=time.monotonic()
        for widget in self.controls:widget.configure(state='disabled')
        self.result_title.configure(text='Inspection in progress…',text_color=T['primary'])
        self.set_text(self.details,'Loading the local model and inspecting the screen. The first run can take longer.')
        self.progress.pack(fill='x',padx=14,pady=(0,6),after=self.status)
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
            except Exception as exc:
                logging.getLogger(__name__).exception('Inspection failed')
                import traceback
                where=''.join(traceback.format_exception(type(exc),exc,exc.__traceback__)[-4:]).strip()
                self.events.put(('error',f'{type(exc).__name__}: {exc}\n\nWhere it failed:\n{where}'))
        threading.Thread(target=worker,daemon=True).start()

    def finish(self):
        self.busy=False;self.progress.stop();self.progress.configure(mode='determinate');self.progress.set(0);self.progress.pack_forget()
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
                    self.finish();self.clear_result();self.result_title.configure(text='Inspection failed',text_color=T['danger'])
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
        self.send_button.configure(state='normal')
        self.delivery_steps.configure(text='✓ Inspection complete    → Review findings    ○ Send evidence')
        self.review_button.configure(state='normal')
        self.review_notes.delete(0,'end')
        self.result_title.configure(text=view['title'],text_color=DECISION_COLORS[verdict['decision']]);self.set_text(self.details,view['summary'])
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
        self.stop_receiver()
        super().destroy()
