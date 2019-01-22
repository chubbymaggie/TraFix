import os
import itertools
import csv
import postOrderUtil as po_util
import re
import logging
import json
from utils.colored_logger_with_timestamp import init_colorful_root_logger
import ConfigParser
import graph_comparison as gc
from abstract_numerals import *
import code_fixer as cf
import random
import compare_hl as hl_util
import pandas
import fix_hl_by_ll
conditions = ['==', '<', '>', '>=', '<=', '!=']
opers = ['-', '+', '*', '/', '%']
digits = map(lambda x: str(x), range(1,10))
numbers_pattern = '^(-|N)?\d+'
two_numbers_pattern = '( |^)' + numbers_pattern[1:] + ' ' + numbers_pattern[1:]
regexp = re.compile(two_numbers_pattern)
negative_num_sign = '@@'

def split_numbers(x):
	temp = re.match(numbers_pattern, x)
	if  (temp is not None and temp.group() == x):
		to_return = ''.join(map(lambda dig: ' ' + dig if dig.isdigit() else dig, x))
		if po_util.use_negative:
			to_return = to_return.replace('-', negative_num_sign)
		return to_return[1:] if to_return.startswith(' ') else to_return
	else:
		return x

def from_numbers_to_digits(line):
	while (regexp.search(line) is not None):
		to_search = regexp.search(line).group()
		add = 2 if to_search[0] == ' ' else 0
		line = line.replace(to_search, to_search.replace(' ', ' | ')[add:])
	return ' '.join(map(lambda x: split_numbers(x), line.split(' ')))

def parsePostOrder(po):
	return po_util.parse(po)


hl2ll = None
def load_compiler(f):
	global hl2ll
	if f.endswith('.py'):
		f = f[:-3]
	if f.endswith('.pyc'):
		f = f[:-4]
	hl2ll =  __import__(f)


class MockHL:
	def __init__(self, s):
		self._s = s
		self._vars = set()
		self._nums = set()
		for x in s.split(' '):
			if re.match('^N[0-9]+$',x):
				self._nums.add(x)
			elif re.match('^X[0-9]+$',x):
				self._vars.add(x)
	def __str__(self):
		return self._s
	def collect_vars(self):
		return self._vars
	def collect_nums(self):
		return self._nums

def compiler(hl):
	if not hl:
		return hl
	s = ''.join([y + ' ; ' for y in filter(lambda x: len(x) > 0, hl.split(';'))])
	return hl2ll.compiler(MockHL(s), check_success=True)


def apply_number_replacements_wrapper(ll, replacements, config):
	min_value = max(config.getint('Number', 'MinValue'), config.getint('Number', 'MinAbstractedValue'))
	max_value = min(config.getint('Number', 'MaxValue'), config.getint('Number', 'MaxAbstractedValue'))
	code = apply_number_replacements(ll, replacements).split(' ')
	for i in range(len(code)):
		if re.match('^N[0-9]+$', code[i]):
			code[i] = str(random.randint(min_value, max_value))
	return ' '.join(code)

def write_stats(id, hl, succeeded, csv_path, df):
	with open(csv_path, 'a') as f:
		csv.writer(f).writerow([id, str(succeeded)] + hl_util.calculate_hl_stats(hl, df))

def try_fix(cs, ll, lls, i, hl ,replacements, x, f, combine=False):
	new_hl = fix_hl_by_ll.fix_hl(cs[x], ll, lls[x], combine)
	if (new_hl is not None and compiler(new_hl) == ll):
		reason = 'my fix' + (' combined' if combine else '')
		csv.writer(f).writerow([str(i), 'true', reason])
		return (i, hl, ll, replacements, new_hl, 0)
	return None

