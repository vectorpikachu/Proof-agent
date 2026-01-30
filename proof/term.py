from coqpyt.coq.structs import TermType
from typing import List, Tuple, Optional

def _is_extend(
        expr: List, entry: str | Tuple[str], exact: bool = True
    ) -> bool:
    if expr[0] != "VernacExtend":
        return False
    if exact:
        return expr[1][0] == entry
    return expr[1][0].startswith(entry)

def _term_type(expr: List) -> TermType:
    if expr[0] == "VernacStartTheoremProof":
        return getattr(TermType, expr[1][0].upper())
    if expr[0] == "VernacDefinition":
        return TermType.DEFINITION
    if expr[0] in ["VernacNotation", "VernacSyntacticDefinition"]:
        return TermType.NOTATION
    if expr[0] == "VernacInductive" and expr[1][0] == "Class":
        return TermType.CLASS
    if expr[0] == "VernacInductive" and expr[1][0] in ["Record", "Structure"]:
        return TermType.RECORD
    if expr[0] == "VernacInductive" and expr[1][0] == "Variant":
        return TermType.VARIANT
    if expr[0] == "VernacInductive" and expr[1][0] == "CoInductive":
        return TermType.COINDUCTIVE
    if expr[0] == "VernacInductive":
        return TermType.INDUCTIVE
    if expr[0] == "VernacInstance":
        return TermType.INSTANCE
    if expr[0] == "VernacCoFixpoint":
        return TermType.COFIXPOINT
    if expr[0] == "VernacFixpoint":
        return TermType.FIXPOINT
    if expr[0] == "VernacScheme":
        return TermType.SCHEME
    # FIXME: These are plugins and should probably be handled differently
    if _is_extend(expr, "Obligations"):
        return TermType.OBLIGATION
    if _is_extend(expr, "VernacDeclareTacticDefinition"):
        return TermType.TACTIC
    if _is_extend(expr, "Function"):
        return TermType.FUNCTION
    if _is_extend(expr, "Define_equations", exact=False):
        return TermType.EQUATION
    if _is_extend(expr, "Derive", exact=False):
        return TermType.DERIVE
    if _is_extend(expr, "AddSetoid", exact=False):
        return TermType.SETOID
    if _is_extend(
        expr, ("AddRelation", "AddParametricRelation"), exact=False
    ):
        return TermType.RELATION
    return TermType.OTHER

def may_intro(term_type: TermType) -> bool:
    return term_type not in [
            TermType.TACTIC,
            TermType.NOTATION,
            TermType.INDUCTIVE,
            TermType.COINDUCTIVE,
            TermType.RECORD,
            TermType.CLASS,
            TermType.SCHEME,
            TermType.VARIANT,
            TermType.OTHER,
        ]

def _get_v(el: List) -> Optional[str]:
    if isinstance(el, dict) and "v" in el:
        return el["v"]
    elif isinstance(el, list) and len(el) == 2 and el[0] == "v":
        return el[1]
    return None

def _get_id(id: List) -> Optional[str]:
    # FIXME: This should be made private once [__step_context] is extracted
    # from ProofFile to here.
    if id[0] == "Ser_Qualid":
        return ".".join([l[1] for l in reversed(id[1][1])] + [id[2][1]])
    elif id[0] == "Id":
        return id[1]
    return None

def _get_ident(el: List) -> Optional[str]:
    # FIXME: This method should be made private once [__get_program_context]
    # is extracted from ProofFile to here.
    def handle_arg_type(args, ids):
        if args[0] == "ExtraArg":
            if args[1] == "identref":
                return ids[0][1][1]
            elif args[1] == "ident":
                return ids[1]
        return None

    if len(el) == 3 and el[0] == "GenArg" and el[1][0] == "Rawwit":
        return handle_arg_type(el[1][1], el[2])
    return None

def _get_toplevel_names(expr: List) -> List[str]:
    inductive = expr[0] == "VernacInductive"
    extend = expr[0] == "VernacExtend"
    stack, res = expr[:0:-1], []
    while len(stack) > 0:
        el = stack.pop()
        v = _get_v(el)
        if v is not None and isinstance(v, list) and len(v) == 2:
            id = _get_id(v)
            if id is not None:
                if not inductive:
                    return [id]
                res.append(id)
            elif v[0] == "Name":
                if not inductive:
                    return [v[1][1]]
                res.append(v[1][1])

        elif isinstance(el, dict):
            for v in reversed(el.values()):
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(el, list):
            if len(el) > 0 and el[0] == "CLocalAssum":
                continue

            ident = _get_ident(el)
            if ident is not None and extend:
                return [ident]

            for v in reversed(el):
                if isinstance(v, (dict, list)):
                    stack.append(v)
    return res

def get_names(expr) -> List[str]:
    #print(expr)
    if expr is None:
        return []
    elif isinstance(expr, dict) and 'v' in expr:
        return get_names(expr['v'])
    elif isinstance(expr, list) and len(expr) == 3 and expr[0] == 'Ser_Qualid':
        #print(expr[2][1])
        dirpath = '.'.join([a[1] for a in expr[1][1]] + [expr[2][1]])
        return [dirpath]
    elif isinstance(expr, list):
        ans = []
        for j in expr:
            ans += get_names(j)
        return ans
    else: return []