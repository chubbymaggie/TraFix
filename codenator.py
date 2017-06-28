import random
import string
import os
import ConfigParser
import ast

config = ConfigParser.ConfigParser()
config.read('codenator.config')

class Expr:
    @staticmethod
    def isValid():
        return True
    def collectVarNames(self):
        return set()
    def collectVars(self):
        return set()

class Number(Expr):
    _minNumber = config.getint('Number','MinValue')
    _maxNumber = config.getint('Number','MaxValue')
    def __init__(self):
        self._num = random.randint(Number._minNumber,Number._maxNumber)
    def __str__(self):
        return str(self._num)
    def __eq__(self, other):
        if not isinstance(other,Number):
            return False
        return other._num == self._num

class Var(Expr):
    _vars=[]
    @staticmethod
    def clear():
        Var._vars = []
    @staticmethod
    def populate(num):
        def createVar(i):
            v = Var()
            v._name = 'X'+str(i)
            return v
        Var._vars = map(createVar,range(num))
    def __str__(self):
        return self._name
    def __eq__(self, other):
        if not isinstance(other,Var):
            return False
        return other._name == self._name
    def __hash__(self):
        return hash(self._name)
    def collectVarNames(self):
        return set([self._name])
    def collectVars(self):
        return set([self])

class SourceVar(Var):
    def __init__(self):
        self._name = Var._vars[random.randrange(0,len(Var._vars))]._name
    @staticmethod
    def isValid():
        return len(Var._vars) > 0

class TargetVar(Var):
    _threshold = 0.8
    def __init__(self):
        if (random.uniform(0,1) <= TargetVar._threshold) or (len(Var._vars) == 0):
            self._name = 'X'+str(len(Var._vars))
            Var._vars.append(self)
        else:
            self._name = Var._vars[random.randrange(0, len(Var._vars))]._name

class Op(Expr):
    pass

class BinaryOp(Op):
    _Ops = ['+','-','*','/','%']
    def __init__(self):
        inner_weights = _inner_weights
        self._op1 = getExpr(inner_weights)
        self._act = BinaryOp._Ops[random.randrange(0,len(BinaryOp._Ops))]
        self._op2 = getExpr(inner_weights)
        while (self._op2==self._op1) or ((self._act == '/') and isinstance(self._op2, Number) and (self._op2._num == 0)) or (isinstance(self._op1,Number) and isinstance(self._op2,Number)):
            self._op2 = getExpr(inner_weights)
    def __str__(self):
        res = ''
        if isinstance(self._op1,Op):
            res += '( '+str(self._op1)+' )'
        else:
            res += str(self._op1)
        res += ' '+self._act+' '
        if isinstance(self._op2,Op):
            res += '( '+str(self._op2)+' )'
        else:
            res += str(self._op2)
        return res
    def __eq__(self, other):
        if not isinstance(other,BinaryOp):
            return False
        return (other._act == self._act) and (other._op1 == self._op1) and (other._op2 == self._op2)
    def collectVarNames(self):
        return self._op1.collectVarNames().union(self._op2.collectVarNames())
    def collectVars(self):
        return self._op1.collectVars().union(self._op2.collectVars())

class UnaryOp(Op):
    _Ops = ['++','--']
    def __init__(self):
        self._op = SourceVar()
        self._act = UnaryOp._Ops[random.randint(0,1)]
        self._position = (random.randint(0,1) == 1)
    def __str__(self):
        res = ''
        if self._position:
            res += self._act+' '
        res += str(self._op)
        if not self._position:
            res += ' '+self._act
        return '( '+res+' )'
    def __eq__(self, other):
        if not isinstance(other,UnaryOp):
            return False
        return (other._act == self._act) and (other._op == self._op)
    def collectVarNames(self):
        return self._op.collectVarNames()
    def collectVars(self):
        return self._op.collectVars()

class Assignment:
    def __init__(self):
        self._source = getExpr()
        self._target = TargetVar()
    def __str__(self):
        return str(self._target) + ' = ' + str(self._source) + ' ;\n'
    def collectVarNames(self):
        return self._source.collectVarNames().union(self._target.collectVarNames())
    def collectVars(self):
        return self._source.collectVars()