def evaluateProg(i, hl, ll, out, replacements, config, failed_dataset=None, shallow_evaluation=False, f=None):
	# if hl in out:
	# 	return (i, hl, ll, replacements, hl, 0)  # success
	ll = po_util.combine_digits(ll)
	# if not (i == 287):
	# 	return (i, hl, ll, replacements, None, 1)
	if len(filter(lambda x: len(x) > 0, out)) == 0:
		if not shallow_evaluation:
			csv.writer(f).writerow([str(i), 'false', 'no translations'])
		return (i, hl, ll, replacements, None, 1)  # no translations
	out = map(lambda x: apply_number_replacements_wrapper(x, replacements, config), out)
	res = map(parsePostOrder, out)
	if all(map(lambda x: not x[0], res)):
		if not shallow_evaluation:
			csv.writer(f).writerow([str(i), 'false', 'unparsable'])
		return (i, hl, ll, replacements, None, 2)  # unparsable
	cs = map(lambda x: x[1].c().strip() if x[0] else '', res)
	# compare c code
	lls = map(lambda x: compiler(x), cs)
	if not any(lls):
		if not shallow_evaluation:
			csv.writer(f).writerow([str(i), 'false', 'does not compile'])
		return (i,hl, ll, replacements, None, 3)  # does not compile
	if shallow_evaluation:
		return (i,hl, ll, replacements, None, 0)
	lls = map(lambda l: re.sub('[ \t]+', ' ', l.strip()) if l is not None else '', lls)
	ll = apply_number_replacements_wrapper(ll, replacements, config)
	if ll in lls:
		csv.writer(f).writerow([str(i), 'true', 'direct success'])
		return (i, hl, ll, replacements, cs[lls.index(ll)], 0)  # success

	# print parsePostOrder(hl)[1].c()

	for x in range(lls.__len__()):
		answer = try_fix(cs, ll, lls, i, hl ,replacements, x, f, combine=False)
		if (answer is not None):
			return answer
		else:
			answer = try_fix(cs, ll, lls, i, hl, replacements, x, f, combine=True)
			if (answer is not None):
				return answer

	graph_comparisons = map(lambda l: gc.compare_codes(l, ll), lls)
	successful_comparisons = filter(lambda j: graph_comparisons[j][0], range(len(graph_comparisons)))
	if len(successful_comparisons) > 0:
		for j in successful_comparisons:
			needed_replacements = graph_comparisons[j][1]
			if all(map(lambda l: len(l) == 0, needed_replacements.values())):
				csv.writer(f).writerow([str(i), 'true', 'graph comperison'])
				return (i, hl, ll, replacements, cs[j], 0)  # success
			else:
				logging.debug('Attempting to fix code for input '+str(i))
				fixed_code = cf.fix_code(cs[j], ll, hl2ll, gc, lls[j], needed_replacements)
				if fixed_code is not None:
					logging.debug('Fix successful!')
					csv.writer(f).writerow([str(i), 'true', 'omers numbers'])
					return (i, hl, ll, replacements, fixed_code, 0)  # success
	if failed_dataset:
		with open(failed_dataset + '.corpus.hl', 'a') as fhl:
			with open(failed_dataset + '.corpus.ll', 'a') as fll:
				with open(failed_dataset + '.corpus.replacements', 'a') as freplacements:
					for j in range(len(out)):
						if len(out[j]) > 0 and len(lls[j]) > 0:
							(l, replaces) = generate_number_replacements(lls[j], config, hl2ll)
							h = apply_number_replacements(out[j], replaces)
							fhl.write(h + '\n')
							hl_util.writeMisMatches_hl(i, failed_dataset, h, apply_number_replacements(hl, replacements))
							fll.write(from_numbers_to_digits(l) + '\n')
							freplacements.write(json.dumps(reverse_mapping(replaces)) + '\n')

	csv.writer(f).writerow([str(i), 'false', 'did not fix'])
	return (i, hl, ll, replacements, None, 4)  # fail


def open_stats_csvs(failed_dataset):

	with open(failed_dataset + 'trees_stats.csv', 'w') as f:
		csv.writer(f).writerow(
			['sentence_id', 'is_successful', 'total_nodes_num', 'total_depth', 'largest_nodes_num', 'largest_depth', 'lines_num', 'mistake_line',
			  'mistake_depth', 'ifs_num', 'else_num', 'loops_num', 'nested_depth'])

	with open(failed_dataset + 'understand_fails.csv', 'w') as f:
		csv.writer(f).writerow(['sentence_id', 'origin_hl', 'models_h', 'mistakes', 'types', 'line_mistaken', 'depth_mistaken', 'worst_type'])


	with open(failed_dataset + 'success_fail_reasons.csv', 'w') as f:
		csv.writer(f).writerow(['sentence_id', 'did_succeeded', 'reason'])

	return failed_dataset + 'trees_stats.csv'


def create_and_save_sentences_from_failes(hl, out_file, writing_type):
	hls_list = []
	hl_list = hl.split(' ')
	hls_list.append(hl)
	for j in range(200):
		tmp = hl_list[:]
		for i in range(hl_list.__len__()):
			if hl_list[i] in conditions:
				tmp[i] = conditions[random.randint(0, conditions.__len__() - 1)]
			elif hl_list[i] in opers:
				tmp[i] = opers[random.randint(0, opers.__len__() - 1)]
			elif hl_list[i] in digits:
				tmp[i] = str(random.randint(1, 9))
			elif fix_hl_by_ll.is_var(hl_list[i]):
				tmp[i] = 'X' + str(random.randint(1, 14))
		hls_list.append(' '.join(tmp))

	lls_list = map(lambda x: from_numbers_to_digits(compiler(parsePostOrder(x)[1].c())), hls_list)
	with open(out_file + '.corpus.hl', writing_type) as fhl:
		with open(out_file + '.corpus.ll', writing_type) as fll:
			for i in range(hls_list.__len__()):
				fhl.write(hls_list[i] + '\n')
				fll.write(lls_list[i] + '\n')



