#!/usr/bin/env python
import sys
import string
import subprocess
import os
import random
import string
from Bio import SeqIO
from Bio.Seq import Seq
from datetime import datetime
from optparse import OptionParser

__author__ = "Jorge Ruiz-Orera"
__contributor__="..."
__copyright__ = ""
__credits__ = []
__license__ = ""
__version__="1.0.0"
__maintainer__ = "Jorge Ruiz-Orera"
__email__ = "jorruior@gmail.com"


### FUNCTIONS
class trans_object:
	def __init__(self, chrm, gene, strand, start, end, biotype):
		self.chrm = chrm
		self.gene = gene
		self.strand = strand
		self.start = start
		self.end = end
		self.biotype = biotype

def lcs(S,T):
	m = len(S)
	n = len(T)
	counter = [[0]*(n+1) for x in range(m+1)]
	longest = 0
	lcs_set = set()
	for i in range(m):
		for j in range(n):
			if S[i] == T[j]:
				c = counter[i][j] + 1
				counter[i+1][j+1] = c
				if c > longest:
					lcs_set = set()
					longest = c
					lcs_set.add(S[i-c+1:i+1])
				elif c == longest:
					lcs_set.add(S[i-c+1:i+1])
	return lcs_set

def get_index_positions(list_of_elems, element):
	''' Returns the indexes of all occurrences of give element in
	the list- listOfElements '''
	index_pos_list = []
	index_pos = 0
	while True:
		try:
			# Search for item in list from indexPos to the end of list
			index_pos = list_of_elems.index(element, index_pos)
			# Add the index position in list
			index_pos_list.append(index_pos)
			index_pos += 1
		except ValueError as e:
			break
	return index_pos_list

def parse_gtf(gtf,field):
	'''Read a gtf and create a dict with sorted transcript coordinates, chrm, strand, and gene'''
	trans = {}
	for line in open(gtf):
		if not "\t" + field + "\t" in line:
			continue
		t_name = line.split('transcript_id "')[1].split('"')[0]
		g_name = line.split('gene_id "')[1].split('"')[0]

		if 'gene_biotype' in line:
			biot = line.split('gene_biotype "')[1].split('"')[0]
		else:
			biot = "unknown"
		
		trans.setdefault(t_name,trans_object(line.split("\t")[0],g_name,line.split("\t")[6],[],[],biot))
		trans[t_name].start.append(int(line.split("\t")[3]))
		trans[t_name].end.append(int(line.split("\t")[4]))

	[trans[x].start.sort() for x in trans]
	[trans[x].end.sort() for x in trans]	

	return trans


def load_fasta(orfs_fa_file,transcriptome_fa_file):
	orfs_fa = SeqIO.index(orfs_fa_file, "fasta")
	transcriptome_fa = SeqIO.index(transcriptome_fa_file, "fasta")
	return orfs_fa,transcriptome_fa


def read_support(t_support): #Modified from general script: Order transcripts by expression
	supp = {}
	for line in open(t_support):
		if not "\ttranscript\t" in line:
			continue
		t = line.split('transcript_id "')[1].split('"')[0]
		try:
			f = float(line.split('FPKM "')[1].split('"')[0])
		except:
			f = 1
		supp[t] = f

	return supp

