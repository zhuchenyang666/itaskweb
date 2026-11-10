import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from openpyxl import load_workbook
import test_auth
from app.main import create_app
from app.excel_export import build_export_workbook

class SettingsTests(unittest.TestCase):
    setUp=test_auth.AuthTests.setUp
    tearDown=test_auth.AuthTests.tearDown
    account=staticmethod(test_auth.AuthTests.account)
    register=test_auth.AuthTests.register
    login=test_auth.AuthTests.login

    def test_permissions_defaults_validation_and_persistence(self):
        self.register(); self.login()
        self.assertEqual(self.client.get('/api/settings').status_code,403)
        self.assertEqual(self.client.put('/api/settings',json={'standard_hours':8,'annual_leave_days':10}).status_code,403)
        self.login('admin')
        self.assertEqual(self.client.get('/api/settings').json(),{'standard_hours':10,'annual_leave_days':7})
        for hours,leave in ((0,7),(24.1,7),(8.25,7),(10,-1),(10,365.5),(10,7.1)):
            self.assertEqual(self.client.put('/api/settings',json={'standard_hours':hours,'annual_leave_days':leave}).status_code,422)
        self.assertEqual(self.client.put('/api/settings',json={'standard_hours':8,'annual_leave_days':9.5}).status_code,200)
        with TestClient(create_app(self.root)) as client:
            client.post('/api/auth/login',json={'username':'admin','password':'123456'})
            self.assertEqual(client.get('/api/settings').json(),{'standard_hours':8,'annual_leave_days':9.5})

    def test_statistics_and_export_use_saved_settings(self):
        self.register(); self.login('admin')
        employee=next(u['id'] for u in self.client.get('/api/users').json() if u['role']=='user')
        self.client.put('/api/settings',json={'standard_hours':8,'annual_leave_days':9})
        self.client.post('/api/records',json=dict(user_id=employee,work_date='2026-11-04',project='年假',task_type='年假',description='休假',hours=8,code_lines=0))
        stats=self.client.get('/api/statistics?year=2026').json()
        row=stats['personalYearly'][0]
        self.assertEqual(row['expectedHours'],row['workdays']*8)
        self.assertEqual(row['leaveDays'],1)
        response=self.client.get('/api/export?year=2026&month=1&keyword=不存在')
        self.assertEqual(response.status_code,200)
        workbook=load_workbook(BytesIO(response.content))
        self.assertEqual(workbook['数据统计汇总']['B2'].value,8)
        self.assertEqual(workbook['数据统计汇总']['B3'].value,9)

    def test_no_statistics_yaml_needed_for_fresh_database_or_export(self):
        original = Path.read_text
        def guarded(path, *args, **kwargs):
            if path.name == 'statistics.yaml':
                raise AssertionError('不应读取已移除的统计配置文件')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded):
            with TestClient(create_app(self.root/'fresh')) as client:
                client.post('/api/auth/login',json={'username':'admin','password':'123456'})
                self.assertEqual(client.get('/api/settings').json(),{'standard_hours':10,'annual_leave_days':7})
                self.assertEqual(len(client.get('/api/options').json()['task_types']),10)
                client.post('/api/users',json={'username':'testing'})
                employee=next(u['id'] for u in client.get('/api/users').json() if u['role']=='user')
                body=dict(user_id=employee,work_date='2026-11-04',project='项目',task_type='编码开发',description='测试',hours=8,code_lines=100)
                self.assertEqual(client.post('/api/records',json=body).status_code,201)
                self.assertEqual(client.get('/api/statistics?year=2026').status_code,200)
                self.assertEqual(client.get('/api/export?year=2026').status_code,200)

    def test_export_widths_and_long_text_row_heights(self):
        people=[f'测试人员{i}(testingaccount{i}@hengbao.com)' for i in range(32)]
        payload={'config':{'people':people,'holidays':[f'2026-01-{i:02}' for i in range(1,25)]},'entries':[dict(date='2026-11-04',person=name,project='项目',taskType='编码开发',description='任务描述内容'*30,hours=8,codeLines=100,note='备注内容'*20) for name in people]}
        workbook=load_workbook(build_export_workbook(payload))
        detail=workbook['工时打卡明细']; summary=workbook['数据统计汇总']
        for column,minimum in [('H',36),('E',50),('I',40),('D',20)]:
            self.assertGreaterEqual(detail.column_dimensions[column].width,minimum)
        self.assertLessEqual(detail.column_dimensions['F'].width,12)
        self.assertLessEqual(detail.column_dimensions['G'].width,12)
        self.assertGreater(detail.row_dimensions[2].height,30)
        self.assertGreaterEqual(summary.column_dimensions['B'].width,40)
        self.assertGreater(summary.row_dimensions[4].height,34)
        self.assertGreater(summary.row_dimensions[5].height,40)
        self.assertEqual(summary['B5'].value,','.join(people))
        self.assertFalse(detail['H2'].protection.locked)

if __name__=='__main__':
    unittest.main()
