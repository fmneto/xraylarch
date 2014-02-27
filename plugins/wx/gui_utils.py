#!/usr/bin/env python

import sys
if not hasattr(sys, 'frozen'):
    try:
        import wxversion
        wxversion.ensureMinimal('2.8')
    except:
        pass

import wx
import time
import os

MODNAME = '_sys.wx'
DEF_CHOICES = [('All Files', '*.*')]

def SafeWxCall(fcn):
    """decorator to wrap function in a wx.CallAfter() so that
    calls can be made in a separate thread, and asynchronously.
    """
    def wrapper(*args, **kwargs):
        "callafter wrapper"
        try:
            wx.CallAfter(fcn, *args, **kwargs)
        except PyDeadObjectError:
            pass
    wrapper.__doc__ = fcn.__doc__
    wrapper.__name__ = fcn.__name__
    wrapper.__dict__.update(fcn.__dict__)
    return wrapper

def ensuremod(_larch, modname=None):
    if _larch is not None:
        symtable = _larch.symtable
        if modname is not None and not symtable.has_group(modname):
            symtable.newgroup(modname)
        return symtable


def _wxupdate(_larch=None, **kws):
    """force an update of wxPython windows"""
    symtable = ensuremod(_larch, '_sys')
    symtable = ensuremod(_larch, '_sys.wx')
    input_handler = symtable.get_symbol('_sys.wx.inputhook').input_handler
    wxping = symtable.get_symbol('_sys.wx.ping')
    if input_handler is not None:
        symtable.set_symbol("_sys.wx.force_wxupdate", True)
        wxping(0.002)

class wxLarchTimer(wx.MiniFrame):
   """hidden wx frame that contains only a timer widget.
   This timer widget will periodically force a wx update
   """
   def __init__(self, parent, _larch, polltime=50):
       wx.MiniFrame.__init__(self, parent, -1, '')
       self.Show(False)
       self.polltime = polltime
       tid = wx.NewId()
       self.timer = wx.Timer(self, tid)
       wx.EVT_TIMER(self, tid, self.OnTimer)
       self.symtable = _larch.symtable
       self.wxping =self.symtable.get_symbol('_sys.wx.ping')

   def Start(self, polltime = None):
       if polltime is None: polltime = self.polltime
       if polltime is None: polltime = 500
       self.timer.Start(polltime)

   def Stop(self):
       self.wxping(0.005)
       self.symtable.set_symbol("_sys.wx.force_wxupdate", True)
       self.timer.Stop()
       self.Destroy()

   def OnTimer(self, event=None):
       """timer events -- here we execute any un-executed shell code"""
       self.symtable.set_symbol('_sys.wx.force_wxupdate', True)
       self.wxping(0.001)
       time.sleep(0.001)
       print(" ..")

# @SafeWxCall
def _gcd(wxparent=None, _larch=None, **kws):
    """Directory Browser to Change Directory"""
    dlg = wx.DirDialog(None, 'Choose Directory',
                       defaultPath = os.getcwd(),
                       style = wx.DD_DEFAULT_STYLE)

    if dlg.ShowModal() == wx.ID_OK:
        os.chdir(dlg.GetPath())
    dlg.Destroy()
    return os.getcwd()


# @SafeWxCall
def _fileprompt(mode='open', multi=True, message = None,
                fname=None, choices=None, _larch=None, **kws):
    """Bring up File Browser for opening or saving file.
    Returns name of selected file.

    options:
       mode:     one of 'open' or 'save'
       fname:    default filename
       message:  text to display in top window bar
       multi:    whether multiple files are allowed [True]
       choices:  list of (title, fileglob) to restrict choices

    > x = fileprompt(choices=(('All Files', '*.*'), ('Python Files', '*.py')))
       
    """
    symtable = ensuremod(_larch)

    if fname is None:
        fname = ''
        try:
            fname = symtable.get_symbol("%s.default_filename" % MODNAME)
        except:
            pass
    symtable.set_symbol("%s.default_filename" % MODNAME, fname)
    
    if choices is None or len(choices) < 1:
        choices = DEF_CHOICES
        try:
            choices = symtable.get_symbol("%s.ext_choices" % MODNAME)
        except:
            pass
    symtable.set_symbol("%s.ext_choices" % MODNAME, choices)

    wildcard = []
    for title, fglob in choices:
        wildcard.append('%s (%s)|%s' % (title, fglob, fglob))
    wildcard = '|'.join(wildcard)

    if mode == 'open':
        style = wx.OPEN|wx.CHANGE_DIR
        if multi:
            style = style|wx.MULTIPLE
        if message is None:
            message = 'Open File '
    else:
        style = wx.SAVE|wx.CHANGE_DIR
        if message is None:
            message = 'Save As '

    #parent.Start()
    parent = _larch.symtable.get_symbol('_sys.wx.wxapp')
    if hasattr(parent, 'GetTopWindow'):
        parent = parent.GetTopWindow()
    timer = wxLarchTimer(parent, _larch)
    dlg = wx.FileDialog(parent=timer, message=message,
                        defaultDir=os.getcwd(),
                        defaultFile=fname,
                        wildcard =wildcard,
                        style=style)
    path = None
    if dlg.ShowModal() == wx.ID_OK:
        path = dlg.GetPaths()
        if len(path) == 1:
            path = path[0]

    dlg.Destroy()
    timer.Destroy()
    return path

def registerLarchPlugin():
    return (MODNAME, {'gcd': _gcd,
                      'fileprompt': _fileprompt,
                      'wx_update': _wxupdate})

