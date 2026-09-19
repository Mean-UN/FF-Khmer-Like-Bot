import ast
import base64
import json
import unittest
from html import escape
from pathlib import Path

class JwtDisplayTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path('telegram_bot.py').read_text(encoding='utf-8-sig'))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('pick', 'format_jwt_check')]
        self.ns = {'json': json, 'escape': escape}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'formatter', 'exec'), self.ns)
        payload = base64.urlsafe_b64encode(json.dumps({'account_id':17853667272, 'lock_region':'SG'}).encode()).rstrip(b'=').decode()
        self.token = 'eyJhbGciOiJIUzI1NiJ9.'+payload+'.test'

    def test_flat_and_nested_oauth_and_claim_fallback(self):
        for auth in ({'access_token':'test-access'}, {'data':{'access_token':'test-access'}}):
            output = self.ns['format_jwt_check']({'Guest_Auth':auth, 'MajorLogin':{'jwt_token':self.token,'nickname':'Name'}})
            for expected in ('17853667272','SG','test-access'):
                self.assertIn(expected, output)
            self.assertNotIn('N/A', output)

    def test_explicit_metadata_wins_and_html_is_escaped(self):
        output = self.ns['format_jwt_check']({'MajorLogin':{'jwt_token':self.token,'account_id':'456','region':'BR','nickname':'<name>'}})
        self.assertIn('456',output)
        self.assertIn('BR',output)
        self.assertIn('&lt;name&gt;',output)
        self.assertIn('<code>N/A</code>',output)

    def test_malformed_jwt_does_not_crash(self):
        output = self.ns['format_jwt_check']({'MajorLogin':{'jwt_token':'invalid'}})
        self.assertIn('N/A',output)

if __name__ == '__main__': unittest.main()
