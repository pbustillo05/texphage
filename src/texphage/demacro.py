## WAYS TO CREATE MACROS
### CLASSICAL WAYS:
# \def, \(re)newcommand, \let, \(re)newenvironment
## Variations: \edef, \gdef=\global\def and \xdef=\global\edef
# and the weird ones: \globaldefs, \futurelet => these looks crazy
#SHIT: how about \providecommand
## Prefixes:
#   -\long can be ignored
#   -\outer should NEVER be used: it creates macros which can't be used inside other macros.. can be ignored if used, it doesnt change meaning
#   -\global can be ignored (should be very rare)
#   -\expandafter is DANGER (absolutely crazy.. avoid it) => ONLY reasonnable use is to create commands with \csname ... \endcsname

###LATEX3
### XPARSE:
    # \NewDocumentCommand \RenewDocumentCommand \ProvideDocumentCommand \DeclareDocumentCommand
    # \NewDocumentEnvironment \RenewDocumentEnvironment \ProvideDocumentEnvironment \DeclareDocumentEnvironment
    # \NewExpandableDocumentCommand \RenewExpandableDocumentCommand \ProvideExpandableDocumentCommand \DeclareExpandableDocumentCommand
# \IfNoValue(TF) \IfValue(TF) \IfBoolean(TF)
## XARGS:
    # \newcommandx \renewcommandx \newenvironmentx \renewenvironmentx \providecommandx \DeclareRobustCommandx
    # these above work with a key list instead of default values
# XTEMPLATE

### KEYS
#expkv, keyval, xkeyval, ltxkeys, l3keys(2e), pgfkeys, kvsetkeys (used in keycommand), kvdefinekeys, options, simplekv, yax, kvoptions

### SPECIAL PACKAGES:
    # letltxmacro: \LetLtxMacro: same as \let except it works for macro with optional arguments and for robust macros
    # etoolbox: \(renew|new|provide)robustcmd(*) + many many weird stuff
    # twoopt: \(renew|new|provide)commandtwoopt with 2 optional arguments
# suffix: \withsuffix weird stuff
    # environ: \NewEnviron 
        #\NewEnviron{⟨name⟩}[⟨N. args⟩][⟨opt. arg.⟩]{⟨macro code⟩}[⟨final code⟩] with \BODY of \environbodyname\.. and \environfinalcode{...}
    # newenviron: \newenviron (very similar)
        #\newenviron{⟨name⟩}[⟨N. args⟩][⟨opt. arg.⟩]{start code⟩}{(macro code)} with \envbody or \<envname>body
# ifthen (obsolete, now superseeded by etoolbox)
# cmdhook: Allows hooking into existing commands and modifying their behavior.
     #too crazy: adds after/before code to any command

### FONTS, COUNTERS and DIMS/BOXES:
# \letcharcode \chardef \charsubdef \charsubdefmax \mathchardef \newfont
# \countdef \newcounter
# \dimendef \muskipdef \skipdef \toksdef \newlength \newsavebox

## TO DO:
# - Find a way to deal with \expandafter especially in \csname ... \endcsname
# - Add support for the "expandable" commands from xparse
# - Add support for grouping
# - Add support for conditional statements (especially for starred environments)
# - Add support for tikzset
# - Add support for \makeatletter and \makeatother: could simply add them when expanding.. this works just fine
# - Add support for \mathpalette: could replace first argument by \currentmathstyle if the mathstyle package is present (this package seems to break xy though)

import regex as re
from .find_packages import find_used_packages
from texphage._regex import (
    embed_brackets, embed_braces, token, not_tokenizer_char,
    num_args, find_com, find_env, xparse,
)

## ALL NECESSARY REGEX

# Naming a command
### IDEALLY: we use the following find_com to catch macros using a single symbol as a command. Unfortunately, this means a bit more work to adapt the regex..
# find_com = re.compile(r'\\([a-zA-Z]+|[^a-zA-Z])')
new_csname = lambda s : r'(?<%s>%s|\{ ?%s ?\})' %(s, find_com.pattern, find_com.pattern)
def com_name(csname):
    return find_com.search(csname)[1]
