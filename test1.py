#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from copy import deepcopy

class A:
	def __init__(self,val):
		self.a=val
		self.b=2+val

	def __repr__(self):
		return('a={}, b={}\n'.format(self.a,self.b))

class B():
	def __init__(self,val):
		self.l=[]
		self.l.append(A(val+5))
		self.l.append(A(val+10))

	def __repr__(self):
		s=''
		for a in self.l:
			s=s+str(a)
		return s

b=B(0)
b1=B(10)
b1=deepcopy(b)
b1.l[0].a=123
print(b)
print(b1)