def evaluate(fhl, fll, fout, freplacemetns, force, config, fs=None, ff=None, failed_dataset=None, shallow_evaluation=False):
	# hl_util.analize_mistakes(failed_dataset, 431)
	nsuccess = 0
	nfail = 0
	# if (True):
	# 	return (nsuccess, nfail)
	hls = [re.sub('[ \t]+', ' ', l.strip()) for l in fhl.readlines()]
	lls = [re.sub('[ \t]+', ' ', l.strip()) for l in fll.readlines()]
	outs = [map(lambda x: re.sub('[ \t]+', ' ', x.strip()), l.strip().split('|||')[0:2]) for l in fout.readlines()]
	replacements = [json.loads(l.strip()) for l in freplacemetns.readlines()]
	groups = {}
	for (n, g) in itertools.groupby(outs, lambda x: x[0]):
		groups[int(n)] = [x[1] for x in g]
	if not shallow_evaluation:
		csv_path = open_stats_csvs(failed_dataset)
	with open(failed_dataset + 'success_fail_reasons.csv', 'a') as f:
		results = map(
			lambda i: evaluateProg(i, hls[i], lls[i], groups[i] if i in groups.keys() else [], replacements[i], config, failed_dataset, shallow_evaluation, f), range(len(lls)))
	if not shallow_evaluation:
	    df = pandas.read_csv(failed_dataset + 'understand_fails.csv')
	for x in results:
		if x[5] == 0:
			if shallow_evaluation:
				continue
			if fs:
				fs.writerow([str(x[0]), x[1], x[2], json.dumps(x[3]), x[4]])
			write_stats(str(x[0]), x[1], True, csv_path, None)
			nsuccess += 1
		else:
			if shallow_evaluation:
				create_and_save_sentences_from_failes(x[1], failed_dataset, 'a' if nfail > 0 else 'w')
			else:
				if ff:
					ff.writerow([str(x[0]), x[1], x[2], json.dumps(x[3]), x[4]])
				write_stats(str(x[0]), x[1], False, csv_path, df[df['sentence_id'] == x[0]])
			nfail += 1
	if force:
		for f in os.listdir('.'):
			if f.startswith('tmp') and (f.endswith('.c') or f.endswith('ll')):
				os.remove(f)

	if shallow_evaluation:
		return (nsuccess, nfail)
	if nfail > 0:
		hl_util.analize_mistakes(failed_dataset, nfail)
	hl_util.analyze_trees_stats(failed_dataset)
	return (nsuccess, nfail)


def do_evaluation(f, k, force, config, fsuccess, ffail, failed_dataset, shallow_evaluation=False):
	with open(f + '.corpus.hl', 'r') as fhl:
		with open(f + '.corpus.ll', 'r') as fll:
			with open(f + '.corpus.' + str(k) + '.out', 'r') as fout:
				with open(f + '.corpus.replacements', 'r') as freplacements:
					if (shallow_evaluation):
						fs = None
						ff = None
					else:
						fs = csv.writer(fsuccess)
						ff = csv.writer(ffail)
					return evaluate(fhl, fll, fout, freplacements, force, config,
										fs=fs, ff=ff, failed_dataset=failed_dataset, shallow_evaluation=shallow_evaluation)


def main(f, k, compiler, force, config, failed_dataset=None, shallow_evaluation=False):
	logging.info('Compiler provided by '+args.compiler)
	load_compiler(compiler)
	gc.set_instruction_class(hl2ll.Instruction)
	if (shallow_evaluation):
		do_evaluation(f, k, force, config, None, None, failed_dataset, True)
		return
	with open(f + '.success.' + str(k) + '.csv', 'w') as fsuccess:
		with open(f + '.fail.' + str(k) + '.csv', 'w') as ffail:
			csv.writer(fsuccess).writerow(['line', 'hl', 'll', 'replacements', 'out'])
			csv.writer(ffail).writerow(['line', 'hl', 'll', 'replacements'])
			(nsuccess, nfail) = do_evaluation(f, k, force, config, fsuccess, ffail, failed_dataset)

	logging.info(str(nsuccess) + ' statements translated successfully')
	logging.info(str(nfail) + ' statements failed to translate')


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser(description="Evaluate dataset translations")
	parser.add_argument('dataset', type=str, help="dataset to translate")
	parser.add_argument('num_translations', type=int, help="number of translations in output for each input")
	parser.add_argument('compiler', type=str, help="file containing implementation of 'compiler' function")
	parser.add_argument('-f', '--force-cleanup', dest='force', help="force delete all tmp files when finished",
						action='count')
	parser.add_argument('-d', '--failed-dataset', dest='failed_dataset', type=str,
						help="dataset for which to write failed translations")
	parser.add_argument('-c', '--config', dest='c', type=str, default='configs/codenator.config',
						help="configuration file (default: \'%(default)s\')")
	parser.add_argument('-v', '--verbose', action='store_const', const=True, help='Be verbose')
	parser.add_argument('--debug', action='store_const', const=True, help='Enable debug prints')
	parser.add_argument('--shallow_evaluation', type=bool, default=False, help="do shallow evaluation (default: \'%(default)s\')")
	args = parser.parse_args()
	init_colorful_root_logger(logging.getLogger(''), vars(args))

	config = ConfigParser.ConfigParser()
	config.read(args.c)

	main(args.dataset, args.num_translations, args.compiler, args.force, config, args.failed_dataset, args.shallow_evaluation)
	if args.force:
		for f in os.listdir('.'):
			if f.startswith('tmp') and (f.endswith('.c') or f.endswith('ll')):
				os.remove(f)
