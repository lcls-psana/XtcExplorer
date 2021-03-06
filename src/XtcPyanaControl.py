#--------------------------------------------------------------------------
# File and Version Information:
#  $Id$
#
# Description:
#  Module XtcPyanaControl...
#
#------------------------------------------------------------------------

"""Brief one-line description of the module.

@see XtcPyanaControl.py

@version $Id: template!python!py 4 2011-02-04 16:01:36Z ofte $

@author Ingrid Ofte
"""
from __future__ import print_function


#------------------------------
#  Module's version from CVS --
#------------------------------
__version__ = "$Revision$"
# $Source$

#--------------------------------
#  Imports of standard modules --
#--------------------------------
import sys, random, os, signal, time, glob

#---------------------------------
#  Imports of base class module --
#---------------------------------
import matplotlib
matplotlib.use('Qt4Agg')

from PyQt5 import QtCore, QtGui, QtWidgets

#-----------------------------
# Imports for other modules --
#-----------------------------

import threading
import multiprocessing as mp
import subprocess 
from pyana import pyanamod

import AppUtils.AppDataPath as apputils

#----------------------------------
# Local non-exported definitions --
#----------------------------------



#------------------------
# Exported definitions --
#------------------------


#---------------------
#  Class definition --
#---------------------
class myPopen(subprocess.Popen):
    status = 1 # running

    def kill(self, signal = signal.SIGTERM):
        os.kill(self.pid, signal)
        print("pyana process %d has been killed "% self.pid)
        status = 0 # not running

    def suspend(self):
        os.kill(self.pid, signal.SIGSTOP)
        print("pyana process %d has been suspended "% self.pid)
        status = 2 # suspended

    def resume(self):
        os.kill(self.pid, signal.SIGCONT)
        print("pyana process %d has been resumed "%self.pid)
        status = 1
        
#class MyThread( threading.Thread ):
class MyThread( QtCore.QThread ):
    """Run pyana module in a separate thread. This allows the GUI windows
    to stay active. The only problem is that Matplotlib windows need to me
    made beforehand, by the GUI -- not in pyana. Not a problem as long as
    they are declared beforehand. Pyana can still call the plt.figure command,
    that way it can be run standalone or from the GUI. 
    In principle...
    Still some issues to look into:
    - matplotlib figure must be created before pyana runs
    - This begs embedded mpl in a tool GUI. 
    Issues: 
    - Pyana threads are unkillable. Will keep going while GUI hangs. 
    # SOLUTION: Run the Plot gui in a subprocess, this subprocess then spawns the thread.
    # That should keep the other GUIs active, while the Plot GUI waits (or not) for pyana.
    # Killing pyana thread then requires killing the Plot GUI subprocess.
    """
    def __init__(self,pyanastring = ""):
        self.lpoptions = pyanastring
        QtCore.QThread.__init__(self)
        #threading.Thread.__init__ ( self )        
        
    def run(self):
        pyanamod.pyana(argv=self.lpoptions)

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()

    def kill(self):
        #self.terminate()  ... hangs indefinitely & freezes up the GUI
        #self.exit(0) ..... does nothing
        #self.quit() .... does nothing
        print(" !   python threads cannot be interupted...")
        print(" !   you'll have to wait...")
        print(" !   or ^Z and kill the whole xtcbrowser process.")
        print("done killing")
    

