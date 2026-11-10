import unittest
from io import BytesIO
from unittest.mock import patch
from pathlib import Path
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session
import test_auth
from app.settings import data_root, ROOT, load_settings
from app.mock import seed_mock
from app.models import WorkRecord

class BusinessTests(unittest.TestCase):
    setUp = test_auth.AuthTests.setUp
    tearDown = test_auth.AuthTests.tearDown
    account = staticmethod(test_auth.AuthTests.account)
    login = test_auth.AuthTests.login
    register = test_auth.AuthTests.register

    def entry(self, **changes):
        return dict(work_date="2026-11-04", project="平台", task_type="编码开发",
                    description="测试实现", hours=7.5, code_lines=100, remark="", **changes)

    def test_ownership_filters_and_cross_year_move(self):
        self.register()
        self.login()
        created = self.client.post("/api/records", json=self.entry()).json()
        record_id = created["id"]
        self.assertEqual(self.client.get("/api/records?year=2026&month=11&day=4&keyword=平台").json()["hours"], 7.5)
        self.client.post("/api/auth/logout")
        self.register("Worker02")
        self.login("Worker02")
        self.assertEqual(self.client.get("/api/records?year=2026").json()["total"], 0)
        self.assertEqual(self.client.delete(f"/api/records/2026/{record_id}").status_code, 403)
        self.assertEqual(self.client.put(f"/api/records/2026/{record_id}", json=self.entry()).status_code, 403)
        self.assertEqual(self.client.get("/api/users").status_code, 403)
        self.assertEqual(self.client.get("/api/export?year=2026").status_code, 403)
        self.assertEqual(self.client.post("/api/records", json=dict(self.entry(), user_id=1)).status_code, 403)
        self.login()
        response = self.client.put(f"/api/records/2026/{record_id}", json=dict(self.entry(),work_date="2025-12-31"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get("/api/records?year=2026").json()["total"], 0)
        moved = self.client.get("/api/records?year=2025").json()
        self.assertEqual(moved["total"], 1)
        self.assertEqual(self.client.delete(f'/api/records/2025/{response.json()["id"]}').status_code, 204)

    def test_record_suggestions_across_years_and_by_owner(self):
        self.register()
        self.login()
        for entry in (
            dict(self.entry(), work_date="2025-12-31", project="旧项目", remark="完成 50%"),
            dict(self.entry(), project="新项目", description="跨行\n任务描述"),
            dict(self.entry(), project="新项目"),
        ):
            self.assertEqual(self.client.post("/api/records", json=entry).status_code, 201)
        path = "/api/records/suggestions"
        owner = self.client.get("/api/auth/me").json()["id"]
        self.assertEqual(self.client.get(path, params={"field": "project"}).json(), ["新项目", "旧项目"])
        self.assertEqual(self.client.get(path, params={"field": "project", "q": "项目"}).json(), ["新项目", "旧项目"])
        self.assertEqual(self.client.get(path, params={"field": "description", "q": "务描"}).json(), ["跨行\n任务描述"])
        self.assertEqual(self.client.get(path, params={"field": "remark", "q": "50%"}).json(), ["完成 50%"])

        self.register("Worker02")
        self.login("Worker02")
        self.assertEqual(self.client.get(path, params={"field": "project"}).json(), [])
        self.assertEqual(self.client.get(path, params={"field": "project", "user_id": owner}).status_code, 403)
        self.login("admin")
        self.assertEqual(self.client.get(path, params={"field": "project", "user_id": owner, "q": "旧"}).json(), ["旧项目"])

    def test_admin_disable_reset_profile_and_export(self):
        self.register()
        self.login()
        profile = self.client.put("/api/profile", json={"name":"同名人员","position":"工程师"})
        self.assertEqual(profile.json()["name"], "同名人员")
        self.client.post("/api/records", json=self.entry())
        self.login("admin")
        users = self.client.get("/api/users").json()
        target = next(u for u in users if u["username"] == self.account("Worker01"))
        self.assertEqual(self.client.post(f'/api/users/{target["id"]}/reset-password').status_code, 204)
        response = self.client.get("/api/export?year=2026")
        self.assertEqual(response.status_code, 200, response.text)
        workbook = load_workbook(BytesIO(response.content))
        self.assertIn("工时打卡明细", workbook.sheetnames)
        self.assertTrue(any(c.data_type == "f" for ws in workbook for row in ws for c in row))
        self.assertEqual(self.client.delete(f'/api/users/{target["id"]}').status_code, 204)
        self.assertEqual(self.client.get("/api/records?year=2026").json()["total"], 1)
        self.assertEqual(self.client.get("/api/export?year=2026").status_code, 400)
        self.assertEqual(self.client.get("/api/export?year=2026&include_inactive=true").status_code, 200)
        self.assertEqual(self.login().status_code, 401)
        self.assertEqual(self.register().status_code, 409)

    def test_cross_year_failure_rolls_back_both_files(self):
        self.register(); self.login()
        record_id = self.client.post("/api/records", json=self.entry()).json()["id"]
        source = self.database.year_engine(2026)
        with source.begin() as connection:
            connection.exec_driver_sql("CREATE TRIGGER force_failure BEFORE DELETE ON work_records BEGIN SELECT RAISE(ABORT, 'test rollback'); END")
        from sqlalchemy.exc import IntegrityError
        with self.assertRaises(IntegrityError):
            self.client.put(f"/api/records/2026/{record_id}", json=dict(self.entry(), work_date="2025-12-31"))
        self.assertEqual(self.client.get("/api/records?year=2026").json()["total"], 1)
        self.assertEqual(self.client.get("/api/records?year=2025").json()["total"], 0)

    def test_export_treats_user_text_as_text_and_leave_rules(self):
        self.register(); self.login()
        self.client.post("/api/records", json=dict(self.entry(), project="=1+1", description="=2+2"))
        self.client.post("/api/records", json=dict(self.entry(), project="年假", task_type="年假", hours=8, code_lines=900))
        self.login("admin")
        result = self.client.get("/api/export?year=2026")
        self.assertEqual(result.status_code, 200)
        workbook = load_workbook(BytesIO(result.content))
        detail = workbook["工时打卡明细"]
        self.assertEqual(detail["C2"].data_type, "s")
        self.assertEqual(detail["E2"].data_type, "s")
        from app.excel_export import parse_payload, calculate_statistics
        config, entries = parse_payload({"config":{"standardHours":10,"annualLeaveDays":7,"people":["a"]},
            "entries":[{"date":"2026-11-04","project":"年假","taskType":"年假","description":"年假","hours":8,"codeLines":900,"person":"a"},
                       {"date":"2026-11-04","project":"开发","taskType":"编码开发","description":"工作","hours":2,"codeLines":100,"person":"a"}]})
        stats = calculate_statistics(config, entries)
        self.assertEqual(stats["totalHours"], 10)
        self.assertEqual(stats["totalCodeLines"], 100)
        self.assertEqual(stats["projects"][0]["hours"], 2)

    def test_calendar_search_pagination_inactive_and_dashboard(self):
        self.register(); self.login()
        for n in range(25):
            self.client.post("/api/records", json=dict(self.entry(), description=f"说明{n}"))
        self.assertEqual(self.client.get("/api/statistics?year=2026").status_code, 403)
        self.assertEqual(self.client.get("/api/records?year=2026&month=2&day=31").status_code, 422)
        self.assertEqual(self.client.get("/api/records?year=2026&day=4").status_code, 422)
        self.assertEqual(self.client.get("/api/records?year=2024&month=2&day=29").status_code, 200)
        self.assertEqual(self.client.get("/api/records?year=2025&month=2&day=29").status_code, 422)
        for word in ("2026-11", "7.5", "100", "平台", "说明", "Worker01"):
            result = self.client.get("/api/records", params={"year":2026,"keyword":word}).json()
            self.assertEqual(result["total"], 25, word)
        result = self.client.get("/api/records?year=2026&page_size=20&page=2").json()
        self.assertEqual((result["total"],len(result["items"])), (25,5))
        self.login("admin")
        stats = self.client.get("/api/statistics?year=2026").json()
        self.assertEqual(stats["totalHours"], 25*7.5)
        self.assertEqual(stats["teamMonthly"][0]["actualHours"], 25*7.5)
        target = next(u for u in self.client.get("/api/users").json() if u["username"] == self.account("Worker01"))
        self.client.delete(f'/api/users/{target["id"]}')
        self.assertEqual(self.client.get("/api/records?year=2026&include_inactive=false").json()["total"],0)
        self.assertEqual(self.client.get("/api/records?year=2026&include_inactive=true").json()["total"],25)
        self.assertIsNone(self.client.get("/api/statistics?year=2026").json())
        self.assertEqual(self.client.get("/api/statistics?year=2026&include_inactive=true").json()["totalHours"],25*7.5)

    def test_export_uses_year_and_inactive_only(self):
        self.register(); self.login()
        for n in range(12):
            self.client.post("/api/records",json=dict(self.entry(),description=f"保留{n}"))
        self.client.post("/api/records",json=dict(self.entry(),work_date="2026-10-04",description="保留但月份不同"))
        self.client.post("/api/records",json=dict(self.entry(),work_date="2026-11-05",description="保留但日期不同"))
        self.client.post("/api/records",json=dict(self.entry(),description="不匹配关键词"))
        self.register("Worker02"); self.login("Worker02")
        self.client.post("/api/records",json=dict(self.entry(),description="保留停用用户"))
        self.login("admin")
        target = next(u for u in self.client.get("/api/users").json() if u["username"] == self.account("Worker02"))
        self.client.delete(f'/api/users/{target["id"]}')
        for include, expected in (("false",15),("true",16)):
            filters = dict(year=2026,month=11,day=4,keyword="保留",include_inactive=include)
            listed = self.client.get("/api/records",params=dict(filters,page_size=10)).json()
            exported = self.client.get("/api/export",params=filters)
            self.assertEqual(exported.status_code,200,exported.text[:100] if exported.status_code != 200 else "")
            workbook = load_workbook(BytesIO(exported.content))
            rows = [r for r in workbook["工时打卡明细"].iter_rows(min_row=2,values_only=True) if r[0] is not None]
            self.assertEqual(listed["total"],12 if include == "false" else 13)
            self.assertEqual(len(rows),expected)
            self.assertTrue(all(r[1].year == 2026 for r in rows))
            self.assertTrue(any(r[1].month == 10 for r in rows))
            self.assertTrue(any(r[4] == "不匹配关键词" for r in rows))
        self.assertEqual(self.client.get("/api/export?year=2026&month=2&day=31").status_code,200)

    def test_reenable_user_keeps_password_history_and_revokes_old_session(self):
        self.register(); self.login()
        self.client.post('/api/records',json=self.entry())
        self.client.post('/api/auth/password',json={'current_password':'123456','new_password':'changed123'})
        self.login(password='changed123')
        old_token=self.client.cookies.get('itime_session')
        self.login('admin')
        target=next(u for u in self.client.get('/api/users').json() if u['username']==self.account('Worker01'))
        path='/api/users/'+str(target['id'])
        self.assertEqual(self.client.delete(path).status_code,204)
        self.assertEqual(self.login(password='changed123').status_code,401)
        self.assertEqual(self.client.post(path+'/enable').status_code,204)
        self.client.cookies.clear()
        self.client.cookies.set('itime_session',old_token)
        self.assertEqual(self.client.get('/api/auth/me').status_code,401)
        self.client.cookies.clear()
        self.assertEqual(self.login(password='changed123').status_code,200)
        self.assertEqual(self.client.get('/api/records?year=2026').json()['total'],1)
        self.assertEqual(self.client.post(path+'/enable').status_code,403)

    def test_admin_excluded_from_statistics_export_and_people_list(self):
        self.register(); self.login()
        self.client.post('/api/records',json=self.entry())
        self.login('admin')
        self.assertEqual(self.client.post('/api/records',json=self.entry()).status_code,422)
        self.assertEqual(self.client.post('/api/records',json=dict(self.entry(),user_id=1)).status_code,422)
        from datetime import date
        with Session(self.database.year_engine(2026)) as db:
            db.add(WorkRecord(user_id=1,work_date=date(2026,11,4),project='旧数据',task_type='编码开发',description='管理员旧记录',hours_tenths=240))
            db.commit()
        for include in ('true','false'):
            stats=self.client.get('/api/statistics',params={'year':2026,'include_inactive':include}).json()
            self.assertEqual(stats['peopleCount'],1)
            self.assertEqual(stats['totalHours'],7.5)
            response=self.client.get('/api/export',params={'year':2026,'include_inactive':include})
            self.assertEqual(response.status_code,200)
            workbook=load_workbook(BytesIO(response.content))
            self.assertNotIn('管理员(admin)',workbook['数据统计汇总']['B5'].value)
            rows=[r for r in workbook['工时打卡明细'].iter_rows(min_row=2,values_only=True) if r[0] is not None]
            self.assertEqual(len(rows),1)
            self.assertNotEqual(rows[0][7],'管理员(admin)')

    def test_admin_cannot_assign_records_to_admin(self):
        self.register(); self.login()
        record=self.client.post('/api/records',json=self.entry()).json()
        self.login('admin')
        path='/api/records/2026/'+str(record['id'])
        self.assertEqual(self.client.put(path,json=dict(self.entry(),user_id=1)).status_code,422)
        self.assertEqual(self.client.put(path,json=self.entry()).status_code,200)
        self.assertEqual(self.client.get('/api/records?year=2026').json()['items'][0]['user_id'],2)

    def test_validation_and_environment(self):
        self.register(); self.login()
        for data in (dict(self.entry(), hours=1.25), dict(self.entry(), code_lines=-1),
                     dict(self.entry(),project=" "), dict(self.entry(), task_type="not-a-type"),
                     dict(self.entry(),work_date="1800-01-01")):
            self.assertEqual(self.client.post("/api/records",json=data).status_code,422)
        self.assertEqual(self.client.get("/api/records?year=0").status_code,422)
        with patch.dict("os.environ", {"ITIME_ENV":"local"}):
            self.assertEqual(load_settings()[1], "local")
            self.assertEqual(data_root(), ROOT / load_settings()[2].get("data-dir", "data/mock"))
        with patch.dict("os.environ", {"ITIME_ENV":"production"}):
            self.assertEqual(load_settings()[1], "production")
            self.assertEqual(data_root(), ROOT / load_settings()[2].get("data-dir", "data"))
        seed_mock(self.database)
        with Session(self.database.year_engine(2026)) as db:
            count = len(list(db.scalars(select(WorkRecord))))
        seed_mock(self.database)
        with Session(self.database.year_engine(2026)) as db:
            self.assertEqual(len(list(db.scalars(select(WorkRecord)))), count)

if __name__ == "__main__":
    unittest.main()
