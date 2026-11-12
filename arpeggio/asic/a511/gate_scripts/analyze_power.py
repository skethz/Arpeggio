#!/usr/bin/env python3
"""ASIC-server-only aggregation of one gate_r4 Innovus power case (Python 3.6). Reads the private reports of CASE_DIR and the
session's insts_private.tsv and writes CASE_DIR/public_summary.json with aggregates only (no instance/net/cell/library
names). Template: an earlier project analysis script. usage: analyze_power.py SESSION_DIR TAG AREA_PUBLIC_TXT"""
import base64, collections, json, os, re, subprocess, sys
sess, tag, area_f = sys.argv[1:4]
d = os.path.join(sess, tag)

def num(pat, text):
    m = re.search(pat, text, re.M)
    return float(m.group(1)) if m else None

def power(path):
    t = open(path).read()
    out = dict(int_mw=num(r'^Total Internal Power:\s+(\S+)', t), sw_mw=num(r'^Total Switching Power:\s+(\S+)', t),
               leak_mw=num(r'^Total Leakage Power:\s+(\S+)', t), tot_mw=num(r'^Total Power:\s+(\S+)', t))
    m = re.search(r'annotation coverage:\s*(\d+)/(\d+)', t)
    out['design_annotation'] = [int(m.group(1)), int(m.group(2))] if m else None
    g = {}
    for mm in re.finditer(r'^(Sequential|Macro|IO|Physical-Only|Combinational|Clock \(Combinational\)|Clock \(Sequential\))\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', t, re.M):
        g[mm.group(1)] = dict(zip(('int_mw', 'sw_mw', 'leak_mw', 'tot_mw'), map(float, mm.groups()[1:])))
    out['groups'] = g
    out['seq_default_activity'] = num(r'Sequential Element Activity:\s*(\S+)', t)
    out['pi_default_activity'] = num(r'Primary Input Activity:\s*(\S+)', t)
    out['clock_period'] = num(r'Clock Period:\s*(\S+)', t)
    out['clock_toggle_rate'] = num(r'Clock Toggle Rate:\s*(\S+)', t)
    m = re.search(r'Clock Toggle Rate:\s*\S+\s*(\S*)', t)
    out['clock_toggle_rate_unit'] = m.group(1) if m else None
    return out

def tcl_list(path):
    env = dict(os.environ, R4_LIST=path)
    script = b'set f [open $::env(R4_LIST) r]; set d [read $f]; close $f; foreach n $d {puts [binary encode base64 -maxlen 0 $n]}\n'
    raw = subprocess.check_output(['tclsh'], input=script, env=env)
    names = [base64.b64decode(x).decode() for x in raw.splitlines()]
    assert len(names) == len(set(names)), path
    return set(names)

tt = power(d + '/power_tt.rpt')
after = open(d + '/activity_after_private.rpt').read()
pi = re.search(r'Primary inputs annotated:\s*(\d+)/(\d+)', after); so = re.search(r'Sequential outputs annotated:\s*(\d+)/(\d+)', after)
src = {r: tcl_list('%s/source_%s_private.rpt' % (d, r)) for r in ('activity_file', 'propagated', 'default', 'set_switching_activity')}
drv = {r: tcl_list('%s/driver_%s_private.rpt' % (d, r)) for r in ('primary_inputs', 'sequential', 'combinational', 'ICG', 'memory', 'black_box')}
allnets = set().union(*src.values())
insts = {}
for line in open(sess + '/insts_private.tsv'):
    p = line.rstrip('\n').split('\t')
    unb = lambda x: x[1:-1] if x.startswith('{') and x.endswith('}') else x
    insts[unb(p[0])] = dict(seq=p[1] == '1', phys=p[2] == '1', base=p[3], outs=[unb(x) for x in p[4].split()] if len(p) > 4 and p[4] else [])
ip = {}
lines = open(d + '/insts_power_tt_private.rpt').read().splitlines()
i = next(k for k, l in enumerate(lines) if l.startswith('Instance') and 'Max Toggles' in l) + 3
pend = None
for l in lines[i:]:
    a = l.split()
    if a and a[0] == 'Total' and pend is None:
        break
    if not a or l.startswith('-') or l.startswith('*'):
        continue
    if len(a) == 1:
        pend = a[0]; continue
    if pend is not None and len(a) == 8:
        name, vals = pend, a
    elif len(a) == 9:
        name, vals = a[0], a[1:]
    else:
        raise ValueError('unparsed line: %d tokens' % len(a))
    pend = None
    ip[name] = dict(int=float(vals[2]), sw=float(vals[3]), leak=float(vals[4]), tot=float(vals[5]))
