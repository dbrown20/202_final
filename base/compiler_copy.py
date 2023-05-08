'''
Group: Tyler Scott, Devin Brown, Olivia Welford

Current Implementation:
- We are starting with Assignment 4 base as recommended in the last lecture (to start without functions)

    What we've done so far:
      - General structure of compiler; added pass outlines in appropriate locations and put into compiler_passes dictionary
      - cast_insert -> a few logical elements we are working out, but otherwise are close to finishing
      - New cases in si_stmt -> Added necessary cases for make_any, tag_of, and value_of. Still adjusting as needed, but mostly set

    What we still have to do:
      - Need to correctly add 'any' type to typechecker; currently get an AssertionError at line 210 'assert t_e == env[x]', in the Assign case
          - we think this is due to not filling primitive dictionaries correctly
      - reveal_casts -> not started yet, biggest piece we have left to do

    Unexpected challenges:
      - We are unsure of the correct way to include the primitives for make_any, tag_of, and value_of
          - Currently adding to each of the 'prim_...' dictionaries in typechecker
      - Similarly we are trying to figure out how to use those primitives for the reveal_casts pass
'''


from typing import Set, Dict
import itertools
import sys
import traceback

from cs202_support.python import *
import cs202_support.x86 as x86
import constants
import cif
from cs202_support.python_ast import Program
from interference_graph import InterferenceGraph

# TODO: HERE
# Imports needed for Dynamic Typing
from typing import TypeVar
from dataclasses import dataclass
# TODO: END

comparisons = ['eq', 'gt', 'gte', 'lt', 'lte']
gensym_num = 0
global_logging = False


def log(label, value):
    if global_logging:
        print()
        print(f'--------------------------------------------------')
        print(f'Logging: {label}')
        print(value)
        print(f'--------------------------------------------------')


def log_ast(label, value):
    log(label, print_ast(value))


def gensym(x):
    """
    Constructs a new variable name guaranteed to be unique.
    :param x: A "base" variable name (e.g. "x")
    :return: A unique variable name (e.g. "x_1")
    """

    global gensym_num
    gensym_num = gensym_num + 1
    return f'{x}_{gensym_num}'


##################################################
# typecheck
##################################################
# op    ::= "add" | "sub" | "not" | "or" | "and" | "eq" | "gt" | "gte" | "lt" | "lte"
# Expr  ::= Var(x) | Constant(n) | Prim(op, List[Expr])
# Stmt  ::= Assign(x, Expr) | Print(Expr) | If(Expr, Stmts, Stmts)
# Stmts ::= List[Stmt]
# LVar  ::= Program(Stmts)

TEnv = Dict[str, type]


# TODO: HERE
T = TypeVar('T')
@dataclass
class AnyVal:
    val: any
    tag: type

def inject(val: T) -> AnyVal: # Call this on something with a known static type to get 'Any'
    return AnyVal(val, type(val))

def project(tagged_val: AnyVal, t: T) -> T: # Call this on an 'Any' to get the desired type
    if tagged_val.tag == t:
        return tagged_val.val
    else:
        raise Exception('run-time type error!')


def cast_insert(program: Program) -> Program:
# def cast_insert(program: Program, t: T) -> Program:
    # Compile 'Ldyn' to 'Lany' by adding inject and project operations
    # For each constant: use inject to convert the constant into a tagged 'Any' value
    # For each primitive; use 'project' to projects the inputs to the correct expected types;
    #       use inject to convert the output to 'Any'

    new_exprs_list = []
    curr_exprs_list = program.stmts  # Check each stmt for either Constant or Prim
    for e in curr_exprs_list:
        match e:
            case Constant(val):
                new_any = inject(val)  # Make AnyVal type
                new_exprs_list.append(new_any)
            case Prim(op, args):
                new_args = []
                for exprs in args:  # TODO: Not sure if should loop through args or exprs list?
                # for exprs in new_exprs_list:
                    # new_type = project(exprs, t)  # Convert AnyVals to the desired type
                    new_type = project(exprs, type(exprs.val))  # TODO: Not sure if correct way to get type
                    new_args.append(new_type)
                new_expr = Prim(op, new_args)
                new_exprs_list.append(inject(new_expr))
            case _:
                new_exprs_list.append(e)  # TODO: Seems weird, but return type error otherwise
                # raise Exception('cast_insert', e)

    return Program(new_exprs_list)  # Return program of newly cast expressions
