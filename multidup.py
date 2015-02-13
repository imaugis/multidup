#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
    multidup purpose is duplication from one linux original disk to many distination disks
    Copyright (C) 2014 thierry Escola for iMaugis

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
# you may read the README file for details

from threading import Thread
import sys,os,re
import subprocess
import tempfile
from PyQt4.QtGui import *
from PyQt4.QtCore import *

debug = False
sem_compte = QSemaphore()

class Partition:
	""" descriptif de chaque partition """
	def __init__(self, part, parent):
		self.parent = parent
		if not isinstance(part,Partition):	# si «part» n'est une Partition, la Partition à créer est un original
			""" part: /dev/sdXN  ex: /dev/sdb1"""
			self.device = ''
			self.npart	= 0 		# num de partition
			self.start 	= 0 		# secteur de début
			self.size 	= 0 		# taille en secteurs
			self.Id 	= 0 		# Id (82 swap ou 83 Linux)
			self.bootable  = ''		# si la partition est bootable
			self.filesytem = ''		# type de sytème de fichiers 'ext2' 'ext3' 'ext4'
			self.uuid 	= ''		# UUID de la partition
			self.nbf 	= 0 		# nombre de fichiers de la partition
			self.mounted = ''		# représente le point de montage de cette partition

			# on doit retrouver les paramètres de la partition dans le param «part» donné à __init__ et issu de 'sfdisk -d'
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
			""" ici «part» est une Partition dont on doit faire une copie """
			self.npart = part.npart
			self.start = part.start
			self.size  = part.size
			self.Id    = part.Id
			self.bootable  = part.bootable
			self.filesytem = part.filesytem
			self.uuid  = part.uuid
			self.nbf   = part.nbf
			self.mounted = ''

	def taille(self):
		return self.size					# retourne la taille de la partition

	def sfdisk_conv(self,disk):
		""" convertit en format compatible avec sfdisk en entree pour pouvoir créer les partitions sur le Disque destination """
		s="{}{} : start={}, size={}, Id={}{}\n".format(disk, str(self.npart), self.start, self.size if self.size !=0 else '', self.Id, ', bootable' if self.bootable else '')
		return (self.npart,s)

	def format(self,device):
		""" formatte la partition en mettant l'UUID d'origine """
		if self.Id == '82':				# il s'agit d'une partition swap
			update_label(self.parent, 'creation swap sur {}{}'.format(device, self.npart))
			if debug:
				print ('crée le swap sur {}{}'.format(device, self.npart))
			p = subprocess.Popen(['mkswap','-U',self.uuid,device+str(self.npart)])	# création du swap avec l'UUID
			p.wait()
		elif self.Id == '83':
			update_label(self.parent, 'formattage {}{}'.format(device, self.npart))
			if debug:
				print ('crée la partition en {} sur {}{}'.format(self.filesytem, device, self.npart))
			p = subprocess.Popen(['mkfs.'+self.filesytem,'-U',self.uuid,device+str(self.npart)])	# formattage extX avec l'UUID
			p.wait()

	def mount(self,device,option=''):
		# on monte la partition
		if self.mounted == '':
			if self.Id == '83':				# 83 est pour l'ext2,3 ou 4
				self.part = device + str(self.npart)
				update_label(self.parent, 'montage de ' + self.part)
				self.mounted = tempfile.mkdtemp()		# crée un répertoire dans /tmp
				if debug:
					print('monte la partition {} dans {}'.format(self.part, self.mounted))
				if option:
					p = subprocess.Popen(['mount', '-o', option, device+str(self.npart), self.mounted])
				else:
					p = subprocess.Popen(['mount', device+str(self.npart), self.mounted])
				p.wait()

	def umount(self):
		if self.mounted != '':								# si la partition est montée
			if debug:
				print('demonte la partition {}'.format(self.part))
			p = subprocess.Popen(['sync'])					# sync indispensable car sinon le umount ne fonctionne pas au cas où le buffer disque n'est pas vide
			p.wait()
			p = subprocess.Popen(['umount', self.mounted])	# démontage réel de la partition
			p.wait()
			os.rmdir(self.mounted)							# suppression du point de montage
			self.mounted = ''

	def copy(self,device,part, nbfichiers):
		""" copie depuis la partition part vers la partition courante """
		self.mount(device)							# monte la partition
		update_label(self.parent, 'copie depuis {}{}'.format(device, self.npart))
		if self.mounted:
			if debug:
				print('copie depuis la partition {} vers {}'.format(part.part, self.part))
			# copie !
			p = subprocess.Popen(['rsync', '-axHAXP', part.mounted+'/', self.mounted], stdout=subprocess.PIPE)
			c = 0
			for line in p.stdout:
				if line.decode('utf-8')[:1] != '\r':	# quand le 1er caractère de la ligne est un \r, il s'agit du débit du transfert et non pas du nom de fichier
					nbfichiers += 1
					c += 1
					if c==100:						# met à jour la barre tous les 100 fichiers
						update_bar(self.parent, nbfichiers)
						c = 0
			p.wait()
		return nbfichiers

	def compte(self, label, nbfichiers):
		""" compte le nombre de fichiers de la partition courante """
		# la partition est censée avoir été montée en lecture seule
		self.nbf = 0
		if self.mounted:			# on vérifie quand même
			p = subprocess.Popen(['rsync', '-naxHAXP', self.mounted, '/tmp/rien'], stdout=subprocess.PIPE)
			c = 0
			for line in p.stdout:	# comptage du nombre de lignes (approximatif mais suffisant)
				self.nbf += 1
				c += 1
				if c==123:			# update tous les 123 fichiers pour que ça ne ralentisse pas trop
					update_label(self.parent, str(nbfichiers+self.nbf))
					c = 0
			update_label(self.parent, '{} fichiers'.format(self.nbf+nbfichiers))
			#errcode = p.returncode
			p.wait()
		return self.nbf+nbfichiers

	def __del__(self):
		""" à la destruction de l'objet, effectue un démontage en bonne et dûe forme """
		self.umount()

	def __repr__(self):
		""" fonction d'affichage de l'objet : à titre utilitaire """
		return 'Partition %s, start=%8s, size=%8s, Id=%2s, filesytem=%6s%s, UUID=%s' % (self.npart, self.start, self.size, self.Id, self.filesytem, ', bootable' if self.bootable else '          ', self.uuid)

