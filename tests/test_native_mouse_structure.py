"""Cross-platform tests for native mouse protocol math and Windows structure sizes."""
import ctypes
import unittest

import native_mouse


class MouseLayoutTests(unittest.TestCase):
    def test_small_coordinate_tolerance(self):
        self.assertTrue(native_mouse._close((101, 203), (100, 200)))
        self.assertFalse(native_mouse._close((105, 200), (100, 200)))

    def test_windows_structure_layout(self):
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_int32), ("dy", ctypes.c_int32),
                ("mouseData", ctypes.c_uint32), ("dwFlags", ctypes.c_uint32),
                ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t),
            ]
        class INPUTUNION(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]
        class INPUT(ctypes.Structure):
            _fields_ = [("type", ctypes.c_uint32), ("union", INPUTUNION)]
        expected = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
        self.assertEqual(ctypes.sizeof(INPUT), expected)


if __name__ == "__main__":
    unittest.main()
