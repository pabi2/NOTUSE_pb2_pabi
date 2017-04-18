# -*- coding: utf-8 -*-
from openerp import models, fields, api


class PabiPurchaseEmploymentWizard(models.TransientModel):

    _name = 'pabi.purchase.employment.report.wizard'

    date_from = fields.Date(string='Start Date')
    date_to = fields.Date(string='End Date')
    format = fields.Selection(
        [('pdf', 'PDF'),
         ('xls', 'Excel')],
        string='Format',
        required=True,
        default='pdf',
    )

    @api.multi
    def run_report(self):
        data = {'parameters': {}}
        report_name = self.format == 'pdf' and \
            'pabi_purchase_employment_report' or \
            'pabi_purchase_employment_report_xls'
        # For SQL, we search simply pass params
        data['parameters']['date_from'] = self.date_from
        data['parameters']['date_to'] = self.date_to
        res = {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': data,
        }
        return res