# TODO: END

def typecheck(program: Program) -> Program:
    """
    Typechecks the input program; throws an error if the program is not well-typed.
    :param program: The Lif program to typecheck
    :return: The program, if it is well-typed
    """
    prim_arg_types = {
        'add':   [int, int],
        'sub':   [int, int],
        'mult':  [int, int],
        'not': [bool],
        'or':  [bool, bool],
        'and':  [bool, bool],
        'gt':   [int, int],
        'gte':  [int, int],
        'lt':   [int, int],
        'lte':  [int, int],

        # TODO: Not 100% sure on these
        'any': [any],
        'tag_of': [any],
        'value_of': [any],
        'make_any': [any, type],
    }

    prim_output_types = {
        'add':   int,
        'sub':   int,
        'mult':  int,
        'not': bool,
        'or':  bool,
        'and':  bool,
        'gt':   bool,
        'gte':  bool,
        'lt':   bool,
        'lte':  bool,

        # TODO: Not 100% sure on these
        'any': any,
        'tag_of': type,   # Returns the tag, which is a 'type'
        'value_of': any,  # Returns the value, which is an 'any'
        'make_any': any,
    }

    def tc_exp(e: Expr, env: TEnv) -> type:
        match e:
            case Var(x):
                return env[x]
            case Constant(i):
                if isinstance(i, bool):
                    return bool
                elif isinstance(i, int):
                    return int
                else:
                    raise Exception('tc_exp', e)
            case Prim('eq', [e1, e2]):
                assert tc_exp(e1, env) == tc_exp(e2, env)
                return bool
            case Prim(op, args):
                arg_types = [tc_exp(a, env) for a in args]
                assert arg_types == prim_arg_types[op]
                return prim_output_types[op]
            case _:
                raise Exception('tc_exp', e)

    def tc_stmt(s: Stmt, env: TEnv):
        match s:
            case If(condition, then_stmts, else_stmts):
                assert tc_exp(condition, env) == bool

                for s in then_stmts:
                    tc_stmt(s, env)
                for s in else_stmts:
                    tc_stmt(s, env)
            case Print(e):
                tc_exp(e, env)
            case Assign(x, e):
                t_e = tc_exp(e, env)
                if x in env:
                    assert t_e == env[x]
                else:
                    env[x] = t_e
            case _:
                raise Exception('tc_stmt', s)

    def tc_stmts(stmts: List[Stmt], env: TEnv):
        for s in stmts:
            tc_stmt(s, env)

    env = {}
    tc_stmts(program.stmts, env)
    return program


##################################################
# remove-complex-opera*
##################################################
# op    ::= "add" | "sub" | "not" | "or" | "and" | "eq" | "gt" | "gte" | "lt" | "lte"
# Expr  ::= Var(x) | Constant(n) | Prim(op, List[Expr])
# Stmt  ::= Assign(x, Expr) | Print(Expr) | If(Expr, Stmts, Stmts)
# Stmts ::= List[Stmt]
# LVar  ::= Program(Stmts)

