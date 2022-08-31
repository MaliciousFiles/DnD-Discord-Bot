# V2, changes: x op is now the lowest operation, so 2x d6+5 would run d6+5 twice, rather than the accidentally working [1,1]d6+5, reworked roll_dice to detect complexity of statement and potentially run it in the simple command
# function allowing for crit tracking

import random


def roll_dice(txt):
    txt = clean(txt)
    comp = 0
    if 'd' in txt:
        o, e = txt.split('d', 1)
        if o == '':
            o = 1
        elif o.isdigit():
            o = int(o)
        else:
            comp = 2
        if e.isdigit() and comp == 0:
            c = simple(o, int(e))
        elif comp == 0:
            if '+' in e:
                e, v = e.split('+', 1)
                c = simple(o, int(e), int(v))
            elif '-' in e:
                e, v = e.split('-', 1)
                c = simple(o, int(e), -int(v))
            else:
                comp = 2
    if comp == 2:
        try:
            p = parse(txt)
        except:
            raise RuntimeError('Parsing Error')
        try:
            v = cal(p)
        except:
            raise RuntimeError('Computation Error')
        c = 'Command: ' + txt + '\nResult: Too Complex' + '\nResult: ' + str(v)
    return (c)


def simple(n, s, v=''):
    rs = rollsep(n, s)
    ors = rs
    c = []
    if s == 20:
        rs = ['**' * (r == 20) + '***' * (r == 1) + str(r) + '**' * (r == 20) + '***' * (r == 1) for r in rs]
    else:
        rs = [str(r) for r in rs]
    E = ''
    t = 0
    if v != '':
        t = v
        E = v
        if E >= 0:
            E = '+' + str(E)
        else:
            E = str(E)

    intrs = ', '.join(rs)
    return ('Command: ' + str(n) + 'd' + str(s) + E + '\nResult: (' + intrs + ')' + E + '\nResult: ' + str(
        sum(ors) + t))


def clean(txt):
    return ''.join([c for c in txt.lower() if c != " "])


def parse(code):
    s = []
    j = ''
    i = 0
    while i < len(code):
        c = code[i]
        if c == '(':
            ss = ''
            depth = 1
            while depth > 0:
                i += 1
                c = code[i]
                ss += c
                if c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
            ss = ss[:-1]
            s.append(parse(ss))
        else:
            oj = j
            j += c
            if oj != '':
                if oj.isdigit() and not j.isdigit():
                    s.append(int(oj))
                    j = j[-1]
            if j in ops:
                s.append(j)
                j = ''
        i += 1
    if j.isdigit():
        s.append(int(j))
    os = []  # checks for any d commands that dont have a front command, in which case it defaults to a 1
    for i in range(len(s)):
        if s[i] == 'd':
            alt = 0
            if i == 0:
                alt = 1
            elif s[i - 1] in ops:
                alt = 1
            if alt:
                os.append(1)
        if s[i] == '-':  # checks for subtraction, and converts it to addition and negation
            alt = 0
            if i == 0:
                alt = 1
            elif s[i - 1] in ops:
                alt = 1
            if not alt:
                os.append('+')
        os.append(s[i])
    s = os

    os = []
    skip = 0
    for i in range(len(s)):  # Order of operations, collapse d, sd, t, b commands
        if not skip:
            if s[i] in ['d', 'sd', 't', 'b']:
                p = os.pop(-1)
                os.append((s[i], p, s[i + 1]))
                skip = True
            else:
                os.append(s[i])
        else:
            skip = False
    s = os

    os = []
    skip = 0
    for i in range(len(s)):  # Order of operations, collapse unary after ^ commands
        if not skip:
            if i > 0:
                if s[i - 1] in ['^'] and s[i] in ['-']:
                    os.append([s[i], s[i + 1]])
                    skip = True
                else:
                    os.append(s[i])
            else:
                os.append(s[i])
        else:
            skip = False
    s = os

    os = []
    skip = 0
    for i in range(len(s)):  # Order of operations, collapse ^ commands
        if not skip:
            if s[i] in ['^']:
                p = os.pop(-1)
                os.append((s[i], p, s[i + 1]))
                skip = True
            else:
                os.append(s[i])
        else:
            skip = False
    s = os

    os = []
    skip = 0
    for i in range(len(s)):  # Order of operations, collapse unary commands
        if not skip:
            if s[i] in ['-']:
                os.append((s[i], s[i + 1]))
                skip = True
            else:
                os.append(s[i])
        else:
            skip = False
    s = os

    os = []
    skip = 0
    for i in range(len(s)):  # Order of operations, collapse *, /, % commands
        if not skip:
            if s[i] in ['*', '/', '%']:
                p = os.pop(-1)
                os.append((s[i], p, s[i + 1]))
                skip = True
            else:
                os.append(s[i])
        else:
            skip = False
    s = os

    os = []
    skip = 0
    for i in range(len(s)):  # Order of operations, collapse +,- commands
        if not skip:
            if s[i] in ['+']:
                p = os.pop(-1)
                os.append((s[i], p, s[i + 1]))
                skip = True
            else:
                os.append(s[i])
        else:
            skip = False
    s = os

    os = []
    skip = 0
    for i in range(len(s)):  # Order of operations, collapse comp commands
        if not skip:
            if s[i] in ["<", "<=", "==", ">", ">=", "!=", "vs"]:
                p = os.pop(-1)
                os.append((s[i], p, s[i + 1]))
                skip = True
            else:
                os.append(s[i])
        else:
            skip = False
    s = os

    os = []
    skip = 0
    for i in range(len(s)):  # Order of operations, collapse x commands
        if not skip:
            if s[i] == 'x':
                p = os.pop(-1)
                os.append((s[i], p, s[i + 1]))
                skip = True
            else:
                os.append(s[i])
        else:
            skip = False
    s = os
    return (s[0])


