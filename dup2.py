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

entree="/dev/sdb"
sorties=["/dev/sdc"]
partition=entree
disques_sortie=[]

class Partition:
	"""descriptif de chaque partition"""
	def __init__(self,part):
		rex=re.compile("^\D+([0-9]*).*start= *([0-9]*).*size= *([0-9]*).*Id= *([0-9]*),? ?([a-zA-Z]*)?")
		self.npart=0
		self.start=0
		self.size=0
		self.Id=0
		self.bootable=''
		self.filesytem=''
		self.uuid=''

		parts = rex.search(part)
		self.npart,self.start,self.size,self.Id,self.bootable=parts.groups()

		if self.Id=='83':
			blkid = commands.getoutput("blkid %s" % part)	# on lit l'UUID et le système de fichier
			rex=re.compile("UUID=\"([^\"]*)\" TYPE=\"([^\"]*)\"")
			resultat=rex.search(blkid)
			self.uuid,self.filesytem=resultat.groups()
		else:
			self.uuid,self.filesytem='',''

	def __repr__(self):
		return 'Partition %s, start=%8s, size=%8s, Id=%2s, filesytem=%6s%s, UUID=%s' % (self.npart, self.start, self.size, self.Id, self.filesytem, ', bootable' if self.bootable else '          ', self.uuid)


class Disque:
	def __init__(self,disque=''):
		self.device=disque
		self.nbre_secteurs=0
		self.nbre_cylindres=0
		#self.taille_secteur=512
		self.nbre_sect_piste=0
		self.nbre_tetes=0
		self.liste_part=[]
		if disque != '':
			s=commands.getoutput("fdisk -l %s" % disque)
			for l in s.split('\n'):
				if l[:1].isdigit():
					rex=re.compile("^(\d+)\D+(\d+)\D+(\d+)\D+(\d+)")
					resultat=rex.search(l)
					self.nbre_tetes,self.nbre_sect_piste,self.nbre_cylindres,self.nbre_secteurs=resultat.groups()
					break

			sfdisk_output = commands.getoutput("sfdisk -d %s" % disque)	# on lit la table de partition du disque
			for line in sfdisk_output.split("\n"):			# on lit ligne par ligne
				if line.startswith("/"):					# si la ligne commence par un / on doit avoir un /dev/sd???
					self.liste_part.append(Partition(line))

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
	d=Disque(entree)
	print(d)

if __name__ == '__main__':
	main()
