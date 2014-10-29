#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
le programme sert à dupliquer un original depuis un disque SSD qui comporte 3 partitions :
1)	1 partition Linux	qui sera le /
2)	1 partition swap
3)	1 partition Linux	qui sera le /home

les partitions 1 & 2 sont fixes
la partition 3 sera variable selon la taille du disque de destination

on impose à la destination d'avoir les même UUID que l'original pour faciliter les configurations
"""

import sys,os,re,commands
#from copy import deepcopy
import subprocess
import tempfile
from PyQt4.QtGui import *
from PyQt4.QtCore import *

debug = True

entree="/dev/sdb"
sorties=["/dev/sdc"]
partition=entree
disques_sortie=[]

def ls():
	p = subprocess.Popen(['ls','/tmp'])
	p.wait()

class Partition:
	"""descriptif de chaque partition"""
	def __init__(self, part, label=None, progressbar=None):
		if not isinstance(part,Partition):
			""" part: /dev/sdXN  ex: /dev/sdb1"""
			self.npart = 0
			self.start = 0
			self.size = 0
			self.Id = 0
			self.bootable  = ''
			self.filesytem = ''
			self.uuid = ''
			self.nbf = 0 			# nombre de fichiers de la partition
			self.label = label
			self.prog_bar = progressbar

			self.mounted = ''		# représente le répertoire monté de cette partition

			parts = re.compile(r"^\D+([0-9]*).*start= *([0-9]*).*size= *([0-9]*).*Id= *([0-9]*),? ?([a-zA-Z]*)?").search(part)
			self.npart,self.start,self.size,self.Id,self.bootable=parts.groups()
			self.npart=int(self.npart)
			self.start=int(self.start)
			self.size =int(self.size)

			blkid = commands.getoutput("blkid %s" % part)	# on lit l'UUID et le système de fichier
			if blkid:
				rex=re.compile(r"UUID=\"([^\"]*)\" TYPE=\"([^\"]*)\"")
				resultat=rex.search(blkid)
				self.uuid,self.filesytem=resultat.groups()
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
			self.label = label
			self.prog_bar = progressbar

			self.mounted = ''		# représente le répertoire monté de cette partition


	def taille(self):
		return self.size		# retourne la taille de la partition

	def sfdisk_conv(self,disk):
		#print self.size, type(self.size)
		""" convertit en format compatible avec sfdisk en entree pour pouvoir créer les partitions sur le Disque destination """
		s="/dev/{}{} : start={}, size={}, Id={}{}\n".format(disk, str(self.npart), self.start, self.size if self.size !=0 else '', self.Id, ', bootable' if self.bootable else '')
		return (self.npart,s)

	def format(self,device):
		""" formatte la partition en mettant l'UUID d'origine """
		#print('formatte partition {}{}'.format(device, self.npart))
		update_label(self.label, 'formattage %s%s' % (device, self.npart))
		if self.Id == '82':
			if debug:
				print ('crée le swap sur {}{}'.format(device, self.npart))
			p = subprocess.Popen(['mkswap','-U',self.uuid,device+str(self.npart)])
			p.wait()
			#print (['mkswap','-U',self.uuid,device+str(self.npart)])
		elif self.Id == '83':
			if debug:
				print ('crée la partition en {} sur {}{}'.format(self.filesytem, device, self.npart))
			p = subprocess.Popen(['mkfs.'+self.filesytem,'-U',self.uuid,device+str(self.npart)])
			p.wait()
			#print (['mkfs.'+self.filesytem,'-U',self.uuid,device+str(self.npart)])

	def mount(self,device,option=''):
		# on monte la partition
		if self.mounted == '':
			update_label(self.label, 'montage de %s%s' % (device, self.npart))
			if self.Id == '83':
				self.mounted = tempfile.mkdtemp()
				#print 'on vient de créer',self.mounted
				if debug:
					self.debug_part = device + str(self.npart)
					print('monte la partition {} dans {}'.format(self.debug_part, self.mounted))
				if option:
					p = subprocess.Popen(['mount', '-o', option, device+str(self.npart), self.mounted])
				else:
					p = subprocess.Popen(['mount', device+str(self.npart), self.mounted])
				p.wait()
				#print (['mount',device+str(self.npart), self.mounted])

	def umount(self):
		if self.mounted != '':
			if debug:
				print('demonte la partition {}'.format(self.debug_part))
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
		if self.mounted:
			if debug:
				print('copie depuis la partition {} vers {}'.format(part.debug_part, self.debug_part))
			# copie
			p = subprocess.Popen(['rsync', '-axHAXP', part.mounted+'/', self.mounted], stdout=subprocess.PIPE)
			c = 0
			for line in p.stdout:
				print line
				nbfichiers += 1
				c += 1
				if c==100:
					update_bar(self.prog_bar, nbfichiers)
					c = 0
			update_bar(self.prog_bar, nbfichiers)
			#errcode = p.returncode
			p.wait()
			# on démonte la partition
			#self.umount()		c'est mieux de le laisser faire par le destructeur
		return nbfichiers

	def compte(self, label, nbfichiers):
		""" compte le nombre de fichiers de la partition courante """
		# la partition est censée avoir été montée en lecture seule
		if self.mounted:	# on vérifie quand même
			self.nbf = 0
			p = subprocess.Popen(['rsync', '-naxHAXP', self.mounted, '/tmp/rien'], stdout=subprocess.PIPE)
			#p = subprocess.Popen(['rsync','-naxHAXP','/home','/tmp/ttttaaaa'], stdout=subprocess.PIPE)
			c = 0
			for line in p.stdout:
				self.nbf += 1
				c += 1
				if c==123:
					update_label(label, nbfichiers+self.nbf)
					c = 0
			update_label(label, '%s fichiers' % (self.nbf+nbfichiers))
			p.wait()
			errcode = p.returncode
		return self.nbf+nbfichiers

	def __del__(self):
		self.umount()

	def __repr__(self):
		return 'Partition %s, start=%8s, size=%8s, Id=%2s, filesytem=%6s%s, UUID=%s' % (self.npart, self.start, self.size, self.Id, self.filesytem, ', bootable' if self.bootable else '          ', self.uuid)


class Disque:
	def lit_disque(self,disk):
		print disk
		if disk != '':
			s=commands.getoutput("fdisk -l %s" % disk)
			for l in s.split('\n'):
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

	def __init__(self,disk, sortie_gui, origin=None, option=''):
		self.device = disk 			# /dev/sdX
		self.nbre_secteurs = 0		# nbre de secteurs du disque
		self.nbre_cylindres = 0		# nbre de cylindres
		#self.taille_secteur=512
		self.nbre_sect_piste = 0	# nbre de secteurs par piste
		self.nbre_tetes = 0
		self.taille_cylindre = 0
		self.liste_part = []
		self.mount_option = option
		self.nbf = 0 				# nbre de fichiers à copier (pour la progress bar)
		self.label = sortie_gui.label
		self.prog_bar = sortie_gui.prog_bar

		self.lit_disque(disk)
		if origin == None:
			sfdisk_output = commands.getoutput("sfdisk -d %s" % disk)	# on lit la table de partition du disque
			for line in sfdisk_output.split("\n"):			# on explore ligne par ligne
				if line.startswith("/"):					# si la ligne commence par un / on doit avoir un /dev/sd???
					p = Partition(line,self.label,self.prog_bar)
					if p.taille() != 0:						# si la partition n'est pas vide
						self.liste_part.append(p)
		else :
			self.liste_part = [ Partition(part, self.label, self.prog_bar) for part in origin.liste_part ]
			self.liste_part[-1].size = 0						# on annule la taille de la dernière partition, ce qui permettra d'étendre cette partition autant que nécessaire

	def sfdisk_conv(self):
		""" convertit en format compatible avec sfdisk en entree pour pouvoir créer les partitions sur le Disque destination """
		s='unit: sectors\n'
		# /dev/sdb4 : start=        0, size=        0, Id= 0
		part={}
		for p in self.liste_part:
			n,s1=p.sfdisk_conv(self.device)
			part[n]=s1
		for n in [1,2,3,4]:  # vérifie s'il y a les 4 partitions, sinon en fait des vides
			if n in part:
				s += part[n]
			else:
				s += '/dev/{}{} : start= 0, size= 0, Id= 0\n'.format(self.device, n)
		return s

	def copy_mbr(self,disk):
		""" copie le MBR et le stage1 de grub depuis le disk vers le disque courant """
		# on copie le secteur 0 complet, en écrasant la table de partition
		# et aussi tous les secteurs soit-disant libre avant la première partition
		nbs=disk.liste_part[0].start
		if debug:
			print('écrase le secteur MBR du disque %s par %s' %(self.device,disk.device))
		s=commands.getoutput("dd if="+disk.device+" of="+self.device+" bs=512 count="+str(nbs))
		p = subprocess.Popen(['sync'])
		p.wait()

	def set_partitions(self):
		#print('crée une nouvelle table de partitions sur {}'.format(self.device))
		instructions = self.sfdisk_conv()
		command = ["sfdisk", self.device ]
		pobj = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		(output, errors) = pobj.communicate(instructions)
		pobj.wait()
		if debug:
			print('formatte les partitions')
		for p in self.liste_part:
			p.format(self.device)

	def copy(self, disk):
		""" on fait la copie depuis disk vers le disque courant """
		#print('copie')
		nombre_fichiers = 0
		self.prog_bar.setRange(0, disk.nbf)

		# copie du mbr
		self.copy_mbr(disk)
		# conversion des partitions pour le disque courant, formattage des partitions
		self.set_partitions()
		# on s'assure que le disque courant est monté. Le disque original a déjà été monté auparavant
		self.mount()
		# copie des partitions (sauf le swap)
		for dest,org in zip( self.liste_part, disk.liste_part):
			#print 'copie depuis %s' % disk.device
			nombre_fichiers = dest.copy(disk.device, org, nombre_fichiers)

	def compte(self):
		""" compte le nombre de fichiers à copier dans le disque original """
		# on s'assure que disk est monté
		self.mount()
		nombre_fichiers = 0
		# comptage des partitions (sauf le swap)
		for part in self.liste_part:
			nombre_fichiers = part.compte(self.label, nombre_fichiers)
		self.nbf = nombre_fichiers

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

def update_label(label,n):
	label.setText(str(n))
	QApplication.processEvents()

def update_bar(bar, n):
	bar.setValue(n)
	QApplication.processEvents()

def liste_disques():
	liste = []
	sfdisk_output = commands.getoutput("sfdisk -s")	# on lit la liste des disques du système
	for line in sfdisk_output.split("\n"):			# on explore ligne par ligne
		if line.startswith("/"):					# si la ligne commence par un / on doit avoir un /dev/sd???
			dev = line.split(':')[0]				# on sépare le /dev/sd?
			if dev != '/dev/sda':
				liste.append(dev)
	return liste

class Sortie(QGridLayout):
	def __init__(self, disk):
		QGridLayout.__init__(self)
		self.device = disk
		self.enabled = True

		self.check = QCheckBox(disk)
		self.label = QLabel('---')
		self.prog_bar = QProgressBar()
		self.addWidget(self.check, 0, 0)
		self.addWidget(self.label, 0, 1, 1, 3)
		self.addWidget(self.prog_bar, 0, 4, 1, 2)

	def enable(self, val):
		self.check.setEnabled(val)
		self.label.setEnabled(val)
		self.prog_bar.setEnabled(val)
		self.enabled = val

class Fen(QWidget):
	def __init__(self,parent=None):
		super(Fen,self).__init__(parent)
		self.indexIn = 0 				# index du disque original dans la liste_dev

		self.box = QVBoxLayout(self)

		self.setWindowTitle('Duplication Multiple')
		self.setMinimumWidth(400)

		self.bouton = QPushButton('Comptage')
		self.bouton.clicked.connect(self.compte)

		self.label = QLabel('Nombre de fichiers')
		self.label_org = QLabel('Disque original')
		self.combo_org = QComboBox()

		self.hbox1 = QHBoxLayout()
		self.hbox1.addWidget(self.label_org)
		self.hbox1.addWidget(self.combo_org)
		self.hbox2 = QHBoxLayout()
		self.hbox2.addWidget(self.bouton)
		self.hbox2.addWidget(self.label)
		self.box.addLayout(self.hbox1)
		self.box.addLayout(self.hbox2)

		self.bsortie = QPushButton("Quitte")
		self.bstart = QPushButton(QString.fromUtf8("Démarrer les copies"))
		self.bsortie.clicked.connect(self.close)
		self.bstart.clicked.connect(self.start)
		self.box.addWidget(self.bstart)

		self.liste_dev = liste_disques()
		self.liste_gui = []
		for dev in self.liste_dev:
			l=Sortie(dev)
			self.box.addLayout(l)
			self.liste_gui.append(l)

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
		disks_out = []
		for s in self.liste_gui:
			if s.enabled:
				if s.check.isChecked():
					disks_out.append(s.device)
		#self.disk_sortie = Disque(sorties[0], self.disk_entree, sortie_gui)
		#self.disk_sortie.copy(self.disk_entree)
		print(disks_out)

	def change_org(self,val):
		global entree
		for s in self.liste_gui:
			s.enable(True)
		self.indexIn = self.combo_org.currentIndex()
		self.liste_gui[self.indexIn].enable(False)
		entree = str(val)

def main(args):
	#chaque programme doit disposer d'une instance de QApplication gérant l'ensemble des widgets
	app=QApplication(args)
	app.setStyle("plastique")
	#un nouveau bouton
	fenetre = Fen()
	fenetre.show()
	app.exec_()

if __name__ == '__main__':
	main(sys.argv)
