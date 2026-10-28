import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from adapters import native_media as native


class NativeTests(unittest.TestCase):
    def test_kuaishou_matches_requested_photo_and_resolves_manifest_refs(self):
        state = {'defaultClient': {
            'VisionVideoDetailPhoto:abc': {'caption':'Test video', 'duration':12000, 'manifest': {'type':'id','id':'manifest'}},
            'manifest': {'adaptationSet':[{'representation':[{'width':640,'height':360,'avgBitrate':200000,'url':'https://v1.kwaicdn.com/test.mp4?token=SIGNED'}]}]},
            'VisionVideoDetailPhoto:other': {'photoUrl':'https://v1.kwaicdn.com/unrelated.mp4'},
        }}
        page = 'advert https://v1.kwaicdn.com/advert.mp4 <script>window.__APOLLO_STATE__=' + json.dumps(state) + ';alert("never execute")</script>'
        info = native.extract_kuaishou(page, 'https://www.kuaishou.com/short-video/abc')
        self.assertEqual(info['duration'],12)
        self.assertEqual(info['formats'][0]['height'],360)
        self.assertEqual(len(info['formats']),1)
        self.assertNotIn('advert',info['formats'][0]['url'])
        with self.assertRaises(native.NativeError):
            native.extract_kuaishou(page,'https://www.kuaishou.com/short-video/missing')

    def test_generic_page_mp4s_never_count_as_requested_video(self):
        with self.assertRaises(native.NativeError):
            native.extract_kuaishou('<title>kuaishou</title>https://v1.kwaicdn.com/app-advert.mp4','https://www.kuaishou.com/short-video/abc')

    def test_cdn_allowlist_and_quality_cap(self):
        for url in ['http://v1.kwaicdn.com/a.mp4','https://kwaicdn.com.evil.test/a.mp4','https://user:pass@v1.kwaicdn.com/a.mp4']:
            self.assertFalse(native.allowed_url(url,native.KS_HOSTS))
        info={'formats':[{'height':1080,'format_id':'hd'},{'height':360,'format_id':'sd'},{'height':None,'format_id':'unknown'}]}
        self.assertEqual(native.select_format(info,'480')['format_id'],'sd')
        self.assertEqual(native.select_format(info,'best')['format_id'],'hd')
        with self.assertRaises(native.NativeError):
            native.select_format({'formats':[{'height':None}]},'720')

    def test_resolver_auth_is_not_a_wechat_login_request(self):
        error=urllib.error.HTTPError(native.WECHAT_RESOLVER,401,'Unauthorized',{},None)
        with patch.object(native.urllib.request,'build_opener') as opener:
            opener.return_value.open.side_effect=error
            with self.assertRaises(native.NativeError) as result:
                native.probe_wechat('https://weixin.qq.com/sph/test',10)
        self.assertEqual(result.exception.code,'resolver_auth_required')
        self.assertIn('not a request to log in',str(result.exception))

    def test_malformed_resolver_response_is_a_typed_failure(self):
        with patch.object(native.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'[]'
            with self.assertRaises(native.NativeError) as result:
                native.probe_wechat('https://weixin.qq.com/sph/test', 10)
        self.assertEqual(result.exception.code, 'resolver_invalid_response')


if __name__=='__main__':
    unittest.main()