def make_bed(prot,trans,gtf,len_cutoff,max_len_cutoff,calculate_coordinates,orfs_bed_file,out_name,mult,genomic,fgenomic):
	print("Matching ORF to transcripts, it can take a while... STEP 1 - " + str(datetime.now()))
	nomap = open(out_name + "_unmapped","w+")
	altmap = open(out_name + "_altmapped","w+")
	lines = []
	multiple = []
	if fgenomic == "none":
		trans_sequences = []
		seqs = {}
		for t in trans:
			if not t in gtf:
				continue
			trans_sequences.append(str(trans[t].seq.translate(cds = False)))	
			trans_sequences.append(str(trans[t].seq[1:].translate(cds = False)))	
			trans_sequences.append(str(trans[t].seq[2:].translate(cds = False)))
			seqs[str(trans[t].seq.translate(cds = False))] = t
			seqs[str(trans[t].seq[1:].translate(cds = False))] = t
			seqs[str(trans[t].seq[2:].translate(cds = False))] = t
	if genomic != "none":
		fgenomic = genomic
	if fgenomic != "none":
		gen_bed = {}
		for line in open(fgenomic):
			name = line.split("\t")[3] + "--" + line.split("\t")[4]
			if not name in gen_bed:
				gen_bed[name] = [line.split("\t")[0],int(line.split("\t")[1])-10,int(line.split("\t")[2])+10]
			if int(line.split("\t")[1])-10 < gen_bed[name][1]:
				gen_bed[name][1] = int(line.split("\t")[1])-10
			if int(line.split("\t")[2])+10 > gen_bed[name][2]:
				gen_bed[name][2] = int(line.split("\t")[2])+10
	n2 = 0
	for p in prot:
		if n2 % 5000 == 0:
			print(str(n2) + " out of " + str(len(prot)) + " ORFs assigned to a transcript - " + str(datetime.now()))
		n2 += 1
		disc = 0
		orf_seq = str(prot[p].seq).replace("*","") + "*"
		if len(orf_seq) < (len_cutoff + 1):
			nomap.write(p + "\tnanoORF\t" + orf_seq + "\n")
			continue
		elif len(orf_seq) > max_len_cutoff:
			nomap.write(p + "\tlongORF\t" + orf_seq + "\n")
			continue	
		elif (calculate_coordinates == "ATG") and (orf_seq[0] != "M"):
			nomap.write(p + "\tNTG\t" + orf_seq + "\n")
			continue
		elif (calculate_coordinates == "NTG") and (orf_seq[0] == "M"):
			nomap.write(p + "\tATG\t" + orf_seq + "\n")
			continue
		det = 0
		if fgenomic != "none":
			trans_sequences2 = []
			seqs2 = {}
			if not p in gen_bed:
				if genomic == "none":
					nomap.write(p + "\tunmapped\t" + orf_seq + "\n")
					continue
			for t in trans:
				if not t in gtf:
					if genomic == "none":
						nomap.write(p + "\tunmapped\t" + orf_seq + "\n")
						continue
				elif p in gen_bed:
					if gtf[t].chrm != gen_bed[p][0]:
						if genomic == "none":
							nomap.write(p + "\tunmapped\t" + orf_seq + "\n")
							continue
					if (gtf[t].start[0] >= gen_bed[p][1] and gtf[t].start[0] <= gen_bed[p][2]) or (gtf[t].end[-1] >= gen_bed[p][1] and gtf[t].end[-1] <= gen_bed[p][2]):
						det = 1
						trans_sequences2.append(str(trans[t].seq.translate(cds = False)))
						trans_sequences2.append(str(trans[t].seq[1:].translate(cds = False)))
						trans_sequences2.append(str(trans[t].seq[2:].translate(cds = False)))
						seqs2[str(trans[t].seq.translate(cds = False))] = t
						seqs2[str(trans[t].seq[1:].translate(cds = False))] = t
						seqs2[str(trans[t].seq[2:].translate(cds = False))] = t
			if len(trans_sequences2) == 0:
				if genomic == "none":
					nomap.write(p + "\tunmapped\t" + orf_seq + "\n")
					continue
		if det == 0:
			res = list(filter(lambda x: orf_seq in x, trans_sequences))
		else:
			res = list(filter(lambda x: orf_seq in x, trans_sequences2))
		done_coords = []
		if len(res) > 0:
			for r in res:
				if det == 0:
					t = seqs[r]
				else:
					t = seqs2[r]

				l = len(str(trans[t].seq))
				f1 = str(trans[t].seq.translate(cds = False)).find(str(orf_seq))
				f2 = str(trans[t].seq[1:].translate(cds = False)).find(str(orf_seq))
				f3 = str(trans[t].seq[2:].translate(cds = False)).find(str(orf_seq))
				fi = [f1,f2,f3].index(max([f1,f2,f3]))
				f = max(f1,f2,f3)*3 + fi
				if f < 0:
					continue
				o = [f+1,f+(len(orf_seq)*3)]		

				if gtf[t].strand == "-":
					o[0],o[1] = o[1],o[0]
					o[0] = l - o[0]	+ 1
					o[1] = l - o[1] + 1

				cumu = 0
				op = 0
				orf_coords = ([],[],gtf[t].chrm,gtf[t].strand)
				for n in range(len(gtf[t].start)):
					if op == 0:
						if (cumu + (gtf[t].end[n] - gtf[t].start[n] + 1) ) >= o[0]:
							orf_coords[0].append(gtf[t].start[n] + o[0] - cumu - 1)
							op = 1
					elif op == 1:
						orf_coords[0].append(gtf[t].start[n])

					if op == 1:
						if (cumu + (gtf[t].end[n] - gtf[t].start[n] + 1) ) >= o[1]:
							orf_coords[1].append(gtf[t].start[n] + o[1] - cumu - 1)
							op = -1
						else:
							orf_coords[1].append(gtf[t].end[n])

					cumu = cumu + (gtf[t].end[n] - gtf[t].start[n] + 1)

				if len(done_coords) > 0: #Some ORFs can map to multiple genomic regions
					if (orf_coords[0][0] != done_coords[0][0]) and (orf_coords[1][-1] != done_coords[1][-1]):
						altmap.write(p + "\taltmap\t" + orf_seq + "\t" + gtf[t].chrm + "\t" + gtf[t].strand + "\t" + ";".join(map(str,orf_coords[0])) + "\t" + ";".join(map(str,orf_coords[1])) + "\t" + done_coords[2] + "\t" + done_coords[3] + "\t" + ";".join(map(str,done_coords[0])) + "\t" + ";".join(map(str,done_coords[1])) + "\n")
						multiple.append(p)
						break
					for n,coord in enumerate(orf_coords[0]):						
						if (orf_coords[0][n] != done_coords[0][n]) or (orf_coords[1][n] != done_coords[1][n]):
							altmap.write(p + "\taltexons\t" + orf_seq + "\t" + gtf[t].chrm + "\t" + gtf[t].strand + "\t" + ";".join(map(str,orf_coords[0])) + "\t" + ";".join(map(str,orf_coords[1])) + "\t" + done_coords[2] + "\t" + done_coords[3] + "\t" + ";".join(map(str,done_coords[0])) + "\t" + ";".join(map(str,done_coords[1])) + "\n")
							multiple.append(p)
							break
				else:
					for n,coord in enumerate(orf_coords[0]):
						lines.append(gtf[t].chrm + "\t" + str(orf_coords[0][n]) + "\t" + str(orf_coords[1][n]) + "\t" + p.split("--")[0] + "\t" + p.split("--")[1] + "\t" + gtf[t].strand + "\n")
					done_coords = orf_coords
		else:
			nomap.write(p + "\tunmapped\t" + orf_seq + "\n")
	bedout = open(orfs_bed_file,"w+")
	done = []
	for line in lines:
		if (mult == "no") and (line.split("\t")[3] + "--" + line.split("\t")[4] in multiple):
			if not line.split("\t")[3] + "--" + line.split("\t")[4] in done:
				nomap.write(line.split("\t")[3] + "--" + line.split("\t")[4] + "\tmultiple_coords\t" +  str(prot[line.split("\t")[3] + "--" + line.split("\t")[4]].seq).replace("*","") + "*" + "\n")
			done.append(line.split("\t")[3] + "--" + line.split("\t")[4])
		else:
			bedout.write(line)
	bedout.close()
	nomap.close()
	altmap.close()


