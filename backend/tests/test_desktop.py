import asyncio
import inspect
from pathlib import Path
import unittest
from unittest.mock import patch
import desktop_start
from desktop_control import check_control
from app import settings

class DesktopTests(unittest.TestCase):
    def test_native_single_instance_and_shutdown_event(self):
        self.assertTrue(check_control())

    def test_source_packaged_app_without_listening(self):
        result = asyncio.run(desktop_start.check_app())
        self.assertTrue(result["database"])
        self.assertTrue(result["api"])
        self.assertTrue(result["frontend"])

    def test_startup_notice_shows_browser_address(self):
        url = "http://127.0.0.1:5173/"
        with patch.object(desktop_start, "message") as notice, patch.object(desktop_start.webbrowser, "open") as browser:
            desktop_start.show_startup(url, True)
            browser.assert_called_once_with(url)
            self.assertIn(url, notice.call_args.args[0])
            browser.reset_mock()
            desktop_start.show_startup(url, False)
            browser.assert_not_called()
            self.assertIn(url, notice.call_args.args[0])

    def test_packaged_resources_live_beside_exe(self):
        source = inspect.getsource(settings)
        namespace = {"__file__":settings.__file__,"__name__":"settings_check"}
        with patch.object(settings.sys, "frozen", True, create=True), patch.object(settings.sys, "executable", "D:/发布/iTime/启动工时服务.exe"):
            exec(compile(source,settings.__file__,"exec"),namespace)
        self.assertEqual(namespace["ROOT"], Path("D:/发布/iTime/backend"))

if __name__ == "__main__":
    unittest.main()
