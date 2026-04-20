# Padrões de Desenvolvimento - VerticeBook 📜

Para garantir que o VerticeBook continue sendo uma plataforma global e escalável, estabelecemos a seguinte **Regra Rígida de Internacionalização (i18n)**. Todo novo código, componente ou página deve obrigatoriamente seguir este padrão.

## 1. Templates HTML (.html)
Nenhum texto fixo deve ser escrito diretamente em Português ou qualquer outro idioma.

- **Obrigatório:** Carregar a biblioteca de tradução no topo: `{% load i18n %}`.
- **Obrigatório:** Envolver todo texto visível em etiquetas: `{% trans "Seu Texto Aqui" %}`.
- **Atributos:** Use tradução também em placeholders e títulos: `<input placeholder="{% trans 'Pesquisar...' %}">`.

## 2. Código Python (.py)
Para strings em models, views ou forms (como mensagens de sucesso ou labels de campos):

- **Importação:** `from django.utils.translation import gettext_lazy as _`
- **Uso:** Envolver a string na função: `messages.success(request, _("Ação realizada!"))`.

## 3. Fluxo de Trabalho
Sempre que um novo componente for criado ou um texto alterado:
1. Executar: `python manage.py makemessages -l en -l pt_BR`
2. Traduzir as novas entradas nos arquivos `.po` em `locale/`.
3. Executar: `python manage.py compilemessages`

## 4. Notificações e Mensagens
O sistema utiliza um padrão global de **Toast Notifications** (notificações flutuantes) no canto superior direito.

- **Backend:** Utilize o sistema de mensagens do Django (`messages.success`, `messages.error`, etc.). O sistema global em `base.html` detectará e exibirá estas mensagens automaticamente como toasts.
- **Frontend (JavaScript):** Utilize a função global `showToast(mensagem, tipo)` onde `tipo` pode ser `'success'`, `'error'`, `'warning'` ou `'info'`.
- **Limpeza:** Nunca inclua blocos `{% if messages %}` em templates individuais de visualização.

## 5. UI e UX
- Novos seletores ou botões devem estar próximos aos ícones globais (Tema e Idioma) se forem configurações de sistema.
- Elementos de interface devem ser flexíveis para suportar palavras de comprimentos diferentes (ex: "Sair" vs "Logout").
- Utilize preferencialmente a biblioteca de ícones Lucide (SVG) para consistência visual.

---
**Esta regra é mandatória.** O não cumprimento invalida o componente para integração na branch principal.
