import datetime

from odoo import models, fields, api
from odoo.tools import date_utils
from datetime import timezone as datetime_timezone
from datetime import timedelta
from pytz import timezone

class BusinessOverviewWizard(models.TransientModel):
    _name = 'business.overview.report'
    _description = 'Business Overview Wizard'

    date_from = fields.Date(string="Start Date", required=True, default=fields.Date.context_today)
    date_to = fields.Date(string="End Date", required=True, default=fields.Date.context_today)

    from datetime import timezone

    def _get_utc_datetime_range(self):
        """Return UTC datetime range for filtering datetime fields correctly."""
        self.ensure_one()

        # Get the user timezone (assuming Dhaka in this case)
        user_tz = self.env.user.tz or 'UTC'

        # Step 1: Convert date_from and date_to to naive datetimes
        date_start_naive = fields.Datetime.to_datetime(self.date_from)
        date_end_naive = date_utils.end_of(fields.Datetime.to_datetime(self.date_to), 'day')

        # Step 2: Localize to Dhaka timezone (UTC+6)
        dhaka_tz = timezone('Asia/Dhaka')  # Dhaka timezone
        date_start_dhaka = dhaka_tz.localize(date_start_naive)  # Localize date_from to Dhaka timezone
        date_end_dhaka = dhaka_tz.localize(date_end_naive)  # Localize date_to to Dhaka timezone

        # Step 3: Convert both dates to UTC
        date_start_utc = date_start_dhaka.astimezone(datetime_timezone.utc)
        date_end_utc = date_end_dhaka.astimezone(datetime_timezone.utc)

        # Step 4: Return the converted datetimes in UTC
        return date_start_utc, date_end_utc

    def _get_data(self):
        self.ensure_one()
        env = self.env
        date_from_utc, date_to_utc = self._get_utc_datetime_range()

        # 🧾 Sales Orders (Datetime field)
        sales = env['sale.order'].search([
            ('date_order', '>=', date_from_utc),
            ('date_order', '<=', date_to_utc),
            ('state', 'in', ['sale', 'done']),
        ])

        # 🧾 Sales Orders (Datetime field)
        # fixme exclude online quotes for public user
        quotations = env['sale.order'].search([
            ('date_order', '>=', date_from_utc),
            ('date_order', '<=', date_to_utc),
            ('state', 'in', ['draft']),
        ])
        public_partner = env.ref('base.public_partner')
        quotations = quotations.filtered(lambda q: q.partner_id.id != public_partner.id)

        # 📦 Purchase Orders (Datetime field)
        purchases = env['purchase.order'].search([
            ('date_order', '>=', date_from_utc),
            ('date_order', '<=', date_to_utc),
            ('state', 'in', ['purchase', 'done']),
        ])

        # 📦 Purchase Orders (Datetime field)
        requests = env['purchase.order'].search([
            ('date_order', '>=', date_from_utc),
            ('date_order', '<=', date_to_utc),
            ('state', 'in', ['draft']),
        ])

        # 🏪 POS Orders (Datetime field)
        pos_orders = env['pos.order'].search([
            ('date_order', '>=', date_from_utc),
            ('date_order', '<=', date_to_utc),
            ('state', 'in', ['paid', 'done', 'invoiced']),
        ])

        # 💰 Payments (Date field — no need to convert)
        payments = env['account.payment'].search([
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'paid'),
        ])
        # 💰 Payments (Date field — no need to convert)
        draft_payments = env['account.payment'].search([
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '<>', 'paid'),
        ])
        journal_data = []
        # Note: journal opening data contains balance for opening date and closing amount for clossing date
        journal_opening_direct_payments_balance=self.get_journal_direct_payments_balance(date_to=self.date_from,date_included=False)
        journal_closing_direct_payments_balance=self.get_journal_direct_payments_balance(date_to=self.date_to,date_included=True)
        journal_opening_last_statement_balance=self._get_journal_current_statement_balance(date_to=self.date_from,date_included=False)
        journal_closing_last_statement__balance=self._get_journal_current_statement_balance(date_to=self.date_to,date_included=True)
        # self.check_accounting( [12], self.date_from, 350)
        # self.journal_entry_correction()
        #note combine both dict as opneing and closing amounts
        for key in journal_opening_direct_payments_balance:
            journal_details=journal_opening_direct_payments_balance[key]
            # rename balance  to opening
            journal_details['opening']=journal_details.pop('balance')
            # add clossing data
            journal_details['closing']=journal_closing_direct_payments_balance[key]['balance']
            # add opening statement Data
            journal_details['opening']+=journal_opening_last_statement_balance[key]['unlinked_amount']+journal_opening_last_statement_balance[key]['balance_end_real']
            journal_details['closing']+=journal_closing_last_statement__balance[key]['unlinked_amount']+journal_closing_last_statement__balance[key]['balance_end_real']



            #append in the journal data
            journal_data.append(journal_details)

        # Totals
        total_sales = sum(s.amount_total for s in sales)
        total_quotes = sum(s.amount_total for s in quotations  )
        total_purchases = sum(p.amount_total for p in purchases)
        total_requests = sum(p.amount_total for p in requests)
        total_pos = sum(p.amount_total for p in pos_orders)
        total_reciept = sum(p.amount for p in payments if p.payment_type=='inbound')
        total_payments = sum(p.amount for p in payments if p.payment_type=='outbound')
        total_draft_payments = sum(p.amount for p in draft_payments)

        gross_profit = total_sales + total_pos - total_purchases
        net_cash_flow = total_reciept-total_payments

        return {
            'date_from': str(self.date_from),
            'date_to': str(self.date_to),
            'total_sales': total_sales,
            'total_quotes': total_quotes,
            'total_purchases': total_purchases,
            'total_requests': total_requests,
            'total_pos': total_pos,
            'total_reciept': total_reciept,
            'total_payments': total_payments,
            'total_draft_payments': total_draft_payments,
            'gross_profit': gross_profit,
            'net_cash_flow': net_cash_flow,
            # 'sales_orders': sales.read(['name', 'partner_id', 'amount_total']),
            'sales_orders': [{
                    'id': sale.id,
                    'name': sale.name,
                    'partner': sale.partner_id.name,
                    'partner_balance': sale.partner_id.total_balance,
                    'amount_total': sale.amount_total,
                    'invoice_status': sale.invoice_status,
                } for sale in sales],
            'quotations': [{
                    'id': sale.id,
                    'name': sale.name,
                    'partner': sale.partner_id.name,
                    'partner_balance': sale.partner_id.total_balance,
                    'amount_total': sale.amount_total,
                    'invoice_status': sale.invoice_status,
                } for sale in quotations],
            'purchase_orders': purchases.read(['name', 'partner_id', 'amount_total']),
            'requests': requests.read(['name', 'partner_id', 'amount_total']),
            'pos_orders': pos_orders.read(['name', 'partner_id', 'amount_total']),
            'payments': payments.read(['name', 'partner_id', 'amount', 'payment_type']),
            'draft_payments': draft_payments.read(['name', 'partner_id', 'amount', 'payment_type']),
            'journals':journal_data,
        }

    # fixme balance= journal.current_statement_balance + direct_payments_balance
    # def _get_direct_bank_payments(self):
    #     self.env.cr.execute("""
    #         SELECT move.journal_id AS journal_id,
    #                move.company_id AS company_id,
    #                move.currency_id AS currency,
    #                SUM(CASE
    #                    WHEN payment.payment_type = 'outbound' THEN -payment.amount
    #                    ELSE payment.amount
    #                END) AS amount_total,
    #                SUM(amount_company_currency_signed) AS amount_total_company
    #           FROM account_payment payment
    #           JOIN account_move move ON move.origin_payment_id = payment.id
    #           JOIN account_journal journal ON move.journal_id = journal.id
    #          WHERE payment.is_matched IS TRUE
    #            AND move.state = 'posted'
    #            AND payment.journal_id = ANY(%s)
    #            AND payment.company_id = ANY(%s)
    #            AND payment.outstanding_account_id = journal.default_account_id
    #       GROUP BY move.company_id, move.journal_id, move.currency_id
    #     """, [self.ids, self.env.companies.ids])
    #     query_result = group_by_journal(self.env.cr.dictfetchall())
    #     result = {}
    #     for journal in self:
    #         # User may have read access on the journal but not on the company
    #         currency = (journal.currency_id or journal.company_id.sudo().currency_id).with_env(self.env)
    #         result[journal.id] = self._count_results_and_sum_amounts(query_result[journal.id], currency)
    #     return result

    from collections import defaultdict

    def _get_journal_current_statement_balance(self,journal_ids=False,date_to=False,date_included=False):
        """
        Python ORM equivalent of the SQL query that fetches latest statement and unlinked lines.
        Returns a dict: {journal_id: {statement_id, balance_end_real, unlinked_amount, unlinked_count}}
        """

        result = {}
        if not journal_ids:
            journals=self.env['account.journal'].search([('type','in',['cash','bank'])])
        else:
            journals = self.env['account.journal'].search([('id','in',journal_ids)])
        if not date_to:
            date_to=datetime.date.today()
        if date_included:
            date_to= date_to + timedelta(days=1)
        companies = self.env.companies
        # Prefetch all latest statements per journal
        for journal in journals:
            # ---- Get latest statement ----
            latest_stmt = self.env['account.bank.statement'].search(
                [
                    ('journal_id', '=', journal.id),
                    ('company_id', 'in', companies.ids),
                ],
                order="date desc, id desc",
                limit=1
            )

            # ---- Compute unlinked statement lines ----
            domain = [
                ('journal_id', '=', journal.id),
                ('company_id', 'in', companies.ids),
                ('statement_id', '=', False),
                ('move_id.state', '!=', 'cancel'),
                ('move_id.date', '<', date_to),
            ]

            # If latest statement exists, limit by internal_index
            if latest_stmt:
                domain.append(('internal_index', '>=', latest_stmt.first_line_index))

            unlinked_lines = self.env['account.bank.statement.line'].search(domain)

            unlinked_amount = sum(unlinked_lines.mapped('amount'))
            unlinked_count = len(unlinked_lines)

            # ---- Store results ----
            result[journal.id] = {
                'journal_id': journal.id,
                'statement_id': latest_stmt.id if latest_stmt else False,
                'balance_end_real': latest_stmt.balance_end_real if latest_stmt else 0.0,
                'unlinked_amount': unlinked_amount,
                'unlinked_count': unlinked_count,
            }

        return result

    def get_journal_direct_payments_balance(self,state_in=['paid',"in_process"],journals=False,date_to=False,date_included=True):
        if not journals:
            journals=self.env['account.journal'].search([('type','in',['bank','cash'])])
        if not date_to:
            date_to=datetime.date.today()
        if date_included:
            date_to= date_to + timedelta(days=1)
        search_domain=[('move_id', '!=', False), ('journal_id', 'in', journals.ids),('is_matched', '=', "TRUE"), ('date', '<', date_to)]
        # search_domain.append(('state','in',state_in))


        pmts = self.env['account.payment'].search( search_domain )
        payment_dict = {}
        for jrn in journals:
            payment_dict[jrn.id]={'name': jrn.name,'type':jrn.type,'default_account_id':jrn.default_account_id.id,'balance':0}


        # Step 3: Loop through the payments and aggregate by journal_id
        for pmt in pmts:
            journal_id = pmt.journal_id.id  # Get the journal ID for the current payment
            # if pmt.payment_type=='inbound':
            #     amt = pmt.amount  # Get the amount of the payment
            # else:
            #     amt=-pmt.amount
            if pmt.outstanding_account_id.id==payment_dict[journal_id]['default_account_id']:
                payment_dict[journal_id]["balance"] += pmt.amount_company_currency_signed  # Add to existing amount if journal_id already in dict

        return payment_dict

    def action_print_report(self):
        data = self._get_data()
        return self.env.ref('daily_admin_report.action_report_company_overview').report_action(self, data=data)



    def check_accounting(self,journal,date_from,days):
        journals = self.env['account.journal'].search([('id', 'in', journal)])
        direct_payment={}
        last_statement={}
        # date_from=datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
        day=1
        while  day <= days:

            direct_payment[date_from]=self.get_journal_direct_payments_balance(date_to=date_from,date_included=True)
            last_statement[date_from]=self._get_journal_current_statement_balance(date_to=date_from, date_included=False)
            date_from=date_from + timedelta(days=2)
            day=day+2

        print ('date,','journal,','statement,','payment,','balance')
        for journal in  journals:
            for key in last_statement.keys():
                print (key ,",",journal.name,",",last_statement[key][journal.id]['balance_end_real'],",",direct_payment[key][journal.id]['balance'],",",direct_payment[key][journal.id]['balance']+last_statement[key][journal.id]['balance_end_real'])


    def journal_entry_correction(self):
        # delete bank statement lines and reprocess
        # statements = self.env['account.bank.statement'].search([])
        # for rec in statements:
        #     rec.button_cancel_reconciliation()
        #     rec.unlink()
        # statement_lines = self.env['account.bank.statement.line'].search([])
        # for line in statement_lines:
        #     if statement_line.reconciled:
        #         # Iterate through the move lines linked to this statement line
        #         for move_line in statement_line.move_line_ids:
        #             # Remove the reconciliation
        #             move_line.remove_move_reconcile()
        #
        #         # Optionally, set the reconciled flag to False
        #         statement_line.reconciled = False
        #     line.unlink()

        # update move lines account_id of outbound payments
        outbound_payments = self.env['account.payment'].search([('payment_type', '=', 'outbound')])

        for payment in outbound_payments:
            move = payment.move_id
            journal = payment.journal_id
            default_account = journal.default_account_id

            if move and default_account:
                # Find move lines matching conditions
                move_lines = self.env['account.move.line'].search([
                    ('move_id', '=', move.id),
                    ('credit', '!=', 0),
                    ('account_id', '!=', default_account.id),
                ], limit=1)

                # Update them
                move_lines.write({'account_id': default_account.id})

        # update move lines account_id of inbound payments
        inbound_payments = self.env['account.payment'].search([('payment_type', '=', 'inbound')])

        for payment in inbound_payments:
            move = payment.move_id
            journal = payment.journal_id
            default_account = journal.default_account_id

            if move and default_account:
                # Find move lines matching conditions
                move_lines = self.env['account.move.line'].search([
                    ('move_id', '=', move.id),
                    ('debit', '!=', 0),
                    ('account_id', '!=', default_account.id),
                ], limit=1)

                # Update them
                move_lines.write({'account_id': default_account.id})

        # update payment outstanding account
        payments= self.env['account.payment'].search([])
        for payment in payments:
            journal=payment.move_id.journal_id
            if payment.journal_id!=journal:
                payment.action_draft()

                payment.journal_id=journal
            if journal and payment.outstanding_account_id != journal.default_account_id:
                payment.outstanding_account_id=journal.default_account_id