def env_name(csname):
    name = find_env.search(csname)
    if name[2]:
        return (name[1] + '_star', name[1] + r' ?\*')
    else:
        return (name[1], name[1])
find_specific_com = lambda s : r'(?<%s>\\(?:%s)(?![a-zA-Z]))' %(s,s)
def find_specific_env(csname):
    if csname[0] == '{':
        truncated = csname[1:-1]
        if re.fullmatch(r'[a-zA-Z]+', truncated):
            return r'(?<%s>\\begin ?%s|\\end ?%s|\\%s(?![a-zA-Z])|\\end%s(?![a-zA-Z]))' %(truncated, csname, csname, truncated)
        elif re.fullmatch(r'[^a-zA-Z]', truncated):
            return r'(?<%s>\\begin ?%s|\\end ?%s|\\%s(?![a-zA-Z]))' %(truncated, csname, csname)
    elif csname[0] == '\\':
        pass #technically, if this token expands to characters, it can be used as a macro name
    else:
        return r'(?<%s>\\begin ?%s|\\end ?%s)' %(csname, csname, csname)
    return ''

# Commands
find_def = r'\\g?def ?%s(?<def_pattern>[^\{]*)%s' %(new_csname('def_csname'), token('def_content'))
find_edef = r'\\(e|x)def ?%s(?<edef_pattern>[^{]*)%s' %(new_csname('edef_csname'), token('edef_content'))
find_let = r'\\(?:let|LetLtxMacro|GlobalLetLtxMacro) ?%s ?=? ?(?<let_content>(?:\\(?<let_called_csname>[a-zA-Z]+))|.)' %new_csname('let_csname')
find_new_com = r'\\(?:(?:renew|new|provide)(?:command(?:twoopt)?|robustcmd)|DeclareRobustCommand)(?<new_com_xargs>x)? ?\*? ?%s ?%s ?%s ?%s ?%s' %(new_csname('new_com_csname'), num_args('new_com_num_args'), embed_braces('new_com_default1'), embed_braces('new_com_default2'), token('new_com_content')) #technically, the robustcmd "x" variants don't exist
find_new_doc_com = r'\\(?:New|Renew|Provide|Declare)(?:Expandable)?DocumentCommand ?%s ?%s ?%s' %(new_csname('new_doc_com_csname'), token('new_doc_com_args'), token('new_doc_com_content'))
#find_twoopt = r'\\(renew|new|provide)commandtwoopt ?\*? ?%s ?%s ?%s ?%s ?%s' %(new_csname('new_com_csname'), num_args('new_com_num_args'), embed_braces('new_com_default1'), embed_braces('new_com_default2'), token('new_com_content'))

# Environments
find_new_env = r'\\(?:re)?newenvironment(?<new_env_xargs>x)? ?\*? ?%s ?%s ?%s ?%s ?%s' %(token('new_env_csname'), num_args('new_env_num_args'), embed_braces('new_env_default'), token('new_env_begin'), token('new_env_end'))
find_new_doc_env = r'\\(?:New|Renew|Provide|Declare)DocumentEnvironment ?%s ?%s ?%s ?%s' %(token('new_doc_env_csname'), token('new_doc_env_args'), token('new_doc_env_begin'), token('new_doc_env_end'))
find_New_Environ = r'\\(?:Ren|N)ewEnviron ?%s ?%s ?%s ?%s ?%s' %(token('New_Env_csname'), num_args('New_Env_num_args'), embed_braces('New_Env_default'), token('New_Env_content'), embed_braces('New_Env_end'))
find_new_environ = r'\\(?:re)?newenviron ?%s ?%s ?%s ?%s ?%s' %(token('New_Env_csname'), num_args('New_Env_num_args'), embed_braces('New_Env_default'), token('New_Env_begin'), token('New_Env_content'))
# Weird stuff
find_weird_stuff = r'(?<mathpalette>\\mathpalette)|(?<makeatother>\\makeatother)|(?<makeatletter>\\makeatletter)'