class Init:
    def __str__(self):
        if len(Var._vars) == 0:
            return ''
        vars = ','.join(map(lambda x:str(x),Var._vars))
        return 'int '+vars+' ;\n'

class Return:
    _threshold = config.getfloat('Return','Threshold')
    @staticmethod
    def getReturn():
        if random.uniform(0,1) <= Return._threshold:
            return ReturnVoid()
        return ReturnInt()
    def getType(self):
        return ''

class ReturnInt(Return):
    def __str__(self):
        return 'return ' + str(getExpr([2, 2, 1,1])) + ' ;\n'
    def getType(self):
        return 'int'

class ReturnVoid(Return):
    def __str__(self):
        return ''
    def getType(self):
        return 'void'

_exprs = [Number, SourceVar, BinaryOp, UnaryOp]
_weights = map(lambda e: config.getint(e.__name__, 'Weight'), _exprs)
_inner_weights = map(lambda e: config.getint(e.__name__, 'InnerWeight'), _exprs)
def getExpr(weights = _weights):
    assert len(weights) == len(_exprs)
    exprs = []
    for i in range(len(weights)):
        exprs += [_exprs[i]] * weights[i]
    expr = exprs[random.randrange(0, len(exprs))]
    while not expr.isValid():
        expr = exprs[random.randrange(0, len(exprs))]
    return expr()

class Program:
    _threshold = config.getfloat('Program','StatementThreshold')
    def __init__(self):
        Var.clear()
        self.statements = [Init()]
        while (random.uniform(0,1) <= Program._threshold) or (len(self.statements) == 1):
            self.statements.append(Assignment())
        self.statements.append(Return.getReturn())
    def getStatements(self):
        return self.statements[1:-1]
    def __str__(self):
        res = self.statements[-1].getType()+' f() {\n\t'
        res += '\t'.join(map(lambda x:str(x),self.statements)).strip()
        res += '\n}\n'
        return res

