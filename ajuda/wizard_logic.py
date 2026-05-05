from datetime import datetime, date
from decimal import Decimal
from django.utils.translation import gettext
from properties.models import Property
from reservations.models import Reservation, Client


class ReservationWizard:
    STEPS = [
        'PROPERTY',
        'DATES',
        'CLIENT_NAME',
        'CLIENT_PHONE',
        'GUESTS',
        'VALUE',
        'CONFIRMATION'
    ]

    def __init__(self, session_data):
        self.data = session_data.get('wizard_data', {})
        self.step = session_data.get('wizard_step', 'PROPERTY')

    def get_next_question(self, property_id=None):
        if self.step == 'PROPERTY':
            if property_id:
                try:
                    prop = Property.objects.get(id=property_id)
                    self.data['property_id'] = prop.id
                    self.data['property_name'] = prop.name
                    self.step = 'DATES'
                    return self.get_next_question()  # Move to next
                except Property.DoesNotExist:
                    pass
            return gettext("Para qual propriedade você deseja fazer a reserva?")

        if self.step == 'DATES':
            return gettext("Qual o período da reserva? (Ex: de 01/05 a 05/05)")

        if self.step == 'CLIENT_NAME':
            return gettext("Qual o nome completo do hóspede principal?")

        if self.step == 'CLIENT_PHONE':
            return gettext("Qual o telefone de contato do hóspede?")

        if self.step == 'GUESTS':
            return gettext("Quantos hóspedes no total?")

        if self.step == 'VALUE':
            return gettext("Qual o valor total da reserva? (Apenas números)")

        if self.step == 'CONFIRMATION':
            summary = f"<b>{gettext('Resumo da Reserva')}</b>:<br>"
            summary += f"- {gettext('Propriedade')}: {self.data.get('property_name')}<br>"
            summary += f"- {gettext('Período')}: {self.data.get('start_date')} {gettext('até')} {self.data.get('end_date')}<br>"
            summary += f"- {gettext('Hóspede')}: {self.data.get('client_name')}<br>"
            summary += f"- {gettext('Valor')}: R$ {self.data.get('total_value')}<br><br>"
            summary += gettext("Confirma o registro desta reserva? (Responda 'Sim' ou 'Não')")
            return summary

        return None

    def process_answer(self, answer, user):
        """Processes the answer and moves to the next step. Returns (message, is_done, mode)"""

        if self.step == 'PROPERTY':
            prop = Property.objects.filter(user=user, name__icontains=answer).first()
            if prop:
                self.data['property_id'] = prop.id
                self.data['property_name'] = prop.name
                self.step = 'DATES'
                return self.get_next_question(), False, 'wizard'
            return gettext("Não encontrei uma propriedade com esse nome. Pode digitar novamente?"), False, 'wizard'

        if self.step == 'DATES':
            try:
                import re
                dates = re.findall(r'\d{2}/\d{2}(?:/\d{4})?', answer)
                if len(dates) >= 2:
                    d1 = dates[0]
                    d2 = dates[1]
                    curr_year = datetime.now().year
                    if len(d1) == 5:
                        d1 += f"/{curr_year}"
                    if len(d2) == 5:
                        d2 += f"/{curr_year}"
                    self.data['start_date'] = datetime.strptime(d1, '%d/%m/%Y').strftime('%Y-%m-%d')
                    self.data['end_date'] = datetime.strptime(d2, '%d/%m/%Y').strftime('%Y-%m-%d')
                    self.step = 'CLIENT_NAME'
                    return self.get_next_question(), False, 'wizard'
                return gettext("Não consegui entender as datas. Por favor, use o formato DD/MM a DD/MM."), False, 'wizard'
            except Exception:
                return gettext("Houve um erro ao processar as datas. Tente novamente (Ex: 10/05 a 15/05)."), False, 'wizard'

        if self.step == 'CLIENT_NAME':
            if len(answer.strip()) < 3:
                return gettext("O nome parece muito curto. Pode informar o nome completo?"), False, 'wizard'
            self.data['client_name'] = answer.strip()
            self.step = 'CLIENT_PHONE'
            return self.get_next_question(), False, 'wizard'

        if self.step == 'CLIENT_PHONE':
            clean_phone = "".join(filter(str.isdigit, answer))
            if len(clean_phone) < 8:
                return gettext("Telefone inválido. Por favor, informe com DDD."), False, 'wizard'
            self.data['client_phone'] = clean_phone
            self.step = 'GUESTS'
            return self.get_next_question(), False, 'wizard'

        if self.step == 'GUESTS':
            try:
                count = int("".join(filter(str.isdigit, answer)))
                self.data['guests_count'] = count
                self.step = 'VALUE'
                return self.get_next_question(), False, 'wizard'
            except Exception:
                return gettext("Por favor, informe apenas o número de hóspedes."), False, 'wizard'

        if self.step == 'VALUE':
            try:
                val_str = answer.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
                val = Decimal(val_str)
                self.data['total_value'] = str(val)
                self.step = 'CONFIRMATION'
                return self.get_next_question(), False, 'wizard'
            except Exception:
                return gettext("Não entendi o valor. Use apenas números (Ex: 1500,00)."), False, 'wizard'

        if self.step == 'CONFIRMATION':
            if answer.lower() in ['sim', 'confirmar', 'ok', 's', 'yes']:
                return self.finalize_reservation()
            else:
                return gettext("Entendido. A reserva não foi criada. Posso te ajudar com outra coisa?"), True, 'normal'

        return gettext("Desculpe, algo deu errado no assistente. Vamos voltar ao chat normal."), True, 'normal'

    def finalize_reservation(self):
        try:
            prop = Property.objects.get(id=self.data['property_id'])
            client, was_created = Client.objects.get_or_create(
                name=self.data['client_name'],
                defaults={'phone': self.data['client_phone']}
            )

            res = Reservation.objects.create(
                property=prop,
                client=client,
                client_name=self.data['client_name'],
                client_phone=self.data['client_phone'],
                start_date=self.data['start_date'],
                end_date=self.data['end_date'],
                total_value=Decimal(self.data['total_value']),
                guests_count=self.data.get('guests_count', 1)
            )

            msg = (
                f"✅ <b>{gettext('Reserva criada com sucesso!')}</b><br>"
                f"{gettext('O código da reserva é')} #{res.id}.<br><br>"
                f"{gettext('Posso ajudar com algo mais?')}"
            )
            return msg, True, 'normal'
        except Exception as exc:
            return f"❌ {gettext('Erro ao criar reserva')}: {str(exc)}", True, 'normal'

    def save_state(self, session):
        session['wizard_data'] = self.data
        session['wizard_step'] = self.step
        session.modified = True
