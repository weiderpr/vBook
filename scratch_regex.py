import re

html_content_5 = """
<p>Nome: {{acompanhante_nome}}</p>
<p>RG: {{acompanhante_rg}}</p>
"""

companions = [{"name": "Joao", "rg": "111"}, {"name": "Maria", "rg": "222"}]

pattern = re.compile(r'<(tr|li|p|div)[^>]*>(?:(?!</?\1>).)*?\{\{acompanhante_(?:nome|rg)\}\}.*?</\1>', re.IGNORECASE | re.DOTALL)

def replacer(match):
    original_block = match.group(0)
    result = ""
    for comp in companions:
        block = original_block.replace('{{acompanhante_nome}}', comp["name"])
        block = block.replace('{{acompanhante_rg}}', comp["rg"])
        result += block
    return result

new_html_5 = re.sub(pattern, replacer, html_content_5)
print("--- TEST 5 ---")
print(new_html_5)
