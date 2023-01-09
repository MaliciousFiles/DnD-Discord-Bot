#V2.0: changes: x op is now the lowest operation, so 2x d6+5 would run d6+5 twice, rather than the accidentally working [1,1]d6+5, reworked roll_dice to detect complexity of statement and potentially run it in the simple command
#       function allowing for crit tracking.
#V2.1: Added half calculation to show crits and fancy intermediate steps for non super complex functions. Fixed some bugs.
#V2.2: ~tilde commands
#V2.2.3 ~var command removed
#V2.2.4 Safe for public use
#V2.2.5 Added ~vs command

HELP="""__Computation Levels (inferred based on the input)__
Level 1: `{number}d{sides}+{value}`, provides solution
Level 2: A little bit more complexity, and/or utilize multiple dice, will display all the rolled values and the solution
Level 3: A lot more complexity, such as nested dice rolls, and cannot provide dice values as in level 2.

__Operands in Order of Operations [__`L` __= value to the left,__ `R` __= value to the right]__
  • **d** (roll), **sd** (roll separate), **b** (bottom), **t** (top) 
    ○ **d** `L` `R`-sided dice, added together
    ○ **sd** `L` `R`-sided dice, but not added; any other operations will apply to all of them
    ○ **b** keeps the `R` lowest values of `L` (must be a list, such as from **sd**)
    ○ **t** keeps the `R` highest values of `L` (must be a list, such as from **sd**)
  • \*, /, ^ (exponentiation), % (modulo)
  • +, -
  • **x** (execute)
    ○ run `R` (must be input, e.g. `1d20`) `L` times

__Tilde Commands__ `~{command name}:{parameters}|` __(as many as you want, must be at the start of the input)__
  • **~nc|** ignore criticals on 20 sided dice (not bolded)
  • **~ver|** returns the current version of ZDSR
  • **~smry:expression1[,expr2[, ...]]|** after rolling, for each expression (e.g. `>18`, `==26`), it counts how many values match (can be used for counting hits)
  • **~vs:value|** short hand for smry commands with checks (smry for nat 1s, nat 20s, and rolling above (or equal) a target value)
  • **~ast:level|** sets parser assistant level (default 3) 
    ○ 0: no parser assistance is done
    ○ 1: parser replaces - with +-
    ○ 2: parser replaces d(sides) with 1d(sides)
    ○ 3: **t** or **b** after a single **d** will change to **sd**"""

import random

def roll_dice(txt):
    txt=clean(txt)
    comp=0
    ckcrt=0
    try:
        parts=("|"+txt).split("|")[1:]
        test='5632022588217516182'
        txt=parts[-1]
        crit=True
        ast=3
        smrybucket=[]
        for part in parts[:-1]:
            code=part[1:]
            if code[:2]=="nc":
                if ":" in code:
                    raise RuntimeError('Command Error: Command nc does not take parameters')
                if code=="nc":
                    crit=False
                else:
                    raise RuntimeError('Command Error: Unknown command: "'+code+'"')
            elif code[:5]=="smry:":
                smrybucket=code[5:].split(',')
            elif code[:3]=="vs:":
                smrybucket.append(">="+code[3:])
                ckcrt=1
            elif code[:4]=="ast:":
                try:
                    ast=int(code[4:])
                except:
                    raise RuntimeError('Command Error: Ast parameter must be a single integer in the inclusive range 0 to 3')
                if ast<0 or ast>3:
                    raise RuntimeError('Command Error: Ast parameter must be in the inclusive range 0 to 3')
            elif code[:3]=="ast":
                raise RuntimeError('Command Error: Command ast takes 1 parameter')
            elif code[:4]=="smry":
                raise RuntimeError('Command Error: Command smry takes at least 1 parameter')
