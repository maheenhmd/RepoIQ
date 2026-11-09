from types import SimpleNamespace
import pytest
from app.services.question_generator import _exact_value_guard

@pytest.mark.parametrize('question', ['What is the default value of settings.embedding_batch_size?', 'What is the default embedding_batch_size?'])
@pytest.mark.parametrize('answer,expected', [('4','correct'),('1000','incorrect')])
def test_cited_literal(question,answer,expected):
    refs=[SimpleNamespace(source_id='S1',content='embedding_batch_size: Literal[4, 8, 16] = 4')]
    assert _exact_value_guard(question,answer,refs)[0]==expected

def test_missing_declaration_is_not_candidate_error():
    refs=[SimpleNamespace(source_id='S1',content='batch_size = settings.embedding_batch_size')]
    assert _exact_value_guard('What is the default embedding_batch_size?','4',refs)[0]=='uncertain'

def test_negation_is_not_literal_confirmation():
    refs=[SimpleNamespace(source_id='S1',content='embedding_batch_size: int = 4')]
    assert _exact_value_guard('What is the default embedding_batch_size?','It is not 4.',refs) is None