## KEYS: pgfkeys
key = lambda s : r' ?(?<%s>(?:\/(?!\.))?(?:[^=,\/]+?(?:\/(?!\.)))*)(?<%s>[^=,\/]+?)(?<%s>\/.[^=,\/]+?)? ?' %(s + '_path', s + '_name', s + '_handler')
value = lambda s : r'(?<%s>(?:%s|[^,\{\}])*)' %(s, embed_brackets('brackted_' + s))
key_value = r'(?!\s)%s(?:=%s)?(?=,|\})' %(key('key'), value('value'))

# Putting them together
find_all = re.compile(r'(?<def>%s)|(?<edef>%s)|(?<let>%s)|(?<new_com>%s)|(?<new_env>%s)|(?<new_doc_com>%s)|(?<new_doc_env>%s)' %(find_def, find_edef, find_let, find_new_com, find_new_env, find_new_doc_com, find_new_doc_env))

## PREPROCESSING: whitespace removal, list of packages
def preprocessing(tex):
    tex = re.sub(r'\s+', ' ', re.sub(r'(?<!\\)%.*$', '\n', tex, flags=re.M)) #removes comments and change ALL whitespaces to ' ' (everything is now on 1 line)
    preamble, document, _ = re.split(r'\\begin ?\{ ?document ?\}|\\end ?\{ ?document ?\}', tex, 2)
    return preamble, document, find_used_packages(preamble)

###### DICTIONARY BUIDLING
def content_replacement(local_content, default_dict ={}, boolean_list=[]):
    def content(arg):
        def arg_replacement(num):
            if re.search(r'#', num[1]):
                return num[1]
            else:
                try:
                    input = arg.group('arg' + num[1][-1:])
                    if not (num[1][-1:] in boolean_list):
                        return input
                    else:
                        return r'\BooleanTrue'
                except IndexError:
                    print(num[1][-1:])
                    return default_dict[num[1][-1:]]
        return re.sub(r'#(#*\d)', arg_replacement, local_content)
    return content