class XtcPyanaControl ( QtWidgets.QWidget ) :
    """Gui interface to pyana configuration & control

    @see pyana
    @see XtcExplorerMain
    """

    #--------------------
    #  Class variables --
    #--------------------

    #----------------
    #  Constructor --
    #----------------
    def __init__ (self,
                  data,
                  psana = False,
                  parent = None) :
        """Constructor.
        
        @param data    object that holds information about the data
        @param parent  parent widget, if any
        """
        self.psana = psana
        if self.psana:
            self.pxana = "psana"
            self.Pxana = "Psana"
        else:
            self.pxana = "pyana"
            self.Pxana = "Pyana"
        QtWidgets.QWidget.__init__(self, parent)
        
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setStyleSheet("QWidget {background-color: #FFFFFF }")
            
        self.lclsLogo = apputils.AppDataPath("XtcExplorer/icons/lclsLogo.gif")
        self.setWindowTitle(self.Pxana + ' Control Center')
        self.setWindowIcon(QtGui.QIcon(self.lclsLogo.path()))

        print("Xtc" + self.Pxana + "Control printing data ", data)
            
        # container for information about the data
        self.filenames = data.files
        self.devices = list(data.devices.keys())
        self.epicsPVs = data.epicsPVs
        self.controls = data.controls
        self.moreinfo = list(data.moreinfo.values())
        self.nevents = data.nevents
        self.ncalib = len(data.nevents)
        
        # ------- SELECTION / CONFIGURATION ------
        self.configuration = None
        self.checklabels = []
        self.checkboxes = []

        self.proc_pyana = None
        self.proc_status = None
        self.configfile = None

        self.pvWindow = None
        self.scrollArea = None

        self.pvlabels = []
        self.pvboxes = []
        self.pvGroupLayout = None

        # buttons
        self.pyana_config_text = QtWidgets.QLabel(self);
        self.config_button = None
        self.econfig_button = None
        self.psana_button = None
        self.pyana_button = None
        self.quit_button = None
        self.susp_button = None

        self.scan_widget = None
        self.pyana_widget = None
        self.info_widget = None

        # assume all events        
        #self.verbose = None
        self.run_n = None 
        self.skip_n = None 
        self.num_cpu = 1
        self.plot_n = 10
        self.accum_n = 0

        self.bool_string = { False: "No" , True: "Yes" }

        self.define_layout()

        self.show()
        self.update()
        


    def define_layout(self):
        """ Main layout of Pyana Control Center
        """
        self.layout = QtWidgets.QVBoxLayout(self)

        # header: icon
        h0 = QtWidgets.QHBoxLayout()
        pic = QtWidgets.QLabel(self)
        pic.setPixmap( QtGui.QPixmap(self.lclsLogo.path()))
        h0.addWidget( pic )
        h0.setAlignment( pic, QtCore.Qt.AlignLeft )

        label = QtWidgets.QLabel(self)
        label_text = """
Configure your analysis here...
Start with selecting data of interest to you from list on the left and general run / display options from the tab(s) on the right.
"""
        label.setText(label_text)
        h0.addWidget( label )
        h0.setAlignment( label, QtCore.Qt.AlignRight )
                                        

        # mid layer: almost everything
        h1 = QtWidgets.QHBoxLayout()

        # to the left:
        detector_gbox = QtWidgets.QGroupBox("In the file(s):")

        # layout of the group must be global, checkboxes added later
        self.lgroup = QtWidgets.QVBoxLayout()
        detector_gbox.setLayout(self.lgroup)
        h1.addWidget(detector_gbox)

        # to the right:
        self.config_tabs = QtWidgets.QTabWidget()
        self.config_tabs.setMinimumWidth(600)
        self.intro_tab()
        self.pyana_tab()
        h1.addWidget(self.config_tabs)

        # bottom layer: pyana run control
        h2 = self.layout_runcontrol()

        # 
        self.layout.addLayout(h0)
        self.layout.addLayout(h1)
        self.layout.addLayout(h2)

    def layout_runcontrol(self):

        # Run psana button
        self.psana_button = QtWidgets.QPushButton("&Run psana")
        self.psana_button.setMaximumWidth(120)
        self.psana_button.clicked.connect(self.run_psana)

        # Run pyana button
        self.pyana_button = QtWidgets.QPushButton("&Run pyana")
        self.pyana_button.setMaximumWidth(120)
        self.pyana_button.clicked.connect(self.run_pyana)

        # Suspend pyana button
        self.susp_button = QtWidgets.QPushButton("&Suspend " + self.pxana)
        self.susp_button.setCheckable(True) # Toggle two states: suspend / resume
        self.susp_button.setMaximumWidth(120)
        self.susp_button.clicked.connect(self.suspend_pyana)

        # Quit pyana button
        self.quit_button = QtWidgets.QPushButton("&Quit " + self.pxana)
        self.quit_button.setMaximumWidth(120)
        self.quit_button.clicked.connect(self.quit_pyana)

        # pyana runstring
        self.runstring_label = QtWidgets.QLabel("")

        # process status
        self.proc_status = QtWidgets.QLabel("")

        pyana_button_line = QtWidgets.QHBoxLayout()
        pyana_button_line.addWidget( self.runstring_label )
        if self.psana:
            pyana_button_line.addWidget( self.psana_button )
        pyana_button_line.addWidget( self.pyana_button )

        pyana_qsusp_line = QtWidgets.QHBoxLayout()
        pyana_qsusp_line.addWidget( self.proc_status )
        pyana_qsusp_line.addWidget( self.susp_button )
        pyana_qsusp_line.addWidget( self.quit_button )
        
        self.runcontrol = QtWidgets.QVBoxLayout()
        self.runcontrol.addLayout( pyana_button_line  )
        self.runcontrol.addLayout( pyana_qsusp_line  )
        self.runcontrol.setAlignment( pyana_button_line, QtCore.Qt.AlignRight )
        self.runcontrol.setAlignment( pyana_qsusp_line, QtCore.Qt.AlignRight )

        ## hide all first
        self.psana_button.setDisabled(True)
        self.pyana_button.setDisabled(True)
        self.susp_button.setDisabled(True)
        self.quit_button.setDisabled(True)

        return self.runcontrol

                
    def intro_tab(self):
        # First tab: help/info
        self.help_widget = QtWidgets.QWidget()
        self.help_layout = QtWidgets.QVBoxLayout(self.help_widget)

        # run pyana with the first Nr events. Skip Ns events. 
        self.run_n_status = QtWidgets.QLabel("Process all shots (or enter how many to process)")
        self.run_n_enter = QtWidgets.QLineEdit("")
        if self.run_n is not None:
            self.run_n_status = QtWidgets.QLabel("Process %s shots"% self.run_n)
            self.run_n_enter.setText( str(self.run_n) )
        self.run_n_enter.setMaximumWidth(90)
        self.run_n_enter.returnPressed.connect(self.run_n_change)
        self.run_n_change_btn = QtWidgets.QPushButton("Change") 
        self.run_n_change_btn.clicked.connect(self.run_n_change)

        self.run_n_layout = QtWidgets.QHBoxLayout()
        self.run_n_layout.addWidget(self.run_n_status)
        self.run_n_layout.addStretch()
        self.run_n_layout.addWidget(self.run_n_enter)
        self.run_n_layout.addWidget(self.run_n_change_btn)
        self.help_layout.addLayout(self.run_n_layout, QtCore.Qt.AlignRight )

        self.skip_n_layout = QtWidgets.QHBoxLayout()
        self.skip_n_status = QtWidgets.QLabel("Skip no shots (or enter how many to skip)")
        self.skip_n_enter = QtWidgets.QLineEdit("")
        self.skip_n_enter.setMaximumWidth(90)
        if self.skip_n is not None:
            self.skip_n_status = QtWidgets.QLabel("Skip the first %d shots of xtc file"%self.skip_n )
            self.skip_n_enter.setText( str(self.skip_n) )
            
        self.skip_n_enter.returnPressed.connect(self.skip_n_change)
        self.skip_n_change_btn = QtWidgets.QPushButton("Change") 
        self.skip_n_change_btn.clicked.connect(self.skip_n_change)

        self.skip_n_layout.addWidget(self.skip_n_status)
        self.skip_n_layout.addStretch()
        self.skip_n_layout.addWidget(self.skip_n_enter)
        self.skip_n_layout.addWidget(self.skip_n_change_btn)
        self.help_layout.addLayout(self.skip_n_layout, QtCore.Qt.AlignRight )

        # Multiprocessing?
        mproc_status = QtWidgets.QLabel("Multiprocessing? No, single CPU")
        mproc_menu = QtWidgets.QComboBox()
        mproc_menu.setMaximumWidth(90)
        for i in range (0,mp.cpu_count()):
            mproc_menu.addItem(str(i+1))
        mproc_menu.setCurrentIndex(0) # Single-CPU

        mproc_layout = QtWidgets.QHBoxLayout()
        mproc_layout.addWidget(mproc_status)
        mproc_layout.addStretch()
        mproc_layout.addWidget(mproc_menu)
        self.help_layout.addLayout(mproc_layout, QtCore.Qt.AlignRight)        

        def mproc_changed():
            text = str(mproc_menu.currentText())
            if ( text is None ) or ( text == "1" ):
                mproc_status.setText("Multiprocessing? No, single CPU")
                self.num_cpu = 1
            else:
                mproc_status.setText("Multiprocessing with %s CPUs"%text)
                self.num_cpu = int(text)                
        mproc_menu.currentIndexChanged[int].connect(mproc_changed)
        
        # divider
        divider = ". . . "*30
        self.help_layout.addWidget(QtWidgets.QLabel(divider))
        
        # Load config file
        self.conf_layout = QtWidgets.QHBoxLayout()
        self.conf_label = QtWidgets.QLabel("Use existing configuration file: ")
        self.conf_widget = QtWidgets.QLineEdit('')
        self.conf_okBtn = QtWidgets.QPushButton("OK") 
        self.conf_widget.returnPressed.connect(self.use_configfile)
        self.conf_okBtn.clicked.connect(self.use_configfile)
        self.conf_layout.addWidget(self.conf_label)
        self.conf_layout.addWidget(self.conf_widget)
        self.conf_layout.addWidget(self.conf_okBtn)
        self.help_layout.addLayout(self.conf_layout, QtCore.Qt.AlignRight)


        # Global Display mode
        self.dmode_layout = QtWidgets.QHBoxLayout()

        self.dmode_menu = QtWidgets.QComboBox()
        self.dmode_menu.setMaximumWidth(90)
        self.dmode_menu.addItem("NoDisplay")
        self.dmode_menu.addItem("SlideShow")
        self.dmode_menu.addItem("Interactive")
        self.dmode_menu.setCurrentIndex(1)
        self.dmode_menu.currentIndexChanged[int].connect(self.process_dmode)
        self.displaymode = self.dmode_menu.currentText()
        self.dmode_status = QtWidgets.QLabel("Display mode is %s"% self.displaymode)
        self.dmode_layout.addWidget(self.dmode_status)
        self.dmode_layout.addWidget(self.dmode_menu)
        self.help_layout.addLayout(self.dmode_layout, QtCore.Qt.AlignRight)

        # plot every N events
        self.plot_n_layout = QtWidgets.QHBoxLayout()
        if self.plot_n == 0:
            self.plotn_status = QtWidgets.QLabel("Plot only after all shots")
        else:
            self.plotn_status = QtWidgets.QLabel("Plot every %d shots"%self.plot_n )
        self.plotn_enter = QtWidgets.QLineEdit()
        self.plotn_enter.setMaximumWidth(90)
        self.plotn_enter.returnPressed.connect(self.plotn_change)
        self.plotn_change_btn = QtWidgets.QPushButton("&Change") 
        self.plotn_change_btn.clicked.connect(self.plotn_change)
        self.plot_n_layout.addWidget(self.plotn_status)
        self.plot_n_layout.addStretch()
        self.plot_n_layout.addWidget(self.plotn_enter)
        self.plot_n_layout.addWidget(self.plotn_change_btn)
        self.help_layout.addLayout(self.plot_n_layout, QtCore.Qt.AlignRight )

        # Accumulate N events (reset after N events)
        self.accum_n_layout = QtWidgets.QHBoxLayout()
        if self.accum_n == 0:
            self.accumn_status = QtWidgets.QLabel("Accumulate all shots (or enter how many to accumulate)")
        else:
            self.accumn_status = QtWidgets.QLabel("Accumulate %d shots (then reset)"%self.accum_n )
        self.accumn_enter = QtWidgets.QLineEdit()
        self.accumn_enter.setMaximumWidth(90)
        self.accumn_enter.returnPressed.connect(self.accumn_change)
        self.accumn_change_btn = QtWidgets.QPushButton("&Change") 
        self.accumn_change_btn.clicked.connect(self.accumn_change)
        self.accum_n_layout.addWidget(self.accumn_status)
        self.accum_n_layout.addStretch()
        self.accum_n_layout.addWidget(self.accumn_enter)
        self.accum_n_layout.addWidget(self.accumn_change_btn)
        self.help_layout.addLayout(self.accum_n_layout, QtCore.Qt.AlignRight )

        # Drop into iPython session at the end of the job?
        self.ipython = False
        self.ipython_status = QtWidgets.QLabel("Drop into iPython at the end of the job?  %s" \
                                           % self.bool_string[ self.ipython ] )
        self.ipython_layout = QtWidgets.QHBoxLayout()
        self.ipython_menu = QtWidgets.QComboBox()
        self.ipython_menu.setMaximumWidth(150)
        self.ipython_menu.addItem("No")
        self.ipython_menu.addItem("Yes")
        self.ipython_menu.currentIndexChanged[int].connect(self.process_ipython)
        self.ipython_layout.addWidget(self.ipython_status)
        self.ipython_layout.addWidget(self.ipython_menu)
        self.help_layout.addLayout(self.ipython_layout)

        self.config_tabs.addTab(self.help_widget,"General Settings")
        self.config_tabs.tabBar().hide()


    def process_ipython(self):
        self.ipython = bool(self.ipython_menu.currentIndex())
        self.ipython_status.setText("Drop into iPython at the end of the job?  %s" \
                                    % self.bool_string[ self.ipython ] )

        if self.configuration is not None:
            self.process_checkboxes()

    def process_dmode(self):
        self.displaymode = self.dmode_menu.currentText()
        self.dmode_status.setText("Display mode is %s"%self.displaymode)

        if self.displaymode == "NoDisplay":
            self.plot_n = 0
            self.plotn_change()

        if self.configuration is not None:
            self.process_checkboxes()

            
    def plotn_change(self):

        self.plot_n = self.plotn_enter.text()
        if self.plot_n == "" or self.plot_n == "0" or self.plot_n == "all" or self.plot_n == "All":
            self.plot_n = 0
            self.plotn_status.setText("Plot only after all shots")
        else:
            self.plot_n = int(self.plot_n)
            self.plotn_status.setText("Plot every %d shots"%self.plot_n )

        self.plotn_enter.setText("")

        if self.configuration is not None:
            self.process_checkboxes()

    def accumn_change(self):

        self.accum_n = self.accumn_enter.text()
        if self.accum_n == "" or self.accum_n == "0" or self.accum_n == "all" or self.accum_n == "All":
            self.accum_n = 0
            self.accumn_status.setText("Accumulate all shots (or enter how many to accumulate)")
        else:
            self.accum_n = int(self.accum_n)
            self.accumn_status.setText("Accumulate %d shots (reset after)"%self.accum_n )

        self.accumn_enter.setText("")

        if self.configuration is not None:
            self.process_checkboxes()

    def run_n_change(self):
        text = self.run_n_enter.text()
        if text == "" or text == "all" or text == "All" or text == "None" :
            self.run_n = None
            self.run_n_status.setText("Process all shots (or enter how many to process)")
        else :
            self.run_n = int( text )
            self.run_n_status.setText("Process %d shots"%self.run_n )
        self.run_n_enter.setText("")

    def skip_n_change(self):
        text = self.skip_n_enter.text()
        if text == "" or text == "0" or text == "no" or text == "None" :
            self.skip_n = None
            self.skip_n_status.setText("Skip no shots (or enter how many to skip)")
        else :
            self.skip_n = int(self.skip_n_enter.text())            
            self.skip_n_status.setText("Skip the first %d shots of xtc file"%self.skip_n )
        self.skip_n_enter.setText("")


    def scan_tab(self, who):
        """ Second tab: Scan
        """
        if self.scan_widget is None :
            self.scan_widget = QtWidgets.QWidget()
            self.scan_layout = QtWidgets.QVBoxLayout(self.scan_widget)

            message = QtWidgets.QLabel()
            message.setText("Scan vs. %s"%"Hallo")

            self.scan_layout.addWidget(message)

            self.config_tabs.addTab(self.scan_widget,"Scan Configuration")

        self.config_tabs.setCurrentWidget(self.scan_widget)
        self.config_tabs.tabBar().show()
        self.write_configuration()

        
    def pyana_tab(self):
        """Pyana configuration text
        """
        pyana_widget = QtWidgets.QWidget()
        pyana_layout = QtWidgets.QVBoxLayout(pyana_widget)
        
        pyana_widget.setLayout(pyana_layout)
        self.pyana_config_label = QtWidgets.QLabel("Current " + self.pxana + " configuration:")
        
        # scroll area for the configuration file text
        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidgetResizable(True)
        scrollArea.setWidget( self.pyana_config_text )
        
        pyana_layout.addWidget(self.pyana_config_label)
        pyana_layout.addWidget(scrollArea)
        
        # add some buttons for this tab: Write / Edit
        pyana_button_layout = QtWidgets.QHBoxLayout()
        self.config_button = QtWidgets.QPushButton("&Write configuration to file") 
        self.config_button.clicked.connect(self.write_configfile)
        pyana_button_layout.addWidget( self.config_button )
        self.econfig_button = QtWidgets.QPushButton("&Edit configuration file")
        self.econfig_button.clicked.connect(self.edit_configfile)
        pyana_button_layout.addWidget( self.econfig_button )

        self.config_button.setDisabled(True)
        self.econfig_button.setDisabled(True)
        pyana_layout.addLayout(pyana_button_layout)
        
        self.config_tabs.addTab(pyana_widget, self.Pxana + " Configuration")
        
        self.config_tabs.tabBar().show()
        self.pyana_widget = pyana_widget
        

    def update_pyana_tab(self):
        if self.pyana_widget is None :
            self.pyana_tab()
        
        self.pyana_config_text.setText(self.configuration)

        self.config_button.setEnabled(True)
        self.econfig_button.setDisabled(True)

        self.config_tabs.setCurrentWidget(self.pyana_widget)

    #-------------------
    #  Public methods --
    #-------------------
                
    def update(self):
        """Update lists of filenames, devices and epics channels
           Make sure GUI gets updated too
        """
        # show all of this in the Gui
        self.setup_gui_checkboxes()
        #for ch in self.checkboxes:
        #    print ch.text()

        # if scan, plot every calib cycle 
        if self.ncalib > 1 :
            print("Have %d scan steps a %d shots each. Set up to plot after every %d shots" %\
                  (self.ncalib, self.nevents[0], self.nevents[0] ))
            self.plotn_enter.setText( str(self.nevents[0]) )
            self.plotn_change()
            self.plotn_enter.setText("")
            
        print("Configure " + self.pxana + " by selecting from the detector list")

    def setup_gui_checkboxes(self) :
        """Draw a group of checkboxes to the GUI

        Each checkbox gets connected to the function process_checkboxes,
        i.e., whenerver *one* checkbox is checked/unchecked, the state of 
        every checkbox is investigated. Not pretty, but works OK.
        """
        # lists of QCheckBoxes and their text lables. 
        self.checkboxes = []
        self.checklabels = []


        # from the controls list
        nctrl = 0
        for ctrl in self.controls:
            ckbox = QtWidgets.QCheckBox("ControlPV: %s"%ctrl, self)
            self.checkboxes.append(ckbox)
            self.checklabels.append(ckbox.text())
            ckbox.stateChanged[int].connect(self.process_checkboxes)
            nctrl += 1

        for label in sorted(self.devices):
            if label.find("ProcInfo") >= 0 : continue  # ignore
            if label.find("NoDetector") >= 0 : continue  # ignore
            
            if self.checklabels.count(label)!=0 : continue # avoid duplicates

            # make checkbox for this device
            #checkbox = QtGui.QCheckBox(': '.join(label.split(":")), self)
            checkbox = QtWidgets.QCheckBox( label.split(":")[1], self)
            checkbox.stateChanged[int].connect(self.process_checkboxes)
            
            # special case: Epics PVs
            if label.find("Epics") >= 0 : 
                checkbox.setText("Epics Process Variables (%d)"%len(self.epicsPVs))
                checkbox.stateChanged[int].connect(self.setup_gui_epics)
                # add epics to front
                self.checkboxes.insert(nctrl,checkbox)
                self.checklabels.insert(nctrl,checkbox.text())
                # make global
                self.epics_checkbox = checkbox
            else :
                # add everything else to the end
                self.checkboxes.append(checkbox)
                self.checklabels.append(label)
                
        # finally, add each to the layout
        for checkbox in self.checkboxes :
            self.lgroup.addWidget(checkbox)
            

    def setup_gui_epics(self):
        """Open a new window if epics_checkbox is checked.
        If not, clear all fields and hide. 
        Add checkboxes for each known epics PV channel.
        connect each of these to process_checkboxes
        """
        if self.epics_checkbox.isChecked():
            if self.pvWindow is None:
                self.make_epics_window()

                # add epics channels to list of checkboxes, place them in a different widget
                for self.pv in self.epicsPVs:
                    pvtext = "EpicsPV:  " + self.pv
                    self.pvi = QtWidgets.QCheckBox(pvtext,self.pvWindow)

                    ## check those that are control pvs
                    #for ctrl in self.controls: 
                    #    if ctrl in pvtext :
                    #        self.pvi.setChecked(True)

                    self.pvi.stateChanged[int].connect(self.process_checkboxes)
                    self.checkboxes.append(self.pvi)
                    self.checklabels.append(self.pvi.text())
                    self.pvGroupLayout.addWidget(self.pvi)

            else :
                self.pvWindow.show()

        else :
            # 
            for box in self.checkboxes :
                if str(box.text()).find("EpicsPV")>=0 :
                    box.setCheckState(0)
            if self.pvWindow:
                self.pvWindow.hide()


    def make_epics_window(self):
        # open Epics window
        self.pvWindow = QtWidgets.QWidget()
        self.pvWindow.setStyleSheet("QWidget {background-color: #FFFFFF }")
        self.pvWindow.setWindowTitle('Available Epics PVs')
        self.pvWindow.setWindowIcon(QtGui.QIcon(self.lclsLogo.path()))
        self.pvWindow.setMinimumWidth(300)
        self.pvWindow.setMinimumHeight(700)

        # scroll area
        self.scrollArea = QtWidgets.QScrollArea()
        self.scrollArea.setWidgetResizable(True)
                
        # list of PVs, a child of self.scrollArea
        pvGroup = QtWidgets.QGroupBox("Epics channels (%d):"%len(self.epicsPVs))
        self.scrollArea.setWidget(pvGroup)

        self.pvGroupLayout = QtWidgets.QVBoxLayout()
        pvGroup.setLayout(self.pvGroupLayout)

        # layout of pvWindow:
        pvLayout = QtWidgets.QHBoxLayout(self.pvWindow)
        self.pvWindow.setLayout(pvLayout)

        # show window
        #pvLayout.addWidget(pvGroup)
        pvLayout.addWidget(self.scrollArea)
        self.pvWindow.show()
        
            

    def process_checkboxes(self):
        """Process the list of checkboxes and
        call the appropriate function based on the
        checkbox name/label
        """        
        if self.configfile is not None:
            # if a config file is already in use, pop up a warning that it will be replaced. 
            warning_text = """You are currently using a saved file (%s).
New checkbox changes will NOT be merged with this file.
A new config file with default settings will be generated.
Do you want to proceed?
 """ % self.configfile

            reply = QtWidgets.QMessageBox.question(self,'Alert', warning_text, 
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.No:
                self.sender().setChecked(False)
                return
            
            
        # clear title 
        self.configfile = None
        if self.econfig_button is not None : self.econfig_button.setDisabled(True)
        if self.psana_button is not None: self.psana_button.setDisabled(True)
        if self.pyana_button is not None: self.pyana_button.setDisabled(True)
        if self.quit_button is not None: self.quit_button.setDisabled(True)
        if self.susp_button is not None: self.susp_button.setDisabled(True)

        self.pyana_config_label.setText("Current %s configuration:" % (self.pxana))

        modules_to_run = []
        options_for_mod = []
        self.configuration= ""

        do_scan = False
        for box in sorted(self.checkboxes):
            if box.isChecked() :
                if str(box.text()).find("ControlPV:")>=0 :
                    do_scan = True
                    self.add_module(box, modules_to_run, options_for_mod)
                elif do_scan :
                    self.add_to_scan(box, modules_to_run, options_for_mod)
                else :
                    self.add_module(box, modules_to_run, options_for_mod)
                
        nmodules = len(modules_to_run)
        if nmodules > 0 and self.displaymode != "NoDisplay" :
            # at the end, append plotter module:
            modules_to_run.append("XtcExplorer.pyana_plotter")
            options_for_mod.append([])
            options_for_mod[nmodules].append("\ndisplay_mode = %s"%self.displaymode )
            options_for_mod[nmodules].append("\nipython = %d"%self.ipython)

        # if several values for same option, merge into a list
        for m in range(0,nmodules):
            tmpoptions = {}
            for options in options_for_mod[m] :
                n,v = options.split(" = ")
                if n in tmpoptions :
                    oldvalue = tmpoptions[n]
                    if oldvalue!=v:   # avoid duplicates
                        tmpoptions[n] = oldvalue+" "+v
                else :
                    tmpoptions[n] = v

            newoptions = []
            for n, v in tmpoptions.items() :
                optstring = "%s = %s" % (n,v)
                newoptions.append(optstring)

            options_for_mod[m] = newoptions

        self.configuration = ""
        if self.psana:
            pxana_list = [ "pyana", "psana" ]
        else:
            pxana_list = [ "pyana" ]
        for pxana in pxana_list:
            self.configuration += "[" + pxana + "]"
            self.configuration += "\nfiles = "
            for i, fname in enumerate(self.filenames):
                if i > 0: 
                    if self.psana:
                        self.configuration += " \\\n\t"
                    else:
                        self.configuration += "\n\t"
                self.configuration += fname
    
            self.configuration += "\nmodules ="
            for module in modules_to_run :
                self.configuration += " "
                self.configuration += module
            self.configuration += "\n\n"

        if self.psana:
            # 32MB is the default limit but some datagrams are a bit bigger...
            self.configuration += "[PSXtcInput.XtcInputModule]\n"
            self.configuration += "dgSizeMB = 128\n\n"

        count_m = 0
        for module in modules_to_run :
            self.configuration += "["
            self.configuration += module
            self.configuration += "]"
            #if len( options_for_mod[ count_m ] )>0 :
            for options in sorted(options_for_mod[ count_m ]) :
                self.configuration += options
            count_m +=1
            self.configuration += "\n\n"
            

        # add linebreaks if needed
        self.configuration = self.add_linebreaks(self.configuration, width=70)
        #print self.configuration

        self.update_pyana_tab()



    def add_to_scan(self,box,modules_to_run,options_for_mod) :
  
        index = None
        try:
            index = modules_to_run.index("XtcExplorer.pyana_scan")
        except ValueError :
            print("ValueError")
            
        #print "XtcExplorer.pyana_scan at ", index
        source = str(box.text())
        if source.find("EpicsPV")>=0 :
            options_for_mod[index].append("\ninput_epics = %s" % source.split(": ")[1])
            return
        else:
            options_for_mod[index].append("\ninput_scalars = %s" % source)
            return



    def add_module(self,box,modules_to_run,options_for_mod) :

        index = None

        # The following sets up one out of two analysis modes:
        #      1) scan
        #      2) all-in-one analysis 

        boxlabel = str(box.text())

        # --- --- --- Scan --- --- ---
        if boxlabel.find("ControlPV:")>=0 :
            try :
                index = modules_to_run.index("XtcExplorer.pyana_scan")
            except ValueError :
                index = len(modules_to_run)
                modules_to_run.append("XtcExplorer.pyana_scan")
                options_for_mod.append([])

            #print "XtcExplorer.pyana_scan at ", index
            pvname = boxlabel.split("PV: ")[1]
            options_for_mod[index].append("\ncontrolpv = %s" % pvname)
            options_for_mod[index].append("\ninput_epics = ")
            options_for_mod[index].append("\ninput_scalars = ")
            #options_for_mod[index].append("\nplot_every_n = %d" % self.plot_n)
            options_for_mod[index].append("\nfignum = %d" % (100*(index+1)))
            return



        # --- --- --- BLD --- --- ---
        if ( boxlabel.find("EBeam")>=0 or 
             boxlabel.find("FEEGasDetEnergy")>=0 or
             boxlabel.find("PhaseCavity")>=0 ):
            try :
                index = modules_to_run.index("XtcExplorer.pyana_bld")
            except ValueError :
                index = len(modules_to_run)
                modules_to_run.append("XtcExplorer.pyana_bld")
                options_for_mod.append([])
                
            #print "XtcExplorer.pyana_bld at ", index
            options_for_mod[index].append("\nplot_every_n = %d" % self.plot_n)
            options_for_mod[index].append("\naccumulate_n = %d" % self.accum_n)
            options_for_mod[index].append("\nfignum = %d" % (100*(index+1)))
            if boxlabel.find("EBeam")>=0 :
                options_for_mod[index].append("\ndo_ebeam = True")
            if boxlabel.find("FEEGasDetEnergy")>=0 :
                options_for_mod[index].append("\ndo_gasdetector = True")
            if boxlabel.find("PhaseCavity")>=0 :
                options_for_mod[index].append("\ndo_phasecavity = True")
            return
            
        # --- --- --- Waveform --- --- ---
        if ( boxlabel.find("Acq")>=0  
             or boxlabel.find("ETof")>=0
             or boxlabel.find("ITof")>=0
             or boxlabel.find("Mbes")>=0
             #or boxlabel.find("Camp")>=0
             ) :
            try :
                index = modules_to_run.index("XtcExplorer.pyana_waveform:%s"%boxlabel)
            except ValueError :
                index = len(modules_to_run)
                modules_to_run.append("XtcExplorer.pyana_waveform:%s"%boxlabel)
                options_for_mod.append([])

            #print "XtcExplorer.pyana_waveform at ", index
            #address = boxlabel.split(":")[1].strip()
            address = boxlabel.strip()
            options_for_mod[index].append("\nsources = %s" % address)
            options_for_mod[index].append("\nplot_every_n = %d" % self.plot_n)
            options_for_mod[index].append("\naccumulate_n = %d" % self.accum_n)
            options_for_mod[index].append("\nfignum = %d" % (100*(index+1)))
            options_for_mod[index].append("\nquantities = average")
            return
                    
        # --- --- --- Ipimb --- --- ---
        if ( boxlabel.find("IPM")>=0 or
             boxlabel.find("DIO")>=0 or
             boxlabel.find("LAS-EM")>=0 or
             boxlabel.find("TCTR")>=0 or             
             boxlabel.find("Ipimb")>=0 ) :
            try :
                index = modules_to_run.index("XtcExplorer.pyana_ipimb")
            except ValueError :
                index = len(modules_to_run)
                modules_to_run.append("XtcExplorer.pyana_ipimb")
                options_for_mod.append([])

            #print "XtcExplorer.pyana_ipimb at ", index
            #address = boxlabel.split(": ")[1].strip()
            address = boxlabel.strip()
            options_for_mod[index].append("\nsources = %s" % address)
            options_for_mod[index].append("\nquantities = fex:channels fex:sum")
            options_for_mod[index].append("\nplot_every_n = %d" % self.plot_n)
            options_for_mod[index].append("\naccumulate_n = %d" % self.accum_n)
            options_for_mod[index].append("\nfignum = %d" % (100*(index+1)))
            return
                    
        # --- --- --- All images --- --- ---
        if ( boxlabel.find("YAG")>=0 
             or  boxlabel.find("TM6740")>=0 
             or boxlabel.find("Opal")>=0 
             or boxlabel.find("Fccd")>=0 
             or boxlabel.find("Princeton")>=0
             or boxlabel.find("pnCCD")>=0 
             or boxlabel.find("Cspad")>=0
             or boxlabel.find("Timepix")>=0 
             or boxlabel.find("Fli")>=0 ):
            try :
                index = modules_to_run.index("XtcExplorer.pyana_image")
            except ValueError :
                index = len(modules_to_run)
                modules_to_run.append("XtcExplorer.pyana_image")
                options_for_mod.append([])

            #print "XtcExplorer.pyana_image at ", index
            #address = boxlabel.split(": ")[1].strip()
            address = boxlabel.strip()
            options_for_mod[index].append("\nsources = %s" % address)
            options_for_mod[index].append("\ninputdark = ")
            options_for_mod[index].append("\n#threshold = lower=0 upper=1200 roi=(x1:x2,y1:y2) type=maximum")
            options_for_mod[index].append("\n#algorithms = rotate shift")
            options_for_mod[index].append("\nquantities = image \n# ... average darks maximum")
            options_for_mod[index].append("\nplot_every_n = %d" % self.plot_n)
            options_for_mod[index].append("\naccumulate_n = %d" % self.accum_n)
            options_for_mod[index].append("\nfignum = %d" % (100*(index+1)))
            #options_for_mod[index].append("\nshow_projections = 0 ; 0:none, 1:average, 2:maxima")
            options_for_mod[index].append("\noutputfile = ")
            options_for_mod[index].append("\nmax_save = 0\n# ... max event images to save" )

            options_for_mod[index].append("\ncmmode_mode = asic");
            options_for_mod[index].append("\ncmmode_thr = 30"); 
            options_for_mod[index].append("\nsmall_tilt = False");
            try:
                calibpath = '/'.join( self.filenames[0].split('/')[0:6]) + "/calib/"
                calibpath = glob.glob(calibpath)[0]
                options_for_mod[index].append("\ncalib_path = %s"%calibpath)
            except:
                print(calibpath)
            return

#        # --- --- --- CsPad --- --- ---
#        if (boxlabel.find("Cspad")>=0 ):
#            try :
#                index = modules_to_run.index("XtcExplorer.pyana_cspad")
#            except ValueError :
#                index = len(modules_to_run)
#                modules_to_run.append("XtcExplorer.pyana_cspad")
#                options_for_mod.append([])

#            #print "XtcExplorer.pyana_cspad at ", index
#            fname = self.filenames[0]
#            exp = fname.split('/')[5]
#            rnr = fname.split('/')[7].split('-')[1]
#            dfile = "cspad_%s_%s.npy"%(exp,rnr) 
#            #address = boxlabel.split(":")[1].strip()
#            address = boxlabel.strip()
#            options_for_mod[index].append("\nsource = %s" % address)
#            options_for_mod[index].append("\nplot_every_n = %d" % self.plot_n)
#            options_for_mod[index].append("\naccumulate_n = %d" % self.accum_n)
#            options_for_mod[index].append("\nfignum = %d" % (100*(index+1)))
#            options_for_mod[index].append("\ndark_img_file = ")
#            options_for_mod[index].append("\nout_avg_file = %s"%dfile)
#            options_for_mod[index].append("\nout_shot_file = ")
#            options_for_mod[index].append("\nplot_vrange = ") 
#            options_for_mod[index].append("\nthreshold =   ; value (xlow:xhigh,ylow:yhigh) ")
#            return

        # --- --- --- Encoder --- --- ---
        if boxlabel.find("Encoder")>=0 :
            try :
                index = modules_to_run.index("XtcExplorer.pyana_encoder")
            except ValueError :
                index = len(modules_to_run)
                modules_to_run.append("XtcExplorer.pyana_encoder") 
                options_for_mod.append([])

            #print "XtcExplorer.pyana_encoder at ", index 
            #address = boxlabel.split(": ")[1].strip()
            address = boxlabel.strip()
            options_for_mod[index].append("\nsources = %s" % address)
            options_for_mod[index].append("\nplot_every_n = %d" % self.plot_n )
            options_for_mod[index].append("\naccumulate_n = %d" % self.accum_n )
            options_for_mod[index].append("\nfignum = %d" % (100*(index+1)))
            return
        
        # --- --- --- Epics --- --- ---
        if boxlabel.find("Epics Process Variables")>=0 :
            return

        if boxlabel.find("EpicsPV:")>=0 :

            try :
                index = modules_to_run.index("XtcExplorer.pyana_epics")
            except ValueError :
                index = len(modules_to_run)
                modules_to_run.append("XtcExplorer.pyana_epics")
                options_for_mod.append([])

            #print "XtcExplorer.pyana_epics at ", index
            pvname = boxlabel.split("PV:  ")[1]
            options_for_mod[index].append("\npv_names = %s" % pvname)
            options_for_mod[index].append("\nplot_every_n = %d" % self.plot_n )
            options_for_mod[index].append("\naccumulate_n = %d" % self.accum_n )
            options_for_mod[index].append("\nfignum = %d" % (100*(index+1)))
            return
        
        print("FIXME! %s requested, not implemented" % box.text()) 

    def add_linebreaks(self, configtext, width=50):
        if self.psana: # don't add linebreaks as they confuse the psana config parser
            return configtext
        lines = configtext.split('\n')
        l = 0
        for line in lines :
            if len(line) > width : # split line
                words = line.split(" ")
                i = 0
                newlines = []
                newline = ""
                while len(newline) <= width and i <len(words) :
                    newline += (words[i]+" ")
                    i += 1
                    if len(newline) > width or i==len(words):
                        newlines.append(newline)
                        newline = "     "
                        
                # now replace the original line with newlines
                l = lines.index(line)
                lines.remove(line)
                if len(newlines)>1 :
                    newlines.reverse()
                for linje in newlines :
                    if linje.strip() != '' :
                        lines.insert(l,linje)
                    
        configtext = "\n".join(lines)
        return configtext
        

    def print_configuration(self):
        print("----------------------------------------")
        print("Configuration file (%s): " % self.configfile)
        print("----------------------------------------")
        print(self.configuration)
        print("----------------------------------------")
        return

    def write_configfile(self):
        """Write the configuration text to a file. Filename is generated randomly
        """

        self.configfile = "xb_%s_%d.cfg" % (self.pxana, random.randint(1000,9999))

        self.pyana_config_label.setText("Current %s configuration: (%s)" % (self.pxana, self.configfile))
        self.conf_widget.setText(self.configfile)

        f = open(self.configfile,'w')
        f.write(self.configuration)
        f.close()

        self.print_configuration()
        
        self.config_button.setDisabled(True)
        self.econfig_button.setEnabled(True)
        self.psana_button.setEnabled(True)
        self.pyana_button.setEnabled(True)


    def use_configfile(self, cfile = None):
        """ Read existing config file, update checkboxes
        """
        if cfile is not None:
            self.configfile = cfile
        else: 
            cfile = self.conf_widget.text()
            
        print("# ", cfile)
        f = open(cfile,'r')
        tmp_configuration = f.read()
        f.close()

        # update checkboxes?
        lines = tmp_configuration.split('\n')
        sources = []
        for line in lines:
            if line.find('source')>=0:
                n,v = line.split('=')
                sources.extend( [_f for _f in v.split(' ') if _f])
            elif line.find('do_ebeam = True'):
                sources.extend('EBeam')
            elif line.find('do_gasdetector = True'):
                sources.extend('FEEGasDetector')
            elif line.find('do_phasecavity = True'):
                sources.extend('PhaseCavity')

        for ch in self.checkboxes:
            if ch.text() in sources:
                ch.setChecked(True)
            else :
                ch.setChecked(False)
                
        # Then use the unchanged text from the file
        self.configfile = cfile
        f = open(cfile,'r')
        self.configuration = f.read()
        f.close()

        self.pyana_config_label.setText("Current %s configuration: (%s)" % (self.pxana, self.configfile))
        self.pyana_config_text.setText(self.configuration)
        self.print_configuration()

        self.config_button.setDisabled(True)
        self.econfig_button.setEnabled(True)
        self.psana_button.setEnabled(True)
        self.pyana_button.setEnabled(True)

 

    def edit_configfile(self):
        # pop up emacs window to edit the config file as needed:

        proc_emacs = None
        try: 
            myeditor = os.environ['EDITOR']
            print("Launching your favorite editor %s to edit config file" % myeditor)
            proc_emacs = myPopen("$EDITOR %s" % self.configfile, shell=True) 
        except :
            print("Launching emacs to edit the config file.")
            print("To launch another editor of your choice, make sure to", end=' ')
            print("set the EDITOR variable in your shell environment.")
            proc_emacs = myPopen("emacs %s" % self.configfile, shell=True)

        # communicate with the process, makes everything wait for editor to finish
        stdout_value = proc_emacs.communicate()[0]


        #proc_emacs = MyThread("emacs %s" % self.configfile) 
        #proc_emacs.start()

        # update text in GUI too
        f = open(self.configfile,'r')
        self.configuration = f.read()
        f.close()

        self.pyana_config_label.setText("Current %s configuration: (%s)" % (self.pxana, self.configfile))
        self.pyana_config_text.setText(self.configuration)
        self.print_configuration()

        self.config_button.setDisabled(True)
        self.econfig_button.setEnabled(True)
        self.psana_button.setEnabled(True)
        self.pyana_button.setEnabled(True)
        

 
    def pxana_runstring(self):
        # Make a command sequence 
        lpoptions = []
        lpoptions.append(self.pxana)
        #if self.verbose is not None:
        #    lpoptions.append("-v")
        if self.num_cpu > 1 :
            lpoptions.append("-p")
            lpoptions.append(str(self.num_cpu))
        if self.run_n is not None:
            lpoptions.append("-n")
            lpoptions.append(str(self.run_n))
        if self.skip_n is not None:
            lpoptions.append("-s")
            lpoptions.append(str(self.skip_n))
        lpoptions.append("-c")
        lpoptions.append("%s" % self.configfile)

        # put this into the config file instead... (6/4/2012)
        #for file in self.filenames :
        #    lpoptions.append(file)

        runstring = ' '.join(lpoptions)
        return runstring

    def run_pxana(self):
        """Run pyana/psana

        Open a dialog to allow chaging options to pyana/psana. Wait for OK, then
        run pyana/psana with the needed modules and configurations as requested
        based on the the checkboxes
        """
        runstring = self.pxana_runstring()

        lpoptions = runstring.split(' ')

        dialog =  QtWidgets.QInputDialog()
        dialog.resize(400,400)
        #dialog.setMinimumWidth(1500)

        text, ok = dialog.getText(self,
                                  self.Pxana + ' options',
                                  'Run ' + self.pxana + ' with the following command (edit as needed and click OK):',
                                  QtWidgets.QLineEdit.Normal,
                                  text=runstring)

        if ok:
            runstring = str(text)
            lpoptions = runstring.split(' ')

            # and update run_n and skip_n in the Gui:
            #if "-v" in lpoptions:
            #    self.verbose = True
            #else :
            #    self.verbose = False
                
            if "-n" in lpoptions:
                self.run_n = int(lpoptions[ lpoptions.index("-n")+1 ])
                self.run_n_status.setText("Process %d shots"% self.run_n)
            if "-s" in lpoptions:
                self.skip_n = int(lpoptions[ lpoptions.index("-s")+1 ])
                self.skip_n_status.setText("Skip the fist %d shots of xtc file"% self.skip_n)
        else :
            return

        print("Calling %s.... " % self.pxana)
        print("     ", ' '.join(lpoptions))

        if 1 :
            # calling a new process
            self.proc_pyana = myPopen(lpoptions) # this runs in separate thread.
            self.proc_status.setText("%s process %d is running " % (self.pxana, self.proc_pyana.pid))
            # this blocks: 
            #stdout_value = self.proc_pyana.communicate()[0]
            #print "Here's what the pyana process communicates: ",stdout_value
            # the benefit of this option is that the GUI remains unlocked
            # the drawback is that pyana needs to supply its own plots, ie. no Qt plots?
            
        if 0 :
            # calling as module... plain
            pyanamod.pyana(argv=lpoptions)
            # the benefit of this option is that pyana will draw plots on the GUI. 
            # the drawback is that GUI hangs while waiting for pyana to finish...

        if 0 :
            # calling as module... using multiprocessing
            #kwargs = {'argv':lpoptions}
            #p = mp.Process(target=pyanamod.pyana,kwargs=kwargs)
            #p.start()
            #p.join()
            # this option is nothing but trouble
            pass
        if 0 :
            # calling as module... using threading
            self.proc_pyana = MyThread(lpoptions)
            self.proc_pyana.start()
            print("I'm back")

        self.psana_button.setDisabled(True)
        self.pyana_button.setDisabled(True)
        self.susp_button.setEnabled(True)
        self.quit_button.setEnabled(True)
        self.susp_button.setDisabled(False)
        self.quit_button.setDisabled(False)
            

    def run_psana(self):
        self.pxana = "psana"
        self.Pxana = "Psana"
        self.run_pxana()

    def run_pyana(self):
        self.pxana = "pyana"
        self.Pxana = "Pyana"
        self.run_pxana()

    def quit_pyana(self) :
        """Kill the pyana process
        """
        statustext = ""

        if self.proc_pyana :
            # is it running? 
            status = self.proc_pyana.poll()
            pid = self.proc_pyana.pid
            if status is None: 
                self.proc_pyana.kill()
                statustext = "%s process %d has been killed" % (self.pxana, pid)
            else :
                statustext = "%s process %d has finished (returncode %d)" % (self.pxana, pid, status)
        else :
            print("No %s process to stop" % (self.pxana))

        self.proc_status.setText(statustext)
        self.quit_button.setDisabled(True)
        self.susp_button.setDisabled(True)
        self.psana_button.setDisabled(False)
        self.pyana_button.setDisabled(False)

#        # double check
#        status = self.proc_pyana.poll()
#        if status is not None: 
#            self.quit_button.setDisabled(True)
#            self.susp_button.setDisabled(True)
#        else:
#            print "finishing... ?"
#            print os.system("ps")


    def suspend_pyana(self):
        """suspend or resume the pyana process
        """
        checked = self.susp_button.isChecked()

        statustext = "" 
        buttontext = ""
        if self.proc_pyana :
            # is it running? 
            status = self.proc_pyana.poll()
            pid = self.proc_pyana.pid
            if status is None: 
                if checked :
                    self.proc_pyana.suspend()
                    statustext = "%s process %d has been suspended" % (self.pxana, pid)
                    buttontext = "Resume"
                else :
                    self.proc_pyana.resume()
                    statustext = "%s process %d has been resumed" % (self.pxana, pid)
                    buttontext = "Suspend"                   
            else :
                statustext = "%s process %d has finished (returncode %d)" % (self.pxana, pid, status)
        else :
            print("No %s process to suspend or resume" % (self.pxana))

        self.proc_status.setText(statustext)
        self.susp_button.setText(buttontext)


    #--------------------------------
    #  Static/class public methods --
    #--------------------------------


    #--------------------
    #  Private methods --
    #--------------------

#
#  In case someone decides to run this module
#
if __name__ == "__main__" :

    # In principle we can try to run test suite for this module,
    # have to think about it later. Right now just abort.
    sys.exit ( "Module is not supposed to be run as main module" )
