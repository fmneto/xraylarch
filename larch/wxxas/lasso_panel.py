#!/usr/bin/env python
"""
Linear Combination panel
"""
import os
import time
import wx
import wx.grid as wxgrid
import numpy as np

from functools import partial
from collections import OrderedDict

from lmfit.printfuncs import gformat
from larch import Group
from larch.math import index_of
from larch.wxlib import (BitmapButton, TextCtrl, FloatCtrl, get_icon,
                         SimpleText, pack, Button, HLine, Choice, Check,
                         CEN, RCEN, LCEN, Font)
from larch.io import read_csv
from larch.utils.strutils import fix_varname

from .taskpanel import TaskPanel

# plot options:
norm   = 'Normalized \u03bC(E)'
dmude  = 'd\u03bC(E)/dE'
chik   = '\u03c7(k)'
noplot = '<no plot>'
noname = '<none>'

FILE_WILDCARDS = "CSV Files(*.csv,*.dat)|*.csv*;*.dat|All files (*.*)|*.*"

FitSpace_Choices = [norm, dmude, chik]
Plot_Choices = ['Mean Spectrum + Active Energies', 'Spectra Stack',
                'Predicted External Varliable']

defaults = dict(fitspace=norm, fit_intercept=True, alpha=0.01,
                varname='valence', xmin=-5.e5, xmax=5.e5)

NROWS = 5000
class ExtVarDataTable(wxgrid.GridTableBase):
    def __init__(self):
        wxgrid.GridTableBase.__init__(self)
        self.colLabels = [' File /Group Name      ',   'External Variable']
        self.dataTypes = [wxgrid.GRID_VALUE_STRING,
                          wxgrid.GRID_VALUE_FLOAT+ ':12,4']

        self.data = []
        for i in range(NROWS):
            self.data.append([' ', 0])

    def GetNumberRows(self):
        return NROWS

    def GetNumberCols(self):
        return 2

    def GetValue(self, row, col):
        try:
            return self.data[row][col]
        except IndexError:
            return ''

    def SetValue(self, row, col, value):
        self.data[row][col] = value

    def GetColLabelValue(self, col):
        return self.colLabels[col]

    def GetRowLabelValue(self, row):
        return "%d" % (row+1)

    def GetTypeName(self, row, col):
        return self.dataTypes[col]

    def CanGetValueAs(self, row, col, typeName):
        colType = self.dataTypes[col].split(':')[0]
        if typeName == colType:
            return True
        else:
            return False

    def CanSetValueAs(self, row, col, typeName):
        return self.CanGetValueAs(row, col, typeName)


class ExtVarTableGrid(wxgrid.Grid):
    def __init__(self, parent):
        wxgrid.Grid.__init__(self, parent, -1)

        self.table = ExtVarDataTable()
        self.SetTable(self.table, True)
        self.SetRowLabelSize(40)
        self.SetMargins(10, 10)
        self.EnableDragRowSize()
        self.EnableDragColSize()
        self.AutoSizeColumns(False)
        self.SetColSize(0, 325)
        self.SetColSize(1, 125)

        self.Bind(wxgrid.EVT_GRID_CELL_LEFT_DCLICK, self.OnLeftDClick)

    def OnLeftDClick(self, evt):
        if self.CanEnableCellControl():
            self.EnableCellEditControl()