def rco(prog: Program) -> Program:
    """
    Removes complex operands. After this pass, the arguments to operators (unary and binary
    operators, and function calls like "print") will be atomic.
    :param prog: An Lif program
    :return: An Lif program with atomic operator arguments.
    """

    def rco_stmt(stmt: Stmt, bindings: Dict[str, Expr]) -> Stmt:
        match stmt:
            case Assign(x, e1):
                new_e1 = rco_exp(e1, bindings)
                return Assign(x, new_e1)
            case Print(e1):
                new_e1 = rco_exp(e1, bindings)
                return Print(new_e1)
            case If(condition, then_stmts, else_stmts):
                new_condition = rco_exp(condition, bindings)
                new_then_stmts = rco_stmts(then_stmts)
                new_else_stmts = rco_stmts(else_stmts)

                return If(new_condition,
                          new_then_stmts,
                          new_else_stmts)
            case _:
                raise Exception('rco_stmt', stmt)

    def rco_stmts(stmts: List[Stmt]) -> List[Stmt]:
        new_stmts = []

        for stmt in stmts:
            bindings = {}
            # (1) compile the statement
            new_stmt = rco_stmt(stmt, bindings)
            # (2) add the new bindings created by rco_exp
            new_stmts.extend([Assign(x, e) for x, e in bindings.items()])
            # (3) add the compiled statement itself
            new_stmts.append(new_stmt)

        return new_stmts

    def rco_exp(e: Expr, bindings: Dict[str, Expr]) -> Expr:
        match e:
            case Var(x):
                return Var(x)
            case Constant(i):
                return Constant(i)
            case Prim(op, args):
                new_args = [rco_exp(e, bindings) for e in args]
                new_e = Prim(op, new_args)
                new_v = gensym('tmp')
                bindings[new_v] = new_e
                return Var(new_v)
            case _:
                raise Exception('rco_exp', e)

    return Program(rco_stmts(prog.stmts))

# TODO: Here
# def reveal_casts(program: Program) -> Program:
#     # TODO: Compiles the casts into lower-level primitives. Put it after RCO, because it introduces new control flow
#     #       Compiles both project and inject:
#     #       Project compiles into an if statement that checks if the tag is correct and returns the value if so; otherwise it exits the program
#     #       Inject compiles into the 'make_any' primitive that attaches a tag (select-instructions will compile it further)
#
#     # For part #1:
#     # - Use two primitives: 'tag_of' and 'value_of'
#     #     - 'tag_of' returns a tag of a value of type 'Any'
#     #     - 'value_of' returns the value of a value of type 'Any'
#     #
#     # For 'x=project(y, int)':
#     # We produce:
#     #
#     # if tag_of(y) == tag_of(int):
#     #     x = value_of(y)
#     # else:
#     #     exit()
#     #
#     # Can calculate the tag value at compile time (Binary tag values -> Book section 10.2, convert them to decimal values).
#     # Will deal with the 3 remaining primitives in select-instructions.
#     pass

def reveal_casts(any_t: AnyVal):
    # CHeck if an inject or project
    match any_t:
        case inject(any_t, t):
            pass
        case project(any_t, t):
            if any_t.tag == int:
                return any_t.value
            elif any_t.tag == bool:
                return any_t.value














# TODO: End

##################################################
# explicate-control
##################################################
# op    ::= "add" | "sub" | "not" | "or" | "and" | "eq" | "gt" | "gte" | "lt" | "lte"
# Atm   ::= Var(x) | Constant(n)
# Expr  ::= Atm | Prim(op, List[Expr])
# Stmt  ::= Assign(x, Expr) | Print(Expr) | If(Expr, Stmts, Stmts)
# Stmts ::= List[Stmt]
# LVar  ::= Program(Stmts)

def explicate_control(prog: Program) -> cif.CProgram:
    """
    Transforms an Lif Expression into a Cif program.
    :param prog: An Lif Expression
    :return: A Cif Program
    """

    # the basic blocks of the program
    basic_blocks: Dict[str, List[cif.Stmt]] = {}

    # create a new basic block to hold some statements
    # generates a brand-new name for the block and returns it
    def create_block(stmts: List[cif.Stmt]) -> str:
        label = gensym('label')
        basic_blocks[label] = stmts
        return label

    def explicate_atm(e: Expr) -> cif.Atm:
        match e:
            case Var(x):
                return cif.Var(x)
            case Constant(c):
                return cif.Constant(c)
            case _:
                raise RuntimeError(e)

    def explicate_exp(e: Expr) -> cif.Expr:
        match e:
            case Prim(op, args):
                new_args = [explicate_atm(a) for a in args]
                return cif.Prim(op, new_args)
            case _:
                return explicate_atm(e)

    def explicate_stmt(stmt: Stmt, cont: List[cif.Stmt]) -> List[cif.Stmt]:
        match stmt:
            case Assign(x, exp):
                new_exp = explicate_exp(exp)
                new_stmt: List[cif.Stmt] = [cif.Assign(x, new_exp)]
                return new_stmt + cont
            case Print(exp):
                new_exp = explicate_atm(exp)
                new_stmt: List[cif.Stmt] = [cif.Print(new_exp)]
                return new_stmt + cont
            case If(condition, then_stmts, else_stmts):
                cont_label = create_block(cont)
                e2_label = create_block(explicate_stmts(then_stmts, [cif.Goto(cont_label)]))
                e3_label = create_block(explicate_stmts(else_stmts, [cif.Goto(cont_label)]))
                return [cif.If(explicate_exp(condition),
                               cif.Goto(e2_label),
                               cif.Goto(e3_label))]
                
            case _:
                raise RuntimeError(stmt)

    def explicate_stmts(stmts: List[Stmt], cont: List[cif.Stmt]) -> List[cif.Stmt]:
        for s in reversed(stmts):
            cont = explicate_stmt(s, cont)
        return cont

    new_body = [cif.Return(cif.Constant(0))]
    new_body = explicate_stmts(prog.stmts, new_body)

    basic_blocks['start'] = new_body
    return cif.CProgram(basic_blocks)


