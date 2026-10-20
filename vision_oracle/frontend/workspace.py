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


def default_service():
    from vision_oracle.services.oracle_service import get_oracle_service
    return get_oracle_service()


class C3Workspace(ctk.CTkFrame):
    def __init__(self, master, service_factory=default_service, handover_callback=None):
        super().__init__(master, fg_color='transparent')
        self.handover_callback=handover_callback
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
        source=ctk.CTkFrame(self)
        source.pack(fill='x',padx=8,pady=6)
        self.buttons(source,[('Choose screenshot',self.choose_image),('Inspect screenshot',lambda:self.run('file')),('Capture phone',lambda:self.run('device'))])
        self.file_label=self.label(source,'Choose an image to begin.',12,wraplength=560)
        row=ctk.CTkFrame(source,fg_color='transparent');row.pack(fill='x',padx=8,pady=5)
        self.device=ctk.CTkOptionMenu(row,values=['No device'],width=150);self.device.pack(side='left',padx=3);self.controls.append(self.device)
        refresh=ctk.CTkButton(row,text='Refresh devices',command=self.refresh_devices,width=110);refresh.pack(side='left',padx=3);self.controls.append(refresh)
        self.slicing=ctk.CTkSwitch(row,text='Multi-view');self.slicing.select();self.slicing.pack(side='left',padx=6);self.controls.append(self.slicing)
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
        self.tabs=ctk.CTkTabview(self,height=410);self.tabs.pack(fill='both',expand=True,padx=8,pady=8)
        inspect=self.tabs.add('Inspection');integration=self.tabs.add('Delivery')
        inspect.grid_columnconfigure(0,weight=1);inspect.grid_columnconfigure(1,weight=2);inspect.grid_rowconfigure(1,weight=1)
        self.result_title=ctk.CTkLabel(inspect,text='Ready to inspect',font=ctk.CTkFont(size=18,weight='bold'));self.result_title.grid(row=0,column=0,columnspan=2,sticky='w',padx=8,pady=6)
        self.preview=tk.Label(inspect,text='Screenshot preview',bg='#e2e8f0',fg='#334155',borderwidth=0);self.preview.grid(row=1,column=0,sticky='nsew',padx=4,pady=4)
        self.details=ctk.CTkTextbox(inspect,wrap='word',height=230,font=ctk.CTkFont(size=13));self.details.grid(row=1,column=1,sticky='nsew',padx=4,pady=4)
        self.set_text(self.details,'Choose a screenshot, then inspect it. You can also capture a connected phone.')
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
        self.measurements.configure(text='Coverage — · Analysis time —')

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
                    self.set_text(self.details,value+'\n\nNo verdict was produced. Check model files, GPU memory or device connection, then retry.')
                    self.status.configure(text='Failed. You can retry.')
                elif kind=='result':self.finish();self.render(value)
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
        color={'defect_detected':'#be123c','no_defect_detected':'#047857','inconclusive':'#a16207'}[verdict['decision']]
        self.result_title.configure(text=view['title'],text_color=color);self.set_text(self.details,view['summary'])
        elapsed=f"{view['total_ms']/1000:.2f}s" if view['total_ms'] is not None else 'unavailable'
        self.measurements.configure(text=f"{view['coverage']} · Analysis: {elapsed} · {verdict['analysis_status']}")
        self.status.configure(text='Inspection saved locally. Review the findings.')
        self.draw_preview(verdict['screenshot']['storage_path'],verdict['findings'])
        self.integration_status.configure(text=f"Session: {verdict['session_id']}\nAction: {verdict.get('action_id') or 'None (unlinked)'}\nCapture: {verdict['capture_id']}\nVerdict: {verdict['verdict_id']}\nHandover: {view['outcome'].replace('_',' ')} · prepared, not sent")
        self.set_text(self.payload,json.dumps(view['handover'],indent=2))
        self.export_button.configure(state='normal');self.handover_button.configure(state='normal')

    def draw_preview(self,path,findings):
        try:
            with Image.open(path) as source:image=source.convert('RGB')
            draw=ImageDraw.Draw(image)
            for index,finding in enumerate(findings,1):
                box=finding.get('bbox_xyxy')
                if box:
                    draw.rectangle(box,outline='#ef4444',width=max(2,image.width//250));draw.text((box[0]+4,max(0,box[1]-14)),str(index),fill='#ef4444')
            image.thumbnail((170,230))
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

    def export(self,handover):
        if not self.latest or self.busy:return
        data=self.latest['handover' if handover else 'verdict'];suffix='c4_handover' if handover else 'evidence'
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile=f"{data['verdict_id']}_{suffix}.json",filetypes=[('JSON','*.json')])
        if path:
            try:Path(path).write_text(json.dumps(data,indent=2),encoding='utf-8');self.status.configure(text='JSON exported. No downstream service was called.')
            except OSError as exc:messagebox.showerror('Export failed',str(exc))

    def destroy(self):
        self.after_cancel(self.poll_id)
        super().destroy()
