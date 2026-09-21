import hashlib, io, json, tempfile, unittest
from pathlib import Path

from capturebrief_core.ledger import append_record, verify_ledger
from capturebrief_core.manifest import download_public_resource

class FakeResponse:
    def __init__(self, data: bytes, url='https://objects.example/file'):
        self._io=io.BytesIO(data); self.headers={'Content-Length':str(len(data))}; self._url=url
    def read(self,n=-1): return self._io.read(n)
    def geturl(self): return self._url
    def __enter__(self): return self
    def __exit__(self,*args): return False

class LedgerDownloadTests(unittest.TestCase):
    def test_public_resource_download_hashes_bytes(self):
        data=b'abc123'
        def opener(req,timeout=30): return FakeResponse(data)
        receipt,content=download_public_resource({'kind':'file','artifact_state':'PUBLIC','resource_id':'rid-1'},opener=opener)
        self.assertEqual(content,data)
        self.assertEqual(receipt['sha256'],hashlib.sha256(data).hexdigest())
        self.assertEqual(receipt['byte_state'],'BYTES_VERIFIED_HASHED')
        self.assertIn('sam.gov/api/prod/opps/v3/opportunities/resources/files/rid-1/download',receipt['source_url'])

    def test_external_link_cannot_be_blind_downloaded(self):
        with self.assertRaises(ValueError):
            download_public_resource({'kind':'link','artifact_state':'EXTERNAL','resource_id':'x'},opener=lambda *a,**k:None)

    def test_tamper_evident_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ledger.jsonl'
            a=append_record(p,record_type='MANIFEST_OBSERVATION',payload={'a':1},recorded_at='2026-09-21T13:00:00+00:00')
            b=append_record(p,record_type='BYTE_RECEIPT',payload={'b':2},recorded_at='2026-09-21T13:01:00+00:00')
            good=verify_ledger(p)
            self.assertTrue(good['valid']); self.assertEqual(good['records'],2); self.assertEqual(good['head_sha256'],b['record_sha256'])
            lines=p.read_text().splitlines(); row=json.loads(lines[0]); row['payload']['a']=999; lines[0]=json.dumps(row,separators=(',',':')); p.write_text('\n'.join(lines)+'\n')
            bad=verify_ledger(p)
            self.assertFalse(bad['valid']); self.assertIn('PAYLOAD_HASH_MISMATCH',{x['code'] for x in bad['errors']})

    def test_chain_break_detected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ledger.jsonl'
            append_record(p,record_type='ONE',payload={'x':1},recorded_at='2026-09-21T13:00:00+00:00')
            append_record(p,record_type='TWO',payload={'x':2},recorded_at='2026-09-21T13:01:00+00:00')
            lines=p.read_text().splitlines(); row=json.loads(lines[1]); row['previous_record_sha256']='0'*64; lines[1]=json.dumps(row,separators=(',',':')); p.write_text('\n'.join(lines)+'\n')
            bad=verify_ledger(p)
            self.assertFalse(bad['valid']); self.assertIn('CHAIN_BREAK',{x['code'] for x in bad['errors']})

if __name__=='__main__': unittest.main()