class Sortie(QThread):
	""" Sortie est la partie graphique de chaque Disque et aussi le thread"""
	def __init__(self, disk):
		QGridLayout.__init__(self)
		QThread.__init__(self)
		self.device = disk
		self.enabled = True

		self.check = QCheckBox(self.device)
		self.label = QLabel('---')
		self.prog_bar = QProgressBar()
		self.box = QGridLayout()
		self.box.addWidget(self.check,    0, 0)
		self.box.addWidget(self.label,    0, 1, 1, 3)
		self.box.addWidget(self.prog_bar, 0, 4, 1, 2)
		# connexion des signaux et slots pour la mise à jour du label et progressBar depuis le thread
		self.box.connect(self, SIGNAL("setValue(int)")              , self.prog_bar , SLOT("setValue(int)"))
		self.box.connect(self, SIGNAL("setLabelText(QString)")      , self.label    , SLOT("setText(QString)"))
		self.box.connect(self, SIGNAL("setLabelStyleSheet(QString)"), self.label    , SLOT("setStyleSheet(QString)"))
		self.box.connect(self, SIGNAL("setRange(int,int)")          , self.prog_bar , SLOT("setRange(int,int)"))

	def enable(self, val):
		""" grise et dégrise une Sortie """
		self.check.setEnabled(val)
		self.label.setEnabled(val)
		self.prog_bar.setEnabled(val)
		self.enabled = val

def update_label(thread, text=None, error=False):
	""" mise à jour du label par signaux et slot """
	if text != None:
		# mise à jour du texte
		thread.emit(SIGNAL("setLabelText(QString)"), text)
	if error:
		# mise à jour du style
		thread.emit(SIGNAL("setLabelStyleSheet(QString)"), "border-radius: 3px; background-color: red;")

def update_bar(thread, n=0, setRange=None):
	""" mise à jour de la progressBar par signaux et slot """
	if setRange:
		# modification du Range
		thread.emit(SIGNAL("setRange(int,int)"),0,setRange)
	else:
		# mise à jour de la valeur
		thread.emit(SIGNAL("setValue(int)"), n)


