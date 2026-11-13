import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
import launch_game
class LauncherTests(unittest.TestCase):
    def test_backup_verify_and_force_renderer(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);(r/'native_bin').mkdir();(r/'companion').mkdir();(r/'game').mkdir()
            (r/'native_bin/Hyperspace.dll').write_bytes(b'new');(r/'game/Hyperspace.dll').write_bytes(b'old')
            exe=r/'game/FTLGame.exe';exe.write_bytes(b'test')
            with patch.object(launch_game,'ROOT',r/'companion'),patch.object(launch_game.subprocess,'Popen') as run:
                launch_game.install_and_launch(exe)
                self.assertEqual((r/'game/Hyperspace.dll').read_bytes(),b'new')
                backup=list((r/'game').glob('*.bak'));self.assertEqual(len(backup),1);self.assertEqual(backup[0].read_bytes(),b'old')
                self.assertEqual(run.call_args.args[0],[str(exe),'--force-opengl'])
                launch_game.install_and_launch(exe);self.assertEqual(len(list((r/'game').glob('*.bak'))),1)
    def test_wrong_executable_refused(self):
        with self.assertRaises(ValueError):launch_game.install_and_launch('ftlman.exe')

    def test_missing_package_dll_allows_only_verified_installed_copy(self):
        import json,hashlib
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);(r/'companion').mkdir();(r/'game').mkdir()
            exe=r/'game/FTLGame.exe';exe.write_bytes(b'test')
            dll=r/'game/Hyperspace.dll';dll.write_bytes(b'correct')
            (r/'BUILD_INFO.json').write_text(json.dumps(dict(dll_sha256=hashlib.sha256(b'correct').hexdigest())))
            with patch.object(launch_game,'ROOT',r/'companion'),patch.object(launch_game.subprocess,'Popen') as run:
                launch_game.install_and_launch(exe);self.assertEqual(run.call_count,1)
                dll.write_bytes(b'old')
                with self.assertRaises(ValueError):launch_game.install_and_launch(exe)
                self.assertEqual(run.call_count,1)
