# if you search for '<xymatrix' in the .log file you'll find the number of times used.. sadly we can't compile everysingle paper lol

import re

## REGEX and DICTIONARIES
# General Latex tokens
embed_brackets = lambda n : r'(?<bracket%i>(?<!\\)\{(?:[^\{\}]++|(?<=\\)\{|(?<=\\)\}|(?&bracket%i))*(?<!\\)\})' %(n,n)
not_special_char = r'[^\\\{\}_\^\|@$&]'
token = lambda n : r'(?:\\[a-zA-Z]+)|%s|%s' %(not_special_char,embed_brackets(n))
# Numbers
num_coeff = r'0?(?:\.\d+)?' # Matches in [0,1): 0.1, .1, 0.0, 0.1
number = r'-? ?(?:\d+)?(?:\.\d+)?' # Matches in \mathbb{R} with optional negative sign
units = r'pt|pc|in|bp|cm|mm|dd|cc|sp|ex|em|px'
dimen = r'%s ?(?:%s)' %(number, units)    # Any number with units
# XY's patterns
variant = r'\^|_|2|3' #gets distributed onto tip AND IF 2|3, also onto conn
conn_variant = r'2|3'
tip_dir = r'''
        <   |   #START (n)tail reversed END (n)head reversed
        >   |   #START (n)tail END . or nhead
        \|  |   #START maps to END maps from
        ’   |   #START hook END hook head
        ‘   |   #START hook'
        <<  |   #START two (n)tail reversed END two (n)head reversed
        >>  |   #START two (n)tail END two (n)head
        \|\||   #START two maps to END two maps from
        \(  |   #NOT SUPPORTED
        \)  |   #NOT SUPPORTED
        \+  |   #NOT SUPPORTED
        \/     #NOT SUPPORTED   ##TO DO: add more not-supported stuff to catch errors
    '''
tip_dict = {
            '<': ['tail reversed', 'ntail reversed', 'head reversed', 'nhead reversed'],  #can be harpooned with nfold = 1
            '>': ['tail', 'ntail', '', 'nhead'],     # third entry = default
            '|':['maps to', 'maps to','maps from', 'maps from'],  #can be harpooned with nfold = 1
            "'": ['hook', '','hook head', ''],    #nfold verions not supported
            "`": ["hook'", '',"hook' head", ''],  #nfold verions not supported
            '<<': ['two tails reversed', 'two ntails reversed', 'two heads reversed','two nheads reversed'],    #can be harpooned with nfold = 1
            '>>':['two tails', 'two ntails', 'two heads','two nheads'],     #can be harpooned with nfold = 1
            '||':['two maps to', 'two maps to', 'two maps from', 'two maps from'],    #can be harpooned with nfold = 1
            '(': ['','', '',''],  #NOT SUPPORTED
            ')':['','', '',''],   #NOT SUPPORTED
            '+':['','', '',''],   #NOT SUPPORTED
            '/':['','', '','']    #NOT SUPPORTED
}
tip_dir = re.sub(r'\s','', re.sub(r'#.*\n', '', tip_dir))
tip = r'(?:%s)? ?(?:\{(?:%s| |)\}|%s)' %(variant, tip_dir, tip_dir)
conn_dir = r'''
    -   |   # default OR scaling nfold = 2|3
    =   |   #equiv to 2-, can't be used with variants
    \.  |   # dotted
    :   |   #equiv to 2., can't be used with variants
    ~   |   #squiggly
    --  |   #dashed
    ==  |   #equive to 2--, can't be used with variants
    ~~    #NOT SUPPORTED
'''
conn_dict = {'-': '',  #default
             '=': '',  #default (equiv to 2-), can't be used with variants
             '.': 'dotted',
             ':': 'dotted',  #equiv to 2., can't be used with variants
             '~':'squiggly',
             '--': 'dashed',
             '==': 'dashed'  #equiv to 2--, can't be used with variants
}
conn_dir = re.sub(r'\s','', re.sub(r'#.*\n', '', conn_dir))
conn = r'(?:%s)? ?(?:\{(?:%s| |)\}|%s)' %(conn_variant, conn_dir, conn_dir)
curve = r'(?:\^|_) ?(?:%s)?' %dimen
shift = r'(?:%s)?' %dimen
pos_label = r'(?:[\<\>]+)|(?:\( ?%s ?\))' %num_coeff
# XY's \ar
ar = r'''\\ar ?#
        (?:#
            (?<style>@ ?(?<variant>%s)? ?\{ ?(?<start>%s)?? ?(?<conn>%s)? ?(?<end>%s)? ?\} ?)|#
            (?:@ ?\/ ?(?<curve>%s) ?\/ ?)|#
            (?:@ ?\< ?(?<shift>%s) ?\> ?)#
        )*#
        (?:#
            (?:\[ ?(?<dir>[udlr]+) ?\] ?)|#
            (?<endpts>\" ?.+ ?\" ?; ?\" ?.+ ?\" ?)|#
            (?:#
                \^ ?#
                (?<uppos>%s)? ?#
                (?<uplabel>%s) ?#
                (?:= ?\" ?(?<upalias>.+) ?\")? ?#
            )|#
            (?:#
                _ ?#
                (?<downpos>%s)? ?#
                (?<downlabel>%s) ?#
                (?:= ?\" ?(?<downalias>.+) ?\")? ?#
            )|#
            (?:#
                \| ?#
                (?<midpos>%s)? ?#
                (?<midlabel>%s) ?#
                (?:= ?\" ?(?<midalias>.+) ?\")? ?#
            )#
        )+#
        ''' %(variant,tip,conn,tip, curve, shift, pos_label, token(0), pos_label, token(1), pos_label, token(2))
