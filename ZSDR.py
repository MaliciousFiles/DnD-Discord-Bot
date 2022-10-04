#V2.0: changes: x op is now the lowest operation, so 2x d6+5 would run d6+5 twice, rather than the accidentally working [1,1]d6+5, reworked roll_dice to detect complexity of statement and potentially run it in the simple command
#       function allowing for crit tracking.
#V2.1: Added half calculation to show crits and fancy intermediate steps for non super complex functions. Fixed some bugs.

import random

def roll_dice(txt):
    txt=clean(txt)
    comp=0
    if 'd' in txt:
        o,e=txt.split('d',1)
        if o=='':
            o=1
        elif o.isdigit():
            o=int(o)
        else:
            comp=1
        if e.isdigit() and comp==0:
            c,ro=simple(o,int(e))
        elif comp==0:
            if '+' in e:
                e,v=e.split('+',1)
                if v.isdigit():
                    c,ro=simple(o,int(e),int(v))
                else:
                    comp=1
            elif '-' in e:
                e,v=e.split('-',1)
                if v.isdigit():
                    c,ro=simple(o,int(e),-int(v))
                else:
                    comp=1
            else:
                comp=1
    else:
        comp=1
    if comp==1:
        try:
            p = parse(txt)
        except:
            raise RuntimeError(f'Parsing Error: {txt}')
        try:
            o=hcompcal(p)
            if type(o)==list:
                c='**Result:**\n'+'\n'.join([v[0]+' **=** '+str(v[1]) for v in o])
                ro=[v[1] for v in o]
            else:
                c='**Result:** '+o[0]+'\n**Total:** '+str(o[1])
                ro=o[1]
        except:
            comp=2 #Code is not comp lvl 1
    if comp==2:
        try:
            p = parse(txt)
        except:
            raise RuntimeError(f'Parsing Error: {txt}')
        try:
            v = cal(p)
        except:
            raise RuntimeError(f'Computation Error: {txt}')
        c='**Result:** Too Complex'+'\n**Total:** '+str(v)
        ro=v
    return(c,ro)
def simple(n,s,v=''):
    rs=rollsep(n,s)
    ors=rs
    c=[]
    if s==20:
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
    return ''.join([c for c in txt.lower() if c!=" "])
def parse(code):
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
            s.append(parse(ss))
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
            if i==0:
                alt=1
            elif s[i-1] in ops:
                alt=1
            if alt:
                os.append(1)
        if s[i]=='-':#checks for subtraction, and converts it to addition and negation
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
def halfcal(parsing):
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
                calX,p1=halfcal(X)
                calY,p2=halfcal(Y)
                cY=str(calY)
                cX=str(calX)
                r2=(code,p1,p2)
            else:
                calX,p1=halfcal(X)
                cX=''
                cY=str(calX)
                r2=(code,p1)
            r=cX+code+cY
        elif code=='d':
            calX,p1=halfcal(X)
            calY,p2=halfcal(Y)
            t=funcs['sd'](calX,calY)
            if calY==20:
                t2=['**'*(r==20)+'***'*(r==1)+str(r)+'**'*(r==20)+'***'*(r==1) for r in t]
            else:
                t2=[str(r) for r in t]
            r = '('+'+'.join(t2)+')'
            r2=sum(t)
        elif code=='sd':
            calX,p1=halfcal(X)
            calY,p2=halfcal(Y)
            t=funcs['sd'](calX,calY)
            if calY==20:
                t2=['**'*(r==20)+'***'*(r==1)+str(r)+'**'*(r==20)+'***'*(r==1) for r in t]
            else:
                t2=[str(r) for r in t]
            r = '01'[calY==20]+'['+', '.join(t2)+']'
            r2=t
        elif code=='t':
            calX,p1=halfcal(X)
            calY,p2=halfcal(Y)
            S=20*int(calX[0])
            t=sorted(p1,reverse=1)
            if S==20:
                t2=['~~'*(i>=calY)+'**'*(t[i]==20)+'***'*(t[i]==1)+str(t[i])+'**'*(t[i]==20)+'***'*(t[i]==1)+'~~'*(i>=calY) for i in range(len(t))]
            else:
                t2=['~~'*(i>=calY)+str(t[i])+'~~'*(i>=calY) for i in range(len(t))]
            r = calX[0]+'['+', '.join(t2)+']'
            r2=funcs[code](p1,p2)
        elif code=='b':
            calX,p1=halfcal(X)
            calY,p2=halfcal(Y)
            S=20*int(calX[0])
            t=sorted(p1)
            if S==20:
                t2=['~~'*(i>=calY)+'**'*(t[i]==20)+'***'*(t[i]==1)+str(t[i])+'**'*(t[i]==20)+'***'*(t[i]==1)+'~~'*(i>=calY) for i in range(len(t))]
            else:
                t2=['~~'*(i>=calY)+str(t[i])+'~~'*(i>=calY) for i in range(len(t))]
            r = calX[0]+'['+', '.join(t2)+']'
            r2=funcs[code](p1,p2)
        elif code=='x':
            raise RuntimeError(f'OperandError: {parsing}')
        return r,r2#returns a the unparsed code with the dice values computed, and the reparsed code to give the correct solution
def hcompcal(parsing):
    if parsing[0]=='x' and type(parsing[1])==int:
        P=parsing[2]
        return [hcompcal(P) for i in range(parsing[1])]
    else:
        P=parsing
        ft,hp=halfcal(P)
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
