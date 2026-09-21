import hashlib, io, json, tempfile, unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from capturebrief_core.ledger import LedgerLockedError, append_record, verify_ledger
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


    def test_concurrent_writers_preserve_one_valid_chain(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ledger.jsonl'
            def write(i):
                return append_record(
                    p,
                    record_type='CONCURRENT',
                    payload={'i':i},
                    recorded_at=f'2026-09-21T13:{i:02d}:00+00:00',
                )
            with ThreadPoolExecutor(max_workers=8) as pool:
                rows=list(pool.map(write,range(20)))
            status=verify_ledger(p)
            self.assertTrue(status['valid'],status['errors'])
            self.assertEqual(status['records'],20)
            self.assertEqual(len({x['record_sha256'] for x in rows}),20)
            self.assertFalse(p.with_name(p.name+'.lock').exists())

    def test_held_lock_times_out_instead_of_guessing_stale(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ledger.jsonl'
            lock=p.with_name(p.name+'.lock')
            lock.write_text('simulated active writer')
            with self.assertRaises(LedgerLockedError):
                append_record(
                    p,
                    record_type='LOCKED',
                    payload={'x':1},
                    lock_timeout_seconds=0.01,
                )
            with self.assertRaises(LedgerLockedError):
                verify_ledger(p,lock_timeout_seconds=0.01)
            self.assertEqual(lock.read_text(),'simulated active writer')

    def test_direct_append_refuses_invalid_existing_chain_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'ledger.jsonl'
            append_record(p,record_type='ONE',payload={'x':1})
            row=json.loads(p.read_text().splitlines()[0])
            row['payload']['x']=999
            p.write_text(json.dumps(row)+'\n')
            before=p.read_bytes()
            with self.assertRaises(ValueError):
                append_record(p,record_type='TWO',payload={'x':2})
            self.assertEqual(p.read_bytes(),before)
            self.assertFalse(p.with_name(p.name+'.lock').exists())

if __name__=='__main__': unittest.main()