def insersect_orf_gtf(orfs_bed_file,transcriptome_gtf_file,folder):
	'''Intersect a set of exonic ORFs against a transcriptome and output all partial/global overlaps'''
	print("Intersecting ORFs with transcriptome")
	overlaps ={}
	overlaps_cds = {}
	other_overlaps = {}
	total_studies = []
	seed = ''.join(random.choice(string.ascii_letters) for i in range(10))
	out = open('tmp/' + seed + 'orfs_to_gtf.ov','w+')
	subprocess.call(['intersectBed', '-a', orfs_bed_file, '-b', transcriptome_gtf_file, '-wo'], stdout=out)
	out.close()
	for line in open('tmp/' + seed + 'orfs_to_gtf.ov'):
		if line.split("\t")[5] != line.split("\t")[12]:
			continue
		if "\ttranscript\t" in line:
			name = line.split("\t")[3] + "--" + line.split("\t")[4]
			if not line.split("\t")[4] in total_studies:
				total_studies.append(line.split("\t")[4])
			gene = line.split('gene_id "')[1].split('"')[0]
			gene_name = line.split('gene_name "')[1].split('"')[0]
			trans = line.split('transcript_id "')[1].split('"')[0]
			g_biotype = line.split('gene_biotype "')[1].split('"')[0]
			t_biotype = line.split('transcript_biotype "')[1].split('"')[0]
			overlaps.setdefault(name,[])
			other_overlaps.setdefault(name,["0","0","0"])
			if not [trans,gene,t_biotype,g_biotype,gene_name] in overlaps[name]:
				overlaps[name].append([trans,gene,t_biotype,g_biotype,gene_name])
	for line in open(transcriptome_gtf_file):
		if "\tCDS\t" in line:
			trans = line.split('transcript_id "')[1].split('"')[0]
			prot = line.split('protein_id "')[1].split('"')[0]
			overlaps_cds[trans] = prot
	total_studies.sort()
	return overlaps,overlaps_cds,other_overlaps,total_studies,seed


