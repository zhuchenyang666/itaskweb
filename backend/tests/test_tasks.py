import unittest
from io import BytesIO
from openpyxl import load_workbook
import test_auth
from app.excel_export import build_export_workbook

class TaskTests(unittest.TestCase):
    setUp=test_auth.AuthTests.setUp
    tearDown=test_auth.AuthTests.tearDown
    account=staticmethod(test_auth.AuthTests.account)
    register=test_auth.AuthTests.register
    login=test_auth.AuthTests.login

    def test_admin_only_task_management_and_history(self):
        self.register(); self.login()
        for method,path,body in [('get','/api/tasks',None),('post','/api/tasks',{'name':'新任务'}),('put','/api/tasks/1',{'name':'新任务'}),('delete','/api/tasks/1',None)]:
            self.assertEqual(getattr(self.client,method)(path,**({'json':body} if body else {})).status_code,403)
        self.login('admin')
        self.assertEqual(self.client.post('/api/tasks',json={'name':'=1+1'}).status_code,422)
        self.assertEqual(self.client.post('/api/tasks',json={'name':'  '}).status_code,422)
        task=self.client.post('/api/tasks',json={'name':'专项测试'}).json()
        employee=next(u['id'] for u in self.client.get('/api/users').json() if u['role']=='user')
        body=dict(user_id=employee,work_date='2026-11-04',project='测试项目',task_type='专项测试',description='历史记录',hours=8,code_lines=0)
        record=self.client.post('/api/records',json=body).json()
        self.assertEqual(self.client.post('/api/records',json=dict(body,work_date='2025-12-31')).status_code,201)
        self.assertEqual(self.client.put('/api/tasks/'+str(task['id']),json={'name':'专项验证'}).status_code,200)
        self.assertIn('专项验证',self.client.get('/api/options').json()['task_types'])
        self.assertEqual(self.client.delete('/api/tasks/'+str(task['id'])).status_code,204)
        self.assertEqual(self.client.post('/api/records',json=body).status_code,422)
        self.assertEqual(self.client.put('/api/records/2026/'+str(record['id']),json=dict(body,hours=9)).status_code,404)
        self.assertEqual(self.client.get('/api/records?year=2026').json()['total'],0)
        self.assertEqual(self.client.get('/api/records?year=2025').json()['total'],0)
        response=self.client.get('/api/export?year=2026')
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.client.post('/api/tasks',json={'name':'专项测试'}).status_code,409)

    def test_leave_rename_delete_removes_old_and_new_records(self):
        self.register(); self.login('admin')
        task=next(t for t in self.client.get('/api/tasks').json() if t['name']=='年假')
        employee=next(u['id'] for u in self.client.get('/api/users').json() if u['role']=='user')
        body=dict(user_id=employee,work_date='2026-11-04',project='年假',task_type='年假',description='休假',hours=8,code_lines=900)
        self.client.post('/api/records',json=body)
        self.client.put('/api/tasks/'+str(task['id']),json={'name':'年休假'})
        self.assertEqual(self.client.post('/api/records',json=dict(body,task_type='年休假')).status_code,201)
        self.client.delete('/api/tasks/'+str(task['id']))
        stats=self.client.get('/api/statistics?year=2026').json()
        self.assertEqual(stats['totalHours'],0)
        self.assertEqual(stats['totalCodeLines'],0)
        self.assertEqual(stats['projects'],[])

    def test_export_many_rows_preserves_values_and_styles(self):
        payload={'config':{'people':['测试人']},'entries':[dict(date='2026-11-04',person='测试人',project='项目',taskType='编码开发',description=f'记录{i}',hours=8,codeLines=i,note='备注') for i in range(300)]}
        workbook=load_workbook(build_export_workbook(payload))
        detail=workbook['工时打卡明细']
        self.assertEqual(detail['A301'].value,300)
        self.assertEqual(detail['E301'].value,'记录299')
        self.assertEqual(detail['F301'].number_format,'0.0')
        self.assertEqual(detail['B301'].number_format,'yyyy-mm-dd')
        self.assertEqual(detail['E301'].font.name,'微软雅黑')
        self.assertFalse(detail['E301'].protection.locked)
        self.assertTrue(any(c.data_type=='f' for ws in workbook for row in ws for c in row))

if __name__=='__main__':
    unittest.main()