class Stats:
    class OperatorCount:
        def __init__(self, name, op):
            self._name = name
            self._op = op
            self._total = 0
            self._statements = 0
            self._inputs = 0
        def updateCounts(self, s):
            self._total += sum(map(lambda o: s.count(' '+o+' '), self._op))
            self._statements += sum(map(lambda x: 1 if len(filter(lambda o: ' '+o+' ' in x, self._op))>0 else 0, s.split(';')))
            self._inputs += 1 if len(filter(lambda o: ' '+o+' ' in s, self._op))>0 else 0
        def toString(self, count_inputs, count_statemtns, count_total):
            return self._name + '\t' + str(self._inputs) + '\t' + "{0:.2f}".format(100.0*self._inputs/float(count_inputs)) + '\t' + str(self._statements) + '\t' + "{0:.2f}".format(100.0*self._statements/float(count_statemtns)) + '\t' + str(self._total) + '\t' + "{0:.2f}".format(100.0*self._total/float(count_total))
    class Counter:
        def __init__(self, f):
            self._f = f
            self._min = None
            self._max = None
        def updateCounts(self, s):
            val = self._f(s)
            if self._min:
                self._min = min(self._min,val)
            else:
                self._min = val
            if self._max:
                self._max = max(self._max,val)
            else:
                self._max = val
        def __str__(self):
            return str(self._min)+'\t'+str(self._max)
    class LengthCounter(Counter):
        def __init__(self):
            Stats.Counter.__init__(self, lambda x: len(filter(lambda x: x!=' ', list(x.strip()))))
    class WordCounter(Counter):
        def __init__(self):
            Stats.Counter.__init__(self, lambda x: x.strip().count(' ')+1)
    def __init__(self):
        self._num_inputs = 0
        self._num_statements = 0
        self._statement_count = dict(map(lambda x: (x+1,0), range(config.getint('Statement', 'MaxStatements'))))
        self._ops = [Stats.OperatorCount('+', ['+']), Stats.OperatorCount('-', ['-']), Stats.OperatorCount('*', ['*']), Stats.OperatorCount('/', ['/']), Stats.OperatorCount('%', ['%']), Stats.OperatorCount('++', ['++']), Stats.OperatorCount('--', ['--']), Stats.OperatorCount('Binary', ['+','-','*','/','%']), Stats.OperatorCount('Unary', ['++','--']), Stats.OperatorCount('All', ['+','-','*','/','%','++','--'])]
        self._c_statement_length = Stats.LengthCounter()
        self._ll_statement_length = Stats.LengthCounter()
        self._c_word_count = Stats.WordCounter()
        self._ll_word_count = Stats.WordCounter()
    def updateStats(self, c, ll):
        self._num_inputs += 1
        self._num_statements += c.count(';')
        self._statement_count[c.count(';')] += 1
        map(lambda o: o.updateCounts(c), self._ops)
        self._c_statement_length.updateCounts(c)
        self._ll_statement_length.updateCounts(ll)
        self._c_word_count.updateCounts(c)
        self._ll_word_count.updateCounts(ll)
    def __str__(self):
        res = ''
        res += '[General]\n'
        res += 'Inputs\t'+str(self._num_inputs)+'\n'
        res += 'Statements\t'+str(self._num_statements)+'\n'
        res += '\n[Lengths]\n'
        res += '\tMin\tMax\n'
        res += 'Input\t'+str(self._c_statement_length)+'\n'
        res += 'Output\t'+str(self._ll_statement_length)+'\n'
        res += '\n[Word Counts]\n'
        res += '\tMin\tMax\n'
        res += 'Input\t'+str(self._c_word_count)+'\n'
        res += 'Output\t'+str(self._ll_word_count)+'\n'
        res += '\n[Operators]\n'
        res += '\tInputs\t%\tStatements\t%\tTotal\t%\n'
        res += '\n'.join(map(lambda x: x.toString(self._num_inputs, self._num_statements, self._ops[-1]._total), self._ops[:-1]))
        res += '\n[Statements]\n'
        res += 'Num\tCount\t%\n'
        res += '\n'.join(map(lambda x: str(x)+'\t'+str(self._statement_count[x])+'\t'+"{0:.2f}".format(100.0*self._statement_count[x]/float(self._num_inputs)),range(1,config.getint('Statement', 'MaxStatements')+1)))
        return res