class Disque(Sortie):
	def lit_disque(self,disk):
		""" lit le nbre de têtes, de secteurs/pistes, de cylindres, de secteurs du disque courant """
		if disk != '':
			for l in subprocess.check_output(['fdisk','-l',disk]).decode('utf-8').split('\n'):	# lecture de la table de partitions
				if l[:1].isdigit():					# 255 têtes, 63 secteurs/piste, 60801 cylindres, total 976773168 secteurs
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
		super(Disque,self).__init__(disk)	# initialise la classe Sortie dont Disque hérite
		self.device = disk 			# /dev/sd?

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
			for line in sfdisk_output.decode('utf-8').split("\n"):		# on explore ligne par ligne
				if line.startswith("/"):								# si la ligne commence par un / on doit avoir un /dev/sd???
					p = Partition(line, parent=self)
					if p.taille() != 0:									# si la partition n'est pas vide
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

	def kill_gpt(self):
		""" supprime toute forme de GPT sur le disque courant """
		# on efface du disque tout ce qui concerne GPT
		update_label(self, 'supprime GPT')
		if debug:
			print('écrase le GPT du disque %s par %s' %(self.device,disk.device))
		subprocess.call(['sgdisk','--zap',self.device])

	def copy_mbr(self,disk):
		""" copie le MBR et le stage1 de grub depuis le disk vers le disque courant """
		# on copie le secteur 0 complet, en écrasant la table de partition
		# et aussi tous les secteurs soit-disant libres avant la première partition
		update_label(self, 'copie du MBR et GRUB stage1')
		nbs=disk.liste_part[0].start
		if debug:
			print('écrase le secteur MBR du disque %s par %s' %(self.device,disk.device))
		subprocess.call(['dd','if='+disk.device,'of='+self.device,'bs=512','count='+str(nbs)])

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
			self.kill_gpt()
			self.copy_mbr(self.disk)					# copie du MBR et du GRUB
			self.set_partitions()						# conversion des partitions pour le disque courant, formattage des partitions
			self.mount()								# monte les partitions du disque courant. Le disque original a déjà été monté auparavant

			sem_compte.acquire()						# attend la fin du comptage de nombre de fichiers

			update_bar(self, setRange=self.disk.nbf)	# 
			for dest,org in zip( self.liste_part, self.disk.liste_part):
				nombre_fichiers = dest.copy(self.disk.device, org, nombre_fichiers)	# copie de chaque partition
			update_label(self, 'copie terminée')
			update_bar(self, setRange=100)				# met la barre à 100%
			update_bar(self, 100)
		except subprocess.CalledProcessError as erc:
			update_label(self, error=True)				# en cas d'erreur, met le label en rouge

	def compte(self):
		""" compte le nombre de fichiers à copier dans le disque original """
		self.mount()				# assure que disk est monté.
		nombre_fichiers = 0
		# comptage des fichiers des partitions (sauf le swap)
		for part in self.liste_part:
			nombre_fichiers = part.compte(self.label, nombre_fichiers)
		self.nbf = nombre_fichiers
		sem_compte.release(50)		# le comptage est terminé : débloquage des autre threads pour la copie

	def run(self):
		""" lancement du thread ici """
		if self.original == True:	# s'il s'agit du disque original
			self.compte()			# on effectue le comptage du nombre de fichiers
		else:
			self.copy()				# sinon on effectue la copie


	def mount(self):
		""" monte les partitions du disque """
		for part in self.liste_part:
			part.mount(self.device,option=self.mount_option)

	def umount(self):
		""" démonte les partitions du disque """
		for part in self.liste_part:
			part.umount()

	def __repr__(self):
		""" fonction d'affichage de l'objet : à titre utilitaire """
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
	""" lecture de la liste des disques présents dans le système, en enlevant /dev/sda qui est le disque système """
	liste = []
	for line in subprocess.check_output(['sfdisk','-s']).decode('utf-8').split('\n'):			# on explore ligne par ligne la liste des disques du système
		if line.startswith("/"):					# si la ligne commence par un / on doit avoir un /dev/sd???
			dev = line.split(':')[0]				# on sépare le /dev/sd?
			if dev != '/dev/sda':
				liste.append(dev)
	return liste

