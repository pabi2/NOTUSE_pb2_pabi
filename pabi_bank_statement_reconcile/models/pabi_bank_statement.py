# -*- coding: utf-8 -*-
import base64
from openerp import fields, models, api, _
from openerp.exceptions import ValidationError


class PABIBankStatement(models.Model):
    _name = 'pabi.bank.statement'
    _description = 'This model hold bank statement generated within Odoo'

    name = fields.Char(
        string='Name',
        default='/',
        required=True,
    )
    import_file = fields.Binary(
        string='Import File (*.csv)',
        copy=False,
    )
    doctype = fields.Selection(
        [('payment', 'Payment'),
         ('receipt', 'Receipt'),
         ],
        string='Doctype',
        default='payment',
    )
    payment_type = fields.Selection(
        [('cheque', 'Cheque'),
         ('transfer', 'Transfer'),
         ],
        string='Payment Type',
        help="Specified Payment Type, can be used to screen Payment Method",
    )
    transfer_type = fields.Selection(
        [('direct', 'DIRECT'),
         ('smart', 'SMART')
         ],
        string='Transfer Type',
        help="- DIRECT is transfer within same bank.\n"
        "- SMART is transfer is between different bank."
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        domain=[('type', '=', 'bank')]
    )
    account_id = fields.Many2one(
        'account.account',
        string='Account',
        compute='_compute_account_id',
        store=True,
    )
    date_from = fields.Date(
        string='From Date',
        required=True,
    )
    date_to = fields.Date(
        string='To Date',
        required=True,
    )
    item_ids = fields.One2many(
        'pabi.bank.statement.item',
        'statement_id',
        string='Statement Item',
        copy=False,
    )
    import_ids = fields.One2many(
        'pabi.bank.statement.import',
        'statement_id',
        string='Statement Import',
        copy=False,
    )
    import_error = fields.Text(
        string='Import Errors',
        readonly=True,
    )
    _sql_constraints = [
        ('name_unique', 'unique (name)', 'Bank Statement name must be unique!')
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            name = self.env['ir.sequence'].get('pabi.bank.statement')
            vals.update({'name': name})
        rec = super(PABIBankStatement, self).create(vals)
        return rec

    @api.multi
    @api.depends('journal_id')
    def _compute_account_id(self):
        for rec in self:
            if rec.journal_id.default_debit_account_id != \
                    rec.journal_id.default_credit_account_id:
                rec.account_id = False
            else:
                rec.account_id = rec.journal_id.default_debit_account_id

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        self.transfer_type = False

    @api.model
    def _prepare_move_items(self, move_lines):
        res = []
        for line in move_lines:
            line_dict = {
                'move_line_id': line.id,
                'document': line.document,
                'partner_id': line.partner_id.id,
                'partner_code': line.partner_id.search_key,
                'partner_name': line.partner_id.name,
                'cheque_number': line.document_id.number_cheque,
                'debit': line.debit,
                'credit': line.credit,
            }
            res.append((0, 0, line_dict))
        return res

    @api.multi
    def action_get_statement(self):
        MoveLine = self.env['account.move.line']
        for rec in self:
            rec.item_ids.unlink()
            rec.import_error = False
            search_domain = [
                ('journal_id', '=', rec.journal_id.id),
                ('account_id', '=', rec.account_id.id),
                ('date_value', '>=', rec.date_from),
                ('date_value', '<=', rec.date_to),
                ]
            if rec.doctype:
                search_domain.append(('doctype', '=', rec.doctype))
            move_lines = MoveLine.search(search_domain)
            # Filtered by payment_type, transfer_type
            if rec.payment_type == 'cheque':
                move_lines = move_lines.filtered(
                    lambda l: l.document_id.payment_type == 'cheque')
            elif rec.payment_type == 'transfer':
                move_lines = move_lines.filtered(
                    lambda l: l.document_id.payment_type == 'transfer' and
                    l.document_id.transfer_type == rec.transfer_type)
            # --
            rec.write({'item_ids': self._prepare_move_items(move_lines)})
        return

    @api.model
    def _add_statement_id_column(self, statement_id, file_txt):
        i = 0
        txt_lines = []
        for line in file_txt.split('\n'):
            if line and i == 0:
                line = '"statement_id/.id",' + line
            elif line:
                line = str(statement_id) + ',' + line
            txt_lines.append(line)
            i += 1
        file_txt = '\n'.join(txt_lines)
        return file_txt

    @api.multi
    def action_import_csv(self):
        _TEMPLATE_FIELDS = ['statement_id/.id',
                            'document',
                            'cheque_number',
                            'description',
                            'debit', 'credit',
                            'date_value',
                            'trans_code']
        for rec in self:
            rec.import_ids.unlink()
            rec.import_error = False
            if not rec.import_file:
                continue
            Import = self.env['base_import.import']
            file_txt = base64.decodestring(rec.import_file)
            file_txt = self._add_statement_id_column(rec.id, file_txt)
            imp = Import.create({
                'res_model': 'pabi.bank.statement.import',
                'file': file_txt,
            })
            [errors] = imp.do(
                _TEMPLATE_FIELDS,
                {'headers': True, 'separator': ',',
                 'quoting': '"', 'encoding': 'utf-8'})
            if errors:
                rec.import_error = str(errors)

    @api.multi
    def _get_match_criteria(self):
        self.ensure_one()
        match_criteria = False
        if self.payment_type == 'cheque':
            # Match by cheque number and amount
            match_criteria = """
                item.cheque_number = import.cheque_number
                and ((item.debit > 0 and item.debit = import.credit) or
                    (item.credit > 0 and item.credit = import.debit))
            """
        elif self.payment_type == 'transfer':
            # Match by document nubmer (PV) and amount
            match_criteria = """
                item.document = import.document
                and ((item.debit > 0 and item.debit = import.credit) or
                    (item.credit > 0 and item.credit = import.debit))
            """
        return match_criteria

    @api.multi
    def action_reconcile(self):
        for rec in self:
            # Clear old matching
            rec.item_ids.write({'match_import_id': False})
            rec.import_ids.write({'match_item_id': False})
            match_criteria = rec._get_match_criteria()
            if not match_criteria:
                raise ValidationError(_('No Reconcile Patter found!'))
            # Update Book (items)
            rec._cr.execute("""
                update pabi_bank_statement_item book set match_import_id =
                (select import.id
                from pabi_bank_statement_item item join
                pabi_bank_statement_import import on %s
                where item.id = book.id
                and item.statement_id = %s and import.statement_id = %s
                limit 1)
                where statement_id = %s
            """ % (match_criteria, rec.id, rec.id, rec.id))
            # Update Bank (import), based on what already matched
            rec._cr.execute("""
                update pabi_bank_statement_import bank set match_item_id =
                (select item.id
                from pabi_bank_statement_item item
                where item.match_import_id = bank.id
                and statement_id = %s
                limit 1)
                where statement_id = %s
            """ % (rec.id, rec.id))
        return

    @api.multi
    def action_import_and_reconcile(self):
        self.action_get_statement()
        self.action_import_csv()
        self.action_reconcile()


class PABIBankStatementItem(models.Model):
    _name = 'pabi.bank.statement.item'
    _order = 'date_value, document, cheque_number'

    statement_id = fields.Many2one(
        'pabi.bank.statement',
        string='Statement ID',
        index=True,
        ondelete='cascade',
        readonly=True,
    )
    document = fields.Char(
        string='Document',
        readonly=True,
    )
    move_line_id = fields.Many2one(
        'account.move.line',
        string='Journal Item',
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        readonly=True,
    )
    partner_code = fields.Char(
        string='Partner Code',
        readonly=True,
    )
    partner_name = fields.Char(
        string='Partner Name',
        readonly=True,
    )
    date_value = fields.Date(
        string='Value Date',
        readonly=True,
    )
    cheque_number = fields.Char(
        string='Cheque',
        readonly=True,
    )
    debit = fields.Float(
        string='Debit',
        readonly=True,
    )
    credit = fields.Float(
        string='Credit',
        readonly=True,
    )
    match_import_id = fields.Many2one(
        'pabi.bank.statement.import',
        string='Matched ID',
        ondelete='set null',
    )


class PABIBankStatementImport(models.Model):
    _name = 'pabi.bank.statement.import'
    _order = 'date_value, document, cheque_number'

    statement_id = fields.Many2one(
        'pabi.bank.statement',
        string='Statement ID',
        index=True,
        ondelete='cascade',
        readonly=True,
    )
    document = fields.Char(
        string='Document',
        readonly=True,
    )
    partner_code = fields.Char(
        string='Partner Code',
        readonly=True,
    )
    partner_name = fields.Char(
        string='Partner Name',
        readonly=True,
    )
    description = fields.Char(
        string='Description',
        readonly=True,
    )
    trans_code = fields.Char(
        string='Trans Code',
        readonly=True,
    )
    date_value = fields.Date(
        string='Value Date',
        readonly=True,
    )
    cheque_number = fields.Char(
        string='Cheque',
        readonly=True,
    )
    debit = fields.Float(
        string='Debit',
        readonly=True,
    )
    credit = fields.Float(
        string='Credit',
        readonly=True,
    )
    match_item_id = fields.Many2one(
        'pabi.bank.statement.item',
        string='Matched ID',
        ondelete='set null',
    )