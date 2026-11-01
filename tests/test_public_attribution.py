"""CaptureBrief public intake acquisition attribution: real JS, fake DOM, zero sends."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]

DOM_RUNNER = r'''
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync(process.argv[1], 'utf8');
const input = JSON.parse(process.argv[2]);
function checkCase(entry) {
  const fields = new Map(['source_page','utm_source','utm_campaign'].map(name => [name, {value:'SENTINEL'}]));
  const form = {querySelector(selector) {
    const match = /^input\[name="(source_page|utm_source|utm_campaign)"\]$/.exec(selector);
    return match ? fields.get(match[1]) : null;
  }};
  const doc = {
    querySelectorAll(selector) {if(selector==='[data-mobile-menu]')return [];throw Error('Unexpected selector '+selector)},
    querySelector(selector) {if(selector==='form[name="pursuit-qa-intake"]')return entry.form===false ? null : form;throw Error('Unexpected selector '+selector)}
  };
  const context = {document:doc,window:{location:{search:entry.search,pathname:entry.path}},URLSearchParams};
  vm.runInNewContext(code,context,{timeout:1000});
  return Object.fromEntries(Array.from(fields).map(([k,v])=>[k,v.value]));
}
console.log(JSON.stringify(input.map(checkCase)));
'''


class PublicAttributionTests(unittest.TestCase):
    def execute(self, *cases):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node unavailable; Ubuntu CI has Node preinstalled')
        completed = subprocess.run(
            [node, '-e', DOM_RUNNER, str(ROOT / 'assets' / 'main.js'), json.dumps(cases)],
            capture_output=True, text=True, check=True, timeout=10,
        )
        return json.loads(completed.stdout)

    def test_retains_bounded_campaign_labels(self):
        got = self.execute(
            {'path':'/', 'search':'?utm_source=Google-Ads&utm_campaign=Fall+Launch_2026'},
            {'path':'/index.html', 'search':'?utm_source=newsletter&utm_campaign=a.b%2Bc'},
            {'path':'/', 'search':'?utm_source=some_source&utm_campaign=Autumn+Campaign'},
        )
        self.assertEqual(got, [
            {'source_page':'/', 'utm_source':'Google-Ads', 'utm_campaign':'Fall Launch_2026'},
            {'source_page':'/index.html', 'utm_source':'newsletter', 'utm_campaign':'a.b+c'},
            {'source_page':'/', 'utm_source':'some_source', 'utm_campaign':'Autumn Campaign'},
        ])

    def test_rejects_oversized_private_and_control_parameters(self):
        bad = [
            'x'*4096, 'person@example.com', 'https://ad.example/secret',
            'x%0aInjected', 'spring&extra=bad', '\u2603', 'a\t\tb',
        ]
        cases = [
            {'path':'/private/person%40example.com',
             'search':'?utm_source='+quote(v,safe='')+'&utm_campaign='+quote(v,safe='')}
            for v in bad
        ]
        for got in self.execute(*cases):
            self.assertEqual(got, {'source_page':'/','utm_source':'','utm_campaign':''})

    def test_duplicate_utm_keys_fail_closed_without_discarding_valid_siblings(self):
        # URLSearchParams.get previously selected the first conflicting tag,
        # which could misattribute a prospect to a channel they did not choose.
        got = self.execute(
            {'path': '/', 'search': '?utm_source=paid&utm_source=organic&utm_campaign=November'},
            {'path': '/', 'search': '?utm_source=paid&utm_source=paid&utm_campaign=Q4'},
            {'path': '/', 'search': '?utm_source=organic&utm_campaign=Q4&utm_campaign=Q5'},
            {'path': '/', 'search': '?utm_source=direct&%75tm_source=affiliate&utm_campaign=case'},
            {'path': '/', 'search': '?utm_source=&utm_source=paid&utm_campaign='},
            {'path': '/index.html', 'search': '?utm_source=Referral&utm_campaign=November'},
        )
        self.assertEqual(got, [
            {'source_page': '/', 'utm_source': '', 'utm_campaign': 'November'},
            {'source_page': '/', 'utm_source': '', 'utm_campaign': 'Q4'},
            {'source_page': '/', 'utm_source': 'organic', 'utm_campaign': ''},
            {'source_page': '/', 'utm_source': '', 'utm_campaign': 'case'},
            {'source_page': '/', 'utm_source': '', 'utm_campaign': ''},
            {'source_page': '/index.html', 'utm_source': 'Referral', 'utm_campaign': 'November'},
        ])

    def test_no_form_and_empty_fields_do_not_trigger_side_effects(self):
        got = self.execute(
            {'path':'/', 'search':'?utm_source=', 'form':False},
            {'path':'/', 'search':'?utm_source=&&utm_campaign='},
        )
        self.assertEqual(got[0], {
            'source_page':'SENTINEL','utm_source':'SENTINEL','utm_campaign':'SENTINEL'
        })
        self.assertEqual(got[1], {'source_page':'/','utm_source':'','utm_campaign':''})


if __name__ == '__main__':
    unittest.main()
