from __future__ import annotations
import json
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from unittest.mock import patch

from scripts.update_schedule import (extract_coverage, extract_match_urls, parse_match_detail,
                                     fetch_schedule, SourceError)
from scripts.notify import decide

FIXTURE = Path(__file__).parent / 'fixtures'
NOW = datetime(2026, 10, 15, 9, 17, tzinfo=ZoneInfo('Asia/Shanghai'))


def read(name):
    return (FIXTURE / name).read_text(encoding='utf-8')


class FakeResponse:
    status_code = 200
    encoding = 'utf-8'
    def __init__(self, body): self.text = body
    def raise_for_status(self): pass


class FakeSession:
    def get(self, url, timeout=None):
        if url.endswith('/kog/schedule'):
            return FakeResponse(read('listing.html'))
        id_ = url.split('/')[-1].split('.')[0]
        return FakeResponse(read(f'match-{id_}.html'))


class ScraperTests(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(len(extract_match_urls(read('listing.html'))), 3)

    def test_dates(self):
        dates = extract_coverage(read('listing.html'), NOW.date())
        self.assertIn('2026-10-15', dates)
        self.assertIn('2026-10-16', dates)
        self.assertIn('2026-10-18', dates)

    def test_detail_has_original_time_when_live(self):
        game = parse_match_detail(read('match-94590.html'), 'https://wanplus.cn/schedule/94590.html')
        self.assertEqual(game['time'], '17:00')
        self.assertEqual(game['team_a'], '成都AG超玩会')
        self.assertEqual(game['status'], 'live')

    @patch('scripts.update_schedule.time.sleep', return_value=None)
    def test_end_to_end_fixture(self, _sleep):
        data = fetch_schedule(FakeSession(), NOW)
        self.assertEqual(len(data['matches']), 3)
        self.assertEqual(data['matches'][0]['time'], '17:00')
        self.assertEqual(data['matches'][1]['time'], '20:00')
        self.assertEqual(data['matches'][2]['date'], '2026-10-16')

    def test_notification_no_duplicates_and_no_stale(self):
        data = {
            'source': 'wanplus_schedule_and_match_details',
            'updated_at': NOW.isoformat(), 'coverage_dates':['2026-10-15'],
            'matches':[{'date':'2026-10-15','time':'17:00'}]
        }
        self.assertEqual(len(decide(data, {'sent_dates': []}, NOW)[0]), 1)
        self.assertEqual(decide(data, {'sent_dates': ['2026-10-15']}, NOW)[0], [])
        stale = NOW.replace(day=17)
        self.assertEqual(decide(data, {'sent_dates': []}, stale)[0], [])


if __name__ == '__main__':
    unittest.main()