##################################################
# select-instructions
##################################################
# op    ::= "add" | "sub" | "not" | "or" | "and" | "eq" | "gt" | "gte" | "lt" | "lte"
# Atm   ::= Var(x) | Constant(n)
# Expr  ::= Atm | Prim(op, List[Expr])
# Stmt  ::= Assign(x, Expr) | Print(Expr)
#        | If(Expr, Goto(label), Goto(label)) | Goto(label) | Return(Expr)
# Stmts ::= List[Stmt]
# Cif   ::= CProgram(Dict[label, Stmts])

def select_instructions(prog: cif.CProgram) -> x86.X86Program:
    """
    Transforms a Lif program into a pseudo-x86 assembly program.
    :param prog: a Lif program
    :return: a pseudo-x86 program
    """

    def si_atm(a: cif.Expr) -> x86.Arg:
        match a:
            case cif.Constant(i):
                return x86.Immediate(int(i))
            case cif.Var(x):
                return x86.Var(x)
            case _:
                raise Exception('si_atm', a)

    def si_stmts(stmts: List[cif.Stmt]) -> List[x86.Instr]:
        instrs = []

        for stmt in stmts:
            instrs.extend(si_stmt(stmt))

        return instrs

    op_cc = {'eq': 'e', 'gt': 'g', 'gte': 'ge', 'lt': 'l', 'lte': 'le'}

    binop_instrs = {'add': 'addq', 'sub': 'subq', 'mult': 'imulq', 'and': 'andq', 'or': 'orq'}

    # TODO: add three cases:
    #   - make_any: make_any adds the tag: shifts the value 3 bits to the left, then adds the tag to the value
    #   - tag_of: tag_of gets JUST the tag piece of a tagged value
    #   - value_of: value_of gets JUST the value piece of a tagged value
    def si_stmt(stmt: cif.Stmt) -> List[x86.Instr]:
        match stmt:
            # 1. make_any adds the tag: shifts the value 3 bits to the left, then adds the tag to the value
            # 'x = make_any(5, 1)'
            # =>
            # '''
            # - If not doing functions in dyn typin
            # salq $3, #x  --shifts left by 3 bits
            # orq $1, #x   -- adds the tag: 001
            # TODO: Check correctness
            case cif.Assign(x, cif.Prim('make_any', [atm1, atm2])):
                return [x86.NamedInstr('salq', [x86.Immediate(3), x86.Var(x)]),
                        x86.NamedInstr('orq', [si_atm(atm2), x86.Var(x)])]

            # 2. tag_of gets JUST the tag piece of a tagged value
            # 'tmp_4 = tag_of(x)'
            # =>
            # '''
            # movq #x, #tmp_4  -- copy the tagged value to the destination
            # andq $7, #tmp_4  -- erase everything except the tag (7 = 0b111)
            # TODO: Check correctness
            case cif.Assign(x, cif.Prim('tag_of', [atm1])):
                return [x86.NamedInstr('movq', [si_atm(atm1), x86.Var(x)]),
                        x86.NamedInstr('andq', [x86.Immediate(7), x86.Var(x)])]

            # 3. value_of gets JUST the value piece of a tagged value
            # 'tmp_1 = value_of(x)'
            # =>
            # '''
            # movq #x, #tmp_1  -- move the tagged value to the destination
            # sarq $3, #tmp_1  -- shift the tagged value 3 bits to the right, erasing the tag
            # '''
            # TODO: Check correctness
            case cif.Assign(x, cif.Prim('value_of', [atm1])):
                return [x86.NamedInstr('movq', [si_atm(atm1), x86.Var(x)]),
                        x86.NamedInstr('sarq', [x86.Immediate(3), x86.Var(x)])]

            # For the exit primitive, you can jump to 'main_conclusion' (which exits the program)
            # TODO: Check correctness
            case cif.Assign(x, cif.Prim('exit', [atm1])):
                return [x86.NamedInstr('jmp', ['conclusion'])]
                # return [x86.NamedInstr('jmp', ['main_conclusion'])]

            # TODO: END


            case cif.Assign(x, cif.Prim(op, [atm1, atm2])):
                if op in binop_instrs:
                    return [x86.NamedInstr('movq', [si_atm(atm1), x86.Reg('rax')]),
                            x86.NamedInstr(binop_instrs[op], [si_atm(atm2), x86.Reg('rax')]),
                            x86.NamedInstr('movq', [x86.Reg('rax'), x86.Var(x)])]
                elif op in op_cc:
                    return [x86.NamedInstr('cmpq', [si_atm(atm2), si_atm(atm1)]),
                            x86.Set(op_cc[op], x86.ByteReg('al')),
                            x86.NamedInstr('movzbq', [x86.ByteReg('al'), x86.Var(x)])]

                else:
                    raise Exception('si_stmt failed op', op)
            case cif.Assign(x, cif.Prim('not', [atm1])):
                return [x86.NamedInstr('movq', [si_atm(atm1), x86.Var(x)]),
                        x86.NamedInstr('xorq', [x86.Immediate(1), x86.Var(x)])]
            case cif.Assign(x, atm1):
                return [x86.NamedInstr('movq', [si_atm(atm1), x86.Var(x)])]
            case cif.Print(atm1):
                return [x86.NamedInstr('movq', [si_atm(atm1), x86.Reg('rdi')]),
                        x86.Callq('print_int')]
            case cif.Return(atm1):
                return [x86.NamedInstr('movq', [si_atm(atm1), x86.Reg('rax')]),
                        x86.Jmp('conclusion')]
            case cif.Goto(label):
                return [x86.Jmp(label)]
            case cif.If(a, cif.Goto(then_label), cif.Goto(else_label)):
                return [x86.NamedInstr('cmpq', [si_atm(a), x86.Immediate(1)]),
                        x86.JmpIf('e', then_label),
                        x86.Jmp(else_label)]
            case _:
                raise Exception('si_stmt', stmt)

    basic_blocks = {label: si_stmts(block) for (label, block) in prog.blocks.items()}
    return x86.X86Program(basic_blocks)


