import json
from copy import deepcopy
from uuid import uuid4
from unittest.mock import Mock
import pytest
from app.core.config import InterviewSettings
from app.db.interviews import _stored_response
from app.schemas.interview import StartInterview,CandidateAnswer,Feedback,InterviewResponse
from app.integrations.llm_client import LLMError
from app.services import question_generator as q

@pytest.fixture
def session(monkeypatch):
    settings=InterviewSettings(_env_file=None,ollama_context_tokens=8192)
    monkeypatch.setattr(q,'get_interview_settings',lambda:settings)
    hit=dict(chunk_id='a'*64,commit_sha='b'*40,file_path='cache.py',symbol_name='lookup',start_line=1,end_line=2,content='def lookup(key):\n    return cache.get(key)\n')
    monkeypatch.setattr(q,'_interview_context',lambda *args:[hit])
    records={}
    monkeypatch.setattr(q.storage,'load',lambda key:deepcopy(records.get(key)))
    def create(request,response):
        records[response.session_id]=dict(initial_request=request.model_dump(mode='json'),version=0,turns=[dict(request_id=str(request.request_id),answer=None,response=_stored_response(response))]);return True
    def save(key,request,feedback):
        record=records[key]
        if record['version']!=request.expected_version:return None
        internal=record['turns'][-1]['response']['_internal']
        pending=internal.setdefault('pending',dict(request_id=str(request.request_id),answer=request.answer,feedback=feedback.model_dump()))
        return pending if pending['request_id']==str(request.request_id) and pending['answer']==request.answer else None
    def append(request,response):
        record=records[response.session_id]
        if record['version']!=request.expected_version:return False
        record['version']=response.version;record['turns'].append(dict(request_id=str(request.request_id),answer=request.answer,response=_stored_response(response)));return True
    monkeypatch.setattr(q.storage,'create',create);monkeypatch.setattr(q.storage,'save_grade',save);monkeypatch.setattr(q.storage,'append',append)
    class Provider:
        count=0;grades=0;fail_next=False;bad_citation=False
        def generate(self,messages,schema):
            if 'reference_answer' in schema['properties']:
                assert 'candidate answer marker' not in json.dumps(messages)
                if self.fail_next:raise LLMError('question unavailable',502)
                self.count+=1
                return json.dumps(dict(question=f'In lookup, how is the cached result returned in case {self.count}?',reference_answer='It returns the cached item.',rubric=['Explain the returned cache item.'],source_ids=['S99' if self.bad_citation else 'S1'],evidence_quote='return cache.get(key)'))
            self.grades+=1
            return json.dumps(dict(assessment='partial',rationale='The answer explains lookup but omits the returned result.',depth='surface',missed_concepts=['Returned result'],source_ids=['S1']))
    return records,Provider(),settings

def test_five_questions_and_hidden_rubric_saved_report_replay(session):
    records,p,_=session;req=StartInterview(repository_id=uuid4(),topic='cache');first=q.start_interview(req,provider=p)
    assert first.max_turns==5 and 'reference_answer' not in first.model_dump_json()
    assert records[first.session_id]['turns'][0]['response']['_internal']['plan']['reference_answer']
    current=first
    for i in range(5):
        answer=CandidateAnswer(expected_version=i,answer='candidate answer marker: lookup checks cache')
        current=q.answer_interview(first.session_id,answer,provider=p)
        assert q.answer_interview(first.session_id,answer,provider=p)==current
        assert current.difficulty==first.difficulty
    assert current.status=='finished' and current.report.answered_turns==5
    assert p.count==5 and p.grades==5
    assert q.get_report(first.session_id)==current.report
    assert '_internal' not in q.get_interview(first.session_id).model_dump_json()
    assert q.start_interview(req,provider=p)==first

def test_question_failure_preserves_grade_and_retry_does_not_regrade(session):
    records,p,_=session;first=q.start_interview(StartInterview(repository_id=uuid4(),topic='cache'),provider=p)
    req=CandidateAnswer(expected_version=0,answer='candidate answer marker')
    p.fail_next=True
    with pytest.raises(LLMError):q.answer_interview(first.session_id,req,provider=p)
    assert records[first.session_id]['version']==0 and p.grades==1
    assert records[first.session_id]['turns'][0]['response']['_internal']['pending']['feedback']['assessment']=='partial'
    with pytest.raises(LLMError):q.answer_interview(first.session_id,CandidateAnswer(expected_version=0,answer='different'),provider=p)
    p.fail_next=False
    assert q.answer_interview(first.session_id,req,provider=p).version==1
    assert p.grades==1

def test_invalid_citation_never_creates_session(session):
    records,p,_=session;p.bad_citation=True
    with pytest.raises(LLMError):q.start_interview(StartInterview(repository_id=uuid4(),topic='cache'),provider=p)
    assert not records

def test_nonanswer_no_inference(session):
    _,p,settings=session;first=q.start_interview(StartInterview(repository_id=uuid4(),topic='cache'),provider=p)
    assert q.grade_answer(settings,first,'I do not know',provider=p).assessment=='uncertain'
    assert p.grades==0