class Fen(QWidget):
	""" fenêtre de l'interface """
	def __init__(self,parent=None):
		super(Fen,self).__init__(parent)
		self.indexIn = 0 							# index du disque original dans la liste_dev

		self.box = QVBoxLayout(self)

		self.setWindowTitle('Duplication Multiple')
		self.setMinimumWidth(400)

		self.label_org = QLabel('Disque original')
		self.combo_org = QComboBox()

		self.hbox1 = QHBoxLayout()
		self.hbox1.addWidget(self.label_org)
		self.hbox1.addWidget(self.combo_org)
		self.box.addLayout(self.hbox1)

		self.bsortie = QPushButton("Quitte")
		self.bsortie.clicked.connect(self.close)

		self.bstart  = QPushButton("Démarrer les copies")
		self.bstart.clicked.connect(self.start)

		self.box.addWidget(self.bstart)

		self.liste_dev = liste_disques()	# lecture de la liste des disques
		self.liste_gui = []
		for dev in self.liste_dev:			# pour tous les disques (sauf /dev/sda)
			s=Disque(dev)					# on crée un Disque (avec sa case à cocher, sa zone label, sa progressBar)
			self.box.addLayout(s.box)		# et on ajoute la partie graphique à l'interface
			self.liste_gui.append(s)

		self.liste_gui[0].enable(False)		# interdit le premier disque dans le gui

		self.hbox3 = QHBoxLayout()
		self.hbox3.addStretch(1)			# le bouton sera à droite
		self.hbox3.addWidget(self.bsortie)
		self.box.addLayout(self.hbox3)
		self.setLayout(self.box)

		self.combo_org.addItems(self.liste_dev)				# init de la liste des disque originaux
		self.combo_org.currentIndexChanged[str].connect(self.change_org)
		#self.change_org(self.liste_dev[0])

	def start(self):
		""" On vient de lancer les copies """
		disks_copie = []

		self.bstart.setEnabled(False)						# on grise le bouton de Démarrage
		self.disk_entree = self.liste_gui[self.indexIn]
		self.disk_entree.init(option='ro')					# init du disque original (montage des partitions en lecture seule)

		for s in self.liste_gui:
			if s.enabled:									# si pas grisé
				if s.check.isChecked():						# et sélectionné
					s.init(origin=self.disk_entree)			# il est initialisé avec le disque d'origine
					disks_copie.append(s)
		self.disk_entree.start()							# lance le comptage sur le disque d'origine
		self.disk_entree.finished.connect(self.thread_fini)	# connecte la fin du comptage
		self.nbthreads = 1 									# le 1 est le thread du disque d'entrée
		for th in disks_copie:								# on lance le thread de chaque disque destination
			th.start()										# par la commande run() de Disque
			self.nbthreads += 1
			th.finished.connect(self.thread_fini)			# connection de la fin du thread

	def change_org(self,val):
		""" l'utilisateur vient de changer le disque d'origine """
		#global entree
		for s in self.liste_gui:
			s.enable(True)
		self.indexIn = self.combo_org.currentIndex()
		self.liste_gui[self.indexIn].enable(False)
		#entree = str(val)									# convertit depuis un QString

	def thread_fini(self):
		""" fait le décompte des threads qui se terminent pour faire un flush des buffers disques
		et passer le bouton «Quitte» en vert """
		self.nbthreads -= 1
		if self.nbthreads == 0:
			p = subprocess.Popen(['sync'])					# on flush les buffers disque
			p.wait()
			self.bsortie.setStyleSheet("QPushButton { color: white; background-color: green; }")

def check_commands():
	""" vérifie la présence des commandes système utilisées """
	erreur = False
	for com,param in (('dd','--version'),('sfdisk','-v'),('fdisk','-v'),('mkswap','--version'),('mount','--version')):
		try:
			subprocess.check_output([com,param])
		except FileNotFoundError:
			print("commande «{}» pas trouvée".format(com))
			erreur = True
	if erreur == True:
		exit(1)
		

def main(args):
	check_commands()
	app=QApplication(args)
	app.setStyle("plastique")
	fenetre = Fen()
	fenetre.show()
	app.exec_()

if __name__ == '__main__':
	main(sys.argv)