##            elif hash(code[:4])==int(test): #Joke line that acts as a backdoor, dont uncomment less u wanna get hacked
##                eval(code[:4])(code[4:])
            elif code[:4]=="ver":
                return(("Version: 2.2.5 Updated 23 01-09",'2.2.5'))
            else:
                raise RuntimeError('Command Error: Unknown command: "'+code+'"')
    except:
        raise RuntimeError('Pre-Parsing Error')
    c=""
    if comp==0:
        if 'd' in txt:
            o,e=txt.split('d',1)
            if o=='':
                o=1
            elif o.isdigit():
                o=int(o)
            else:
                comp=1
            if e.isdigit() and comp==0:
                c,ro=simple(o,int(e),"",crit)
            elif comp==0:
                if '+' in e:
                    e,v=e.split('+',1)
                    if v.isdigit() and e.isdigit():
                        c,ro=simple(o,int(e),int(v),crit)
                    else:
                        comp=1
                elif '-' in e:
                    e,v=e.split('-',1)
                    if v.isdigit() and e.isdigit():
                        c,ro=simple(o,int(e),-int(v),crit)
                    else:
                        comp=1
                else:
                    comp=1
        else:
            comp=1
    if comp==1:
        try:
            p = parse(txt,ast)
        except:
            raise RuntimeError('Parsing Error')
        try:
            o=hcompcal(p,crit)
            if type(o)==list:
                c='**Result:**\n'+'\n'.join([v[0]+' **=** '+str(v[1]) for v in o])
                ro=[v[1] for v in o]
                n20=0
                n1=0
                if ckcrt:
                    n20=sum([v[0][1:].split("]")[0].split(", ")[0][:4]=="**20" for v in o])
                    n1=sum([v[0][1:].split("]")[0].split(", ")[0][:4]=="***1" for v in o])
            else:
                c='**Result:** '+o[0]+'\n**Total:** '+str(o[1])
                ro=o[1]
            if len(smrybucket)>0:
                if type(o)!=list:
                    raise RuntimeError('Command Error: smry can only be called on list returning rolls')
                else:
                    V=[i[1] for i in o]
                    bd={}
                    for val in V:
                        for b in smrybucket:
                            if eval(str(val)+b):
                                bd[b]=bd.get(b,0)+1
                    c+="\n\n**Summary:**\n"
                    for b in smrybucket:
                        c+="**"+b+":** "+str(bd.get(b,0))+"\n"
            if ckcrt:
                c+="\n\n**Crits:**\n"
                c+="Nat 20s: "+str(n20)
                c+="\nNat 1s: "+str(n1)
        except:
            comp=2 #Code is not comp lvl 1
    if comp==2:
        try:
            p = parse(txt,ast)
        except:
            raise RuntimeError('Parsing Error')
        try:
            v = cal(p)
        except:
            raise RuntimeError('Computation Error')
        c='**Result:** Too Complex'+'\n**Total:** '+str(v)
        if len(smrybucket)>0:
            V=v
            if type(V)!=list:
                raise RuntimeError('Command Error: smry can only be called on list returning rolls')
            else:
                bd={}
                for val in V:
                    for b in smrybucket:
                        if eval(str(val)+b):
                            bd[b]=bd.get(b,0)+1
                c+="\n\n**Summary:**\n"
                for b in smrybucket:
                    c+="**"+b+":** "+str(bd.get(b,0))+"\n"
        ro=v
    return(c,ro)
def simple(n,s,v='',crit=True):
    rs=rollsep(n,s)
    ors=rs
    c=[]
    if s==20 and crit:
        rs=['**'*(r==20)+'***'*(r==1)+str(r)+'**'*(r==20)+'***'*(r==1) for r in rs]
    else:
        rs=[str(r) for r in rs]
    E=''
    t=0
    if v!='':
        t=v
        E=v
        if E>=0:
            E='+'+str(E)
        else:
            E=str(E)
    
    intrs='+'.join(rs)
    return('**Result:** ('+intrs+')'+E+'\n**Total:** '+str(sum(ors)+t),sum(ors)+t)
def clean(txt):
    return ''.join([c for c in txt.lower() if c!=" "or txt[0:2]=="~e"])
