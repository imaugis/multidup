#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys
import subprocess
from PyQt4.QtGui import *
from PyQt4.QtCore import *

class Fen(QWidget):
	def __init__(self,parent=None):
		super(Fen,self).__init__(parent)
		self.box = QFormLayout(self)

		self.bouton = QPushButton(QString.fromUtf8("lire qté de fichiers de /home"))
		self.bouton.clicked.connect(self.compte)
		self.label = QLabel('nombre de fichiers')
		self.box.addRow(self.bouton, self.label)

		self.hbox2 = QHBoxLayout()
		self.bsortie = QPushButton("Quitte")
		self.bstart = QPushButton("Start !")
		self.bsortie.clicked.connect(self.close)
		self.prog_bar = QProgressBar()
		self.box.addRow(self.bstart, self.prog_bar)

		self.box.addWidget(self.bsortie)
		self.setLayout(self.box)

	def compte(self):
		self.nbf = 0
		p = subprocess.Popen(['rsync','-naxHAXP','/home','/tmp/ttttaaaa'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		for line in p.stdout:
			self.nbf += 1
			self.label.setText(str(self.nbf))
		errcode = p.returncode

def main(args) :
	#chaque programme doit disposer d'une instance de QApplication gérant l'ensemble des widgets
	app=QApplication(args)
	#un nouveau bouton
	fenetre = Fen()
	fenetre.show()
	app.exec_()

if __name__ == "__main__" :
	main(sys.argv)