class LASSOPanel(TaskPanel):
    """LASSO Panel"""
    def __init__(self, parent, controller, **kws):
        TaskPanel.__init__(self, parent, controller,
                           configname='lasso_config', config=defaults,
                           title='LASSO, Linear Feature Selection', **kws)
        self.result = None
        self.save_filename = 'LassoData.csv'

    def process(self, dgroup, **kws):
        """ handle LASSO processing"""
        if self.skip_process:
            return
        self.skip_process = True
        form = self.read_form()

    def build_display(self):
        panel = self.panel
        wids = self.wids
        self.skip_process = True

        wids['fitspace'] = Choice(panel, choices=FitSpace_Choices, size=(250, -1))
        wids['fitspace'].SetStringSelection(norm)
        wids['plotchoice'] = Choice(panel, choices=Plot_Choices,
                                  size=(250, -1), action=self.onPlot)

        add_text = self.add_text

        opts = dict(digits=2, increment=1.0)

        w_xmin = self.add_floatspin('xmin', value=defaults['xmin'], **opts)
        w_xmax = self.add_floatspin('xmax', value=defaults['xmax'], **opts)
        w_alpha = self.add_floatspin('alpha', digits=5,
                                     value=defaults['alpha'],
                                     increment=0.0002, with_pin=False,
                                     min_val=0, max_val=1.0)

        wids['auto_alpha'] = Check(panel, default=False, label='auto?')

        wids['fit_intercept'] = Check(panel, default=True, label='fit intercept?')

        wids['save_csv'] = Button(panel, 'Save CSV File', size=(150, -1),
                                    action=self.onSaveCSV)
        wids['load_csv'] = Button(panel, 'Load CSV File', size=(150, -1),
                                    action=self.onLoadCSV)

        wids['train_model'] = Button(panel, 'Train Model From These Data',
                                     size=(250, -1),  action=self.onTrainLassoModel)

        wids['fit_group'] = Button(panel, 'Predict Variable for Selected Groups', size=(275, -1),
                                   action=self.onPredictGroups)
        wids['fit_group'].Disable()


        wids['save_model'] = Button(panel, 'Save Lasso Model', size=(200, -1),
                                    action=self.onSaveLassoModel)
        wids['save_model'].Disable()

        wids['load_model'] = Button(panel, 'Load Lasso Model', size=(200, -1),
                                    action=self.onLoadLassoModel)

        wids['varname'] = wx.TextCtrl(panel, -1, 'valence', size=(150, -1))

        wids['table'] = ExtVarTableGrid(panel)
        wids['table'].SetMinSize((550, 200))

        wids['use_selected'] = Button(panel, 'Use Selected Groups',
                                     size=(200, -1),  action=self.onFillLassoTable)

        panel.Add(SimpleText(panel, 'LASSO, Linear Feature Selection',
                             font=Font(12), colour='#AA0000'), dcol=4)
        add_text('Array to Use: ', newrow=True)
        panel.Add(wids['fitspace'], dcol=3)
        panel.Add(wids['load_model'])

        add_text('Plot : ', newrow=True)
        panel.Add(wids['plotchoice'], dcol=3)
        panel.Add(wids['save_model'])

        add_text('Fit Energy Range: ')
        panel.Add(w_xmin)
        add_text(' : ', newrow=False)
        panel.Add(w_xmax)

        add_text('Alpha: ')
        panel.Add(wids['alpha'])
        panel.Add(wids['auto_alpha'])
        panel.Add(wids['fit_intercept'])

        panel.Add(HLine(panel, size=(550, 2)), dcol=5, newrow=True)
        panel.Add((10, 10), newrow=True)
        add_text('Set External Variable for each Data Set: ', newrow=True, dcol=2)

        add_text('Attribute : ')
        panel.Add(wids['varname'], dcol=2)

        panel.Add(wids['use_selected'],  dcol=2)

        panel.Add(wids['table'], newrow=True, dcol=5)
        panel.Add(wids['load_csv'], newrow=True, dcol=2)
        panel.Add(wids['save_csv'], newrow=False, dcol=2)

        panel.Add(wids['train_model'], dcol=3, newrow=True)

        panel.Add(HLine(panel, size=(550, 2)), dcol=5, newrow=True)
        panel.Add((10, 10), newrow=True)
        add_text('Use This Model : ')
        panel.Add(wids['fit_group'], dcol=3)
        panel.pack()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add((10, 10), 0, LCEN, 3)
        sizer.Add(panel, 1, LCEN, 3)
        pack(self, sizer)
        self.skip_process = False

    def fill_form(self, dgroup):
        opts = self.get_config(dgroup)
        self.dgroup = dgroup
        if isinstance(dgroup, Group):
            d_emin = min(dgroup.energy)
            d_emax = max(dgroup.energy)
            if opts['xmin'] < d_emin:
                opts['xmin'] = -40 + int(dgroup.e0/10.0)*10
            if opts['xmax'] > d_emax:
                opts['xmax'] =  110 + int(dgroup.e0/10.0)*10

        self.skip_process = True
        wids = self.wids
        for attr in ('xmin', 'xmax', 'alpha'):
            val = opts.get(attr, None)
            if val is not None:
                wids[attr].SetValue(val)

        for attr in ('fitspace',):
            if attr in opts:
                wids[attr].SetStringSelection(opts[attr])

        self.skip_process = False

    def onFillLassoTable(self, event=None):
        selected_groups = self.controller.filelist.GetCheckedStrings()
        varname = fix_varname(self.wids['varname'].GetValue())
        grid_data = []
        for fname in self.controller.filelist.GetCheckedStrings():
            gname = self.controller.file_groups[fname]
            grp = self.controller.get_group(gname)
            grid_data.append((fname, getattr(grp, varname, 0.0)))

        self.wids['table'].table.data = grid_data
        self.wids['table'].table.View.Refresh()

    def onTrainLassoModel(self, event=None):
        print("train")
        opts = self.read_form()
        print(" train ", opts)
        print(" Varname: ")
        varname = opts['varname']

        grid_data = self.wids['table'].table.data
        groups = []
        for fname, yval in grid_data:
            gname = self.controller.file_groups[fname]
            grp = self.controller.get_group(gname)
            setattr(grp, varname, yval)
            groups.append(gname)

        print("groups ", groups, varname)

        cmds = ['# train lasso model',
               'lasso_traingroups = [%s]' % ', '.join(groups)]

        copts = ["varname='%s'" % varname,
                 "xmin=%.4f" % opts['xmin'],
                 "xmax=%.4f" % opts['xmax'],
                 ]
        if opts['auto_alpha']:
            copts.append('alpha=None')
        else:
            copts.append('alpha=%.4f' % opts['alpha'])
        if opts['fit_intercept']:
            copts.append('fit_intercept=True')
        else:
            copts.append('fit_intercept=False')


        cmds.append("lasso_model = lasso_train(lasso_traingroups, %s)" % ', '.join(copts))
        print(cmds)
        self.larch_eval('\n'.join(cmds))



    def onPredictGroups(self, event=None):
        print("predict groups")

    def onSaveLassoModel(self, event=None):
        print("save model")

    def onLoadLassoModel(self, event=None):
        print("load model")

    def onLoadCSV(self, event=None):
        dlg = wx.FileDialog(self, message="Load CSV Data File",
                            defaultDir=os.getcwd(),
                            wildcard=FILE_WILDCARDS, style=wx.FD_OPEN)

        fname = None
        if dlg.ShowModal() == wx.ID_OK:
            fname = dlg.GetPath()
        dlg.Destroy()
        if fname is None:
            return

        self.save_filename = fname
        varname = fix_varname(self.wids['varname'].GetValue())
        csvgroup = read_csv(fname)
        script = []
        grid_data = []
        for sname, yval in zip(csvgroup.col_01, csvgroup.col_02):
            if sname.startswith('#'):
                continue
            if sname in self.controller.file_groups:
                gname = self.controller.file_groups[sname]
                script.append('%s.%s = %f' % (gname, varname, yval))
                grid_data.append([sname, yval])

        self.larch_eval('\n'.join(script))
        self.wids['table'].table.data = grid_data
        self.wids['table'].table.View.Refresh()
        self.write_message('Read CSV File %s ' % fname)

    def onSaveCSV(self, event=None):
        dlg = wx.FileDialog(self, message="Save CSV Data File",
                            defaultDir=os.getcwd(),
                            defaultFile=self.save_filename,
                            wildcard=FILE_WILDCARDS,
                            style=wx.FD_SAVE)
        fname = None
        if dlg.ShowModal() == wx.ID_OK:
            fname = dlg.GetPath()
        dlg.Destroy()
        if fname is None:
            return
        self.save_filename = fname

        buff = []
        for  row in self.wids['table'].table.data:
            buff.append("%s, %s" % (row[0], gformat(row[1])))
        buff.append('')
        with open(fname, 'w') as fh:
            fh.write('\n'.join(buff))
        self.write_message('Wrote CSV File %s ' % fname)

    def onPlot(self, event=None):
        print("on Plot")

    def onCopyParam(self, name=None, evt=None):
        print("on Copy Param")
        conf = self.get_config()