def pseudo_or_cds_ov(orfs_bed_file,transcriptome_gtf_file,other_overlaps,folder,seed):
	'''Intersect with pseudogenes or CDS in any strand and any frame'''
	print("Intersecting ORFs with transcriptome")
	for line in open('tmp/' + seed + 'orfs_to_gtf.ov'):
		if ("\texon\t" in line) and ("pseudogene" in line) and (line.split("\t")[5] == line.split("\t")[12]):
			name = line.split("\t")[3] + "--" + line.split("\t")[4]
			other_overlaps.setdefault(name,["0","0","0"])
			other_overlaps[name][0] = "1" 
		if "\tCDS\t" in line:
			name = line.split("\t")[3] + "--" + line.split("\t")[4]
			if ("\t+\t" in line) and ("\t-\t" in line):
				other_overlaps.setdefault(name,["0","0","0"])
				other_overlaps[name][2] = "1" 
			else:
				other_overlaps.setdefault(name,["0","0","0"])
				other_overlaps[name][1] = "1" 
	return other_overlaps


def orf_tags(overlaps,overlaps_cds,orfs_fa,transcriptome_fa,gtf,len_cutoff,max_len_cutoff,folder,seed):
	'''Check the relative overlap of the ORFs in transcript(s)'''
	print("Checking for ORF overlaps in transcriptome")
	atgstop = open('tmp/' + seed + 'atg_to_stop.bed',"w+")
	candidates = {}
	trans_orfs = {}
	coord_psites = {}
	for orf in overlaps:
		cat = "sORF"
		cat2 = "non-coding"
		try:
			orf_seq = str(orfs_fa[orf].seq)
		except:
			continue
		try:
			cat = str(orfs_fa[orf].description).split()[-1].split("--")[0]
		except:
			pass
		if len(orf_seq.replace("*","")) < len_cutoff:
			continue
		elif len(orf_seq.replace("*","")) > max_len_cutoff:
			continue
		co = 0
		for trans in overlaps[orf]:
			if not trans[0] in transcriptome_fa:
				continue	
			gene = trans[1]
			genename = trans[4]
			f1 = str(transcriptome_fa[trans[0]].seq.translate(cds = False)).find(str(orf_seq))
			f2 = str(transcriptome_fa[trans[0]].seq[1:].translate(cds = False)).find(str(orf_seq))
			f3 = str(transcriptome_fa[trans[0]].seq[2:].translate(cds = False)).find(str(orf_seq))
			fi = [f1,f2,f3].index(max([f1,f2,f3]))
			f = max(f1,f2,f3)*3 + fi
			if f < 0:
				continue
			if trans[3] == "protein_coding": #Gene biotype
				cat2 = "protein_coding"

			candidates.setdefault(orf,[])
			candidates[orf].append([trans[0],gene,genename,cat,cat2,fi,f,orf_seq])

			trans_orfs.setdefault(trans[0],[])
			trans_orfs[trans[0]].append([orf,fi,f,orf_seq])

			#Write ATG and STOP
			if co == 0:
				co = 1
				all_coords = [[],[],gtf[trans[0]].chrm,gtf[trans[0]].strand,[],[]]
				if gtf[trans[0]].strand == "-":
					rev = len(str(transcriptome_fa[trans[0]].seq)) - (f+(len(orf_seq)*3))
					f = rev
				tt = 0
				tt2 = -1
				ranges = []
				for n,exon in enumerate(gtf[trans[0]].start):
					for j in range(gtf[trans[0]].start[n],gtf[trans[0]].end[n]+1):
						if (tt == f):
							tt2 = 0
							atgstop.write(gtf[trans[0]].chrm + "\t" + str(j) + "\t" + str(j) + "\t" + orf + "\tboundaries\t" + gtf[trans[0]].strand + "\n")
						elif (tt == f+(len(orf_seq)*3)-1):
							tt2 = -1
							atgstop.write(gtf[trans[0]].chrm + "\t" + str(j) + "\t" + str(j) + "\t" + orf + "\tboundaries\t" + gtf[trans[0]].strand + "\n")
						if (tt2 != -1):
							if ((tt2 % 3 == 2 and gtf[trans[0]].strand == "+") or (tt2 % 3 == 0 and gtf[trans[0]].strand == "-")):
								coord_psites.setdefault(orf,[])
								coord_psites[orf].append(j)
							tt2 += 1
						tt += 1	

	atgstop.close()
	return candidates,trans_orfs,coord_psites


