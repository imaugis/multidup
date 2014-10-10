#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
le programme sert à dupliquer un original depuis un disque SSD qui comporte 3 partitions :
1)	1 partition Linux	qui sera le /
2)	1 partition swap
3)	1 partition Linux	qui sera le /home

les partitions 1 & 2 sont fixes
la partition 3 sera variable selon la taille du disque de destination

on impose à la destination d'avoir le même UUID que l'original pour faciliter les configurations
"""

import sys,os,re,commands
from copy import deepcopy
import subprocess
import tempfile

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
	def __init__(self,part):
		""" part: /dev/sdXN  ex: /dev/sdb1"""
		self.npart = 0
		self.start = 0
		self.size = 0
		self.Id = 0
		self.bootable  = ''
		self.filesytem = ''
		self.uuid = ''

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

	def taille(self):
		return self.size		# retourne la taille de la partition

	def sfdisk_conv(self,taille_cyl):
		#print self.size, type(self.size)
		""" convertit en format compatible avec sfdisk en entree pour pouvoir créer les partitions sur le Disque destination """
		s=",{},{}".format(self.size/taille_cyl if self.size!=0 else '','S' if self.Id=='82' else 'L')
		if self.bootable=='bootable':
			s+=',*'
		s+='\n'
		return s

	def format(self,device):
		""" formatte la partition en mettant l'UUID d'origine """
		#print('formatte partition {}{}'.format(device, self.npart))
		if self.Id == '82':
			if debug:
				print ('crée le swap sur {}{}'.format(device, self.npart))
			else:
				p = subprocess.Popen(['mkswap','-U',self.uuid,device+str(self.npart)])
				p.wait()
				#print (['mkswap','-U',self.uuid,device+str(self.npart)])
		elif self.Id == '83':
			if debug:
				print ('crée la partition en {} sur {}{}'.format(self.filesytem, device, self.npart))
			else:
				p = subprocess.Popen(['mkfs.'+self.filesytem,'-U',self.uuid,device+str(self.npart)])
				p.wait()
				#print (['mkfs.'+self.filesytem,'-U',self.uuid,device+str(self.npart)])

	def mount(self,device):
		# on monte la partition
		if self.mounted == '':
			if self.Id == '83':
				self.mounted = tempfile.mkdtemp()
				print 'on vient de créer',self.mounted
				if debug:
					self.debug_part = device + str(self.npart)
					print('monte la partition {} dans -{}-'.format(self.debug_part, self.mounted))
				p = subprocess.Popen(['mount',device+str(self.npart), self.mounted])
				p.wait()
				print (['mount',device+str(self.npart), self.mounted])

	def umount(self):
		if self.mounted:
			if debug:
				print('demonte la partition {}'.format(self.debug_part))
			p = subprocess.Popen(['umount', self.mounted])
			p.wait()
			#os.rmdir(self.mounted)
			self.mounted = ''

	def copy(self,device,part):
		""" copie depuis la partition part vers la partition courante """
		# on monte la partition
		self.mount(device)

		if self.mounted:
			if debug:
				print('copie depuis la partition {} vers {}'.format(part.debug_part, self.debug_part))
			else:
				# copie
				p = subprocess.Popen(['rsync', '-axHAXP', part.mounted, self.mounted])
				p.wait()
			# on démonte la partition
			self.umount()

	def __del__(self):
		self.umount()

	def __repr__(self):
		return 'Partition %s, start=%8s, size=%8s, Id=%2s, filesytem=%6s%s, UUID=%s' % (self.npart, self.start, self.size, self.Id, self.filesytem, ', bootable' if self.bootable else '          ', self.uuid)


class Disque:
	def lit_disque(self,disk):
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

	def __init__(self,disk,origin=None, option=None):
		if disk=='':
			raise ValueError("erreur de paramètre disk")

		self.device=disk 			# /dev/sdX
		self.nbre_secteurs=0		# nbre de secteurs du disque
		self.nbre_cylindres=0		# nbre de cylindres
		#self.taille_secteur=512
		self.nbre_sect_piste=0		# nbre de secteurs par piste
		self.nbre_tetes=0
		self.taille_cylindre=0
		self.liste_part=[]

		self.lit_disque(disk)
		if origin == None:
			sfdisk_output = commands.getoutput("sfdisk -d %s" % disk)	# on lit la table de partition du disque
			for line in sfdisk_output.split("\n"):			# on explore ligne par ligne
				if line.startswith("/"):					# si la ligne commence par un / on doit avoir un /dev/sd???
					p=Partition(line)
					if p.taille() != 0:						# si la partition n'est pas vide
						self.liste_part.append(p)
		else :
			self.liste_part=deepcopy(origin.liste_part)		# recopie de la liste de partition du disque d'origine
			self.liste_part[-1].size=0						# on annule la taille de la dernière partition, ce qui permettra d'étendre cette partition autant que nécessaire

	def sfdisk_conv(self):
		""" convertit en format compatible avec sfdisk en entree pour pouvoir créer les partitions sur le Disque destination """
		s=''
		for p in self.liste_part:
			s+=p.sfdisk_conv(self.taille_cylindre)
		return s

	def copy_mbr(self,disk):
		""" copie le MBR depuis le disk vers le disque courant """
		# on copie le secteur 0 complet, en écrasant la table de partition
		print('écrase le secteur MBR du disque %s par %s' %(self.device,disk.device))
		if not debug:
			s=commands.getoutput("dd if="+disk.device+" of="+self.device+" bs=512 count=1")

	def set_partitions(self):
		print('crée une nouvelle table de partitions sur {}'.format(self.device))
		instructions = self.sfdisk_conv()
		command = ["sfdisk", self.device ]
		if not debug:
			pobj = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			(output, errors) = pobj.communicate(instructions)
			pobj.wait()
		print('formatte les partitions')
		for p in self.liste_part:
			p.format(self.device)

	def copy(self,disk):
		""" on fait la copie depuis disk vers le disque courant """
		# on s'assure que disk est monté
		disk.mount()
		# copie du mbr
		self.copy_mbr(disk)
		# conversion des partitions pour le disque courant, formattage des partitions
		self.set_partitions()
		# copie des partitions (sauf le swap)
		for index in range(len(disk.liste_part)):
			self.liste_part[index].copy(self.device, disk.liste_part[index])


	def mount(self):
		""" monte les partitions du disque """
		for part in self.liste_part:
			part.mount(self.device)

	def umount(self):
		""" démonte les partitions du disque """
		for part in self.liste_part:
			part.umount()

	def __del__(self):
		self.umount()

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

def main():
	i=Disque(entree, option='ro')
	o=Disque(sorties[0],i)
	o.copy(i)

if __name__ == '__main__':
	main()

