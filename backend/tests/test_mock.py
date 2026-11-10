import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Database
from app.models import User, WorkRecord
from app.mock import seed_mock, rebalance_mock, PEOPLE
from app.business import annual_payload
from app.excel_export import parse_payload, calculate_statistics
from app.security import hash_password

class MockTests(unittest.TestCase):
    def test_replace_roster_and_calendar_saturation(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Database(Path(folder))
            try:
                database.initialize()
                original_hash = hash_password('preserve-admin-password')
                with Session(database.accounts) as db:
                    db.add(User(username='admin', name='管理员', position='管理员', role='admin', password_hash=original_hash))
                    db.add(User(username='worker01', name='旧假人员', password_hash=hash_password('123456')))
                    db.commit()
                seed_mock(database, replace=True)
                with Session(database.accounts) as db:
                    users = list(db.scalars(select(User)))
                    self.assertEqual(len(users),33)
                    self.assertEqual({u.username for u in users if u.role != 'admin'}, {username for _, _, username in PEOPLE})
                    self.assertEqual(db.scalar(select(User).where(User.username=='admin')).password_hash,original_hash)
                    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(database=database)))
                    for year in (2025,2026):
                        config,entries = parse_payload(annual_payload(request,year,True,db))
                        stats = calculate_statistics(config,entries)
                        self.assertEqual(stats['peopleCount'],32)
                        for group in ('personalMonthly','personalYearly','teamMonthly'):
                            rates = [r['saturation'] for r in stats[group]]
                            self.assertTrue(any(r < .8 for r in rates))
                            self.assertTrue(any(.8 <= r <= 1 for r in rates))
                            self.assertTrue(any(r > 1 for r in rates))
                with Session(database.year_engine(2026)) as work:
                    count = len(list(work.scalars(select(WorkRecord.id))))
                seed_mock(database)
                with Session(database.year_engine(2026)) as work:
                    self.assertEqual(len(list(work.scalars(select(WorkRecord.id)))),count)
                    target_id=work.scalar(select(WorkRecord.user_id).limit(1))
                    from datetime import date
                    actual=WorkRecord(user_id=target_id,work_date=date(2026,1,5),project='真实项目',task_type='编码开发',description='手工填报',hours_tenths=55,code_lines=0,remark='非模拟数据')
                    work.add(actual); work.commit(); actual_id=actual.id
                with Session(database.accounts) as db:
                    target=db.get(User,target_id); target.is_active=False; saved_hash=target.password_hash; db.commit()
                rebalance_mock(database)
                with Session(database.accounts) as db:
                    self.assertFalse(db.get(User,target_id).is_active)
                    self.assertEqual(db.get(User,target_id).password_hash,saved_hash)
                with Session(database.year_engine(2026)) as work:
                    self.assertEqual(work.get(WorkRecord,actual_id).hours_tenths,55)
            finally:
                database.close()

if __name__=='__main__':
    unittest.main()