def exclude_variants(orfs_fa,trans_orfs,col_thr,candidates,method,coord_psites,folder,seed):
	'''Cluster ORFs'''
	print("Collapsing shorter variants")
	out = open('tmp/' + seed + 'atg_to_stop.ov','w+')
	subprocess.call(['intersectBed', '-s','-a', 'tmp/' + seed + 'atg_to_stop.bed', '-b', 'tmp/' + seed + 'atg_to_stop.bed', '-wo'], stdout=out)
	out.close()
	ovs = {}
	ovs_psites = {}
	for line in open('tmp/' + seed + 'atg_to_stop.ov'):
		if "boundaries" in line:
			ovs.setdefault(line.split("\t")[3],[])
			ovs.setdefault(line.split("\t")[9],[])
			if not line.split("\t")[9] in ovs[line.split("\t")[3]]:
				ovs[line.split("\t")[3]].append(line.split("\t")[9])
			if not line.split("\t")[3] in ovs[line.split("\t")[9]]:
				ovs[line.split("\t")[9]].append(line.split("\t")[3])

	exc = []
	variants = {}
	variants_names = {}
	datasets = {}
	for trans in trans_orfs:
		for orf in trans_orfs[trans]:
			for orf2_name in ovs[orf[0]]:
				if (orf[0] in exc):
				 	continue
				# if (orf[0] in exc) or (orf2_name in exc):
				# 	continue
				variants.setdefault(orf[0],[])
				variants_names.setdefault(orf[0],[])
				variants_names[orf[0]].append(orf[0])
				datasets.setdefault(orf[0],[])
				datasets[orf[0]].append(orf[0].split("--")[1])
				orf2 = candidates[orf2_name]
				# if (orf[0].split("--")[0] == orf2_name.split("--")[0]):
				# 	if not orf2[0][7] in variants[orf[0]]:
				# 		if orf2[0][7] != orf[3]:
				# 			variants[orf[0]].append(orf2[0][7])
				# 	variants_names[orf[0]].append(orf2_name)					
				# 	datasets[orf[0]].append(orf2_name.split("--")[1])
				# 	exc.append(orf2_name)	
				if (orf[0] != orf2_name):
					if str(orfs_fa[orf[0]].seq) == str(orfs_fa[orf2_name].seq):
						if not orf2[0][7] in variants[orf[0]]:
							if orf2[0][7] != orf[3]:
								variants[orf[0]].append(orf2[0][7])
						variants_names[orf[0]].append(orf2_name)					
						datasets[orf[0]].append(orf2_name.split("--")[1])						
						exc.append(orf2_name)
						continue
					if method == "longest_string":
						match = len(str(list(lcs(orf[3], orf2[0][7]))[0]))
						if match > 0:
							if (len(orf[3]) >= len(orf2[0][7])) and (match >= (float(len(orf2[0][7]))*col_thr)): #Remove shorter variant if intersect more than thr%
								if not orf2[0][7] in variants[orf[0]]:
									if orf2[0][7] != orf[3]:
										variants[orf[0]].append(orf2[0][7])
								variants_names[orf[0]].append(orf2_name)
								datasets[orf[0]].append(orf2_name.split("--")[1])
								exc.append(orf2_name)
					elif method == "psite_overlap":
						match = len([value for value in list(set(coord_psites[orf[0]])) if value in list(set(coord_psites[orf2_name]))])
						if match > 0:
							if (len(orf[3]) >= len(orf2[0][7])) and (match*3 >= (float(len(orf2[0][7]))*col_thr)): #Remove shorter variant if intersect more than thr%
								if not orf2[0][7] in variants[orf[0]]:
									if orf2[0][7] != orf[3]:
										variants[orf[0]].append(orf2[0][7])
								variants_names[orf[0]].append(orf2_name)					
								datasets[orf[0]].append(orf2_name.split("--")[1])
								exc.append(orf2_name)	

	#for var in variants:
	#	print(var + "\t" + str(variants[var]))					

	return exc,variants,variants_names,datasets


