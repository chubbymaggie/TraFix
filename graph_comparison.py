import re
import itertools

# overriden with Instruction class from compiler api
Instruction = None
def set_instruction_class(instruction_class):
	global Instruction
	Instruction = instruction_class

class VarInstruction:
	def __init__(self, var):
		self.defines = [var]
		self.code = 'Var '+var
		self.is_jump = False
		self.is_label = False
		self.targets = []
		self.is_branch = False
		self.is_condition = False
		self.uses = []
		self.is_symmetric = False

class Graph:
	def __init__(self, code):
		# remove garbage
		cleaned_code = ' __entry__ ; ' + re.sub('i32\*?', '', re.sub('i1', '', code)).replace('  ', ' ') + ' __exit__ ; '
		# parse code
		split_code = filter(lambda y: len(y) > 0, map(lambda x: x.strip(), cleaned_code.split(';')))
		self.instructions = dict(zip(range(len(split_code)), [Instruction(split_code[i], i) for i in range(len(split_code))]))
		# build cfg
		self.childs = dict([(i, []) for i in self.instructions])
		self.parents = dict([(i, []) for i in self.instructions])
		for i in self.instructions:
			if self.instructions[i].is_jump:
				for label in self.instructions[i].targets:
					index = filter(lambda j: label in self.instructions[j].labels, self.instructions)[0]
					self.childs[i].append(index)
					self.parents[index].append(i)
			else:
				if (i+1) in self.instructions:
					self.childs[i].append(i+1)
					self.parents[i+1].append(i)
		# clean cfg
		redundant = filter(lambda i: (self.instructions[i].is_jump and not self.instructions[i].is_branch) or self.instructions[i].is_label, self.instructions.keys())
		for j in redundant:
			childs = self.childs[j][:]
			parents = self.parents[j][:]
			for c in childs:
				self.parents[c].remove(j)
				self.parents[c] += parents
			for p in parents:
				self.childs[p].remove(j)
				self.childs[p] += childs
			del self.childs[j]
			del self.parents[j]
			del self.instructions[j]
		# create nodes for vars
		all_vars = set(filter(lambda v: v is not None and re.match('^X[0-9]+$', v), set.union(*map(lambda i: set(self.instructions[i].uses), self.instructions)).union(set.union(*map(lambda i: set(self.instructions[i].defines), self.instructions)))))
		for var in all_vars:
			self.instructions[var] = VarInstruction(var)
		entry_childs = self.childs[0][:]
		for e in entry_childs:
			self.parents[e].remove(0)
			self.parents[e] += list(all_vars)
		self.childs[0] = list(all_vars)
		for v in all_vars:
			self.parents[v] = [0]
			self.childs[v] = entry_childs
		# build ddg
		ddg_init = dict([(i, set()) for i in self.instructions])
		ddg_gen = dict(map(lambda i: (i, [(d, i) for d in self.instructions[i].defines]), self.instructions))
		ddg_kill = dict(map(lambda i: (i, itertools.product(self.instructions[i].defines, self.instructions.keys())), self.instructions))
		self.reaching_definitions = self.get_fixed_point(ddg_init, ddg_gen, ddg_kill, set.union, self.parents, self.childs)
		self.ddg = dict(map(lambda i: (i, map(lambda u: map(lambda y: y[1], filter(lambda x: x[0] == u, self.reaching_definitions[i])), self.instructions[i].uses)), self.instructions))
		self.rddg = dict([(i, set()) for i in self.instructions])
		for i in self.ddg.keys():
			for d in self.ddg[i]:
				for x in d:
					self.rddg[x].add(i)
		# compute dominators
		dom_init = dict([(i, set(self.instructions.keys())) for i in self.instructions])
		last_instruction = max(self.instructions.keys())
		dom_init[last_instruction] = set([last_instruction])
		dom_gen = dict([(i, [i]) for i in self.instructions])
		dom_kill = dict([(i, []) for i in self.instructions])
		self.post_dominators = self.get_fixed_point(dom_init, dom_gen, dom_kill, set.intersection, self.childs, self.parents)
		self.immediate_post_dominators = {}
		for i in self.post_dominators:
			post_dominators = self.post_dominators[i]
			immediates = filter(lambda d: all(map(lambda x: d not in self.post_dominators[x], post_dominators)), post_dominators)
			if len(immediates) > 0:
				self.immediate_post_dominators[i] = immediates[0]
			else:
				self.immediate_post_dominators[i] = None
		self.cdg = dict([(i, set()) for i in self.instructions])
		self.rcdg = dict([(i, set()) for i in self.instructions])
		branches = filter(lambda i: self.instructions[i].is_branch, self.instructions)
		for b in branches:
			immediate_post_dominator = self.immediate_post_dominators[b]
			reachable = set()
			new_reachable = set(filter(lambda c: c != immediate_post_dominator, self.childs[b]))
			while new_reachable != reachable:
				reachable = new_reachable
				new_reachable = set(filter(lambda c: c != immediate_post_dominator, reachable.union(*map(lambda x: self.childs[x], reachable))))
			for r in reachable:
				self.cdg[r].add(b)
				self.rcdg[b].add(r)


	def get_fixed_point(self, init, gen, kill, merge, predecessors, successors):
		in_states = init
		out_states = dict([(i, set()) for i in self.instructions])
		worklist = set(self.instructions.keys())
		while len(worklist) > 0:
			i = worklist.pop()
			if len(predecessors[i]) > 0:
				states = [out_states[p] for p in predecessors[i]]
				new_in_state = set(merge(*states))
			else:
				new_in_state = in_states[i]
			new_out_state = set(filter(lambda x: x not in kill[i], new_in_state)).union(gen[i])
			in_states[i] = new_in_state
			if new_out_state != out_states[i]:
				out_states[i] = new_out_state
				worklist.update(successors[i])
		return in_states

	def print_code(self):
		for i in sorted(self.instructions.keys()):
			print i, self.instructions[i].code