ar =re.sub(r'\#\s*','', ar)
print(ar)
find_ar = re.compile(ar)
# XY's \xymatrix
find_xymatrix = re.compile(r'\\xymatrix ?(?<options>[^\{}]*)%s' %(embed_brackets(0)))
add_op = r'\+|-|=|\+=|-='
xy_options = r'(?<axis>R|C|)(?<addop>%s)(?<dimen>%s|R|C)|(?<fixed>!R|!C|!)' %(add_op, dimen)

def replace_ar(match):
    arrow = []  #list of arguments
    # End points
    if match.group('dir'):
        arrow.append(match.group('dir'))
    elif match.group('endpts'):
       end_points = re.search(r"\"(?<start>.+)\";\"(?<end>.+)\"", match.group('endpts'))
       arrow.append('from=' + end_points.group('start'))
       arrow.append('to=' + end_points.group('end'))
    # Labels
    if match.group('uplabel'):
        label = '"{'+match.group('uplabel') + '}"'
        argument = []
        if match.group('uppos'):
            position = re.search(r'\((%s)\)' %num_coeff, match.group('uppos'))
            if position:
                argument.append('pos=' + position.group(0))
            elif re.search(r'\<', match.group('uppos')):
                argument.append('near start')
            elif re.search(r'\>', match.grouo('uppos')):
                argument.append('near end')
        if match.group('upalias'):
            argument.append('name=' + match.group('upalias'))
        if len(argument) != 0:
            label += '{' + ' , '.join(argument) + '}'
        arrow.append(label)
    if match.group('downlabel'):
        label = '"{' + match.group('downlabel') + '}"\''
        argument = []
        if match.group('downpos'):
            position = re.search(r'\((%s)\)' %num_coeff, match.group('downpos'))
            if position:
                argument.append('pos=' + position.group(0))
            elif re.search(r'\<', match.grouo('downpos')):
                argument.append('near start')
            elif re.search(r'\>',match.grouo('downpos')):
                argument.append('near end')
        if match.group('downalias'):
            argument.append('name=' + match.group('downalias'))
        if len(argument) != 0:
            label += '{' + ' , '.join(argument) + '}'
        arrow.append(label)
    if match.group('midlabel'):
        label = '"{' + match.group('midlabel') + '}"'
        argument = ['description', 'inner sep=0.05pt']
        if match.group('midpos'):
            position = re.search(r'\((%s)\)' %num_coeff, match.group('midpos'))
            if position:
                argument.append('pos=' + position.group(0))
            elif re.search(r'\<', match.grouo('midpos')):
                argument.append('near start')
            elif re.search(r'\>', match.grouo('midpos')):
                argument.append('near end')
        if match.group('midalias'):
            argument.append('name=' + match.group('midalias'))
        label += '{' + ' , '.join(argument) + '}'
        arrow.append(label)
    # Bend
    if match.group('curve'):
        if match.group('curve') == '^':
            arrow.append('bend left')
        elif match.group('curve') == '_':
            arrow.append('bend right')
        elif match.group('curve')[0] == '_':
            arrow.append('curve={height=' + match.group('curve')[1:] + '}')
        elif match.group('curve')[:1] == '^-':
            arrow.append('curve={height=' + match.group('curve')[2:] + '}')
        else:
            arrow.append('curve={height=-' + match.group('curve')[1:] + '}')
    # Shift
    if match.group('shift'):
        arrow.append('shift left=' + match.group('shift'))
    # Arrow Style
    ## TO DO: add support for harpoons (variants ^|_)
    if match.group('style'):
        start_triv = (('{}' in (match.group('start') or '')) or (r'{ }' in (match.group('start') or '')) or not(match.group('start')))
        conn_triv = (('{}' in (match.group('conn') or '')) or (r'{ }' in (match.group('conn') or '')) or not(match.group('conn')))
        end_triv = (('{}' in (match.group('end') or '')) or (r'{ }' in (match.group('end') or '')) or not(match.group('end')))
        if '3' in (match.group('conn') or '') or '3' in (match.group('variant') or ''):
            nfold = 3
        elif '2' in (match.group('conn') or '') or '=' in (match.group('conn') or '') or '2' in (match.group('variant') or ''):
            nfold = 2
        elif start_triv and conn_triv and end_triv:
            nfold = 0
        else:
            nfold = 1
        if not(start_triv):
            arrow.append(tip_dict[re.search(tip_dir, match.group('start'))[0]][min(nfold,2)-1])
        if not(conn_triv):
            arrow.append(conn_dict[re.search(conn_dir, match.group('conn'))[0]])
        if not(end_triv):
            arrow.append(tip_dict[re.search(tip_dir, match.group('end'))[0]][1+min(nfold,2)])
        if nfold == 0:
            arrow.append('phantom')
        elif nfold > 1:
            arrow.append('scaling nfold=' + str(nfold))
    # Return
    if '' in arrow:
        arrow.remove('')
    return r'\arrow[' + ' , '.join(arrow) + r']'