def build_dictionary(tex):
    macro_dict, find_macro = {}, ''
    # to_expand = r'(?<_pattern_>%s)' %pattern.pattern
    for macro in re.finditer(find_all, tex):
        # csname = macro.group(macro.lastgroup + '_csname')
        # try:
        #     if re.search(to_expand, macro.group(macro.lastgroup + '_content')):
        #         to_expand += r'|(?<%s>\\%s(?![a-zA-Z]))' %(csname, csname)
        # except IndexError:
        #     if re.search(to_expand, macro.group(macro.lastgroup + '_begin')) or re.search(to_expand, macro.group(macro.lastgroup + '_end')):
        #         to_expand += r'|\\(?<%s>begin ?\{ ?%s ?\}|(?<%s>end ?\{ ?%s ?\})|(?<%s>%s(?![a-zA-Z]))|(?<%s>end%s(?![a-zA-Z]))' %(csname, csname)
        # COMMANDS
        if macro.group('def'):
            csname = com_name(macro.group('def_csname'))
            pattern = (r'\\%s(?![a-zA-Z])' %csname) + re.sub(r'#(\d)', lambda num : r'(?<%s>%s)' %('arg' + num[1], token('bracket_arg'+ num[1])), macro.group('def_pattern'))
            content = content_replacement(macro.group('def_content'))
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder
        elif macro.group('edef'):
            csname = com_name(macro.group('edef_csname'))
            pattern = (r'\\%s(?![a-zA-Z])' %csname) + re.sub(r'#(\d)', lambda num : r'(?<%s>%s)' %('arg' + num[1], token('bracket_arg'+ num[1])), macro.group('edef_pattern'))
            #Content needs to be extended first:
            expanded_content = expand(macro.group('edef_content'), macro_dict, find_macro)
            content = content_replacement(expanded_content)
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder
        elif macro.group('let'):
            csname = com_name(macro.group('let_csname'))
            if macro.group('let_called_csname') in macro_dict:
                called = macro_dict[macro.group('let_called_csname')]
                pattern = re.sub(r'\\' + macro.group('let_called_csname'), (r'\\%s(?![a-zA-Z])' %csname), called[0], 1)
                macro_dict[csname] = [pattern, called[1]]
            else:
                macro_dict[csname] = [(r'\\%s(?![a-zA-Z])' %csname), macro.group('let_content')]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder
        elif macro.group('new_com'):
            csname = com_name(macro.group('new_com_csname'))
            pattern = r'\\%s(?![a-zA-Z])' %csname
            if macro.group('new_com_num_args'):
                num_args = int(macro.group('new_com_num_args'))
                i = 0
                default_dict = {}
                if macro.group('new_com_default1'):
                    i += 1
                    pattern += r' ?' + embed_braces('arg1')
                    default_dict['1'] = macro.group('new_com_default1')
                if macro.group('new_com_default2'):
                    i += 1
                    pattern += r' ?' + embed_braces('arg2')
                    default_dict['2'] = macro.group('new_com_default2')
                while i < num_args:
                    i+=1
                    pattern += r' ?(?<%s>%s)' %('arg' + str(i), token('bracket_arg' + str(i)))
                content = content_replacement(macro.group('new_com_content'), default_dict)
            else:   #else used here because otherwise the re.sub seemed to fail.. can it be removed?
                # Lambda used here because (for some reason) it makes macro.group('new_com_content') be seen as raw
                content = lambda arg, local_content = macro.group('new_com_content') : local_content
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder
        elif macro.group('new_doc_com'):
            csname = com_name(macro.group('new_doc_com_csname'))
            pattern = r'\\%s(?![a-zA-Z])' %csname
            arg_num = 0
            default_dict = {}
            boolean_list = []
            for args in re.finditer(xparse, macro.group('new_doc_com_args')):
                arg_num += 1
                if args.lastgroup == 'm':
                    pattern += ' ?' + embed_brackets('arg' + str(arg_num))
                elif args.lastgroup == 'o':
                    pattern += ' ?' + embed_braces('arg' + str(arg_num))
                elif args.lastgroup == 'O':
                    pattern += ' ?' + embed_braces('arg' + str(arg_num))
                    default_dict[str(arg_num)] = args.group('default')
                elif args.lastgroup == 's':
                    pattern += r' ?(?<arg%s>\*)? ?' %str(arg_num)
                    default_dict[str(arg_num)] = r'\BooleanFalse'
                    boolean_list.append(str(arg_num))
                elif args.lastgroup == 't':
                    pattern += r' ?(?<arg%s>\%s)? ?' %(str(arg_num), args.group('t')[1:])
                    default_dict[str(arg_num)] = r'\BooleanFalse'
                    boolean_list.append(str(arg_num))
            if arg_num != 0:
                content = content_replacement(macro.group('new_doc_com_content'), default_dict)
            else:   #else used here because otherwise the re.sub seemed to fail.. can it be removed?
                # Lambda used here because (for some reason) it makes macro.group('new_doc_com_content') be seen as raw
                content = lambda arg, local_content = macro.group('new_doc_com_content') : local_content
            macro_dict[csname] = [pattern, content]
            csname_finder = find_specific_com(csname)
            find_macro += '|' + csname_finder

        # ENVIRONMENTS
        elif macro.group('new_env'):
            csname_group, csname_latex = env_name(macro.group('new_env_csname'))
            pattern = r'\\begin ?\{ ?%s ?\}' %csname_latex
            if macro.group('new_env_num_args'):
                num_args = int(macro.group('new_env_num_args'))
                i = 0
                if macro.group('new_env_default'):
                    i += 1
                    pattern += r' ?' + embed_braces('arg1')
                    default_dict = {'1':macro.group('new_env_default')}
                while i < num_args:
                    i+=1
                    pattern += r' ?(?<%s>%s)' %('arg' + str(i), token('bracket_arg' + str(i)))
            pattern += r'(?<between>.*)\\end ?\{ ?%s ?\}' %csname_latex
            begin = content_replacement(macro.group('new_env_begin'), default_dict)
            end = content_replacement(macro.group('new_env_end'), default_dict)
            content = lambda arg : begin(arg) + arg.group('between') + end(arg)
            macro_dict[csname_group] = [pattern, content]
            find_macro += r'|(?<%s>\\begin ?\{ ?%s ?\})' %(csname_group, csname_latex)
        elif macro.group('new_doc_env'):
            csname_group, csname_latex = env_name(macro.group('new_doc_env_csname'))
            pattern = r'\\begin ?\{ ?%s ?\}' %csname_latex
            arg_num = 0
            default_dict = {}
            boolean_list = []
            for args in re.finditer(xparse, macro.group('new_doc_env_args')):
                arg_num += 1
                if args.lastgroup == 'm':
                    pattern += ' ?' + embed_brackets('arg' + str(arg_num))
                elif args.lastgroup == 'o':
                    pattern += ' ?' + embed_braces('arg' + str(arg_num))
                elif args.lastgroup == 'O':
                    pattern += ' ?' + embed_braces('arg' + str(arg_num))
                    default_dict[str(arg_num)] = args.group('default')
                elif args.lastgroup == 's':
                    pattern += r' ?(?<arg%s>\*)? ?' %str(arg_num)
                    default_dict[str(arg_num)] = r'\BooleanFalse'
                    boolean_list.append(str(arg_num))
                elif args.lastgroup == 't':
                    pattern += r' ?(?<arg%s>\%s)? ?' %(str(arg_num), args.group('t')[1:])
                    default_dict[str(arg_num)] = r'\BooleanFalse'
                    boolean_list.append(str(arg_num))
            arg_num += 1
            pattern += r'(?<arg%s>.*)\\end ?\{ ?%s ?\}' %(str(arg_num), csname_latex)
            begin = content_replacement(macro.group('new_doc_env_begin'), default_dict)
            end = content_replacement(macro.group('new_doc_env_end'), default_dict)
            between = 'arg%s' %str(arg_num)
            content = lambda arg : begin(arg) + arg.group(between) + end(arg)
            macro_dict[csname_group] = [pattern, content]
            find_macro += r'|(?<%s>\\begin ?\{ ?%s ?\})' %(csname_group, csname_latex)
        else: #tikzset
            pass
    return macro_dict, find_macro[1:]

###### EXPANDING
def expand(tex, macro_dict, find_macro, verbose = False):
    macro = re.search(find_macro, tex)
    pos = 0
    problematic_macros = []
    while macro:
        pos += macro.start()
        macro_def = macro_dict[macro.lastgroup]
        if re.search(macro_def[0], tex[pos:]):
            tex = tex[:pos] + re.sub(macro_def[0], macro_def[1], tex[pos:], count = 1)
        else:
            if verbose:
                print('Macro %s found at position %i not replacable' % (macro.lastgroup, pos))
            problematic_macros.append((macro.lastgroup, pos))
            pos += 1
        macro = re.search(find_macro, tex[pos:])
    return tex, problematic_macros

###### MAIN
def demacro(tex, verbose = False):
    preamble, document, list_packages = preprocessing(tex)
    macro_dict, find_macro = build_dictionary(preamble)
    if verbose:
        print(find_macro)
    expanded_tex, problematic_macros = expand(document, macro_dict, find_macro, verbose)
    return expanded_tex, list_packages, problematic_macros