def generatePrograms():
    import sys
    limited = False
    limit = 0
    outDir = 'out'
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            limited = True
        except:
            pass
        if len(sys.argv) > 2:
            outDir = sys.argv[2]
    # from cleanup import cleanup
    # cleanup(outDir)
    if os.path.exists(outDir):
        import shutil
        shutil.rmtree(outDir)
    os.mkdir(outDir)
    os.mkdir(os.path.join(outDir, 'block'))
    os.mkdir(os.path.join(outDir, 'line'))
    if limited:
        print 'Generating ' + str(limit) + ' programs'
    else:
        print 'Generating programs until manually stopped (ctrl+C)'
    print 'Saving to folder: ' + outDir
    print ''
    j = 1
    vocabc = set()
    vocabll = set()
    first = True
    minC = None
    maxC = None
    minLL = None
    maxLL = None
    with open(os.path.join(outDir, 'corpus.c'), 'w') as corpusc:
        with open(os.path.join(outDir, 'corpus.ll'), 'w') as corpusll:
            while (not limited) or (j <= limit):
                filename = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
                while os.path.exists(os.path.join(outDir, filename + '.c')):
                    filename = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
                if limited:
                    print '\r\t' + filename + '\t\t' + str(j) + '/' + str(limit),
                else:
                    print '\r\t' + filename + '\t\t' + str(j),
                sys.stdout.flush()
                done = False
                while not done:
                    try:
                        p = Program()
                        done = True
                    except RuntimeError:
                        pass
                with open(os.path.join(outDir, 'block', filename + '.c'), 'w') as f:
                    f.write(str(p))
                os.system(
                    'clang -S -emit-llvm -o ' + os.path.join(outDir, 'block', filename + '.ll') + ' ' + os.path.join(
                        outDir, 'block', filename + '.c') + ' > /dev/null 2>&1')
                with open(os.path.join(outDir, 'block', filename + '.ll'), 'r') as f:
                    lines = [l.strip() for l in f.readlines()]
                start = min(filter(lambda i: lines[i].startswith('define') and 'f()' in lines[i], range(len(lines))))
                end = min(filter(lambda i: lines[i] == '}' and i > start, range(len(lines))))
                with open(os.path.join(outDir, 'block', filename + '.ll'), 'w') as f:
                    for i in range(start, end + 1):
                        f.write(lines[i] + '\n')
                os.mkdir(os.path.join(outDir, 'line', filename))
                statements = p.getStatements()
                for i in range(len(statements)):
                    s = statements[i]
                    s._target._name = 'Y'
                    k = 0
                    for v in s.collectVars():
                        v._name = 'X' + str(k)
                        k += 1
                    v = s.collectVarNames()
                    with open(os.path.join(outDir, 'line', filename, filename + '_' + str(i) + '.c'), 'w') as f:
                        f.write('void f() {\n')
                        f.write('int ' + ','.join(v) + ';\n')
                        f.write(str(s))
                        f.write('}\n')
                    os.system('clang -S -emit-llvm -o ' + os.path.join(outDir, 'line', filename, filename + '_' + str(
                        i) + '.ll') + ' ' + os.path.join(outDir, 'line', filename,
                                                         filename + '_' + str(i) + '.c') + ' > /dev/null 2>&1')
                    with open(os.path.join(outDir, 'line', filename, filename + '_' + str(i) + '.ll'), 'r') as f:
                        lines = [l.strip() for l in f.readlines()]
                    start = min(
                        filter(lambda i: lines[i].startswith('define') and 'f()' in lines[i], range(len(lines))))
                    end = min(filter(lambda i: lines[i] == '}' and i > start, range(len(lines))))
                    lenC = 0
                    with open(os.path.join(outDir, 'line', filename, filename + '_' + str(i) + '.c'), 'w') as f:
                        line = str(s)
                        f.write(line)
                        corpusc.write(line)
                        vocabc.update(map(lambda x: x.strip(), line.split(' ')))
                        lenC = line.strip().count(' ') + 1
                        lenLL = 0
                    with open(os.path.join(outDir, 'line', filename, filename + '_' + str(i) + '.ll'), 'w') as f:
                        for i in range(start + 1 + len(v), end - 1):
                            line = lines[i].strip().replace(',', ' ,')
                            if line.endswith(', align 4'):
                                line = line[:-len(', align 4')].strip()
                            f.write(line + ' ;\n')
                            vocabll.update(map(lambda x: x.strip(), line.split(' ')))
                            corpusll.write(line + ' ; ')
                            lenLL += line.strip().count(' ') + 2
                        corpusll.write('\n')
                    if first:
                        minC = lenC
                        maxC = lenC
                        minLL = lenLL
                        maxLL = lenLL
                        first = False
                    else:
                        minC = min(minC, lenC)
                        maxC = max(maxC, lenC)
                        minLL = min(minLL, lenLL)
                        maxLL = max(maxLL, lenLL)
                j += 1
    with open(os.path.join(outDir, 'vocab.c.json'), 'w') as f:
        f.write('{\n')
        i = 0
        n = len(vocabc)
        for w in vocabc:
            f.write('  "' + w + '": ' + str(i))
            i += 1
            if i != n:
                f.write(', ')
            f.write('\n')
        f.write('}')
    with open(os.path.join(outDir, 'vocab.ll.json'), 'w') as f:
        f.write('{\n')
        i = 0
        n = len(vocabll)
        for w in vocabll:
            f.write('  "' + w + '": ' + str(i))
            i += 1
            if i != n:
                f.write(', ')
            f.write('\n')
        f.write('}')
    print '\nDone!\n'
    print 'input lengths (ll): ' + str(minLL) + '-' + str(maxLL)
    print 'output lengths (ll): ' + str(minC) + '-' + str(maxC)

