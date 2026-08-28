import pickle,collections,statistics,json
G=pickle.load(open('/Users/nickzwart/Desktop/PTCG-AI-Challenge/analysis/pal/games.pkl','rb'))

def snap(g,T):
    best=None
    for d in sorted(g['decs'],key=lambda x:x['step']):
        if d['turn']<=T and d['turn']>=1: best=d
    return best

def curve(sub,label):
    print('\n--- %s n=%d'%(label,len(sub)))
    print('  turn |  his prizes taken | opp prizes taken | diff')
    for T in (4,8,12):
        me=[];op=[]
        for g in sub:
            d=snap(g,T)
            if not d: continue
            me.append(6-d['me']['prizeRem']); op.append(6-d['op']['prizeRem'])
        if me: print('   %3d  |   %.2f            |   %.2f           | %+.2f  (n=%d)'%(T,statistics.mean(me),statistics.mean(op),statistics.mean(me)-statistics.mean(op),len(me)))
    fin_me=[];fin_op=[];length=[]
    for g in sub:
        ds=sorted(g['decs'],key=lambda x:x['step'])
        last=[d for d in ds if d['turn']>=1]
        last=last[-1] if last else ds[-1]
        fin_me.append(6-last['me']['prizeRem']); fin_op.append(6-last['op']['prizeRem'])
        length.append(max(d['turn'] for d in ds))
    print('  FINAL |   %.2f            |   %.2f           | %+.2f ; mean game length %.1f turns'%(
        statistics.mean(fin_me),statistics.mean(fin_op),statistics.mean(fin_me)-statistics.mean(fin_op),statistics.mean(length)))

print('=== PRIZE CURVE (prizes TAKEN, cumulative by end of turn T) ===')
curve([g for g in G if g['won']],'WINS')
curve([g for g in G if not g['won']],'LOSSES')
for arch in ('Alakazam','Grimmsnarl','MFroslass/MLopunny','Dragapult','MKangaskhan','MLucario'):
    sub=[g for g in G if g['arch']==arch]
    curve(sub,'ALL vs '+arch)
    curve([g for g in sub if g['won']],'  WINS vs '+arch)
    curve([g for g in sub if not g['won']],'  LOSSES vs '+arch)
