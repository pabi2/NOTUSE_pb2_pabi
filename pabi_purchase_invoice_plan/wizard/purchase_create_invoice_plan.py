# -*- coding: utf-8 -*-
import calendar
from datetime import datetime

from openerp import models, fields, api, _
from openerp.exceptions import Warning as UserError


class PurchaseCreateInvoicePlanInstallment(models.TransientModel):
    _inherit = 'purchase.create.invoice.plan.installment'

    fiscal_year_id = fields.Many2one(
        'account.fiscalyear',
        string='Fiscal Year',
    )

    @api.onchange('percent')
    def _onchange_percent(self):
        if not self.plan_id.by_fiscalyear:
            return super(PurchaseCreateInvoicePlanInstallment, self).\
                _onchange_percent()
        obj_precision = self.env['decimal.precision']
        prec = obj_precision.precision_get('Account')
        line_by_fiscalyear = self.plan_id._get_total_by_fy()
        order_amount = line_by_fiscalyear[self.fiscal_year_id.id]
        self.amount = round(order_amount * self.percent / 100, prec)

    @api.onchange('amount')
    def _onchange_amount(self):
        if not self.plan_id.by_fiscalyear:
            return super(PurchaseCreateInvoicePlanInstallment, self)._onchange_amount()
        obj_precision = self.env['decimal.precision']
        prec = obj_precision.precision_get('Account')
        line_by_fiscalyear = self.plan_id._get_total_by_fy()
        order_amount = line_by_fiscalyear[self.fiscal_year_id.id]
        if not order_amount:
            raise Warning(_('Order amount equal to 0.0!'))
        new_val = self.amount / order_amount * 100
        if round(new_val, prec) != round(self.percent, prec):
            self.percent = new_val