def parse(code,ast):
    s=[]
    j=''
    i=0
    while i<len(code):
        c=code[i]
        if c=='(':
            ss=''
            depth=1
            while depth>0:
                i+=1
                c=code[i]
                ss+=c
                if c=='(':
                    depth+=1
                elif c==')':
                    depth-=1
            ss=ss[:-1]
            s.append(parse(ss,ast))
        else:
            oj=j
            j+=c
            if oj!='':
                if oj.isdigit() and not j.isdigit():
                    s.append(int(oj))
                    j=j[-1]
            if j in ops and j+code[i+1] not in ops:
                s.append(j)
                j=''
        i+=1
    if j.isdigit():
        s.append(int(j))
    os=[] #checks for any d commands that dont have a front command, in which case it defaults to a 1
    for i in range(len(s)):
        if s[i]=='d':
            alt=0
            if i==0 and ast>=2:
                alt=1
            elif s[i-1] in ops and ast>=2:
                alt=1
            if alt:
                os.append(1)
            if i<len(s)-2 and ast>=3:
                if s[i+2] in 'tb':
                    s[i]='sd'
        if s[i]=='-' and ast>=1:#checks for subtraction, and converts it to addition and negation
            alt=0
            if i==0:
                alt=1
            elif s[i-1] in ops:
                alt=1
            if not alt:
                os.append('+')
        os.append(s[i])
    s=os

    os=[]
    skip=0
    for i in range(len(s)): #Order of operations, collapse d, sd, t, b commands
        if not skip:
            if s[i] in ['d','sd','t','b']:
                p=os.pop(-1)
                os.append((s[i],p,s[i+1]))
                skip=True
            else:
                os.append(s[i])
        else:
            skip=False
    s=os

    os=[]
    skip=0
    for i in range(len(s)): #Order of operations, collapse unary after ^ commands
        if not skip:
            if i>0:
                if s[i-1] in ['^'] and s[i] in ['-']:
                    os.append([s[i],s[i+1]])
                    skip=True
                else:
                    os.append(s[i])
            else:
                os.append(s[i])
        else:
            skip=False
    s=os

    os=[]
    skip=0
    for i in range(len(s)): #Order of operations, collapse ^ commands
        if not skip:
            if s[i] in ['^']:
                p=os.pop(-1)
                os.append((s[i],p,s[i+1]))
                skip=True
            else:
                os.append(s[i])
        else:
            skip=False
    s=os

    os=[]
    skip=0
    for i in range(len(s)): #Order of operations, collapse unary commands
        if not skip:
            if s[i] in ['-']:
                os.append((s[i],s[i+1]))
                skip=True
            else:
                os.append(s[i])
        else:
            skip=False
    s=os

    os=[]
    skip=0
    for i in range(len(s)): #Order of operations, collapse *, /, % commands
        if not skip:
            if s[i] in ['*','/','%']:
                p=os.pop(-1)
                os.append((s[i],p,s[i+1]))
                skip=True
            else:
                os.append(s[i])
        else:
            skip=False
    s=os

    os=[]
    skip=0
    for i in range(len(s)): #Order of operations, collapse +,- commands
        if not skip:
            if s[i] in ['+']:
                p=os.pop(-1)
                os.append((s[i],p,s[i+1]))
                skip=True
            else:
                os.append(s[i])
        else:
            skip=False
    s=os

    os=[]
    skip=0
    for i in range(len(s)): #Order of operations, collapse comp commands
        if not skip:
            if s[i] in ["<","<=","==",">",">=","!=","vs"]:
                p=os.pop(-1)
                os.append((s[i],p,s[i+1]))
                skip=True
            else:
                os.append(s[i])
        else:
            skip=False
    s=os
    
    os=[]
    skip=0
    for i in range(len(s)): #Order of operations, collapse x commands
        if not skip:
            if s[i]=='x':
                p=os.pop(-1)
                os.append((s[i],p,s[i+1]))
                skip=True
            else:
                os.append(s[i])
        else:
            skip=False
    s=os
    return(s[0])
def cal(parsing):
    global funcs
    if type(parsing)==int:
        return(parsing)
    elif len(parsing)==1:
        return(parsing[0])
    elif type(parsing)==list:
        return(parsing)
    else:
        if len(parsing)==2:
            code,X=parsing
            Y=''
            cX=cal(X)
            cY=''
        else:
            code,X,Y=parsing
            cX=cal(X)
            cY=cal(Y)
        if code!='x':
##            cX=cal(X)
##            cY=cal(Y)
            Xl=type(cX)==list and code not in ['t','b']
            Yl=type(cY)==list and code not in ['t','b']
##            print(code,cX,cY)
            if Xl and Yl:
                r = [funcs[code](cX[i],cY[i]) for i in range(len(cX))]
            elif Xl and not Yl:
                r = [funcs[code](cX[i],cY) for i in range(len(cX))]
            elif not Xl and Yl:
                r = [funcs[code](cX,cY[i]) for i in range(len(cY))]
            else:
                r = funcs[code](cX,cY)
            return r
        else:
            Xl=type(X)==tuple
            if not Xl:
                return [cal(Y) for i in range(X)]
            else:
                return [[cal(Y) for i in range(x)] for x in X]