def write_output(orfs_fa_file,orfs_bed_file,candidates,exc,variants,variants_names,datasets,supp,gtf,transcriptome_fa,len_cutoff,max_len_cutoff,col_thr,total_studies,other_overlaps,folder,out_name,method,seed,genomic,fgenomic,cds_cases):
	'''Select main transcript and write output'''
	print("Writing output")
	#Check Riboseq ORF annotations
	done = []
	riboseq_orfs = {}
	for line in open("list_riboseq_orfs.txt"):
		if "\tCDS\t" in line or "\tNMD\t" in line:
			continue
		seq = line.split("\t")[3]
		riboseq_orfs[seq] = line.split("\t")[0]
		if len(line.split("\t")[4].rstrip("\n")) > 0:
			if ";" in line.split("\t")[4].rstrip("\n"):
				for s in line.split("\t")[4].rstrip("\n"):
					riboseq_orfs[s] = line.split("\t")[0] + "_var"
			else:
				riboseq_orfs[line.split("\t")[4].rstrip("\n")] = line.split("\t")[0] + "_var"

	outs = []
	outs2 = []
	all_ids = {}
	out = open(out_name + ".orfs.out","w+")
	out.write("orf_id\tphaseI_id\tchrm\tstarts\tends\tstrand\ttrans\tgene\tgene_name\torf_biotype\tgene_biotype\tpep\torf_length\tn_datasets\t")
	out.write("\t".join(total_studies))
	out.write("\tpseudogene_ov\tCDS_ov\tCDS_as_ov\tall_trans\tall_genes\tall_gene_names\tn_variants\tseq_variants\tall_orf_names\n")
	out3 = open(out_name + ".orfs.bed","w+")
	out3b = open(out_name + ".orfs.gtf","w+")
	out4 = open(out_name + ".orfs.fa","w+")
	outf = open(out_name + ".orfs.frames.bed","w+")
	outf2 = open(out_name + ".orfs.allframes.bed","w+")
	outlogs = open(out_name + ".logs","w+")
	outlogs.write("input fasta: " + orfs_fa_file + "\ninput bed: " + orfs_bed_file + "\nannotation folder:" + folder + "\nmin_length_cutoff: " + str(len_cutoff) + "\nmax_length_cutoff: " + str(max_len_cutoff).replace("999999999999","none") + "\ncollapse_method: " + str(method) + "\ncollapse_cutoff: " + str(col_thr) + "\ngenomic_bed : " + str(genomic) + "\nforced_genomic_bed: " + str(fgenomic) + "\ntotal_studies: " + ";".join(total_studies) + "\n\n")
	for orf in candidates:
		if orf in exc:
			continue
		all_t = []
		all_g = []
		all_gn = []
		ncod = []
		cod = []
		for cand in candidates[orf]:
			all_t.append(cand[0])
			all_g.append(cand[1])
			all_gn.append(cand[2])
			if cand[3] == "lncRNA":
				ncod.append(cand[0])	
			else:
				cod.append(cand[0])	

		all_t = list(set(all_t))
		all_g = list(set(all_g))
		all_gn = list(set(all_gn))	
		ncod = list(set(ncod))	
		cod = list(set(cod))

		all_t.sort() #Sort list, in case of several transcripts with equal evidence, the first one is selected

		max_t = ["none",0]
		for trans in all_t:
			if trans in supp:
				if supp[trans] >= max_t[1]:
					max_t = [trans,supp[trans]]
			elif max_t[0] == "none":
				max_t = [trans,0]

		t = max_t[0]

		for trans in candidates[orf]:
			if trans[0] == t:

				#Annotate gene as pseudogene
				if other_overlaps[orf][0] == "1":
					trans[4] = "pseudogene"
				#Vector 0/1 studies
				stu = []
				for study in total_studies:
					if study in datasets[orf]:
						stu.append("1")
					else:
						stu.append("0")

				#Compare with original Riboseq annotation
				if trans[7] in riboseq_orfs:
					done.append(trans[7])
					id2 = riboseq_orfs[trans[7]]
				else:
					id2 = "unknown"

				#Write coordinate output
				all_coords = [[],[],gtf[t].chrm,gtf[t].strand,[],[]]
				if gtf[t].strand == "-":
					rev = len(str(transcriptome_fa[trans[0]].seq)) - (trans[6]+(len(trans[7])*3))
					trans[6] = rev

				tt = 0
				ranges = []
				for n,exon in enumerate(gtf[t].start):
					for j in range(gtf[t].start[n],gtf[t].end[n]+1):
						if (tt >= trans[6]) and (tt < trans[6]+(len(trans[7])*3)):
							ranges.append(j)		
						tt += 1					
				
				if not t in supp:
					supp[t] = 0
				n2 = 0
				n3 =1
				for n,r in enumerate(ranges):
					if n2 == 0:
						start = ranges[n]
					elif ranges[n] - ranges[n-1] != 1:
						end = ranges[n-1]
						all_coords[4].append(gtf[t].chrm + "\t" + str(start) + "\t" + str(end) + "\tP1_ID\t" + trans[1] + "\t" + gtf[t].strand + "\n")
						#all_coords[5].append(gtf[t].chrm + "\tphaseI\tCDS\t" + str(start) + "\t" + str(end) + "\t.\t" + gtf[t].strand + "\t.\tgene_id \"" + trans[1] + "\"; gene_name \"" + trans[2] + "--" + trans[3] + "\"; transcript_id \"P1_ID\";\n")
						all_coords[5].append(gtf[t].chrm + "\tphaseI\tCDS\t" + str(start) + "\t" + str(end) + "\t.\t" + gtf[t].strand + "\t.\tgene_id \"" + trans[1] + "\"; gene_name \"" + trans[2] + "\"; gene_biotype \"" + trans[4] + "\"; transcript_id \"" + t + "\"; orf_id \"P1_ID\"; orf_biotype \"" + trans[3] + "\"; phaseI_id \"" + id2 + "\"; FPKM \"" + str(supp[t]) + "\"; exon_number \"" + str(n3) + "\";\n")
						all_coords[0].append(str(start))
						all_coords[1].append(str(end))
						start = ranges[n]
						n3 += 1
					n2 += 1	

				all_coords[4].append(gtf[t].chrm + "\t" + str(start) + "\t" + str(ranges[n]) + "\tP1_ID\t" + trans[1] + "\t" + gtf[t].strand + "\n")	
				#all_coords[5].append(gtf[t].chrm + "\tphaseI\tCDS\t" + str(start) + "\t" + str(ranges[n]) + "\t.\t" + gtf[t].strand + "\t.\tgene_id \"" + trans[1] + "\"; gene_name \"" + trans[2] + "--" + trans[3] + "\"; transcript_id \"P1_ID\";\n")
				all_coords[5].append(gtf[t].chrm + "\tphaseI\tCDS\t" + str(start) + "\t" + str(ranges[n]) + "\t.\t" + gtf[t].strand + "\t.\tgene_id \"" + trans[1] + "\"; gene_name \"" + trans[2] + "\"; gene_biotype \"" + trans[4] + "\"; transcript_id \"" + t + "\"; orf_id \"P1_ID\"; orf_biotype \"" + trans[3] + "\"; phaseI_id \"" + id2 + "\"; FPKM \"" + str(supp[t]) + "\"; exon_number \"" + str(n3) + "\";\n")

				all_coords[0].append(str(start))
				all_coords[1].append(str(ranges[n]))

				#Convert variants to second name
				new_variant_names = list(set(variants_names[orf]))

				#In-frame overlaps with annotated CDSs
				id = "P1_" + all_coords[2] + ":" + all_coords[0][0] + "_" + all_coords[1][-1] + ":" + all_coords[3] + ":" + str(len(all_coords[1])) + ":" + str(len(trans[7])*3)
				a = 0
				while id in all_ids:
					if trans[7] == all_ids[id]:
						a = 1
					id = id + "__v"
				if a == 1:
					continue
				all_ids[id] = trans[7]
				phase = -1
				for line in all_coords[4]:
					out3.write(line.replace("P1_ID",id))
					#Frames
					if phase == -1:
						if line.split("\t")[5].rstrip("\n") == "+":
							phase = 0
						elif line.split("\t")[5].rstrip("\n") == "-":
							phase = 2
					for coord in range(int(line.split("\t")[1]),int(line.split("\t")[2])+1):
						if line.split("\t")[5].rstrip("\n") == "+":
							outf2.write(line.split("\t")[0] + "\t" + str(coord) + "\t" + str(coord) + "\t" + id + "\tp" + str(phase % 3) + "\t" + line.split("\t")[5].rstrip("\n") + "\n")
						else:
							outf2.write(line.split("\t")[0] + "\t" + str(coord) + "\t" + str(coord) + "\t" + id + "\tp" + str((phase+1) % 3) + "\t" + line.split("\t")[5].rstrip("\n") + "\n")
						if phase % 3 == 2:							
							outf.write(line.split("\t")[0] + "\t" + str(coord) + "\t" + str(coord) + "\t" + id + "\t" + str(phase) + "\t" + line.split("\t")[5].rstrip("\n") + "\n")
						phase += 1
				
				for line in all_coords[5]:
					outs2.append(line.replace("P1_ID",id))

				outs.append(id + "\t" + id2 + "\t" + all_coords[2] + "\t" + ";".join(all_coords[0]) + "\t" + ";".join(all_coords[1]) + "\t" + all_coords[3] + "\t" + trans[0] + "\t" + trans[1] + "\t" + trans[2] + "\t" + trans[3] + "\t" + trans[4] + "\t" + trans[7] + "\t" + str(len(trans[7])*3) + "\t" + str(len(list(set(datasets[orf])))) + "\t" + "\t".join(stu) + "\t" + \
				"\t".join(other_overlaps[orf]) + "\t" + ";".join(all_t) + "\t" + ";".join(all_g) + "\t" + ";".join(all_gn) + "\t" + str(len(variants[orf])) + "\t" + ";".join(variants[orf]) + "\t" + ";".join(new_variant_names) + "\n")

				#Write FASTA
				out4.write(">" + id + "\n" + trans[7] + "\n")	


	outf.close()
	outf2.close()

	cdsinf = []
	for line in outs:
		out.write(line)
	for line in outs2:
		out3b.write(line)
		
	for orf in riboseq_orfs:
		if not orf in done:
			if not "_var" in riboseq_orfs[orf]:
				outlogs.write(riboseq_orfs[orf] + " not mapped to this version\t" + orf + "\n")
	out.close()
	out3.close()
	out3b.close()
	out4.close()
	outlogs.close()

	# for f in os.listdir('tmp/'):
	# 	if seed in f:
	# 		os.remove(os.path.join(folder + '/tmp/', f))