inst_sum = sum(v['tot'] for v in ip.values())
unmatched = [n for n in ip if n not in insts]
INS = re.compile(r'(^|/)(CTS_|FE_|V2_TIE)')
icg_nets = drv['ICG']
cls = collections.Counter(); pwr = collections.Counter(); kind_n = collections.Counter(); kind_p = collections.Counter(); fe_n = collections.Counter(); fe_p = collections.Counter()
ff_tot = ff_ann = 0; mac_tot = mac_ann = 0
for n, v in insts.items():
    if v['phys']:
        continue
    inserted = bool(INS.search(n))
    ann = any(o in src['activity_file'] for o in v['outs'])
    is_icg = any(o in icg_nets for o in v['outs'])
    is_macro = v['base'] == 'block'
    is_ff = v['seq'] and not is_icg and not is_macro
    if is_ff:
        ff_tot += 1; ff_ann += ann
    if is_macro:
        mac_tot += 1; mac_ann += ann
    key = ('inserted' if inserted else 'synthesis') + '/' + ('annotated' if ann else 'propagated')
    cls[key] += 1; pwr[key] += ip.get(n, dict(tot=0.0))['tot']
    m = re.search(r'(^|/)(CTS_|FE_|V2_TIE)', n)
    k = m.group(2).rstrip('_') if m else 'synthesis'
    kind_n[k] += 1; kind_p[k] += ip.get(n, dict(tot=0.0))['tot']
    mf = re.search(r'(^|/)FE_([A-Za-z]+)', n)
    if mf:
        fe_n[mf.group(2)] += 1; fe_p[mf.group(2)] += ip.get(n, dict(tot=0.0))['tot']
    if is_icg:
        cls['icg'] += 1; pwr['icg'] += ip.get(n, dict(tot=0.0))['tot']
area = dict(zip(*[iter(open(area_f).read().split())] * 2))
net_total = len(allnets)
clock_mw = tt['groups'].get('Clock (Combinational)', {}).get('tot_mw', 0) + tt['groups'].get('Clock (Sequential)', {}).get('tot_mw', 0)
summary = dict(tag=tag, die_um2=float(area['die_um2']), core_um2=float(area['core_um2']), std_logic_um2=float(area['std_logic_um2']),
               macro_um2=float(area['macro_um2']),
               p_tt_mw=tt['tot_mw'], int_tt_mw=tt['int_mw'], sw_tt_mw=tt['sw_mw'], leak_tt_mw=tt['leak_mw'], groups_tt=tt['groups'],
               clock_network_mw=clock_mw, clock_network_share=clock_mw / tt['tot_mw'] if tt['tot_mw'] else None,
               clock_period=tt['clock_period'], clock_toggle_rate=tt['clock_toggle_rate'], clock_toggle_rate_unit=tt['clock_toggle_rate_unit'],
               design_annotation=tt['design_annotation'], default_activity=dict(seq=tt['seq_default_activity'], pi=tt['pi_default_activity']),
               primary_inputs_annotated=[int(pi.group(1)), int(pi.group(2))] if pi else None,
               sequential_outputs_annotated=[int(so.group(1)), int(so.group(2))] if so else None,
               nets=dict(total=net_total, **{k: len(v) for k, v in src.items()}),
               nets_activity_file_pct=100.0 * len(src['activity_file']) / net_total, nets_propagated_pct=100.0 * len(src['propagated']) / net_total,
               flipflops=dict(total=ff_tot, annotated=ff_ann, pct=100.0 * ff_ann / ff_tot if ff_tot else None),
               macros=dict(total=mac_tot, outputs_from_file=mac_ann),
               drivers={k: len(v) for k, v in drv.items()},
               instance_classes=dict(cls), instance_class_power_mw={k: round(v, 6) for k, v in pwr.items()},
               inserted_kinds_count=dict(kind_n), inserted_kinds_power_mw={k: round(v, 6) for k, v in kind_p.items()},
               fe_subkinds_count=dict(fe_n), fe_subkinds_power_mw={k: round(v, 6) for k, v in fe_p.items()},
               power_share_propagated=(pwr['synthesis/propagated'] + pwr['inserted/propagated']) / inst_sum,
               power_share_inserted=(pwr['inserted/propagated'] + pwr['inserted/annotated']) / inst_sum,
               instance_power_sum_mw=inst_sum, instance_power_rows=len(ip), instance_power_rows_unmatched=len(unmatched))
json.dump(summary, open(d + '/public_summary.json', 'w'), indent=1)
print(json.dumps({k: summary[k] for k in ('tag', 'p_tt_mw', 'leak_tt_mw', 'clock_network_mw', 'flipflops', 'nets_activity_file_pct',
                                          'power_share_propagated', 'power_share_inserted', 'instance_power_sum_mw', 'instance_power_rows_unmatched')}))
