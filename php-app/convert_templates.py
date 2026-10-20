"""One-time migration helper; the PHP app does not use Python at runtime."""
import ast
from pathlib import Path
import re

root = Path(__file__).parent
source = root.parent / 'templates'

def expr(text):
    text = text.strip()
    if '| selectattr' in text:
        name = text.split('|')[0].strip()
        return f"array_values(array_filter({expr(name)}, fn($item) => !$item['is_valid']))"
    text = re.sub(r"\|(?:default\(''\)|e)\s*$", '', text)
    def emit(node):
        if isinstance(node, ast.Constant):
            if node.value is None: return 'null'
            if node.value is True: return 'true'
            if node.value is False: return 'false'
            return repr(node.value)
        if isinstance(node, ast.Name): return {'None':'null','false':'false','true':'true'}.get(node.id, '$'+node.id)
        if isinstance(node, ast.List): return '['+', '.join(emit(x) for x in node.elts)+']'
        if isinstance(node, ast.Attribute): return emit(node.value)+"['"+node.attr+"']"
        if isinstance(node, ast.Subscript): return emit(node.value)+'['+emit(node.slice)+']'
        if isinstance(node, ast.UnaryOp): return '!('+emit(node.operand)+')'
        if isinstance(node, ast.BoolOp): return '('+(' && ' if isinstance(node.op, ast.And) else ' || ').join(emit(x) for x in node.values)+')'
        if isinstance(node, ast.Compare):
            left=emit(node.left); right=emit(node.comparators[0]); op=node.ops[0]
            if isinstance(op, ast.In): return f'array_key_exists({left}, {right})'
            return left+(' === ' if isinstance(op, ast.Eq) else ' !== ')+right
        if isinstance(node, ast.Call):
            obj=node.func.value; method=node.func.attr; args=[emit(x) for x in node.args]
            if ast.unparse(obj)=='request.form': return 'form('+', '.join(args)+')'
            if method=='get': return '('+emit(obj)+'['+args[0]+'] ?? '+(args[1] if len(args)>1 else 'null')+')'
            if method=='startswith': return 'str_starts_with('+emit(obj)+', '+args[0]+')'
        raise ValueError(ast.dump(node))
    return emit(ast.parse(text,mode='eval').body)

def convert(text):
    def tag(m):
        s=m.group(1).strip()
        if s.startswith('if '): return '<?php if ('+expr(s[3:])+'): ?>'
        if s.startswith('elif '): return '<?php elseif ('+expr(s[5:])+'): ?>'
        if s=='else': return '<?php else: ?>'
        if s=='endif': return '<?php endif; ?>'
        if s.startswith('for '):
            var,seq=s[4:].split(' in ',1)
            return '<?php foreach ('+expr(seq)+' as $'+var+'): ?>'
        if s=='endfor': return '<?php endforeach; ?>'
        if s.startswith('set '):
            var,value=s[4:].split(' = ',1)
            return '<?php $'+var+' = '+expr(value)+'; ?>'
        raise ValueError(s)
    text=text.replace('{{ loop.index0 }}', '{{ loc.pe_code }}')
    text=re.sub(r'{%\s*(.*?)\s*%}',tag,text,flags=re.S)
    return re.sub(r'{{\s*(.*?)\s*}}',lambda m:'<?= e('+expr(m[1])+') ?>',text,flags=re.S)

index=(source/'index.html').read_text(encoding='utf-8')
blocks=dict(re.findall(r'{% block (\w+) %}(.*?){% endblock %}',index,re.S))
base=(source/'base.html').read_text(encoding='utf-8')
base=re.sub(r'{% block (\w+) %}(.*?){% endblock %}',lambda m:blocks.get(m[1],m[2]),base,flags=re.S)
(root/'templates/index.php').write_text(convert(base),encoding='utf-8')
(root/'templates/select_050.php').write_text(convert((source/'select_050.html').read_text(encoding='utf-8')),encoding='utf-8')