def compare_graphs(graph1, graph2):
	if len(graph1.instructions) != len(graph2.instructions):
		return False
	def is_matching_instructions(index1, index2):
		def is_number(x):
			return re.match('^\-?[0-9]+$', x) or re.match('^N[0-9]+$', x)
		inst1 = graph1.instructions[index1]
		inst2 = graph2.instructions[index2]
		# handle VarInsturctions
		if isinstance(inst1, VarInstruction):
			return isinstance(inst2, VarInstruction)
		if isinstance(inst2, VarInstruction):
			return False
		if inst1.op != inst2.op:
			return False
		if inst1.is_condition:
			if inst1.relation != inst2.relation:
				return False
		if len(inst1.uses) != len(inst2.uses):
			return False
		numeric_args1 = len(filter(is_number, inst1.uses))
		numeric_args2 = len(filter(is_number, inst2.uses))
		if numeric_args1 != numeric_args2:
			return False
		# # Following lines verify that all numeric values match.
		# # These lines are commented out to allow for "close" matches, where the only error is a numeric value.
		# # This relies on the assumption that substituting numbers to "fix" the code is relatively easy
		# if inst1.is_symmetric:
		# 	func = itertools.product
		# else:
		# 	func = zip
		# args = func(inst1.uses, inst2.uses)
		# matching_numeric_args = len(filter(lambda (x, y): is_number(x) and (x == y), args))
		# expected_numeric_args_pairs = 4 if ((numeric_args1 == 2) and (inst1.uses[0] == inst1.uses[1])) else numeric_args1
		# if expected_numeric_args_pairs != matching_numeric_args:
		# 	return False
		cdg1 = graph1.cdg[index1]
		cdg2 = graph2.cdg[index2]
		if len(cdg1) != len(cdg2):
			return False
		rcdg1 = graph1.rcdg[index1]
		rcdg2 = graph2.rcdg[index2]
		if len(rcdg1) != len(rcdg2):
			return False
		ddg1 = graph1.ddg[index1]
		ddg2 = graph2.ddg[index2]
		if len(ddg1) != len(ddg2):
			return False
		if sorted(map(len,ddg1)) != sorted(map(len,ddg2)):
			return False
		rddg1 = graph1.rddg[index1]
		rddg2 = graph2.rddg[index2]
		if len(rddg1) != len(rddg2):
			return False
		return True
	def generate_all_dependency_pairs(index1, index2):
		cdg1 = graph1.cdg[index1]
		cdg2 = graph2.cdg[index2]
		dependency_pairs = set(list(itertools.product(cdg1, cdg2)))
		rcdg1 = graph1.rcdg[index1]
		rcdg2 = graph2.rcdg[index2]
		dependency_pairs.update(set(list(itertools.product(rcdg1, rcdg2))))
		rddg1 = graph1.rddg[index1]
		rddg2 = graph2.rddg[index2]
		dependency_pairs.update(set(list(itertools.product(rddg1, rddg2))))
		ddg1 = graph1.ddg[index1]
		ddg2 = graph2.ddg[index2]
		if graph1.instructions[index1].is_symmetric:
			func = itertools.product
		else:
			func = zip
		for (x,y) in func(ddg1, ddg2):
			if len(x) == len(y):
				dependency_pairs.update(list(itertools.product(x, y)))
		return len(set(map(lambda x: x[0], dependency_pairs))), dependency_pairs
	all_pairs = itertools.product(graph1.instructions.keys(), graph2.instructions.keys())
	initial_pairs = filter(lambda (x, y): is_matching_instructions(x, y), all_pairs)
	pairs_dependencies = dict(map(lambda p: (p, generate_all_dependency_pairs(*p)), initial_pairs))
	changed = True
	while changed:
		changed = False
		for pair in pairs_dependencies.keys():
			dependencies = pairs_dependencies[pair][1]
			required_matches = pairs_dependencies[pair][0]
			dependencies = set(filter(lambda p: p in pairs_dependencies.keys(), dependencies))
			lhs_count = len(set(map(lambda x: x[0], dependencies)))
			rhs_count = len(set(map(lambda x: x[1], dependencies)))
			if (lhs_count >= required_matches) and (rhs_count >= required_matches):
				pairs_dependencies[pair] = (required_matches, dependencies)
			else:
				changed = True
				del pairs_dependencies[pair]
	if set(map(lambda x: x[0], pairs_dependencies.keys())) != set(graph1.instructions.keys()):
		return False
	if set(map(lambda x: x[1], pairs_dependencies.keys())) != set(graph2.instructions.keys()):
		return False
	return True


def compare_codes(code1, code2):
	return compare_graphs(Graph(code1), Graph(code2))


def load_external(f):
	if f.endswith('.py'):
		f = f[:-3]
	if f.endswith('.pyc'):
		f = f[:-4]
	return __import__(f)


if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser(description="Parse codes to PDG and compare graphs")
	parser.add_argument('compiler', type=str, help="file containing implementation of 'Instruction' class")
	args = parser.parse_args()
	set_instruction_class(load_external(args.compiler).Instruction)