# Latex lengths-to-em (default: cm in font size 12) approximations
dimen_dict = {
    'em' : 1,
    'pt' : 0.1,
    'mm' : 0.28,
    'cm' : 2.8,
    'ex' : 0.43,
    'bp' : 0.1,
    'dd' : 0.1,
    'pc' : 1.2,
    'in' : 7.2,
    'sp' : 1.5 * 10**-6,
    'cc' : 1.2,  #same as 12*dd
    'px' : 0.1  #same as bp
}

def unit_to_em(dimension: str):
    unit = re.search(r'(%s)(%s)' %(number, units), dimension)
    return float(unit.group(1)) * dimen_dict[unit.group(2)]

def replace_xymatrix(match):
    options=['nodes in empty cells']
    #default is 2pc for row/col sep in XY, but 1.8em in Tikz. Tikz doesn't  have a way to add a value to a row/col sep so you need to do the addition manually
    for settings in re.finditer(xy_options, match.group('options')):
        if settings.group('addop'):
            if settings.group('addop') == '+':
                if settings.group('axis') == 'R':
                    options.append('row sep=' + str(1.8+unit_to_em(settings.group('dimen'))) + 'em')
                elif settings.group('axis') == 'C':
                    options.append('column sep=' + str(1.8+unit_to_em(settings.group('dimen'))) + 'em')
                else:
                    options.append('row sep=' + str(1.8+unit_to_em(settings.group('dimen'))) + 'em')
                    options.append('column sep=' + str(1.8+unit_to_em(settings.group('dimen'))) + 'em')
            elif settings.group('addop') == '-':
                if settings.group('axis') == 'R':
                    options.append('row sep=' + str(1.8-unit_to_em(settings.group('dimen'))) + 'em')
                elif settings.group('axis') == 'C':
                    options.append('column sep=' + str(1.8-unit_to_em(settings.group('dimen'))) + 'em')
                else:
                    options.append('row sep=' + str(1.8-unit_to_em(settings.group('dimen'))) + 'em')
                    options.append('column sep=' + str(1.8-unit_to_em(settings.group('dimen'))) + 'em')
            elif settings.group('addop') == '=':
                if settings.group('axis') == 'R':
                    options.append('row sep=' + str(unit_to_em(settings.group('dimen'))) + 'em')
                elif settings.group('axis') == 'C':
                    options.append('column sep=' + str(unit_to_em(settings.group('dimen'))) + 'em')
                else:
                    options.append('row sep=' + str(unit_to_em(settings.group('dimen'))) + 'em')
                    options.append('column sep=' + str(unit_to_em(settings.group('dimen'))) + 'em')
            else:
                print('ERROR: Invalid operator in XY matrix options')
                return r'\begin{tikzcd}' + re.sub(find_ar, replace_ar, match.group('bracket0')[1:-1]) + r'\end{tikzcd}'
        else:
            print('ERROR: Invalid operator in XY matrix options')
            return r'\begin{tikzcd}' + re.sub(find_ar, replace_ar, match.group('bracket0')[1:-1]) + r'\end{tikzcd}'
    return r'\begin{tikzcd}[' + ' , '.join(options) + ']' + re.sub(find_ar, replace_ar, match.group('bracket0')[1:-1]) + r'\end{tikzcd}'

# Find and replace any xy code with tikzd code in tex
def xy_to_tikzcd(tex) :
    return re.sub(find_xymatrix, replace_xymatrix, tex)

## TESTING
# test = open('test.tex', 'r').read()
# output = open('translation.tex', 'w')
# output.write(re.sub(find_xymatrix, replace_xymatrix, test))

##PROBLEMS:
# - xymatrix can be inside \vcenter but not tikzcd
# - can't handle holes such as |!{[dl];[rr]}\hole: in tikzcd the proper way to do this is to use "crossing over" as an option on the OTHER arrow: we'd need to figure out which one it is.. very complicated