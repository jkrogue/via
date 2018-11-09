import pydicom
import os
from os.path import join
import pickle

in_dir =input("Directory of dicoms: ")

files = [each for each in os.listdir(in_dir) if each.lower().endswith('dcm')]
fn_accessions = {}

for each in files:
	ds = pydicom.dcmread(join(in_dir,each))
	fn_accessions[each.split('.')[0]] = ds.AccessionNumber

pickle.dump(fn_accessions, open(input("Where to save pickle file: "),'wb'))