class PurchaseCreateInvoicePlan(models.TransientModel):
    _inherit = 'purchase.create.invoice.plan'
    _description = 'Create Purchase Invoice Plan'

    @api.model
    def _get_total_by_fy(self):
        order = self.po_id
        if self._context.get('active_id', False):
            purchase_id = self._context['active_id']
            order = self.env['purchase.order'].browse(purchase_id)
        line_by_fiscalyear = {}
        for line in order.order_line:
            line_fy = line.fiscal_year_id
            if line_fy:
                if line_fy.id not in line_by_fiscalyear:
                    line_by_fiscalyear[line_fy.id] = line.price_subtotal
                else:
                    line_by_fiscalyear[line_fy.id] += line.price_subtotal
        return line_by_fiscalyear

    @api.model
    def _get_interval_type(self):
        order = self.env['purchase.order'].\
            browse(self._context.get('active_id'))
        selection_list = [('day', 'Day'),
                          ('month', 'Month')]
        if order.by_fiscalyear:
            return selection_list
        else:
            selection_list.append(('year', 'Year'))
            return selection_list

    @api.model
    def _default_order(self):
        return self.env['purchase.order'].\
            browse(self._context.get('active_id'))

    @api.model
    def _default_by_fiscalyear(self):
        order = self.env['purchase.order'].\
            browse(self._context.get('active_id'))
        if order.by_fiscalyear:
            if any([not l.fiscal_year_id for l in order.order_line]):
                raise UserError(_('Please set fiscal year on product line'))
        return order.by_fiscalyear

    by_fiscalyear = fields.Boolean(
        string='By Fiscal Year',
        readonly=True,
        default=_default_by_fiscalyear,
    )
    interval_type = fields.Selection(
        _get_interval_type,
    )
    po_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        default=_default_order,
    )

    @api.one
    @api.onchange('installment_date',
                  'interval_type',
                  'interval',
                  'installment_amount')
    def _onchange_installment_config(self):
        if self.interval < 0:
            raise UserError('Negative interval not allowed!')
        return super(PurchaseCreateInvoicePlan, self)._onchange_installment_config()

    @api.model
    def _compute_installment_details(self):
        obj_precision = self.env['decimal.precision']
        prec = obj_precision.precision_get('Account')
        if not self.by_fiscalyear:
            return super(PurchaseCreateInvoicePlan, self).\
                    _compute_installment_details()
        order = self.env['purchase.order'].browse(self._context['active_id'])
        self._check_invoice_mode(order)
        fiscalyear_dict = {}
        for f in self.env['account.fiscalyear'].search_read([],
                                                            ['name', 'id']):
            fiscalyear_dict[f['id']] = f['name']

        line_by_fiscalyear = self._get_total_by_fy()
        line_by_fiscalyear = dict(sorted(line_by_fiscalyear.iteritems()))

        new_line_dict = {}
        installment_no = 1
        for l in line_by_fiscalyear:
            line_total = line_by_fiscalyear[l]
            line_percentage = (100 * line_total) / order.amount_total
            number_of_lines = (line_percentage * self.num_installment) / 100
            number_of_lines = round(number_of_lines)
            remaining_amt = line_by_fiscalyear[l]
            line_cnt = number_of_lines

            while line_cnt > 0:
                installment_amt = self.installment_amount
                if line_cnt == 1 or installment_no == self.num_installment or\
                        remaining_amt < self.installment_amount:
                    installment_amt = remaining_amt
                if installment_amt < 0:
                    installment_amt = 0
                remaining_amt -= self.installment_amount
                new_line_dict[installment_no] =\
                    (fiscalyear_dict[l], installment_amt, l)
                installment_no += 1
                line_cnt -= 1

        count = 0
        installment_date = datetime.strptime(self.installment_date, "%Y-%m-%d")
        day = installment_date.day
        month = installment_date.month
        old_fy = False
        for i in self.installment_ids:
            if i.is_advance_installment or i.is_deposit_installment:
                i.date_invoice = self.installment_date
                continue
            interval = self.interval
            if i.installment in new_line_dict:
                f_amount = line_by_fiscalyear[new_line_dict[i.installment][2]]
                i.fiscal_year_id = new_line_dict[i.installment][2]
                i.amount = new_line_dict[i.installment][1]
                new_val = i.amount / f_amount * 100
                if round(new_val, prec) != round(i.percent, prec):
                    i.percent = new_val
                fy = new_line_dict[i.installment][0]

                if count == 0:
                    interval = 0

                if self.interval_type == 'month':
                    if month < 12:
                        month += interval
                    if month > 12:
                        month = 12
                else:
                    day += interval
                    day_range = calendar.monthrange(int(fy), month)[1]
                    if day > day_range:
                        day = day - day_range
                        month += 1

                if not old_fy:
                    old_fy = fy
                if old_fy != fy:
                    day = installment_date.day
                    month = installment_date.month
                    old_fy = fy

                date_str = str(month) + '/' + str(day) + '/' + fy
                i.date_invoice = datetime.strptime(date_str, '%m/%d/%Y')
                count += 1

    @api.one
    def do_create_purchase_invoice_plan(self):
        if not self.by_fiscalyear:
            return super(PurchaseCreateInvoicePlan, self).do_create_purchase_invoice_plan()
        self._validate_total_amount()
        self._check_installment_amount()
        self.env['purchase.invoice.plan']._validate_installment_date(
            self.installment_ids)
        order = self.env['purchase.order'].browse(self._context['active_id'])
        self._check_invoice_mode(order)
        order.invoice_plan_ids.unlink()
        lines = []

        for install in self.installment_ids:
            if install.installment == 0:
                self._check_deposit_account()
                if install.is_advance_installment:
                    line_data = self._prepare_advance_line(order, install)
                    lines.append(line_data)
                if install.is_deposit_installment:
                    line_data = self._prepare_deposit_line(order, install)
                    lines.append(line_data)
            elif install.installment > 0:
                for order_line in order.order_line:
                    if order_line.fiscal_year_id == install.fiscal_year_id:
                        line_data = self._prepare_installment_line(order,
                                                                   order_line,
                                                                   install)
                        lines.append(line_data)
        order.invoice_plan_ids = lines
        order.use_advance = self.use_advance
        order.use_deposit = self.use_deposit
        order.invoice_mode = self.invoice_mode

    @api.model
    def _prepare_advance_deposit_line(self, order, install, advance, deposit):
        result = super(PurchaseCreateInvoicePlan, self).\
                _prepare_advance_deposit_line(order, install, advance, deposit)
        if not self.by_fiscalyear:
            return result
        result.update({'fiscal_year_id': install.fiscal_year_id.id})
        return result