def generateStatements():
    import sys
    limited = False
    limit = 0
    outFile = 'out'
    varCount = 10
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            limited = True
        except:
            pass
        if len(sys.argv) > 2:
            outFile = sys.argv[2]
            if len(sys.argv) > 3:
                varCount = int(sys.argv[3])
    # from cleanup import cleanup
    # cleanup(outDir)
    if limited:
        print 'Generating ' + str(limit) + ' statements'
    else:
        print 'Generating statements until manually stopped (ctrl+C)'
    print 'Saving to files: '+outFile+'.corpus.c, '+outFile+'.corpus.ll'
    print ''
    j = 1
    vocabc = set()
    vocabll = set()
    max_statements = config.getint('Statement', 'MaxStatements')
    statements_weights = ast.literal_eval(config.get('Statement', 'Weights'))
    assert len(statements_weights) >= max_statements
    num_statements_weights = []
    for i in range(max_statements):
        num_statements_weights += [i+1] * statements_weights[i]
    stats = Stats()
    with open(outFile+'.corpus.c', 'w') as corpusc:
        with open(outFile+'.corpus.ll', 'w') as corpusll:
            Var.clear()
            Var.populate(varCount)
            statements = set()
            while (not limited) or (j <= limit):
                if limited:
                    print '\r\t' + str(j) + '/' + str(limit),
                else:
                    print '\r\t' + str(j),
                sys.stdout.flush()
                done = False
                num_statements = num_statements_weights[random.randrange(0,len(num_statements_weights))]
                while not done:
                    try:
                        s = map(lambda i:getExpr(),range(num_statements))
                        if config.getboolean('General', 'SimplifyVars'):
                            for x in s:
                                k = 0
                                for v in x.collectVars():
                                    v._name = 'X' + str(k)
                                    k += 1
                        if ' '.join(map(lambda x:str(x),s)) not in statements:
                            done = True
                    except RuntimeError:
                        pass
                statements.add(' '.join(map(lambda x:str(x),s)))
                with open('tmp.c', 'w') as f:
                    f.write('void f() {\n')
                    f.write('int Y' + ','.join(['']+map(lambda v: v._name, Var._vars)) + ';\n')
                    for x in s:
                        f.write('Y = '+str(x)+' ;\n')
                    f.write('}\n')
                os.system('clang -S -emit-llvm -o tmp.ll tmp.c > /dev/null 2>&1')
                with open('tmp.ll', 'r') as f:
                    lines = [l.strip() for l in f.readlines()]
                start = min(filter(lambda i: lines[i].startswith('define') and 'f()' in lines[i], range(len(lines))))
                end = min(filter(lambda i: lines[i] == '}' and i > start, range(len(lines))))
                line = ''
                for x in s:
                    line += 'Y = '+str(x)+' ; '
                line += '\n'
                corpusc.write(line)
                cline = line
                vocabc.update(map(lambda x: x.strip(), line.split(' ')))
                llline = ''
                for i in range(start + 2 + varCount, end - 1):
                    line = lines[i].strip().replace(',', ' ,')
                    if config.getboolean('General', 'SimplifyVars'):
                        if line.endswith(', align 4'):
                            line = line[:-len(', align 4')].strip()
                    vocabll.update(map(lambda y: y.strip(), line.split(' ')))
                    llline += line + ' ; '
                corpusll.write(llline+'\n')
                stats.updateStats(cline, llline)
                os.remove('tmp.c')
                os.remove('tmp.ll')
                j += 1
    with open(outFile+'.vocab.c.json', 'w') as f:
        f.write('{\n')
        i = 0
        n = len(vocabc)
        for w in vocabc:
            f.write('  "' + w + '": ' + str(i))
            i += 1
            if i != n:
                f.write(', ')
            f.write('\n')
        f.write('}')
    with open(outFile+'.vocab.ll.json', 'w') as f:
        f.write('{\n')
        i = 0
        n = len(vocabll)
        for w in vocabll:
            f.write('  "' + w + '": ' + str(i))
            i += 1
            if i != n:
                f.write(', ')
            f.write('\n')
        f.write('}')
    with open(outFile+'.stats.tsv', 'w') as f:
        f.write(str(stats))
    print '\nDone!\n'

if __name__ == "__main__":
    generateStatements()