import os
import sys
import win32api
import win32con
import win32gui
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))))
from utility.setting import *


def leftClick(x, y, hwnd):
    lParam = win32api.MAKELONG(x, y)
    win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
    win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP, 0, lParam)


def doubleClick(x, y, hwnd):
    leftClick(x, y, hwnd)
    leftClick(x, y, hwnd)
    win32api.Sleep(300)


def window_enumeration_handler(hwndd, top_windows):
    top_windows.append((hwndd, win32gui.GetWindowText(hwndd)))


def enum_windows():
    windows = []
    win32gui.EnumWindows(window_enumeration_handler, windows)
    return windows


def find_window(caption):
    hwnd = win32gui.FindWindow(None, caption)
    if hwnd == 0:
        windows = enum_windows()
        for handle, title in windows:
            if caption in title:
                hwnd = handle
                break
    return hwnd


def enter_keys(hwndd, data):
    win32api.SendMessage(hwndd, win32con.EM_SETSEL, 0, -1)
    win32api.SendMessage(hwndd, win32con.EM_REPLACESEL, 0, data)
    win32api.Sleep(300)


def click_button(btn_hwnd):
    win32api.PostMessage(btn_hwnd, win32con.WM_LBUTTONDOWN, 0, 0)
    win32api.Sleep(100)
    win32api.PostMessage(btn_hwnd, win32con.WM_LBUTTONUP, 0, 0)
    win32api.Sleep(300)


def manual_login(gubun):
    """
    gubun == 1 : 첫번째 계정 모의서버
    gubun == 2 : 첫번째 계정 본서버
    gubun == 3 : 두번째 계정 모의서버
    gubun == 4 : 두번째 계정 본서버
    """
    hwnd = find_window('Open API login')
    if gubun in [1, 3]:
        if win32gui.IsWindowEnabled(win32gui.GetDlgItem(hwnd, 0x3EA)):
            click_button(win32gui.GetDlgItem(hwnd, 0x3ED))
    elif gubun in [2, 4]:
        if not win32gui.IsWindowEnabled(win32gui.GetDlgItem(hwnd, 0x3EA)):
            click_button(win32gui.GetDlgItem(hwnd, 0x3ED))
    if gubun in [1, 2]:
        enter_keys(win32gui.GetDlgItem(hwnd, 0x3E8), DICT_SET['아이디1'])
        enter_keys(win32gui.GetDlgItem(hwnd, 0x3E9), DICT_SET['비밀번호1'])
        enter_keys(win32gui.GetDlgItem(hwnd, 0x3EA), DICT_SET['인증서비밀번호1'])
        doubleClick(15, 15, win32gui.GetDlgItem(hwnd, 0x3E8))
        enter_keys(win32gui.GetDlgItem(hwnd, 0x3E8), DICT_SET['아이디1'])
        doubleClick(15, 15, win32gui.GetDlgItem(hwnd, 0x3EA))
        enter_keys(win32gui.GetDlgItem(hwnd, 0x3EA), DICT_SET['인증서비밀번호1'])
        click_button(win32gui.GetDlgItem(hwnd, 0x1))
    elif gubun in [3, 4]:
        enter_keys(win32gui.GetDlgItem(hwnd, 0x3E8), DICT_SET['아이디2'])
        enter_keys(win32gui.GetDlgItem(hwnd, 0x3E9), DICT_SET['비밀번호2'])
        enter_keys(win32gui.GetDlgItem(hwnd, 0x3EA), DICT_SET['인증서비밀번호2'])
        doubleClick(15, 15, win32gui.GetDlgItem(hwnd, 0x3E8))
        enter_keys(win32gui.GetDlgItem(hwnd, 0x3E8), DICT_SET['아이디2'])
        doubleClick(15, 15, win32gui.GetDlgItem(hwnd, 0x3EA))
        enter_keys(win32gui.GetDlgItem(hwnd, 0x3EA), DICT_SET['인증서비밀번호2'])
        click_button(win32gui.GetDlgItem(hwnd, 0x1))
    click_button(win32gui.GetDlgItem(hwnd, 0x1))


def auto_on(gubun):
    """
    gubun == 1 : 첫번째 계정
    gubun == 2 : 두번째 계정
    """
    hwnd = find_window('계좌비밀번호')
    if hwnd != 0:
        edit = win32gui.GetDlgItem(hwnd, 0xCC)
        if gubun == 1:
            win32gui.SendMessage(edit, win32con.WM_SETTEXT, 0, DICT_SET['계좌비밀번호1'])
        elif gubun == 2:
            win32gui.SendMessage(edit, win32con.WM_SETTEXT, 0, DICT_SET['계좌비밀번호2'])
        click_button(win32gui.GetDlgItem(hwnd, 0xD4))
        click_button(win32gui.GetDlgItem(hwnd, 0xD3))
        click_button(win32gui.GetDlgItem(hwnd, 0x01))
