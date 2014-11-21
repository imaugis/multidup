#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
le programme sert à dupliquer un original depuis un disque SSD qui comporte 3 partitions :
1)	1 partition Linux	qui sera le /
2)	1 partition swap
3)	1 partition Linux	qui sera le /home

les partitions 1 & 2 sont fixes
la partition 3 sera variable selon la taille du disque de destination

il n'y a pas de limite au nombre de disques destination

on impose à la destination d'avoir les même UUID que l'original pour ne pas avoir de config à faire sur les copies

nécessite python3 et python3-pyqt4
"""

from threading import Thread
import sys,os,re
import subprocess
import tempfile
from PyQt4.QtGui import *
from PyQt4.QtCore import *

debug = False
sem_compte = QSemaphore()

class Partition:
	"""descriptif de chaque partition"""
	def __init__(self, part, parent):
		self.parent = parent
		if not isinstance(part,Partition):
			""" part: /dev/sdXN  ex: /dev/sdb1"""
			self.device = ''
			self.npart	= 0
			self.start 	= 0
			self.size 	= 0
			self.Id 	= 0
			self.bootable  = ''
			self.filesytem = ''
			self.uuid 	= ''
			self.nbf 	= 0 			# nombre de fichiers de la partition

			self.mounted = ''		# représente le répertoire monté de cette partition
			#parts = re.compile(r"^\D+([0-9]*).*start= *([0-9]*).*size= *([0-9]*).*Id= *([0-9]*),? ?([a-zA-Z]*)?").search(part)
			parts = re.compile(r"^([^0-9]*)([0-9]*).*start= *([0-9]*).*size= *([0-9]*).*Id= *([0-9]*),? ?([a-zA-Z]*)?").search(part)
			self.device, self.npart, self.start, self.size, self.Id, self.bootable = parts.groups()
			self.npart= int(self.npart)
			self.start= int(self.start)
			self.size = int(self.size)
			update_label(self.parent, 'lecture UUID')

			if self.size != 0:
				p = subprocess.check_output(["blkid",self.device+str(self.npart)])
				blkid = p.decode('utf-8').split('\n')[0]
				if blkid:
					rex = re.compile(r"UUID=\"([^\"]*)\" TYPE=\"([^\"]*)\"")
					resultat = rex.search(blkid)
					self.uuid, self.filesytem = resultat.groups()
					print('uuid = {}  et fstype = {}'.format(self.uuid,self.filesytem))

		else:
			""" ici part est une partition dont on doit faire une copie """
			self.npart = part.npart
			self.start = part.start
			self.size  = part.size
			self.Id    = part.Id
			self.bootable  = part.bootable
			self.filesytem = part.filesytem
			self.uuid  = part.uuid
			self.nbf   = part.nbf 			# nombre de fichiers de la partition


			self.mounted = ''		# représente le répertoire monté de cette partition


	def taille(self):
		return self.size		# retourne la taille de la partition

	def sfdisk_conv(self,disk):
		#print self.size, type(self.size)
		""" convertit en format compatible avec sfdisk en entree pour pouvoir créer les partitions sur le Disque destination """
		s="{}{} : start={}, size={}, Id={}{}\n".format(disk, str(self.npart), self.start, self.size if self.size !=0 else '', self.Id, ', bootable' if self.bootable else '')
		return (self.npart,s)

	def format(self,device):
		""" formatte la partition en mettant l'UUID d'origine """
		#print('formatte partition {}{}'.format(device, self.npart))
		if self.Id == '82':
			update_label(self.parent, 'creation swap sur %s%s' % (device, self.npart))
			if debug:
				print ('crée le swap sur {}{}'.format(device, self.npart))
			p = subprocess.Popen(['mkswap','-U',self.uuid,device+str(self.npart)])
			p.wait()
		elif self.Id == '83':
			update_label(self.parent, 'formattage %s%s' % (device, self.npart))
			if debug:
				print ('crée la partition en {} sur {}{}'.format(self.filesytem, device, self.npart))
			p = subprocess.Popen(['mkfs.'+self.filesytem,'-U',self.uuid,device+str(self.npart)])
			p.wait()

	def mount(self,device,option=''):
		# on monte la partition
		if self.mounted == '':
			if self.Id == '83':
				self.part = device + str(self.npart)
				update_label(self.parent, 'montage de ' + self.part)
				self.mounted = tempfile.mkdtemp()
				if debug:
					print('monte la partition {} dans {}'.format(self.part, self.mounted))
				if option:
					p = subprocess.Popen(['mount', '-o', option, device+str(self.npart), self.mounted])
				else:
					p = subprocess.Popen(['mount', device+str(self.npart), self.mounted])
				p.wait()

	def umount(self):
		if self.mounted != '':
			#update_label(thread, self.label, 'demontage de '+ self.part)
			if debug:
				print('demonte la partition {}'.format(self.part))
			p = subprocess.Popen(['sync'])
			p.wait()
			p = subprocess.Popen(['umount', self.mounted])
			p.wait()
			os.rmdir(self.mounted)
			self.mounted = ''

	def copy(self,device,part, nbfichiers):
		""" copie depuis la partition part vers la partition courante """
		# on monte la partition
		self.mount(device)
		update_label(self.parent, 'copie depuis %s%s' % (device, self.npart))
		if self.mounted:
			if debug:
				print('copie depuis la partition {} vers {}'.format(part.part, self.part))
			# copie
			p = subprocess.Popen(['rsync', '-axHAXP', part.mounted+'/', self.mounted], stdout=subprocess.PIPE)
			c = 0
			for line in p.stdout:
				if line.decode('utf-8')[:1] != '\r':
					#print(line)
					nbfichiers += 1
					c += 1
					if c==100:
						update_bar(self.parent, nbfichiers)
						c = 0
			#update_bar(self.prog_bar, nbfichiers)
			p.wait()
		return nbfichiers

	def compte(self, label, nbfichiers):
		""" compte le nombre de fichiers de la partition courante """
		# la partition est censée avoir été montée en lecture seule
		if self.mounted:	# on vérifie quand même
			self.nbf = 0
			p = subprocess.Popen(['rsync', '-naxHAXP', self.mounted, '/tmp/rien'], stdout=subprocess.PIPE)
			c = 0
			for line in p.stdout:
				self.nbf += 1
				c += 1
				if c==123:
					update_label(self.parent, str(nbfichiers+self.nbf))
					c = 0
			update_label(self.parent, '%s fichiers' % (self.nbf+nbfichiers))
			p.wait()
			errcode = p.returncode
		return self.nbf+nbfichiers

	def __del__(self):
		self.umount()

	def __repr__(self):
		return 'Partition %s, start=%8s, size=%8s, Id=%2s, filesytem=%6s%s, UUID=%s' % (self.npart, self.start, self.size, self.Id, self.filesytem, ', bootable' if self.bootable else '          ', self.uuid)


class Sortie(QThread):
	def __init__(self, disk):
		QGridLayout.__init__(self)
		QThread.__init__(self)
		self.device = disk
		self.enabled = True

		self.check = QCheckBox(self.device)
		self.label = QLabel('---')
		self.prog_bar = QProgressBar()
		self.box = QGridLayout()
		self.box.addWidget(self.check, 0, 0)
		self.box.addWidget(self.label, 0, 1, 1, 3)
		self.box.addWidget(self.prog_bar, 0, 4, 1, 2)
		self.box.connect(self , SIGNAL("progress(int)"), self.prog_bar , SLOT("setValue(int)"))
		self.box.connect(self , SIGNAL("setLabelText(QString)"), self.label , SLOT("setText(QString)"))
		self.box.connect(self , SIGNAL("setLabelStyleSheet(QString)"), self.label , SLOT("setStyleSheet(QString)"))

	def enable(self, val):
		self.check.setEnabled(val)
		self.label.setEnabled(val)
		self.prog_bar.setEnabled(val)
		self.enabled = val

def update_label(thread, text=None, error=False):
	if text != None:
		thread.emit(SIGNAL("setLabelText(QString)"), text)
		#thread.emit(SIGNAL("progress(int)"), val)
		#label.setText(str(n))
	if error:
		thread.emit(SIGNAL("setLabelStyleSheet(QString)"), "border-radius: 3px; background-color: red;")
		#label.setStyleSheet("border-radius: 3px;"
        #                    "background-color: red;")

def update_bar(thread, n):
	#bar.setValue(thread, n)
	thread.emit(SIGNAL("progress(int)"), n)

class Disque(Sortie):
	def lit_disque(self,disk):
		if disk != '':
			#s=commands.getoutput("fdisk -l %s" % disk)
			for l in subprocess.check_output(['fdisk','-l',disk]).decode('utf-8').split('\n'):
				if l[:1].isdigit():
					rex=re.compile(r"^(\d+)\D+(\d+)\D+(\d+)\D+(\d+)")
					resultat=rex.search(l)
					self.nbre_tetes,self.nbre_sect_piste,self.nbre_cylindres,self.nbre_secteurs=resultat.groups()
					self.nbre_tetes     =int(self.nbre_tetes)
					self.nbre_sect_piste=int(self.nbre_sect_piste)
					self.nbre_cylindres =int(self.nbre_cylindres)
					self.nbre_secteurs  =int(self.nbre_secteurs)
					self.taille_cylindre=self.nbre_sect_piste * self.nbre_tetes
					break

	def __init__(self, disk):
		super(Disque,self).__init__(disk)
		#Sortie.__init__(self, disk)
		self.device = disk 			# /dev/sdX

	def init(self, origin=None, option=''):
		print('init de {}'.format(self.device))
		#disk.device = disk 			# /dev/sdX
		self.nbre_secteurs = 0		# nbre de secteurs du disque
		self.nbre_cylindres = 0		# nbre de cylindres
		#self.taille_secteur=512
		self.nbre_sect_piste = 0	# nbre de secteurs par piste
		self.nbre_tetes = 0
		self.taille_cylindre = 0
		self.liste_part = []
		self.mount_option = option
		self.nbf = 0 				# nbre de fichiers à copier (pour la progress bar)
		self.original = True		# si True, il s'agit du disque original
		self.disk = None			# est le Disque original

		self.lit_disque(self.device)
		if origin == None:
			update_label(self, 'lecture tbl part de ' + self.device)
			sfdisk_output = subprocess.check_output(["sfdisk","-d",self.device])	# on lit la table de partition du disque
			for line in sfdisk_output.decode('utf-8').split("\n"):			# on explore ligne par ligne
				if line.startswith("/"):							# si la ligne commence par un / on doit avoir un /dev/sd???
					p = Partition(line, parent=self)
					if p.taille() != 0:								# si la partition n'est pas vide
						self.liste_part.append(p)
		else :
			self.original = False
			self.disk = origin
			self.liste_part = [ Partition(part, parent=self) for part in origin.liste_part ]
			self.liste_part[-1].size = 0						# on annule la taille de la dernière partition, ce qui permettra d'étendre cette partition autant que nécessaire

	def sfdisk_conv(self):
		""" convertit en format compatible avec sfdisk en entree pour pouvoir créer les partitions sur le Disque destination """
		s='unit: sectors\n'
		# /dev/sdb4 : start=        0, size=        0, Id= 0
		part={}
		for p in self.liste_part:
			n,s1=p.sfdisk_conv(self.device)
			part[n]=s1
		for n in [1,2,3,4]:  # vérifie s'il y a bien les 4 partitions, sinon en fait des vides
			if n in part:
				s += part[n]
			else:
				s += '{}{} : start= 0, size= 0, Id= 0\n'.format(self.device, n)
		return s

	def copy_mbr(self,disk):
		""" copie le MBR et le stage1 de grub depuis le disk vers le disque courant """
		# on copie le secteur 0 complet, en écrasant la table de partition
		# et aussi tous les secteurs soit-disant libre avant la première partition
		update_label(self, 'copie du MBR et GRUB stage1')
		nbs=disk.liste_part[0].start
		if debug:
			print('écrase le secteur MBR du disque %s par %s' %(self.device,disk.device))
		subprocess.call(['dd','if='+disk.device,'of='+self.device,'bs=512','count='+str(nbs)])
		#s=commands.getoutput("dd if="+disk.device+" of="+self.device+" bs=512 count="+str(nbs))
		#p = subprocess.Popen(['sync'])
		#p.wait()

	def set_partitions(self):
		""" crée une nouvelle table de partitions sur le device courant """
		instructions = self.sfdisk_conv()
		command = ["sfdisk", self.device ]
		pobj = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		(output, errors) = pobj.communicate(instructions.encode('utf-8'))
		pobj.wait()
		if debug:
			print('formatte les partitions')
		for p in self.liste_part:
			p.format(self.device)

	def copy(self):
		""" on fait la copie depuis disk vers le disque courant """
		nombre_fichiers = 0
		try:
			# copie du mbr
			self.copy_mbr(self.disk)
			# conversion des partitions pour le disque courant, formattage des partitions
			self.set_partitions()
			# on s'assure que le disque courant est monté. Le disque original a déjà été monté auparavant
			self.mount()
			sem_compte.acquire()	# attend la fin du comptage de nombre de fichiers
			# copie des partitions (sauf le swap)
			self.prog_bar.setRange(0, self.disk.nbf)
			for dest,org in zip( self.liste_part, self.disk.liste_part):
				nombre_fichiers = dest.copy(self.disk.device, org, nombre_fichiers)
			update_label(self, 'copie terminée')
			self.prog_bar.setRange(0, 100)
			update_bar(self, 100)
		except subprocess.CalledProcessError as erc:
			update_label(self, error=True)

	def compte(self):
		""" compte le nombre de fichiers à copier dans le disque original """
		# on s'assure que disk est monté
		self.mount()
		nombre_fichiers = 0
		# comptage des partitions (sauf le swap)
		for part in self.liste_part:
			nombre_fichiers = part.compte(self.label, nombre_fichiers)
		self.nbf = nombre_fichiers
		sem_compte.release(50)	# débloquage des autre threads pour la copie

	def run(self):
		print('run')
		print(self.original)
		if self.original == True:
			self.compte()
		else:
			self.copy()


	def mount(self):
		""" monte les partitions du disque """
		for part in self.liste_part:
			part.mount(self.device,option=self.mount_option)

	def umount(self):
		""" démonte les partitions du disque """
		for part in self.liste_part:
			part.umount()

	#def __del__(self):
	#	self.umount()

	def __repr__(self):
		s=''
		for p in self.liste_part:
			s=s+'   {}\n'.format(p)
		return ("Disque {}\n".format(self.device) +
				"  secteurs : {}\n".format(self.nbre_secteurs) +
				"  têtes    : {}\n".format(self.nbre_tetes) +
				"  s/piste  : {}\n".format(self.nbre_sect_piste) +
				"  cylindres: {}\n".format(self.nbre_cylindres) +
				s)


def liste_disques():
	liste = []
	for line in subprocess.check_output(['sfdisk','-s']).decode('utf-8').split('\n'):			# on explore ligne par ligne la liste des disques du système
		if line.startswith("/"):					# si la ligne commence par un / on doit avoir un /dev/sd???
			dev = line.split(':')[0]				# on sépare le /dev/sd?
			if dev != '/dev/sda':
				liste.append(dev)
	return liste

class Fen(QWidget):
	def __init__(self,parent=None):
		super(Fen,self).__init__(parent)
		self.indexIn = 0 				# index du disque original dans la liste_dev

		self.box = QVBoxLayout(self)

		self.setWindowTitle('Duplication Multiple')
		self.setMinimumWidth(400)

		#self.bouton = QPushButton('Comptage')
		#self.bouton.clicked.connect(self.compte) ############################## bouton compte inactif

		#self.label = QLabel('Nombre de fichiers')
		self.label_org = QLabel('Disque original')
		self.combo_org = QComboBox()

		self.hbox1 = QHBoxLayout()
		self.hbox1.addWidget(self.label_org)
		self.hbox1.addWidget(self.combo_org)
		#self.hbox2 = QHBoxLayout()
		#self.hbox2.addWidget(self.bouton)
		#self.hbox2.addWidget(self.label)
		self.box.addLayout(self.hbox1)
		#self.box.addLayout(self.hbox2)

		self.bsortie = QPushButton("Quitte")
		self.bstart = QPushButton("Démarrer les copies")
		#self.bstart = QPushButton(QString.fromUtf8("Démarrer les copies"))
		self.connect(self.bsortie,SIGNAL("clicked()"), self.close)
		self.connect(self.bstart,SIGNAL("clicked()"), self.start)
		#self.bsortie.clicked.connect(self.close)
		#self.bstart.clicked.connect(self.start)
		self.box.addWidget(self.bstart)

		self.liste_dev = liste_disques()
		self.liste_gui = []
		for dev in self.liste_dev:
			s=Disque(dev)
			self.box.addLayout(s.box)
			self.liste_gui.append(s)

		self.hbox3 = QHBoxLayout()
		self.hbox3.addStretch(1)
		self.hbox3.addWidget(self.bsortie)
		self.box.addLayout(self.hbox3)
		self.setLayout(self.box)

		self.combo_org.addItems(self.liste_dev)
		self.combo_org.currentIndexChanged[str].connect(self.change_org)
		self.change_org(self.liste_dev[0])

	def compte(self):
		self.disk_entree = Disque(self.liste_dev[self.indexIn], self.liste_gui[self.indexIn], option='ro')
		self.disk_entree.compte()

	def start(self):
		#self.compte()
		disks_out = []
		disks_copie = []

		self.bstart.setEnabled(False)
		self.disk_entree = self.liste_gui[self.indexIn]
		self.disk_entree.init(option='ro')

		for s in self.liste_gui:
			if s.enabled:
				if s.check.isChecked():
					disks_out.append(s.device)		# à des fins de test
					s.init(origin=self.disk_entree)
					#disks_copie.append(Thread(target=Disque(s.device, s, origin=self.disk_entree).copy, args = (self.disk_entree,)))
					disks_copie.append(s)
		self.disk_entree.start()
		self.disk_entree.finished.connect(self.thread_fini)
		self.nbthreads = 1
		for th in disks_copie:
			th.start()
			self.nbthreads += 1
			th.finished.connect(self.thread_fini)
		print(disks_out)		# à des fins de test

	def change_org(self,val):
		global entree
		for s in self.liste_gui:
			s.enable(True)
		self.indexIn = self.combo_org.currentIndex()
		self.liste_gui[self.indexIn].enable(False)
		entree = str(val)

	def thread_fini(self):
		self.nbthreads -= 1
		if self.nbthreads == 0:
			self.bsortie.setStyleSheet("QPushButton { color: white; background-color: green; }")

def main(args):
	app=QApplication(args)
	app.setStyle("plastique")
	fenetre = Fen()
	fenetre.show()
	app.exec_()

if __name__ == '__main__':
	main(sys.argv)