##################################################
# allocate-registers
##################################################
# Arg    ::= Immediate(i) | Reg(r) | ByteReg(r) | Var(x) | Deref(r, offset)
# op     ::= 'addq' | 'cmpq' | 'andq' | 'orq' | 'xorq' | 'movq' | 'movzbq'
# cc     ::= 'e'| 'g' | 'ge' | 'l' | 'le'
# Instr  ::= NamedInstr(op, List[Arg]) | Callq(label) | Retq()
#         | Jmp(label) | JmpIf(cc, label) | Set(cc, Arg)
# Blocks ::= Dict[label, List[Instr]]
# X86    ::= X86Program(Blocks)

Color = int
Coloring = Dict[x86.Var, Color]
Saturation = Set[Color]

def allocate_registers(program: x86.X86Program) -> x86.X86Program:
    """
    Assigns homes to variables in the input program. Allocates registers and
    stack locations as needed, based on a graph-coloring register allocation
    algorithm.
    :param program: A pseudo-x86 program.
    :return: An x86 program, annotated with the number of bytes needed in stack
    locations.
    """

    all_vars: Set[x86.Var] = set()
    live_before_sets = {'conclusion': set()}
    live_after_sets = {}
    homes: Dict[x86.Var, x86.Arg] = {}
    blocks = program.blocks

    # --------------------------------------------------
    # utilities
    # --------------------------------------------------
    def vars_arg(a: x86.Arg) -> Set[x86.Var]:
        match a:
            case x86.Immediate(i):
                return set()
            case x86.Reg(r):
                return set()
            case x86.ByteReg(r):
                return set()
            case x86.Var(x):
                all_vars.add(x86.Var(x))
                return {x86.Var(x)}
            case _:
                raise Exception('ul_arg', a)

    def reads_of(i: x86.Instr) -> Set[x86.Var]:
        match i:
            case x86.NamedInstr(i, [e1, e2]) if i in ['movq', 'movzbq']:
                return vars_arg(e1)
            case x86.NamedInstr(i, [e1, e2]) if i in ['addq', 'cmpq', 'imulq', 'subq', 'andq', 'orq', 'xorq']:
                return vars_arg(e1).union(vars_arg(e2))
            case x86.Jmp(label) | x86.JmpIf(_, label):
                # if we don't know the live-before set for the destination,
                # calculate it first
                if label not in live_before_sets:
                    ul_block(label)

                # the variables that might be read after this instruction
                # are the live-before variables of the destination block
                return live_before_sets[label]
            case _:
                if isinstance(i, (x86.Callq, x86.Set)):
                    return set()
                else:
                    raise Exception(i)

    def writes_of(i: x86.Instr) -> Set[x86.Var]:
        match i:
            case x86.NamedInstr(i, [e1, e2]) \
                if i in ['movq', 'movzbq', 'addq', 'subq', 'imulq', 'cmpq', 'andq', 'orq', 'xorq']:
                return vars_arg(e2)
            case _:
                if isinstance(i, (x86.Jmp, x86.JmpIf, x86.Callq, x86.Set)):
                    return set()
                else:
                    raise Exception(i)

    # --------------------------------------------------
    # liveness analysis
    # --------------------------------------------------
    def ul_instr(i: x86.Instr, live_after: Set[x86.Var]) -> Set[x86.Var]:
        return live_after.difference(writes_of(i)).union(reads_of(i))

    def ul_block(label: str):
        instrs = blocks[label]
        current_live_after: Set[x86.Var] = set()

        block_live_after_sets = []
        for i in reversed(instrs):
            block_live_after_sets.append(current_live_after)
            current_live_after = ul_instr(i, current_live_after)

        live_before_sets[label] = current_live_after
        live_after_sets[label] = list(reversed(block_live_after_sets))

    # --------------------------------------------------
    # interference graph
    # --------------------------------------------------
    def bi_instr(e: x86.Instr, live_after: Set[x86.Var], graph: InterferenceGraph):
        for v1 in writes_of(e):
            for v2 in live_after:
                graph.add_edge(v1, v2)

    def bi_block(instrs: List[x86.Instr], live_afters: List[Set[x86.Var]], graph: InterferenceGraph):
        for instr, live_after in zip(instrs, live_afters):
            bi_instr(instr, live_after, graph)

    # --------------------------------------------------
    # graph coloring
    # --------------------------------------------------
    def color_graph(local_vars: Set[x86.Var], interference_graph: InterferenceGraph) -> Coloring:
        coloring: Coloring = {}

        to_color = local_vars.copy()

        # Saturation sets start out empty
        saturation_sets = {x: set() for x in local_vars}

        # Loop until we are finished coloring
        while to_color:
            # Find the variable x with the largest saturation set
            x = max(to_color, key=lambda x: len(saturation_sets[x]))

            # Remove x from the variables to color
            to_color.remove(x)

            # Find the smallest color not in x's saturation set
            x_color = next(i for i in itertools.count() if i not in saturation_sets[x])

            # Assign x's color
            coloring[x] = x_color

            # Add x's color to the saturation sets of its neighbors
            for y in interference_graph.neighbors(x):
                saturation_sets[y].add(x_color)

        return coloring

    # --------------------------------------------------
    # assigning homes
    # --------------------------------------------------
    def align(num_bytes: int) -> int:
        if num_bytes % 16 == 0:
            return num_bytes
        else:
            return num_bytes + (16 - (num_bytes % 16))

    def ah_arg(a: x86.Arg) -> x86.Arg:
        match a:
            case x86.Immediate(i):
                return a
            case x86.Reg(r):
                return a
            case x86.ByteReg(r):
                return a
            case x86.Var(x):
                return homes[x86.Var(x)]
            case _:
                raise Exception('ah_arg', a)

    def ah_instr(e: x86.Instr) -> x86.Instr:
        match e:
            case x86.NamedInstr(i, args):
                return x86.NamedInstr(i, [ah_arg(a) for a in args])
            case x86.Set(cc, a1):
                return x86.Set(cc, ah_arg(a1))
            case _:
                if isinstance(e, (x86.Callq, x86.Retq, x86.Jmp, x86.JmpIf)):
                    return e
                else:
                    raise Exception('ah_instr', e)

    def ah_block(instrs: List[x86.Instr]) -> List[x86.Instr]:
        return [ah_instr(i) for i in instrs]

    # --------------------------------------------------
    # main body of the pass
    # --------------------------------------------------

    # Step 1: Perform liveness analysis
    ul_block('start')
    log_ast('live-after sets', live_after_sets)

    # Step 2: Build the interference graph
    interference_graph = InterferenceGraph()

    for label in blocks.keys():
        bi_block(blocks[label], live_after_sets[label], interference_graph)

    log_ast('interference graph', interference_graph)

    # Step 3: Color the graph
    coloring = color_graph(all_vars, interference_graph)
    colors_used = set(coloring.values())
    log('coloring', coloring)

    # Defines the set of registers to use
    available_registers = constants.caller_saved_registers + constants.callee_saved_registers

    # Step 4: map variables to homes
    color_map = {}
    stack_locations_used = 0

    # Step 4.1: Map colors to locations (the "color map")
    for color in sorted(colors_used):
        if available_registers != []:
            r = available_registers.pop()
            color_map[color] = x86.Reg(r)
        else:
            offset = stack_locations_used+1
            color_map[color] = x86.Deref('rbp', -(offset * 8))
            stack_locations_used += 1

    # Step 4.2: Compose the "coloring" with the "color map" to get "homes"
    for v in all_vars:
        homes[v] = color_map[coloring[v]]
    log('homes', homes)

    # Step 5: replace variables with their homes
    blocks = program.blocks
    new_blocks = {label: ah_block(block) for label, block in blocks.items()}
    return x86.X86Program(new_blocks, stack_space = align(8 * stack_locations_used))