def cal(parsing, meta=''):
    global funcs
    if type(parsing) == int:
        return (parsing)
    elif len(parsing) == 1:
        return (parsing[0])
    else:
        if len(parsing) == 2:
            code, X = parsing
            Y = ''
        else:
            code, X, Y = parsing
        if code != 'x':
            Xl = type(X) == list
            Yl = type(Y) == list
            if Xl and Yl:
                r = [funcs[code](cal(X[i]), cal(Y[i])) for i in range(len(X))]
            elif Xl and not Yl:
                r = [funcs[code](cal(X[i]), cal(Y)) for i in range(len(X))]
            elif not Xl and Yl:
                r = [funcs[code](cal(X), cal(Y[i])) for i in range(len(Y))]
            else:
                r = funcs[code](cal(X), cal(Y))
            return r
        else:
            Xl = type(X) == list
            if not Xl:
                return [cal(Y) for i in range(X)]
            else:
                return [[cal(Y) for i in range(x)] for x in Xl]


def roll(n, d):
    return (sum([random.randint(1, d) for i in range(n)]))


def rollsep(n, d):
    return ([random.randint(1, d) for i in range(n)])


def top(s, n):
    if n == 1:
        return (max(s))
    else:
        return (sorted(s)[:-n])


def bottom(s, n):
    if n == 1:
        return (min(s))
    else:
        return (sorted(s)[:n])


def add(x, y):
    return (x + y)


def negative(x, null):
    return (-x)


def prod(x, y):
    return (x * y)


def div(x, y):
    return (x // y)


def mod(x, y):
    return (x % y)


def less(x, y):
    return (x < y)


def lesseq(x, y):
    return (x <= y)


def equal(x, y):
    return (x == y)


def great(x, y):
    return (x > y)


def greateq(x, y):
    return (x >= y)


def noteq(x, y):
    return (x != y)


def vs(x, y):
    if x < y:
        return (-1)
    elif x == y:
        return (0)
    else:
        return (1)


ops = ["x", "d", "sd", "t", "b", "^", "+", "-", "*", "/", "%", "<", "<=", "==", ">", ">=", "!=", "vs"]
funcs = {"d": roll, "sd": rollsep, "t": top, "b": bottom, "^": pow, "+": add, "-": negative, "*": prod, "/": div,
         "%": mod, "<": less, "<=": lesseq, "==": equal, ">": great, ">=": greateq, "!=": noteq, "vs": vs}