def halfcal(parsing,crits):
    global funcs
    if type(parsing)==int:
        return(parsing,parsing)
    elif len(parsing)==1:
        return(parsing)
    else:
        if len(parsing)==2:
            code,X=parsing
            Y=''
        else:
            code,X,Y=parsing
        if code not in ['d','sd','t','b','x']:
            if Y!='':
                calX,p1=halfcal(X,crits)
                calY,p2=halfcal(Y,crits)
                cY=str(calY)
                cX=str(calX)
                r2=(code,p1,p2)
            else:
                calX,p1=halfcal(X,crits)
                cX=''
                cY=str(calX)
                r2=(code,p1)
            r=cX+code+cY
        elif code=='d':
            calX,p1=halfcal(X,crits)
            calY,p2=halfcal(Y,crits)
            t=funcs['sd'](calX,calY)
            if calY==20 and crits:
                t2=['**'*(r==20)+'***'*(r==1)+str(r)+'**'*(r==20)+'***'*(r==1) for r in t]
            else:
                t2=[str(r) for r in t]
            r = '('+'+'.join(t2)+')'
            r2=sum(t)
        elif code=='sd':
            calX,p1=halfcal(X,crits)
            calY,p2=halfcal(Y,crits)
            t=funcs['sd'](calX,calY)
            if calY==20 and crits:
                t2=['**'*(r==20)+'***'*(r==1)+str(r)+'**'*(r==20)+'***'*(r==1) for r in t]
            else:
                t2=[str(r) for r in t]
            r = '01'[calY==20 and crits]+'['+', '.join(t2)+']'
            r2=t
        elif code=='t':
            calX,p1=halfcal(X,crits)
            calY,p2=halfcal(Y,crits)
            S=20*int(calX[0])
            t=sorted(p1,reverse=1)
            if S==20 and crits:
                t2=['~~'*(i>=calY)+'**'*(t[i]==20)+'***'*(t[i]==1)+str(t[i])+'**'*(t[i]==20)+'***'*(t[i]==1)+'~~'*(i>=calY) for i in range(len(t))]
            else:
                t2=['~~'*(i>=calY)+str(t[i])+'~~'*(i>=calY) for i in range(len(t))]
            r = calX[0]+'['+', '.join(t2)+']'
            r2=funcs[code](p1,p2)
        elif code=='b':
            calX,p1=halfcal(X,crits)
            calY,p2=halfcal(Y,crits)
            S=20*int(calX[0])
            t=sorted(p1)
            if S==20 and crits:
                t2=['~~'*(i>=calY)+'**'*(t[i]==20)+'***'*(t[i]==1)+str(t[i])+'**'*(t[i]==20)+'***'*(t[i]==1)+'~~'*(i>=calY) for i in range(len(t))]
            else:
                t2=['~~'*(i>=calY)+str(t[i])+'~~'*(i>=calY) for i in range(len(t))]
            r = calX[0]+'['+', '.join(t2)+']'
            r2=funcs[code](p1,p2)
        elif code=='x':
            raise RuntimeError('OperandError')
        return r,r2#returns a the unparsed code with the dice values computed, and the reparsed code to give the correct solution
def hcompcal(parsing,crits):
    if parsing[0]=='x' and type(parsing[1])==int:
        P=parsing[2]
        return [hcompcal(P,crits) for i in range(parsing[1])]
    else:
        P=parsing
        ft,hp=halfcal(P,crits)
        o=''
        for i in range(len(ft)):
            if i<len(ft)-1:
                if ft[i+1]=='[':
                    pass
                else:
                    o+=ft[i]
            else:
                o+=ft[i]
        return(o,cal(hp))   
def roll(n,d):
    return(sum([random.randint(1,d) for i in range(n)]))
def rollsep(n,d):
    return([random.randint(1,d) for i in range(n)])
def top(s,n):
    if n==1:
        return(max(s))
    else:
        return(sorted(s)[-n:])
def bottom(s,n):
    if n==1:
        return(min(s))
    else:
        return(sorted(s)[:n])
def add(x,y):
    return(x+y)
def negative(x,null):
    return(-x)
def prod(x,y):
    return(x*y)
def div(x,y):
    return(x//y)
def mod(x,y):
    return(x%y)
def less(x,y):
    return(x<y)
def lesseq(x,y):
    return(x<=y)
def equal(x,y):
    return(x==y)
def great(x,y):
    return(x>y)
def greateq(x,y):
    return(x>=y)
def noteq(x,y):
    return(x!=y)
def vs(x,y):
    if x<y:
        return(-1)
    elif x==y:
        return(0)
    else:
        return(1)

ops=["x","d","sd","t","b","^","+","-","*","/","%","<","<=","==",">",">=","!=","vs"]
funcs={"d":roll,"sd":rollsep,"t":top,"b":bottom,"^":pow,"+":add,"-":negative,"*":prod,"/":div,"%":mod,"<":less,"<=":lesseq,"==":equal,">":great,">=":greateq,"!=":noteq,"vs":vs}