##################################################
# patch-instructions
##################################################
# Arg    ::= Immediate(i) | Reg(r) | ByteReg(r) | Deref(r, offset)
# op     ::= 'addq' | 'cmpq' | 'andq' | 'orq' | 'xorq' | 'movq' | 'movzbq'
# cc     ::= 'e'| 'g' | 'ge' | 'l' | 'le'
# Instr  ::= NamedInstr(op, List[Arg]) | Callq(label) | Retq()
#         | Jmp(label) | JmpIf(cc, label) | Set(cc, Arg)
# Blocks ::= Dict[label, List[Instr]]
# X86    ::= X86Program(Blocks)

def patch_instructions(program: x86.X86Program) -> x86.X86Program:
    """
    Patches instructions with two memory location inputs, using %rax as a temporary location.
    :param program: An x86 program.
    :return: A patched x86 program.
    """

    def pi_instr(e: x86.Instr) -> List[x86.Instr]:
        match e:
            case x86.NamedInstr(i, [x86.Deref(r1, o1), x86.Deref(r2, o2)]):
                return [x86.NamedInstr('movq', [x86.Deref(r1, o1), x86.Reg('rax')]),
                        x86.NamedInstr(i, [x86.Reg('rax'), x86.Deref(r2, o2)])]
            case x86.NamedInstr('movzbq', [x86.Deref(r1, o1), x86.Deref(r2, o2)]):
                    return [x86.NamedInstr('movzbq', [x86.Deref(r1, o1), x86.Reg('rax')]),
                            x86.NamedInstr('movq', [x86.Reg('rax'), x86.Deref(r2, o2)])]
            case x86.NamedInstr('cmpq', [a1, x86.Immediate(i)]):
                return [x86.NamedInstr('movq', [x86.Immediate(i), x86.Reg('rax')]),
                        x86.NamedInstr('cmpq', [a1, x86.Reg('rax')])]
            case _:
                if isinstance(e, (x86.Callq, x86.Retq, x86.Jmp, x86.JmpIf, x86.NamedInstr, x86.Set)):
                    return [e]
                else:
                    raise Exception('pi_instr', e)

    def pi_block(instrs: List[x86.Instr]) -> List[x86.Instr]:
        new_instrs = [pi_instr(i) for i in instrs]
        flattened = [val for sublist in new_instrs for val in sublist]
        return flattened

    blocks = program.blocks
    new_blocks = {label: pi_block(block) for label, block in blocks.items()}
    return x86.X86Program(new_blocks, stack_space = program.stack_space)


