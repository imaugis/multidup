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

entree="/dev/sdb"
sorties=["/dev/sdc"]
partition=entree
disques_sortie=[]

class Partition:
	"""descriptif de chaque partition"""
	def __init__(self,part):
		""" part: /dev/sdXN  ex: /dev/sdb1"""
		self.npart=0
		self.start=0
		self.size=0
		self.Id=0
		self.bootable=''
		self.filesytem=''
		self.uuid=''

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
		print self.size, type(self.size)
		""" convertit en format compatible avec sfdisk en entree pour pouvoir créer les partitions sur le Disque destination """
		s=",{},{}".format(self.size/taille_cyl if self.size!=0 else '','S' if self.Id=='82' else 'L')
		if self.bootable=='bootable':
			s+=',*'
		s+='\n'
		return s

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

	def __init__(self,disk,origin=None):
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
	i=Disque(entree)
	o=Disque(sorties[0],i)
	print o.device

if __name__ == '__main__':
	main()
