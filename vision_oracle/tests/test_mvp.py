"""Behavioral regressions for the standalone MVP, using isolated test storage."""
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from vision_oracle.frontend.presentation import present_result
from vision_oracle.contracts.v2 import VerdictEnvelopeV2, ScreenshotRef, Finding, Coverage
from vision_oracle.persistence.db import DatabaseManager
from vision_oracle.persistence.repository import OracleRepository
from vision_oracle.services.oracle_service import OracleService
from local_vision_oracle.engine import OracleEngine, MockInferenceBackend


def result(decision='no_defect_detected', status='complete', findings=None):
    v = VerdictEnvelopeV2(job_id='j', capture_id='c', session_id='s',
        screenshot=ScreenshotRef(width=100, height=200), analysis_status=status,
        decision=decision, findings=findings or [],
        coverage=Coverage(planned_views=1, completed_views=1 if status=='complete' else 0),
        timings_ms={'total_pipeline_ms': 2345})
    return {'verdict_v2':v.model_dump(mode='json')}


def test_clean_is_not_certified_or_assigned_fake_confidence():
    view=present_result(result())
    assert view['title']=='No defect detected'
    assert '95' not in view['summary']
    assert 'does not certify' in view['summary']
    assert view['total_ms']==2345
    assert view['outcome']=='evidence_only'


def test_inconclusive_stays_inconclusive_in_handover():
    view=present_result(result('inconclusive','error'))
    assert view['handover']['has_gui_defect'] is None
    assert view['outcome']=='unsupported_inconclusive'


def test_defect_without_action_context_is_evidence_only():
    finding=Finding(type='text_truncation', explanation='Text ends mid-word', bbox_xyxy=[2,4,60,30])
    view=present_result(result('defect_detected',findings=[finding]))
    assert view['outcome']=='evidence_only'
    assert 'not calibrated' in view['summary']
    assert 'dispatched' not in view['summary']


@pytest.fixture
def service(tmp_path,monkeypatch):
    import vision_oracle.services.oracle_service as module
    monkeypatch.setattr(module,'log_model_configuration',lambda *args: None)
    monkeypatch.setattr(module,'VERDICTS_DIR',tmp_path)
    repo=OracleRepository(db_manager=DatabaseManager(tmp_path/'store.db'),artifacts_dir=tmp_path/'images')
    return OracleService(engine=OracleEngine(backend=MockInferenceBackend()),repository=repo)


def test_live_capture_timings_and_action_survive_persistence(service):
    class Device:
        serial='test-phone'
        def screencap(self,**kwargs): return Image.new('RGB',(80,120),'white')
        def dump_hierarchy(self,**kwargs): return '<hierarchy />'
        def get_display_metrics(self): return {'width':80,'height':120}
    response=service.evaluate_device(device=Device(),action_id='checkout-1',session_id='s',enable_sahi=False)
    v=response['verdict_v2']
    saved=service.repository.get_verdict(v['verdict_id'])
    assert saved.action_id=='checkout-1'
    assert saved.metadata['device_serial']=='test-phone'
    assert saved.timings_ms==v['timings_ms']
    assert response['oracle_result']['latency_breakdown']['total_pipeline_ms']==v['timings_ms']['total_pipeline_ms']
    assert response['c4_verdict']['evidence']['timings_ms']==v['timings_ms']
    assert v['timings_ms']['total_pipeline_ms']>=v['timings_ms']['capture_ms']


def test_readiness_model_failure_is_503(monkeypatch):
    from vision_oracle.api import routes_v2
    from vision_oracle.server import app
    def unavailable(): raise RuntimeError('adapter missing')
    monkeypatch.setattr(routes_v2,'get_oracle_service',unavailable)
    response=TestClient(app).get('/health/ready')
    assert response.status_code==503
    assert response.json()['detail']['ready'] is False

def test_invalid_job_policy_and_review_are_rejected():
    from vision_oracle.api.routes_v2 import JobSubmitRequest, ReviewSubmitRequest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        JobSubmitRequest(capture_id='c', policy='invented')
    with pytest.raises(ValidationError):
        ReviewSubmitRequest(verdict_id='v', review_status='invented')


def test_feedback_persists_without_changing_original_verdict(service):
    response=service.evaluate(Image.new('RGB',(80,120),'white'),enable_sahi=False)
    vid=response['verdict_v2']['verdict_id']
    before=service.repository.get_verdict(vid).model_dump()
    rid=service.repository.add_review(vid,'rejected',notes='Tester observed clipped text')
    row=service.repository.db.get_connection().execute('SELECT * FROM reviews WHERE review_id=?',(rid,)).fetchone()
    assert row['review_status']=='rejected'
    assert row['reviewer_notes']=='Tester observed clipped text'
    assert service.repository.get_verdict(vid).model_dump()==before


def test_service_initializes_once_under_concurrent_requests(monkeypatch):
    import concurrent.futures
    import time
    import vision_oracle.services.oracle_service as module
    calls=[]
    instance=object()
    def factory():
        calls.append(1)
        time.sleep(.02)
        return instance
    monkeypatch.setattr(module,'_ORACLE_SERVICE',None)
    monkeypatch.setattr(module,'OracleService',factory)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:module.get_oracle_service(), range(4)))
    assert all(x is instance for x in results)
    assert len(calls)==1

def test_c4_receives_real_contract_and_persists_idempotently(tmp_path):
    from c4.ui.controller import C4DemoController
    import json
    payload=present_result(result())['handover']
    controller=C4DemoController()
    receipt=controller.receive_inspection(payload,tmp_path)
    assert receipt['status']=='received'
    assert json.loads(__import__('pathlib').Path(receipt['path']).read_text())['verdict_id']==payload['verdict_id']
    assert controller.receive_inspection(payload,tmp_path)['path']==receipt['path']
    assert len(list(tmp_path.glob('*.json')))==1