##################################################
# prelude-and-conclusion
##################################################
# Arg    ::= Immediate(i) | Reg(r) | ByteReg(r) | Deref(r, offset)
# op     ::= 'addq' | 'cmpq' | 'andq' | 'orq' | 'xorq' | 'movq' | 'movzbq'
# cc     ::= 'e'| 'g' | 'ge' | 'l' | 'le'
# Instr  ::= NamedInstr(op, List[Arg]) | Callq(label) | Retq()
#         | Jmp(label) | JmpIf(cc, label) | Set(cc, Arg)
# Blocks ::= Dict[label, List[Instr]]
# X86    ::= X86Program(Blocks)

def prelude_and_conclusion(program: x86.X86Program) -> x86.X86Program:
    """
    Adds the prelude and conclusion for the program.
    :param program: An x86 program.
    :return: An x86 program, with prelude and conclusion.
    """

    prelude = [x86.NamedInstr('pushq', [x86.Reg('rbp')]),
               x86.NamedInstr('movq',  [x86.Reg('rsp'), x86.Reg('rbp')]),
               x86.NamedInstr('subq',  [x86.Immediate(program.stack_space),
                                        x86.Reg('rsp')]),
               x86.Jmp('start')]

    conclusion = [x86.NamedInstr('addq', [x86.Immediate(program.stack_space),
                                          x86.Reg('rsp')]),
                  x86.NamedInstr('popq', [x86.Reg('rbp')]),
                  x86.Retq()]

    new_blocks = program.blocks.copy()
    new_blocks['main'] = prelude
    new_blocks['conclusion'] = conclusion
    return x86.X86Program(new_blocks, stack_space = program.stack_space)


