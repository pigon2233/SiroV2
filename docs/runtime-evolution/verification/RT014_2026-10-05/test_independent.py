from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location('rt014_fixture', Path(__file__).resolve().parents[4] / 'tests/integration/test_memory_ingress.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

def test_deleted_memory_no_fresh_prompt_and_revision_sources(tmp_path, monkeypatch):
    client, model, _ = fixture.boot(tmp_path, monkeypatch)
    with client:
        headers = fixture.auth(client)
        assert client.post('/v1/conversations/A/turns', headers=headers, json={'text':'請記住： synthetic violet original'}).status_code == 200
        item = client.get('/v1/memories', headers=headers, params={'identity_id':'siro'}).json()['items'][0]
        memory_id = item['memory_id']
        original_source = item['source_event_ids'][0]
        assert client.post(f'/v1/memories/{memory_id}/correct', headers=headers, json={'text':'synthetic violet corrected'}).status_code == 200
        revisions = client.get(f'/v1/memories/{memory_id}/revisions', headers=headers).json()['items']
        assert original_source in revisions[0]['source_event_ids']
        assert original_source in revisions[1]['source_event_ids']
        assert len(revisions[1]['source_event_ids']) == 2
        assert client.delete(f'/v1/memories/{memory_id}', headers=headers).status_code == 200
    client, model, _ = fixture.boot(tmp_path, monkeypatch)
    with client:
        headers = fixture.auth(client)
        assert client.post('/v1/conversations/FRESH/turns', headers=headers, json={'text':'violet'}).status_code == 200
        assert model.requests
        request = model.requests[-1]
        serialized = request.prompt + ' '.join(m.content for m in request.messages)
        assert 'synthetic violet original' not in serialized
        assert 'synthetic violet corrected' not in serialized
        revisions = client.get(f'/v1/memories/{memory_id}/revisions', headers=headers).json()['items']
        assert len(revisions) == 3
        assert revisions[2]['source_event_ids'] == revisions[1]['source_event_ids']