##################################################
# Compiler definition
##################################################

# TODO: Added pass in here
compiler_passes = {
    'cast insert': cast_insert,
    'typecheck': typecheck,
    'remove complex opera*': rco,
    'reveal cast': reveal_casts,
    'explicate control': explicate_control,
    'select instructions': select_instructions,
    'allocate registers': allocate_registers,
    'patch instructions': patch_instructions,
    'prelude & conclusion': prelude_and_conclusion,
    'print x86': x86.print_x86
}


def run_compiler(s, logging=False):
    def print_prog(current_program):
        print('Concrete syntax:')
        if isinstance(current_program, x86.X86Program):
            print(x86.print_x86(current_program))
        elif isinstance(current_program, Program):
            print(print_program(current_program))
        elif isinstance(current_program, cif.CProgram):
            print(cif.print_program(current_program))

        print()
        print('Abstract syntax:')
        print(print_ast(current_program))

    current_program = parse(s)

    if logging == True:
        print()
        print('==================================================')
        print(' Input program')
        print('==================================================')
        print()
        print_prog(current_program)

    for pass_name, pass_fn in compiler_passes.items():
        current_program = pass_fn(current_program)

        if logging == True:
            print()
            print('==================================================')
            print(f' Output of pass: {pass_name}')
            print('==================================================')
            print()
            print_prog(current_program)

    return current_program


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python compiler.py <source filename>')
    else:
        file_name = sys.argv[1]
        with open(file_name) as f:
            print(f'Compiling program {file_name}...')

            try:
                program = f.read()
                x86_program = run_compiler(program, logging=True)

                with open(file_name + '.s', 'w') as output_file:
                    output_file.write(x86_program)

            except:
                print('Error during compilation! **************************************************')
                traceback.print_exception(*sys.exc_info())
